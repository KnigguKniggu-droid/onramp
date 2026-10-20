# Corrections and known limitations (written by the team, 2026-10-11)

IBM Bob's plan allowance (180 Bobcoins) ran out on 2026-10-11 while Bob was fixing the classifier. Bob could not make the corrections below, and the team did not change Bob's kit code. This file records what was wrong in the published evidence, what Bob fixed, and what remains open. Original evidence files are kept as recorded, except for one privacy redaction, noted at the end.

## 1. "29 pre-existing failures fixed" was wrong (fixed by Bob in code; the old report is kept)
- **What was wrong:**
  - `docs/onramp/evidence/REPORT_webhook-205.md` reports "Fixed pre-existing failures: 29, Inherited: 0". Those numbers came from `post_fix_webhook-205.txt`, a 1-test run.
  - The original classifier counted every baseline failure that was absent from the run as fixed (`fixed = baseline − run`), including failures that simply never ran.
- **Bob's fix:**
  - Bob reproduced the defect with failing tests (5c0b878) and fixed it (2a527f8): FIXED now requires the test to have run and passed, and absent tests are NOT RUN.
  - Incomplete runs are INCONCLUSIVE.
  - Evidence files with a BOM or in UTF-16 are now read correctly.
  - The kit's tests pass 65/65.
- **Correct reading of the evidence:**
  - The 1-test post-fix run says nothing about the 29 Windows-only failures: they were **not run**.
  - the team's independent full verbose run after the fix and feature (1,767 tests, published with the Evidence Explorer) classifies as FULL: 29 inherited, 0 fixed, 0 regressions, 6 new passing tests. Bob's corrected classifier and the browser classifier agree.

## 2. Known limitation in Bob's corrected parser
Bob's verbose-output parser does not handle tests whose docstring is printed between the test name and its result. Bob's own new test `test_webhooks_accept_http_205` has such a docstring. The parser then finds no outcomes and reports the run as INCONCLUSIVE. This fails safe: the run is not judged at all, rather than being judged wrongly. The browser classifier on the Evidence Explorer handles this case.

## 3. Fresh installation needs a profile (workaround added by the team)
The quick start copies only `.bob/`, but `/onramp`, the skills and the modes read `docs/onramp/profile.json`. Bob's kit has no step that creates it. In the TaskFlow portability runs, Bob created the profile when asked.

The team added a separate, clearly attributed module, `.bob/onramp_normalize.py`, with 12 tests. Bob's files were not changed. In a fresh repository, run this once before `/onramp`:

```
python .bob/onramp_normalize.py init-profile --write
```

It detects Django (`manage.py` plus a settings module) or a plain unittest layout, writes a reviewable `docs/onramp/profile.json`, and does nothing if a profile already exists.

The same module also provides:
- **`normalize`:** turns a verbose test log into versioned JSON. It handles docstring lines and warnings printed mid-line, and fails closed when the "Ran N" count does not match.
- **`classify`:** classifies two normalized runs. It keeps NEW FAILURE separate from REGRESSION and rejects unsupported schema versions.

The Evidence Explorer's in-browser demo uses this same Python module as its authority. A CI parity check compares it with the browser code.

## 4. The post-edit hook reports PASS/FAIL only (open)
`.bob/hooks/run-app-tests.mjs` runs the relevant tests and reports PASS or FAIL from the runner's summary. It does not call the baseline classifier, so a FAIL from the hook can be an inherited failure. Run `.bob/gen_report.py classify` for the baseline-aware verdict.

## 5. What the modes enforce
- Explorer has no edit or command tools, so it is read-only by tool permission.
- Reproducer may edit any `.py` file. "Failing test before fix" is a role instruction to Bob, not a tool restriction.
- Verifier can run commands, so "no edits outside evidence" is likewise an instruction.

## 6. The blind benchmark
- **What the seal proves:** the exact brief text (SHA-256) and the time it was recorded (21:05:38 UTC). It was sealed before Bob began the issue-specific work. It was not sealed before Bob first saw the code: Bob had mapped the repository earlier (`CODEBASE_MAP.md`, 38c4ea2).
- **Isolation controls, which the seal itself does not record:**
  - Bob worked in a single-commit snapshot of Healthchecks with no remote and no upstream history.
  - The maintainer's fix existed only in a separate clone that Bob's workspace never referenced, enforced by a guard in the team.
  - Bob received the symptoms only.
- **Empty fields:** the seal's `allowed_information` and `withheld_information` were left empty at the time and are kept as recorded.
- **Brief wording:** the brief said "a 2xx response such as 205 means the notification was delivered", which invites a broader rule than the maintainer chose.

## 7. Privacy redaction
Absolute paths in public evidence files contained the local Windows user folder. The team replaced those path prefixes with `<home>` and `<repo>` in `pre_fix_webhook-205.txt`, `pre_fix_non_ascii_json_body.txt` and `REPORT_webhook-205.md`. Nothing else in those files changed.
