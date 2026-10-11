# OnRamp — Design Plan

**Goal:** A drop-in IBM Bob kit that takes a developer from "never seen this
repo" to a verified bug fix and a useful feature, with evidence behind every
claim.  All extension points are Bob-native (custom modes, skills, slash
commands, hooks).  The kit has a generic core and a thin Healthchecks profile.

**Constraints:** No network access, no external services, no new runtime
dependencies.  This document describes only what to build; nothing is
implemented here.

---

## Repository Profile (Healthchecks)

| Fact | Value |
|------|-------|
| Framework | Django 6.1 |
| Language | Python 3.12 – 3.14 |
| Test runner | `python manage.py test` (Django unittest) |
| Test root | `hc/<app>/tests/test_*.py` |
| Base test class | `hc.test.BaseTestCase` in `hc/test.py` |
| Settings module | `hc.settings` |
| Main apps | `hc.accounts`, `hc.api`, `hc.front`, `hc.logs`, `hc.payments`, `hc.integrations.*` |
| Virtual env | `.venv\Scripts\activate` (Windows) |
| Targeted test | `python manage.py test hc.api.tests.test_ping.PingTestCase` |
| Full suite | `python manage.py test` |
| Verbosity flag | `--verbosity=2` |
| Keep DB flag | `--keepdb` |

---

## 1. Custom Modes  (`.bob/custom_modes.yaml`)

### 1.1  `explorer` — Read-Only Codebase Guide

**Role:** An opinionated tour guide for a developer who has never seen the
repo.  It explains structure, traces a request through layers, maps models to
URLs to views, and answers "where does X live?" questions — always with file
references.  It never writes code.

**Tool groups allowed:** read-only (`read_file`, `list_files`, `grep`, `glob`,
`GetSymbolsOverview`, `FindSymbol`, `FindReferencingSymbols`).  No write or
execute tools.

**File-pattern focus:** `hc/**/*.py`, `hc/urls.py`, `hc/settings.py`,
`templates/**`, `hc/test.py`, `README.md`, `CHANGELOG.md`.

**When to switch here:** At the very start of a session, when the developer
needs to understand layout, trace a data-flow, or find where a behaviour is
implemented before any change is attempted.

---

### 1.2  `reproducer` — Reproduce-First Fixer

**Role:** Takes a bug report (symptom description or issue text) and guides
the developer through: locating the relevant code path, writing a failing test
that captures the bug exactly, running that test to confirm it fails for the
right reason, and only then drafting the minimal fix.  It refuses to write a
fix before a failing test exists.

**Tool groups allowed:** read-only tools plus `execute_command` (to run the
test suite and git commands: `git stash`, `git diff`, `git log`, `git status`),
plus write tools scoped to `hc/**/tests/` and the specific source file being
fixed.

**File-pattern focus:** `hc/**/tests/test_*.py`, `hc/**/models.py`,
`hc/**/views.py`, `hc/**/forms.py`, `hc/test.py`.

**When to switch here:** After `explorer` has identified the affected area and
the developer is ready to write a failing test before touching production code.

---

### 1.3  `verifier` — Evidence-Gated Reviewer

**Role:** Reviews a completed change against concrete evidence: the pre-fix
failing test output, the post-fix passing test output, and the git diff.  It
flags any fix that was merged without a failing-first test, any test that
passes vacuously (e.g. no assertions), or any diff that touches more files
than the failing test justifies.  It produces a structured evidence report.

**Tool groups allowed:** read-only tools plus `execute_command` (to re-run
tests and any git command needed to inspect the change).  No write tools except
to emit the evidence report file.

**File-pattern focus:** `docs/onramp/evidence/`, `hc/**/tests/test_*.py`,
`hc/**/*.py`.

**When to switch here:** After a fix is written and the developer believes it
is correct.  The verifier is the final gate before the change is considered
done.

---

## 2. Skills  (`.bob/skills/<name>/SKILL.md`)

### 2.1  `map-codebase`

**Purpose:** Walk an unfamiliar Django codebase systematically.  The skill
instructs Bob to: list top-level apps, trace the URL → view → model → template
chain for a representative endpoint, identify the base test class and test
conventions, and produce a one-page `CODEBASE_MAP.md` that becomes a shared
reference for all other skills.

**Key instructions the skill encodes:**
- Start with `list_files` at the root, then inside each `hc/<app>/`.
- Open `hc/urls.py` and one integration URL file to understand routing.
- Read `hc/test.py` for test fixtures and helpers.
- Read `hc/settings.py` lines 1–60 for environment-variable configuration.
- Output `docs/onramp/CODEBASE_MAP.md` with sections: Apps, URL Routing,
  Models, Test Conventions, Run Commands.

**Relevant repo files:** `hc/urls.py`, `hc/settings.py`, `hc/test.py`,
`hc/<app>/models.py`, `hc/<app>/tests/`.

---

### 2.2  `bug-to-test`

**Purpose:** Turn a bug report into a failing test before any fix is written.
Encodes the reproduce-first discipline as a checklist Bob follows step-by-step.

**Key instructions the skill encodes:**
1. Read the bug description and locate the affected view/model using `grep`
   and `FindSymbol`.
2. Find the most relevant existing test file in `hc/<app>/tests/`.
3. Write a new test method in `BaseTestCase` style that asserts the *correct*
   behaviour (not the buggy one), using the same setUp fixtures already in
   that file.
4. Run only that one test with `python manage.py test <module>.<Class>.<method>`.
5. Confirm the output contains `FAIL` or `AssertionError` — not `ERROR`.
6. Save the raw output to `docs/onramp/evidence/pre_fix_<slug>.txt`.
7. Only after step 6 is done, allow switching to `reproducer` mode to write
   the fix.

**Relevant repo files:** `hc/test.py`, `hc/api/tests/test_ping.py` (example
pattern), `hc/<app>/tests/`.

---

### 2.3  `verify-change`

**Purpose:** After a fix is written, re-run the targeted test, capture the
passing output, compute the diff, and verify the change satisfies the
evidence criteria.

**Key instructions the skill encodes:**
1. Run the exact test identified in `pre_fix_<slug>.txt`.
2. Confirm the output contains `OK` and `Ran 1 test`.
3. Save output to `docs/onramp/evidence/post_fix_<slug>.txt`.
4. Run `git diff HEAD` and save to `docs/onramp/evidence/diff_<slug>.txt`.
5. Run the full affected app suite (`python manage.py test hc.<app>`) and
   confirm no new failures.
6. Call the `write-evidence-report` skill to assemble the final report.

---

### 2.4  `write-evidence-report`

**Purpose:** Assemble a human-readable evidence report from the three artefacts
produced by `bug-to-test` and `verify-change`.

**Key instructions the skill encodes:**
- Read `pre_fix_<slug>.txt`, `post_fix_<slug>.txt`, `diff_<slug>.txt`.
- Extract test name, failure reason, fix summary, and line-count of the diff.
- Write `docs/onramp/evidence/REPORT_<slug>.md` using the template defined in
  section 4 of this plan.
- Flag any anomaly: test that was already passing before fix, diff that touches
  unrelated files, zero assertions in the test.

---

## 3. Slash Commands and Hooks

### 3.1  Slash Command: `/onramp`

**What it does:** A guided walkthrough that a newcomer runs once at the start
of a session.  When invoked, it:

1. Prints the OnRamp checklist (steps 1–5 from section 5 of this plan).
2. Reads the pre-seeded `docs/onramp/CODEBASE_MAP.md` (always present; see ST-6).
3. Switches to `explorer` mode and summarises the repo in three bullets:
   what the app does, how a ping flows through the stack, how to run the tests.
4. Prints the exact `python manage.py test` commands for this repo.

**Definition location:** `.bob/slash_commands/onramp.md`

---

### 3.2  Slash Command: `/evidence <slug>`

**What it does:** Assembles or re-assembles the evidence report for a given
slug by invoking `write-evidence-report`.  Useful when artefacts exist but the
report was not yet written or needs to be regenerated after a change.

**Definition location:** `.bob/slash_commands/evidence.md`

---

### 3.3  Hook: post-edit Python file → run affected tests

**Trigger:** `tool_use` stop event, specifically when the tool is `write_file`,
`apply_diff`, or `search_and_replace` and the edited file matches `**/*.py`
(any Python file in the repo, not only files under `hc/<app>/`).

**Action:** Derive the Django app from the edited file path
(`hc/<app>/...` → `hc.<app>`), then run
`python manage.py test hc.<app> --verbosity=2`.

**Intent:** Keeps the feedback loop tight — a developer editing any `.py` file
sees the relevant test suite result automatically, without having to remember
the command.

**Constraint:** The hook runs only the app-level suite, not the full suite, to
keep it fast.  If the edited file is `hc/test.py` (the base class) or lives
outside any recognised `hc/<app>/` subtree (e.g. `docs/onramp/gen_report.py`),
the hook runs the full suite as the safe fallback.

**Definition location:** `.bob/hooks.yaml`

---

## 4. Evidence Report

### 4.1  Report Template  (`REPORT_<slug>.md`)

```
# Evidence Report — <slug>

## Summary
- **Bug:** <one-line description>
- **Fix:** <one-line description>
- **Test:** `<module.Class.method>`
- **Diff size:** <N lines changed across M files>

## Pre-Fix Test Run
- **Result:** FAIL
- **Failure reason:** <extracted from pre_fix output>
- **Raw output:** `docs/onramp/evidence/pre_fix_<slug>.txt`

## Post-Fix Test Run
- **Result:** PASS
- **Tests run:** <N>
- **Raw output:** `docs/onramp/evidence/post_fix_<slug>.txt`

## Regression Check
- **App suite result:** <OK / FAIL>
- **New failures introduced:** <none / list>

## Diff
- **File(s) changed:** <list>
- **Raw diff:** `docs/onramp/evidence/diff_<slug>.txt`

## Verification Flags
- [ ] Test existed before fix and was FAIL  
- [ ] Test passes after fix  
- [ ] No new failures in app suite  
- [ ] Diff is minimal (only the files the test implicates)  
- [ ] Test contains at least one assertion  
```

### 4.2  Evidence Generator Script  (`docs/onramp/gen_report.py`)

A stdlib-only Python script that reads the three artefact files and writes the
`REPORT_<slug>.md` file.  No third-party libraries.

**Inputs (positional CLI arguments):**
```
python docs/onramp/gen_report.py <slug>
```

**What it does:**
1. Reads `docs/onramp/evidence/pre_fix_<slug>.txt`.
2. Reads `docs/onramp/evidence/post_fix_<slug>.txt`.
3. Reads `docs/onramp/evidence/diff_<slug>.txt`.
4. Parses the Django test runner output to extract: test name, failure/error
   message, number of tests run, `OK` or `FAIL` result.  Uses only `re` and
   `pathlib` from stdlib.
5. Distinguishes **pre-existing failure** (test ran before the fix and failed)
   from **regression** (test that was passing before is now failing) by
   comparing the pre- and post-fix outputs.
6. Populates all template fields from section 4.1.
7. Sets verification flags automatically where provable, leaves unchecked
   where human judgement is required (e.g. "diff is minimal").
8. Writes `docs/onramp/evidence/REPORT_<slug>.md`.

**Key parsing rules (no third-party libs):**
- `FAIL` / `OK` at the end of the runner output: match with
  `re.search(r'^(OK|FAIL)', output, re.MULTILINE)`.
- Test name: match `re.search(r'(FAIL|ERROR): (\S+)', output)`.
- Failure reason: the first `AssertionError:` or `Error:` line in the
  traceback block.
- Diff file count: count lines starting with `diff --git`.
- Diff line count: count lines starting with `+` or `-` (excluding `+++`/`---`).

---

## 5. Newcomer Walkthrough

The ordered steps a developer follows when using this kit on Healthchecks for
the first time.

```
Step 1 — Orient
  Run: /onramp
  Bob reads or creates CODEBASE_MAP.md, then summarises the repo in explorer mode.
  Exit criterion: developer can answer "where does a /ping/<uuid> request land?"

Step 2 — Choose a bug
  Pick a known issue or the sample bug provided in CODEBASE_MAP.md.
  Switch to reproducer mode.

Step 3 — Write the failing test (bug-to-test skill)
  Follow the skill checklist.
  Exit criterion: pre_fix_<slug>.txt exists and shows FAIL.

Step 4 — Fix the bug (reproducer mode)
  Write the minimal change.  The post-edit hook runs the app suite automatically.
  Exit criterion: the targeted test passes; the app suite shows no new failures.

Step 5 — Verify (verifier mode, verify-change skill)
  Run /evidence <slug>.
  Exit criterion: REPORT_<slug>.md exists with all five verification flags set.

Step 6 — Add a feature (optional)
  Switch to agent mode.
  The same bug-to-test → fix → verify loop applies.
```

---

## 6. How We Measure It Worked

| Measurement | How to check |
|-------------|-------------|
| Explorer answers "where does /ping land?" with a file reference | Review CODEBASE_MAP.md — it must name `hc/api/views.py` and the ping URL pattern |
| Failing test produced before fix | `pre_fix_<slug>.txt` exists and contains `FAIL` |
| Fix does not accidentally pass before being written | `pre_fix_<slug>.txt` timestamp is earlier than the fix commit |
| Fix passes the targeted test | `post_fix_<slug>.txt` contains `OK` and `Ran 1 test` |
| No regressions | App-suite result in `REPORT_<slug>.md` is `OK` |
| Evidence report is complete | `REPORT_<slug>.md` exists and all five verification flags are marked |
| Post-edit hook fired | After editing `hc/api/views.py`, the `hc.api` suite result appears in Bob's output automatically |
| Kit is portable | Cloning a different Django repo and running `/onramp` produces a valid CODEBASE_MAP.md without editing any kit files (only the thin repo profile in `CODEBASE_MAP.md` differs) |

---

## 7. File Layout Produced by This Kit

```
.bob/
  custom_modes.yaml          ← explorer, reproducer, verifier modes
  hooks.yaml                 ← post-edit Python hook
  skills/
    map-codebase/SKILL.md
    bug-to-test/SKILL.md
    verify-change/SKILL.md
    write-evidence-report/SKILL.md
  slash_commands/
    onramp.md
    evidence.md

docs/
  onramp/
    PLAN.md                  ← this file
    CODEBASE_MAP.md          ← pre-seeded by ST-6; always present before /onramp runs
    gen_report.py            ← stdlib-only evidence report generator
    evidence/
      pre_fix_<slug>.txt
      post_fix_<slug>.txt
      diff_<slug>.txt
      REPORT_<slug>.md
```

---

## 8. Sub-Tasks for Implementation

Each sub-task is scoped so it can be handed to agent mode independently and
reviewed before the next one starts.

### ST-1  Custom Modes  `[ ] pending`
**Intent:** Create `.bob/custom_modes.yaml` with the three modes.  
**Outcomes:** `explorer`, `reproducer`, and `verifier` modes appear in Bob's
mode switcher.  
**Steps:**
1. Create `.bob/` directory.
2. Write `custom_modes.yaml` with mode entries per the designs in section 1.
3. Verify Bob loads the file (no YAML parse errors).  

**Relevant context:** Bob custom_modes schema requires `slug`, `name`,
`roleDefinition`, `groups`, and optionally `customInstructions` and
`source: project`.

---

### ST-2  Skills  `[ ] pending`
**Intent:** Create the four skill SKILL.md files.  
**Outcomes:** Each skill is loadable via `use_skill` and contains the
step-by-step instructions described in section 2.  
**Steps:**
1. Create `.bob/skills/map-codebase/SKILL.md`.
2. Create `.bob/skills/bug-to-test/SKILL.md`.
3. Create `.bob/skills/verify-change/SKILL.md`.
4. Create `.bob/skills/write-evidence-report/SKILL.md`.

**Relevant context:** Skills are Markdown files.  The `description` frontmatter
field is what the mode switcher and skill selector display.  The body is the
instruction text Bob follows when the skill is activated.

---

### ST-3  Slash Commands  `[ ] pending`
**Intent:** Create the two slash command definition files as Markdown files
under `.bob/slash_commands/` (not inlined into mode `customInstructions`).
**Outcomes:** `/onramp` and `/evidence` are available as slash commands.
**Steps:**
1. Create `.bob/slash_commands/onramp.md`.
2. Create `.bob/slash_commands/evidence.md`.

---

### ST-4  Hooks  `[ ] pending`
**Intent:** Create `.bob/hooks.yaml` with the post-edit Python test hook.
**Outcomes:** Editing any `.py` file in the repo triggers the app-level (or
full) test suite automatically.
**Steps:**
1. Write `.bob/hooks.yaml` with the `stop` event hook.
2. Verify the hook command is a valid `python manage.py test` invocation.

---

### ST-5  Evidence Script  `[ ] pending`
**Intent:** Create `docs/onramp/gen_report.py`.  
**Outcomes:** Running
`python docs/onramp/gen_report.py <slug>` produces a complete
`REPORT_<slug>.md`.  
**Steps:**
1. Create `docs/onramp/` directory.
2. Write `gen_report.py` using only stdlib (`re`, `pathlib`, `sys`,
   `textwrap`).
3. Smoke-test with synthetic fixture files to confirm parsing logic works.

---

### ST-6  CODEBASE_MAP.md Seed  `[ ] pending`
**Intent:** Pre-seed `docs/onramp/CODEBASE_MAP.md` now by manually running
the `map-codebase` skill against this repo.  The file is always present before
any `/onramp` run; it is the thin Healthchecks profile while the kit stays
generic.
**Outcomes:** `CODEBASE_MAP.md` exists and correctly answers "where does
/ping land?" with file references.
**Steps:**
1. Activate `map-codebase` skill in explorer mode.
2. Follow the skill checklist against the actual repo.
3. Write output to `docs/onramp/CODEBASE_MAP.md`.
