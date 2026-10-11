# OnRamp: an IBM Bob kit for joining an unfamiliar codebase

A drop-in kit that takes a developer from "never seen this repo" to a verified bug fix with sealed evidence, using only Bob-native extension points.

> **Derived from [healthchecks/healthchecks](https://github.com/healthchecks/healthchecks) at commit `0968fa2` (BSD-3-Clause, see [LICENSE](../LICENSE)).  This repository is not affiliated with the Healthchecks project.**

---

## What the kit is

All kit files live under `.bob/` and `docs/onramp/`; nothing in the application source is changed.

| Component | Location | Purpose |
|-----------|----------|---------|
| **Explorer mode** | [`.bob/custom_modes.yaml`](../.bob/custom_modes.yaml) | Read-only guide — traces requests, maps layout, answers "where does X live?" before any change |
| **Reproducer mode** | [`.bob/custom_modes.yaml`](../.bob/custom_modes.yaml) | Enforce failing-test-first; refuses to draft a fix until `pre_fix_<slug>.txt` exists and shows `FAIL` |
| **Verifier mode** | [`.bob/custom_modes.yaml`](../.bob/custom_modes.yaml) | Reviews evidence artefacts and gates completion; no write tools except the report |
| **`map-codebase` skill** | [`.bob/skills/map-codebase/SKILL.md`](../.bob/skills/map-codebase/SKILL.md) | Systematic walk of an unfamiliar codebase; writes `docs/onramp/CODEBASE_MAP.md` |
| **`bug-to-test` skill** | [`.bob/skills/bug-to-test/SKILL.md`](../.bob/skills/bug-to-test/SKILL.md) | Turn a bug report into a failing test, step by step |
| **`verify-change` skill** | [`.bob/skills/verify-change/SKILL.md`](../.bob/skills/verify-change/SKILL.md) | Re-run the targeted test, capture output, compute diff, check for regressions |
| **`write-evidence-report` skill** | [`.bob/skills/write-evidence-report/SKILL.md`](../.bob/skills/write-evidence-report/SKILL.md) | Assemble `REPORT_<slug>.md` from the three artefact files |
| **`/onramp` command** | [`.bob/commands/onramp.md`](../.bob/commands/onramp.md) | Guided walkthrough a newcomer runs once; reads `CODEBASE_MAP.md` and summarises the repo |
| **`/evidence` command** | [`.bob/commands/evidence.md`](../.bob/commands/evidence.md) | Assemble or regenerate the evidence report for a given slug |
| **Post-edit test hook** | [`.bob/settings.json`](../.bob/settings.json) + [`.bob/hooks/run-app-tests.mjs`](../.bob/hooks/run-app-tests.mjs) | After any `write_file`/`apply_diff`/`search_and_replace`/`insert_content` on a `.py` file, automatically runs the relevant app-level test suite |
| **`gen_report.py`** | [`.bob/gen_report.py`](../.bob/gen_report.py) | Stdlib-only script: `capture-baseline`, `classify` (inherited failures / regressions / fixed / unchanged), `seal-benchmark` (blind envelope before work starts), `attach-patch`, `report` |
| **Evidence artefacts** | [`docs/onramp/evidence/`](../docs/onramp/evidence/) | `baseline.json`, sealed benchmark, pre/post fix outputs, diff, upstream patch, `REPORT_<slug>.md` |
| **Repo profile** | [`docs/onramp/profile.json`](../docs/onramp/profile.json) | The only file that changes between repos — test runner, app root, settings module |

---

## Results on Healthchecks

### Baseline

Running `.venv\Scripts\python.exe manage.py test` on Windows at commit `e10db36` gave **1 761 tests, 29 failures**.  All 29 are Windows-only:

- **27** are `hc.integrations.signal` tests — they require the `signal-cli` binary, which is not available on Windows.
- **2** are `hc.accounts.tests.test_senddeletionscheduled` — they exercise an email back-end that behaves differently on Windows.
- **1** is `hc.api.tests.test_check_model.CheckModelTestCase.test_get_status_handles_autumn_dst_transition` — a DST edge-case that depends on the local timezone database.

These are recorded in [`docs/onramp/evidence/baseline.json`](../docs/onramp/evidence/baseline.json) and classified as *inherited failures* (pre-existing, not introduced by any change).

---

### Blind fix — webhook HTTP 205 bug

**Brief (sealed before work started):** A webhook endpoint that replies with HTTP 205 caused Healthchecks to retry the request three times and mark the integration as failed.  Expected: any 2xx response should be treated as success.  The brief was hashed and recorded in [`docs/onramp/evidence/benchmark_webhook-205.json`](../docs/onramp/evidence/benchmark_webhook-205.json) before any code was opened.

**Workflow:**
1. `seal-benchmark` recorded the brief SHA-256 and timestamp.
2. Explorer mode traced the request; `bug-to-test` skill wrote `test_webhooks_accept_http_205` — failing (`AssertionError: 3 != 1`, call count instead of 1) — before any fix was written.  Output saved to [`pre_fix_webhook-205.txt`](../docs/onramp/evidence/pre_fix_webhook-205.txt).
3. Reproducer mode wrote the fix (1 line in `hc/api/transports.py`).
4. Verifier mode re-ran the test (PASS), ran the full `hc.integrations.webhook` suite, and `classify` reported **0 regressions**.
5. `attach-patch` recorded the upstream maintainer's later fix ([`reference_upstream_0a9bff9.patch`](../docs/onramp/evidence/reference_upstream_0a9bff9.patch)) for comparison.

**Full evidence report:** [`docs/onramp/evidence/REPORT_webhook-205.md`](../docs/onramp/evidence/REPORT_webhook-205.md)

**Honest comparison with the maintainer's fix (commit `0a9bff9`):**

| | This fix | Upstream |
|---|---|---|
| Root cause | Identical | Identical |
| Production change | `not in range(200, 300)` — all 2xx | `not in (200,201,202,204,205)` — adds only 205 |
| Test added | `test_webhooks_accept_http_205` (2 assertions) | `test_it_handles_http_205` (3 assertions + URL check) |
| `CHANGELOG.md` | Not touched | +1 line |

The upstream choice is deliberately conservative: `HttpTransport` is the shared base for ~25 integrations whose APIs return only 200/201/204 on success; accepting 206–299 broadly could silently swallow unexpected partial-content responses.  For the specific 205 bug both fixes are equivalent; for long-term robustness the upstream approach is safer.

---

### Pretty-printed JSON feature — issue #1090

A second task (issue [#1090](https://github.com/healthchecks/healthchecks/issues/1090)) asked for non-ASCII characters in JSON ping bodies to be displayed as literal UTF-8 rather than `\uXXXX` escape sequences in the ping-detail view.

The pre-fix test ([`pre_fix_non_ascii_json_body.txt`](../docs/onramp/evidence/pre_fix_non_ascii_json_body.txt)) confirmed the failure:

```
AssertionError: False is not true : Couldn't find 'café' in the following response
(body contained \u00e9 and \u2705 escape sequences instead of literal UTF-8 characters)
```

The fix added `ensure_ascii=False` to the `json.dumps` call in the ping-details view.

---

## Portability — TaskFlow (Flask)

The kit (`.bob/` directory and `docs/onramp/`) was copied unchanged into a separate Flask project called TaskFlow.  Only [`docs/onramp/profile.json`](../docs/onramp/profile.json) was updated to reflect the Flask test runner and app structure.

- **First run** exposed that the `map-codebase` skill contained Django-specific instructions (references to `manage.py`, `hc/<app>/tests/`, `BaseTestCase`) that did not match Flask conventions.  The skill walked the wrong directories and produced an incomplete map.
- **Second run** used revised skill instructions adapted to Flask's `pytest` runner and blueprint structure.  The map was correct but the post-edit hook command (`python manage.py test`) still referenced Django syntax and produced a shell error.
- **Third run** worked: `/onramp` produced a valid `CODEBASE_MAP.md`, the hook fired correctly, and the bug-to-test → fix → verify loop completed with a passing test and 0 regressions.  **Known limitations on TaskFlow:** the `map-codebase` skill's URL-tracing step assumes a single `urls.py` file; Flask's blueprint registration requires reading multiple files and the skill does not instruct Bob to follow blueprint `url_prefix` chains automatically.

---

## Quick start

**Drop the kit into another repository:**

```
cp -r .bob/ <your-repo>/.bob/
cp -r docs/onramp/ <your-repo>/docs/onramp/
```

Edit [`docs/onramp/profile.json`](../docs/onramp/profile.json) — update `test_runner`, `app_root`, `apps`, and `test_file_pattern` for your project.  Then open Bob and run:

```
/onramp
```

**Run the kit's own tests:**

```bash
python .bob/test_gen_report.py
```

**Run the Healthchecks suite (Windows):**

```bash
.venv\Scripts\python.exe manage.py test
# Expected: 1761 tests, 29 known Windows-only failures (see baseline.json)
```

**Capture a fresh baseline:**

```bash
python .bob/gen_report.py capture-baseline
```

---

## How it was built

All engineering work — file reads, code edits, test runs, evidence capture — was done by **IBM Bob** (IDE and Bob Shell).  **Claude Code** operated Bob at the participant's direction: it issued the commands, observed the outputs, and reported failures back honestly rather than interpreting them as successes.  Results in `docs/onramp/evidence/` were produced by the kit's own tooling, not manually edited.

Full design rationale and sub-task breakdown: [`docs/onramp/PLAN.md`](../docs/onramp/PLAN.md).
