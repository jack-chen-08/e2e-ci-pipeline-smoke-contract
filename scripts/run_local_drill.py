#!/usr/bin/env python3
"""Local rehearsal of the CI pipeline, writing the evidence files committed in evidence/.

    python scripts/run_local_drill.py

Steps: build → compose up --wait → alembic upgrade head → seed baseline → smoke+contract →
Playwright e2e → AC2 fault injection (INJECT_FAILURE=1) → WeCom summary to the local stub →
teardown and leftover-container check.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
PROJECT = "e2e-local-drill"
COMPOSE = ["docker", "compose", "-f", "docker-compose.test.yml", "-p", PROJECT]
EVIDENCE = ROOT / "evidence"
STUB_LOG = Path("/tmp/wecom_local_drill.jsonl")
HTTP_PORT = os.environ.get("DRILL_HTTP_PORT", "18000")
BASE_URL = "http://127.0.0.1:%s" % HTTP_PORT
os.environ.setdefault("DRILL_HTTP_PORT", HTTP_PORT)


def log(handle, message: str) -> None:
    line = f"{datetime.now(timezone.utc).strftime('%H:%M:%S')} {message}"
    print(line, flush=True)
    handle.write(line + "\n")
    handle.flush()


def run(cmd: list[str], handle, check: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    started = time.time()
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env={**os.environ, **(env or {})})
    took = time.time() - started
    head = (proc.stdout or "").strip().splitlines()
    tail = "\n".join(head[-6:]) if head else ""
    log(handle, f"$ {' '.join(cmd)}  (exit {proc.returncode}, {took:.1f}s)\n{tail}")
    if check and proc.returncode != 0:
        log(handle, f"STDERR:\n{(proc.stderr or '')[-2000:]}")
        raise SystemExit(f"step failed: {' '.join(cmd)}")
    return proc


def main() -> int:
    EVIDENCE.mkdir(exist_ok=True)
    if STUB_LOG.exists():
        STUB_LOG.unlink()
    with (EVIDENCE / "local_drill.log").open("w", encoding="utf-8") as handle:
        log(handle, "=== step 1: build images ===")
        run(COMPOSE + ["build"], handle)

        log(handle, "=== step 2: start stack (PG16/pgvector + Redis + stub + backend) ===")
        run(COMPOSE + ["up", "-d", "--wait", "--wait-timeout", "300"], handle)

        try:
            log(handle, "=== step 3: alembic upgrade head ===")
            run(COMPOSE + ["exec", "-T", "backend", "alembic", "upgrade", "head"], handle)

            log(handle, "=== step 4: seed.py --scenario baseline ===")
            run(COMPOSE + ["exec", "-T", "backend", "python", "seed.py", "--scenario", "baseline"], handle)

            log(handle, "=== step 5: smoke + contract (junit) ===")
            run([PY, "-m", "pytest", "tests/smoke", "tests/contract", "-m", "smoke or contract",
                 "--junitxml=reports/junit-smoke-contract.xml"], handle,
                env={"E2E_BASE_URL": BASE_URL})

            log(handle, "=== step 6: playwright e2e (HTML report + trace) ===")
            run([PY, "-m", "pytest", "tests/e2e", "-m", "e2e",
                 "--junitxml=reports/junit-e2e.xml", "--tracing", "retain-on-failure",
                 "--output", "reports/playwright"], handle,
                env={"E2E_BASE_URL": BASE_URL})

            log(handle, "=== step 7: AC2 — one injected failing case must fail the gate ===")
            injection = run([PY, "-m", "pytest", "tests/smoke", "-m", "smoke",
                             "--junitxml=reports/junit-injected.xml"],
                            handle, check=False, env={"INJECT_FAILURE": "1",
                                                      "E2E_BASE_URL": BASE_URL})
            log(handle, f"injected run exit code = {injection.returncode} (non-zero = gate blocks merge)")
            if injection.returncode == 0:
                raise SystemExit("fault injection did not fail the suite")

            log(handle, "=== step 8: AC3 — WeCom summary posts to the local stub ===")
            stub = subprocess.Popen([PY, "scripts/wecom_stub.py", "--port", "8099", "--log", str(STUB_LOG)],
                                    cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.5)
            try:
                run([PY, "scripts/notify_failure.py", "--junit", "reports/junit-injected.xml",
                     "--report-url", "https://github.com/jack-chen-08/e2e-ci-pipeline-smoke-contract/actions/runs/local-drill",
                     "--endpoint", "http://127.0.0.1:8099/cgi-bin/webhook/send"], handle)
            finally:
                stub.terminate()
                stub.wait(timeout=10)
            received = [json.loads(line) for line in STUB_LOG.read_text(encoding="utf-8").splitlines() if line]
            log(handle, f"stub received {len(received)} payload(s)")
            body = json.loads(received[-1]["body"])
            log(handle, "payload:\n" + json.dumps(body, ensure_ascii=False, indent=1))
            content = body["markdown"]["content"]
            for needle in ("失败用例", "case_id", "test_"):
                if needle not in content:
                    raise SystemExit(f"summary missing {needle}")
        finally:
            log(handle, "=== step 9: teardown + leftover check ===")
            run(COMPOSE + ["down", "-v", "--remove-orphans"], handle, check=False)
            leftover = subprocess.run(["docker", "ps", "-a", "--filter", f"label=com.docker.compose.project={PROJECT}",
                                       "--format", "{{.Names}}"], capture_output=True, text=True).stdout.strip()
            log(handle, f"leftover containers: {leftover or 'none'}")
            if leftover:
                raise SystemExit("containers survived teardown")

        log(handle, "\nRESULT: PASS — gate green on a clean stack, red on a single injected failure, "
                    "summary delivered to the stub, no leftover containers")
    print("log written to evidence/local_drill.log")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
