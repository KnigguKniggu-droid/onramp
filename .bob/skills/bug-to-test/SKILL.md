---
name: bug-to-test
description: >-
  Use when you have a bug report and need to write a failing test before
  any fix. Guides through locating the affected code, writing the test,
  confirming it fails for the right reason, and saving the pre-fix artefact.
  Must complete before any fix is written.
---

# Bug to Test

Follow these steps exactly. Do not write a fix until Step 7 is complete.

## Step 1 — Read the profile

Read `docs/onramp/profile.json`. Extract:
- `test_runner` — command to run tests
- `app_root` — e.g. `hc`
- `test_file_pattern` — e.g. `hc/**/tests/test_*.py`
- `evidence_dir` — where to save artefacts (e.g. `docs/onramp/evidence`)
- `base_test_class` — e.g. `hc/test.py`

## Step 2 — Understand the bug

Read the bug description carefully. Write a one-sentence statement:
> "When X happens, Y is observed. The correct behaviour is Z."

Ask the user to confirm this reading before continuing.

## Step 3 — Locate the code

1. Use `grep` with a regex matching the symptom (endpoint URL, function name,
   model field, error message).
2. Use `FindSymbol` to locate the view or model function involved.
3. Read the function body. Identify the exact line(s) responsible.
4. Find the existing test file for that module:
   `grep` for the test class covering the same view/model.

## Step 4 — Write the failing test

In the existing test file for the affected module:
1. Add a new test method to the most relevant `TestCase` class.
   - Name it `test_<bug_slug>` (e.g. `test_ping_rejects_empty_body`).
   - Use the same `setUp` fixtures already in that class — do not duplicate.
   - The test must assert the *correct* (post-fix) behaviour, not the buggy one.
   - Include at least one `assertEqual` / `assertIn` / `assertRaises` assertion.
2. Do not change any existing test.
3. Do not change any production code.

## Step 5 — Run the test

Run only the new test. For Django (`profile.framework == "django"`):
```
<test_runner> <Module.ClassName.test_method> --verbosity=2
```
For plain unittest or other frameworks, omit `--verbosity=2`:
```
<test_runner> <Module.ClassName.test_method>
```

Capture the full stdout + stderr output.

## Step 6 — Confirm the right failure

The output must contain:
- `FAIL` or `AssertionError` (not `ERROR` — an `ERROR` means the test itself
  is broken, not the production code).
- The test method name.

If the output shows `ERROR`, fix the test until it shows `FAIL`, then
re-run.

If the output shows `OK`, the bug is not reproduced by this test. Revise
the assertion and repeat from Step 4.

## Step 7 — Save the pre-fix artefact

Write the raw test output to:
`<evidence_dir>/pre_fix_<slug>.txt`

where `<slug>` is a short snake_case identifier for this bug
(e.g. `ping_empty_body`).

## Step 8 — Hand off

Tell the user:
- The test name: `<Module.ClassName.test_method>`
- The artefact path: `<evidence_dir>/pre_fix_<slug>.txt`
- The exact fix command to run next in Reproducer mode

Do not write any production code changes. Switch to Reproducer mode and
instruct it to fix only the lines identified in Step 3.
