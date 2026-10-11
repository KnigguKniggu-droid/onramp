# OnRamp: an IBM Bob kit for joining an unfamiliar codebase

A drop-in kit that takes a developer from "never seen this repo" to a verified bug fix with sealed evidence, using only Bob-native extension points.

> **Derived from [healthchecks/healthchecks](https://github.com/healthchecks/healthchecks) at commit `0968fa2` (BSD-3-Clause, see [LICENSE](../LICENSE)).  This repository is not affiliated with the Healthchecks project.**

**[Evidence Explorer (live demo)](https://kniggukniggu-droid.github.io/onramp-evidence/)** · **[Pitch deck (PDF)](../docs/deck/OnRamp-pitch-deck.pdf)** · **[Corrections and known limitations](../docs/evidence/CLAUDE_CORRECTIONS_2026-10-11.md)**

---

## What the kit is

The reusable kit lives under `.bob/` (plus a per-repository profile in `docs/onramp/`). The Healthchecks case study itself changes application code under `hc/` (the bug fix and the feature).

| Component | Location | Purpose |
|-----------|----------|---------|
| **Explorer mode** | [`.bob/custom_modes.yaml`](../.bob/custom_modes.yaml) | Read-only guide — traces requests, maps layout, answers "where does X live?" before any change |
| **Reproducer mode** | [`.bob/custom_modes.yaml`](../.bob/custom_modes.yaml) | Failing-test-first workflow; instructed not to draft a fix until `pre_fix_<slug>.txt` exists and shows `FAIL` (an instruction, not a tool restriction) |
| **Verifier mode** | [`.bob/custom_modes.yaml`](../.bob/custom_modes.yaml) | Reviews evidence artefacts and gates completion; edits limited to the evidence folder (it can still run commands) |
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

- **26** are `hc.integrations.signal` tests — they fail with `AttributeError: module 'socket' has no attribute 'AF_UNIX'`, which does not exist on Windows.
- **2** are `hc.accounts.tests.test_senddeletionscheduled` tests — they fail with `ValueError: Invalid format string` because the strftime format used is Linux-only.
- **1** is `hc.api.tests.test_check_model.CheckModelTestCase.test_get_status_handles_autumn_dst_transition` — fails because time-zone switching does not work on Windows.

These are recorded in [`docs/onramp/evidence/baseline.json`](../docs/onramp/evidence/baseline.json) and classified as *inherited failures* (pre-existing, not introduced by any change).

> **Note:** `baseline.json` records `error_type: "Unknown"` for all 29 entries because the baseline was captured from a `unittest` run without `-v`; the error types above come from direct inspection of the test sources and Windows behaviour.

---

### Blind fix — webhook HTTP 205 bug

**Brief (sealed before the issue-specific work began; Bob had already mapped the repository):** A webhook endpoint that replies with HTTP 205 caused Healthchecks to retry the request three times and mark the integration as failed.  The brief's expectation was "a 2xx response such as 205 means the notification was delivered".  The brief was hashed and recorded in [`docs/onramp/evidence/benchmark_webhook-205.json`](../docs/onramp/evidence/benchmark_webhook-205.json) at 21:05:38 UTC, before Bob started reproducing the bug.

**Workflow:**
1. `seal-benchmark` recorded the brief SHA-256 and timestamp.
2. `bug-to-test` skill wrote `test_webhooks_accept_http_205` — failing (`AssertionError: 3 != 1`, call count instead of 1) — before any fix was written.  Output saved to [`pre_fix_webhook-205.txt`](../docs/onramp/evidence/pre_fix_webhook-205.txt).
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

Issue [#1090](https://github.com/healthchecks/healthchecks/issues/1090) asked for JSON ping bodies to be pretty-printed in the ping-detail view.  Commit `786c034` implemented this by passing the parsed JSON through `json.dumps` with `indent=2`, keeping the **Download Original** link byte-for-byte unchanged.  A follow-up commit `e4032c2` added `ensure_ascii=False` after a reviewer noticed that `json.dumps` was escaping non-ASCII characters such as `café` as `\u00e9`.

The pre-fix test ([`pre_fix_non_ascii_json_body.txt`](../docs/onramp/evidence/pre_fix_non_ascii_json_body.txt)) confirmed the failure after the pretty-print change was in place:

```
AssertionError: False is not true : Couldn't find 'café' in the following response
(body contained \u00e9 and \u2705 escape sequences instead of literal UTF-8 characters)
```

---

## Portability — TaskFlow (Flask)

The `.bob/` directory was copied unchanged into a separate Flask project called TaskFlow.  Only [`docs/onramp/profile.json`](../docs/onramp/profile.json) was updated to reflect the Flask test runner and app structure.  All three runs validated the installation, created the profile, captured the baseline, and generated the codebase map; none ran a bug-to-test loop, none used pytest directly, and no kit files were edited in the TaskFlow project.

- **Run 1** exposed Django assumptions baked into the kit: the post-edit hook was hardcoded to `hc/`, output parsing was Django-only, baseline storage used `baseline.txt` instead of `baseline.json`, the Reproducer mode's edit scope was Django-specific, and several skill steps referenced Django conventions.  These were fixed in commits `4facc4b` and `6be3235`.
- **Run 2** found that `unittest` error types were recorded as `"Unknown"` when the run lacked `-v`.  Fixed in commit `8165552`.
- **Run 3** recorded `AssertionError` correctly.  **Known limitations from run 3:** on Windows the profile's test command must use the venv's own Python executable, and failures from `unittest` runs without `-v` lose the module path in the recorded id.

---

## Quick start

**Drop the kit into another repository** — copy only `.bob/`; `docs/onramp/` holds Healthchecks-specific evidence and should not be copied:

```
cp -r .bob/ <your-repo>/.bob/
```

Then open Bob in the new repository and run:

```
/onramp
```

`/onramp` needs `docs/onramp/profile.json`, which the kit does not create yet: copy this repository's profile as a template or ask Bob to create it first (see [known limitations](../docs/evidence/CLAUDE_CORRECTIONS_2026-10-11.md)).

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

IBM Bob (IDE and Bob Shell) performed the OnRamp implementation, repository exploration, debugging, testing workflows and code changes; its commits end with `Generated-by: IBM Bob`. Claude Code orchestrated Bob at the participant's direction, verified results independently, and assembled the public evidence presentation (pitch deck, Evidence Explorer, corrections). Claude's commits say so in their messages.

Full design rationale and sub-task breakdown: [`docs/onramp/PLAN.md`](../docs/onramp/PLAN.md).
