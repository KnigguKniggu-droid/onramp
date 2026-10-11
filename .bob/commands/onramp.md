# /onramp

Guided OnRamp walkthrough for a developer who is new to this repository.

---

## What this command does

1. Reads `docs/onramp/profile.json` and `docs/onramp/CODEBASE_MAP.md` to orient
   you in the repository.
2. Summarises the repo in three bullets: what it does, how a request flows
   end-to-end, and how to run the tests.
3. Prints the OnRamp checklist so you know exactly what to do next.

---

## Steps Bob follows when you run /onramp

### 1 — Load the profile

Read `docs/onramp/profile.json`. Confirm the key values are present:
`test_runner`, `apps`, `evidence_dir`, `venv_activate`.

### 2 — Load the codebase map

Read `docs/onramp/CODEBASE_MAP.md`. If it does not exist, activate the
`map-codebase` skill to generate it now before continuing.

### 3 — Summarise the repository

Print a three-bullet summary:
- **What it does:** one sentence from the CODEBASE_MAP "What This App Does" section.
- **Request flow:** the URL -> view -> model trace from the CODEBASE_MAP.
- **How to test:** the exact run commands from the CODEBASE_MAP.

Switch to Explorer mode to deliver this summary with file references.

### 4 — Print the OnRamp checklist

```
OnRamp Checklist
================

Step 1 — Orient (you are here)
  /onramp in Explorer mode.
  Exit: you can answer "where does a ping request land?" with a file reference.

Step 2 — Choose a bug
  Pick any issue or use an example from CODEBASE_MAP.md.
  Switch to Reproducer mode.

Step 3 — Write the failing test
  Activate the bug-to-test skill.
  Exit: docs/onramp/evidence/pre_fix_<slug>.txt exists and shows FAIL.

Step 4 — Fix the bug
  Write the minimal change.
  The post-edit hook runs the app suite automatically.
  Exit: targeted test passes; no new app-suite failures.

Step 5 — Verify
  /evidence <slug> in Verifier mode.
  Exit: REPORT_<slug>.md exists, all five flags set.

Step 6 — Commit (Agent mode)
  git add <files>; git commit -m "<message>"
```

### 5 — Tell the user what to do next

Ask: "Do you have a bug report ready, or would you like to explore the codebase
first?"

If they have a bug report: guide them to Step 3 (switch to Reproducer mode,
activate bug-to-test skill).

If they want to explore: stay in Explorer mode and answer their questions.
