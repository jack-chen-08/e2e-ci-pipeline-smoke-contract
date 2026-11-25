#!/usr/bin/env python3
"""Build the nightly failure summary and post it to a WeCom group-bot webhook.

    python scripts/notify_failure.py --junit reports/junit.xml \
        --report-url https://github.com/<org>/<repo>/actions/runs/<id> \
        --endpoint "$WECOM_WEBHOOK"

The webhook address is passed in from a CI secret; it is never written to disk and never
echoed. `--endpoint` accepts any URL that speaks the WeCom payload shape — the local
drill uses scripts/wecom_stub.py so no real group is disturbed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

MAX_CASES = 10


def parse_junit(path: Path) -> tuple[int, int, list[str], float]:
    """Return (total, failed, first ten failing case ids, duration seconds)."""
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    total = failed = 0
    duration = 0.0
    failing: list[str] = []
    for suite in suites:
        total += int(suite.get("tests", 0))
        duration += float(suite.get("time", 0) or 0)
        for case in suite.iter("testcase"):
            if case.find("failure") is not None or case.find("error") is not None:
                failed += 1
                failing.append(case.get("name", "unknown"))
    return total, failed, failing[:MAX_CASES], round(duration, 2)


def build_payload(total: int, failed: int, failing: list[str], report_url: str) -> dict:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    case_lines = "\n".join(f"> {i}. {name}" for i, name in enumerate(failing, 1)) or "> （无）"
    content = (
        f"**夜间回归失败**\n"
        f"> 时间：{stamp}\n"
        f"> 失败用例：{failed} / {total}\n"
        f"> 报告：{report_url}\n"
        f"前 {len(failing)} 条失败 case_id：\n{case_lines}"
    )
    return {"msgtype": "markdown", "markdown": {"content": content}}


def post(endpoint: str, payload: dict) -> tuple[int, str]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        endpoint, data=data, method="POST", headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, response.read().decode("utf-8", "replace")[:400]
    except urllib.error.HTTPError as exc:  # pragma: no cover
        return exc.code, exc.read().decode("utf-8", "replace")[:400]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--junit", default="reports/junit.xml")
    ap.add_argument("--report-url", default=os.getenv("REPORT_URL", ""))
    ap.add_argument("--endpoint", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="send even when there are no failures")
    args = ap.parse_args()

    junit = Path(args.junit)
    if not junit.exists():
        print(f"junit report not found: {junit}", file=sys.stderr)
        return 2

    total, failed, failing, duration = parse_junit(junit)
    print(f"parsed junit: total={total} failed={failed} duration={duration}s")
    if failed == 0 and not args.force:
        print("no failures — nothing to notify")
        return 0

    payload = build_payload(total, failed, failing, args.report_url or "(未提供)")
    if args.dry_run or not args.endpoint:
        print("DRY RUN — payload that would be posted:")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    status, body = post(args.endpoint, payload)
    print(f"webhook HTTP {status}: {body}")
    return 0 if status < 400 else 1


if __name__ == "__main__":
    raise SystemExit(main())
