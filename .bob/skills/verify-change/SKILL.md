---
name: verify-change
description: >-
  Use after a fix is written. Re-runs the targeted test, runs the app suite,
  compares failing IDs against the baseline, and saves the post-fix artefacts.
  Must be run before the write-evidence-report skill.
---

# Verify Change

Follow these steps in order after a fix has been written but before committing.

## Step 1 — Read the profile and locate artefacts

1. Read `docs/onramp/profile.json`. Extract `test_runner`, `evidence_dir`,
   `app_root`, and `framework` (default `"django"`).
2. Identify the slug for this fix (should match the `pre_fix_<slug>.txt`
   artefact already saved by the bug-to-test skill).
3. Confirm `<evidence_dir>/pre_fix_<slug>.txt` exists. If it does not,
   stop and run the bug-to-test skill first.

## Step 2 — Read the baseline

Read `<evidence_dir>/baseline.json`. This file records failing test IDs
that existed *before any change* in this repository. Keep this in context
for Step 5. (The file is written by `gen_report.py capture-baseline`.)

## Step 3 — Run the targeted test

Run only the test written for this bug. For Django (`framework == "django"`):
```
<test_runner> <Module.ClassName.test_method> --verbosity=2
```
For plain unittest or other frameworks, omit `--verbosity=2`:
```
<test_runner> <Module.ClassName.test_method>
```

Capture full stdout + stderr.

## Step 4 — Confirm it passes

The output must contain `OK` and `Ran 1 test`.

If it does not, the fix is incomplete. Report the failure reason and stop.
Do not proceed to Step 5.

## Step 5 — Save the post-fix artefact

Write the raw output to `<evidence_dir>/post_fix_<slug>.txt`.

## Step 6 — Run the app suite

For **Django**: derive the app label from the test module path (e.g.
`hc.api.tests.test_ping` -> `hc.api`) and run with `--verbosity=2`:
```
<test_runner> <app_label> --verbosity=2
```
For **plain unittest / other**: run the full suite:
```
<test_runner>
```

Capture full stdout + stderr.

## Step 7 — Regression check

Parse the app suite output for failed/errored test IDs.

Compare against `baseline.json` (field `failing[].id`):
- IDs also in the baseline: **pre-existing failures** — list but do not treat
  as regressions.
- IDs not in the baseline: **regressions** — the fix introduced new failures.

If any regressions exist, stop and report them. Do not proceed until they
are resolved.

## Step 8 — Capture the diff

Run:
```
git diff HEAD
```

Save output to `<evidence_dir>/diff_<slug>.txt`.

## Step 9 — Hand off to write-evidence-report

All three artefacts now exist:
- `pre_fix_<slug>.txt`
- `post_fix_<slug>.txt`
- `diff_<slug>.txt`

Activate the `write-evidence-report` skill to assemble the final report.
