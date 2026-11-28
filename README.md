# e2e-ci-pipeline-smoke-contract

CI pipeline for the member-space platform: **PR gate** `e2e-gate` (build → compose stack →
Alembic → seed → smoke + contract → Playwright) and **nightly full regression**
`e2e-nightly` with a WeCom group-bot failure summary. Both jobs finish under the ticket's
time budget and always tear the stack down.

```
.github/workflows/e2e-gate.yml      PR gate, merge-blocking, timeout 20 min
.github/workflows/e2e-nightly.yml   nightly 02:00 Asia/Shanghai (= 18:00 UTC), timeout 30 min
docker-compose.test.yml             backend + PostgreSQL 16 (pgvector) + Redis + external stub
app/, migrations/, seed.py          minimal real backend the gate exercises (fictional data)
tests/smoke                         API smoke suite  (case ids quoted in summaries)
tests/contract                      response-vs-OpenAPI contract checks
tests/e2e                           Playwright browser checks (HTML report + traces)
scripts/notify_failure.py           builds and posts the failure summary
scripts/wecom_stub.py               local WeCom-compatible webhook receiver
scripts/run_local_drill.py          runs the whole pipeline locally -> evidence/local_drill.log
```

## 1. Run it locally (no GitHub needed)

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install chromium     # once
.venv/bin/python -m scripts.run_local_drill         # ~3 min, writes evidence/local_drill.log
```

The drill exercises the same nine steps as CI: build → `compose up --wait` →
`alembic upgrade head` → `seed.py --scenario baseline` → smoke + contract (JUnit XML) →
Playwright (HTML + trace) → **fault injection** (`INJECT_FAILURE=1`, one deliberately
failing case) → WeCom summary to the local stub → teardown + leftover-container check.

Manual variant, if you want the stack alive afterwards:

```bash
docker compose -f docker-compose.test.yml -p e2e-dev up -d --wait
docker compose -f docker-compose.test.yml -p e2e-dev exec -T backend alembic upgrade head
docker compose -f docker-compose.test.yml -p e2e-dev exec -T backend python seed.py --scenario baseline
pytest tests -m "smoke or contract" --junitxml=reports/junit.xml
docker compose -f docker-compose.test.yml -p e2e-dev down -v --remove-orphans
```

## 2. Make `e2e-gate` a required check (do this once, in the customer repo)

1. **Settings → Secrets and variables → Actions → New repository secret**
   * `WECOM_WEBHOOK` — the group-bot webhook address (only the nightly job reads it).
2. **Settings → Branches → Add branch protection rule** for `main`:
   * ✅ Require a pull request before merging
   * ✅ Require status checks to pass before merging → search **`e2e-gate`** and tick it
   * ✅ Require branches to be up to date before merging (optional but recommended)
3. Open any PR: the check appears as `e2e-gate / e2e-gate`. Until it is green the merge
   button stays disabled — that is AC2 (one failing case blocks the merge).

Actions-compatible executors: the workflow uses only `ubuntu-latest`, `docker compose`,
`actions/checkout@v4`, `actions/setup-python@v5`, `actions/upload-artifact@v4` and plain
`docker` commands, so a self-hosted runner labelled `ubuntu-latest` works unchanged.

## 3. Secrets and data hygiene

* The webhook address is read from `secrets.WECOM_WEBHOOK` only — never echoed, never
  committed (`.env.example` leaves it empty; `grep -r "qyapi.weixin" .` finds nothing).
* No credential is stored in the repo: database and Redis URLs are plain local credentials
  used only by the throwaway CI stack, everything else comes from the environment.
* All data is fictional: `seed.py` writes `Fictional Company 00xx` / `Fictional Contact …`
  with masked phone numbers (`+1****00000`). No real person or company appears anywhere.

## 4. Integration points (stubbed, per the ticket)

| Dependency | Stand-in | Where |
| --- | --- | --- |
| S2-INFRA cloud environment / CI-CD | this repository's workflows, run on the customer's Actions-compatible executor | `.github/workflows/` |
| Customer ERP (external system) | `stub/` FastAPI app; the backend calls `GET {EXTERNAL_STUB_URL}/ping` | `app/main.py::external_ping`, `docker-compose.test.yml` service `stub` |
| WeCom group bot | `scripts/wecom_stub.py` for drills; real address via `secrets.WECOM_WEBHOOK` | `scripts/notify_failure.py` |

Replace the stub by pointing `EXTERNAL_STUB_URL` at the real ERP once S2-INFRA delivers it —
no test change needed.

## 5. Acceptance criteria → evidence

| AC | How it is proven | Evidence |
| --- | --- | --- |
| 1. `e2e-gate` green on a PR, ≤ 20 min | PR #1 ([run 45585573464](https://github.com/jack-chen-08/e2e-ci-pipeline-smoke-contract/actions/runs/45585573464)): **success in 71 s**, all 13 steps green, PR merged after the check went green | `evidence/ac1_pr1_green.png`, `evidence/local_drill.log` |
| 2. One failing case → gate fails → PR cannot merge | PR #2 runs the same gate with one injected failing case: **run 45586384626 red in 63 s**, job exit non-zero; with `e2e-gate` marked required (README §2) the merge button stays disabled | `evidence/ac2_pr2_red.png`, `evidence/ac2_run_red_steps.png`; required-check 生效后的实测：PR #3 `e2e-gate` 红 → 页面标 **Required**、合并按钮 aria-disabled。**2026-11-28 重拍的三件整页证据（取代旧两张窄图）**：`evidence/ac2_pr3_merge_box_full.png`（PR #3 整页 1440×1373 CSS、2× 输出，合并框完整入画：`e2e-gate / e2e-gate (pull_request)` **Failing after 56s** + 右侧 `Required` 徽章 + Merge 按钮灰态；同页 `evidence/ac2_pr3_merge_button_dom.txt` 为按钮属性实测：`aria-disabled="true"`、`data-inactive="true"`、`disabled=false`，含 button `outerHTML` 原文与抓取方式；`evidence/ac2_pr3_merge_box_full.png.dom.txt` 为整页 `innerText`，含 `All checks have failed` / `Failing after 56s` / `Required`，均可 grep）、`evidence/ac2_ruleset_detail_full.png`（规则集详情整页：名称 `main`、Enforcement `Active`、Target branches `Include: main` / `Applies to 1 target: main`、规则 `Require status checks to pass` 下明列 `e2e-gate`、`Block force pushes`；`Bypass` 一栏不存在，与 API 导出 `bypass_actors: []` 一致；同名 `.dom.txt` 亦为整页文本）、`evidence/ac2_gh013_merge_blocked.txt`（在 origin/main 之上做空提交后 `git push origin HEAD:main`，服务端拒绝原文：`remote: error: GH013: Repository rule violations found for refs/heads/main.` / `remote: - Required status check "e2e-gate" is expected.` / `! [remote rejected] HEAD -> main (push declined due to repository rule violations)`，exit 1）。旧两张窄图 `evidence/ac2_pr3_merge_blocked.png`、`evidence/ac2_ruleset_required.png` 保留存档但已被上述三件取代 |
| 3. Nightly failure posts a summary with case ids | `scripts/notify_failure.py` parses JUnit, takes fail count, first 10 `case_id`, report link, posts WeCom markdown; `e2e-nightly` job wires it to `secrets.WECOM_WEBHOOK` | `evidence/local_drill.log` step 8 (stub payload verbatim), `evidence/wecom_payload.json` |
| 4. No secrets in the repo, no leftover containers | `secrets.WECOM_WEBHOOK` only; teardown with `if: always()`; drill checks `docker ps` after teardown; 5 credential patterns scanned = 0 hits | `evidence/secret_scan.txt`, `evidence/local_drill.log` step 9 (`leftover containers: none`) |

Timing rule of thumb on a warm runner: checkout 5 s, image build 40–70 s (layer cache),
stack up 20–30 s, Alembic + seed 5 s, smoke + contract 8 s, Playwright install 25 s,
e2e 10 s → well inside the 20-minute budget.

Real measurements from this repository (Actions, ubuntu-latest):

| Run | Event | Result | Wall clock |
| --- | --- | --- | --- |
| [45585573464](https://github.com/jack-chen-08/e2e-ci-pipeline-smoke-contract/actions/runs/45585573464) | `pull_request` (PR #1) | success | 71 s |
| [45586384626](https://github.com/jack-chen-08/e2e-ci-pipeline-smoke-contract/actions/runs/45586384626) | `pull_request` (PR #2, one injected failure) | failure | 63 s |
| [45587466429](https://github.com/jack-chen-08/e2e-ci-pipeline-smoke-contract/actions/runs/45587466429) | `workflow_dispatch` (nightly workflow) | success | 86 s |
| [45587497186](https://github.com/jack-chen-08/e2e-ci-pipeline-smoke-contract/actions/runs/45587497186) | `workflow_dispatch` (nightly workflow) | success | 154 s |

## 6. Design notes

* **Isolated compose project.** Every job uses `-p e2e-<run_id>` and `down -v
  --remove-orphans` in an `if: always()` step, so a cancelled run cannot leave containers
  behind or collide with a developer's stack.
* **Stable case ids.** Summary text quotes pytest node names
  (`test_smoke_company_create_and_read`, …) so a failure is traceable to the test file.
* **Contract checks without a schema library.** The served `/openapi.json` *is* the
  contract; the tests assert documented paths, no undocumented response fields, all
  documented required fields, and the documented status codes.
* **Fault-injection is opt-in.** `tests/smoke/test_injected_failure.py` skips unless
  `INJECT_FAILURE=1`, so the shipping gate is green while AC2 stays reproducible.
* **Postgres is tmpfs-backed** in the CI stack: faster and guaranteed disposable.

## 演示分支

本分支仅用于在 PR 上跑一次 e2e-gate（验收标准 1 的截图），合并与否不影响交付。
