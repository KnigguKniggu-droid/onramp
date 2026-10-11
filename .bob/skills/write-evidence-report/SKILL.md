---
name: write-evidence-report
description: >-
  Use after verify-change has saved all three artefacts. Reads pre_fix,
  post_fix, and diff files for a given slug, then runs gen_report.py to
  produce REPORT_<slug>.md. Flags anomalies automatically where detectable.
---

# Write Evidence Report

Run this skill only after `verify-change` has confirmed all three artefacts
exist.

## Step 1 — Read the profile

Read `docs/onramp/profile.json`. Extract `evidence_dir`.

## Step 2 — Confirm artefacts

Check that the following files exist (use `list_files` on `<evidence_dir>`):
- `pre_fix_<slug>.txt`
- `post_fix_<slug>.txt`
- `diff_<slug>.txt`
- `baseline.json` (optional but recommended — produced by `gen_report.py capture-baseline`)

If any of the first three are missing, stop and tell the user which artefact
is absent and which skill produces it. Missing `baseline.json` is non-fatal;
the generator will note "N/A" for regression counts.

## Step 3 — Run the generator

Run:
```
python .bob/gen_report.py report <slug>
```

The script reads the artefacts, compares against the baseline, and writes
`<evidence_dir>/REPORT_<slug>.md`.

Capture stdout and stderr. If the script exits non-zero, report the error
message and stop.

## Step 4 — Read and surface the report

Read the generated `<evidence_dir>/REPORT_<slug>.md`.

Report to the user:
1. The five verification flags and their status (checked/unchecked).
2. Any anomaly lines the generator flagged (lines starting with `ANOMALY:`).
3. The diff size (files changed, lines changed).

## Step 5 — Anomaly handling

For each `ANOMALY:` line:
- **"Test was already passing before fix"**: the pre_fix run showed OK — the
  bug was not reproduced before the fix. Re-run the bug-to-test skill.
- **"No assertions detected in test body"**: open the test file and add at
  least one `assertEqual` / `assertIn` / `assertRaises`.
- **"Diff touches files outside expected scope"**: review the diff and confirm
  with the user that the extra files are intentional.
- **"Regression detected"**: new test failures appeared that were not in
  baseline. The fix must be revised.

## Step 6 — Done

If all five flags are set and no unresolved anomalies remain, tell the user:
- Path to the report: `<evidence_dir>/REPORT_<slug>.md`
- The change is verified and ready to commit in Agent mode.
