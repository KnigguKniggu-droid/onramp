---
name: map-codebase
description: >-
  Use when starting work on an unfamiliar repository. Walks through the
  project layout, URL routing, models, test conventions, and run commands,
  then writes docs/onramp/CODEBASE_MAP.md as a shared reference for the
  whole OnRamp kit.
---

# Map Codebase

Follow these steps in order. Use only read tools. Do not write anything except
the final CODEBASE_MAP.md output.

## Step 1 — Read the profile

Read `docs/onramp/profile.json`. This file contains repository-specific values:
`test_runner`, `app_root`, `apps`, `settings_module`, `base_test_class`,
`test_file_pattern`, and `venv_activate`. Use these values wherever a
framework-specific command or path is needed throughout this skill.

## Step 2 — Top-level layout

1. Run `list_files` at the repository root (non-recursive).
2. For each directory that looks like an application (listed in `profile.apps`
   or named in the project config), list its contents one level deep.
3. Note: `manage.py`, `requirements*.txt`, settings file, URL root, WSGI file.

## Step 3 — URL routing

1. Open the root URL file (e.g. `hc/urls.py`). Read it fully.
2. For each `include(...)` call, note the target module.
3. Pick one representative endpoint (prefer the simplest ping/health-check
   route). Trace it: URL pattern -> view function -> model(s) touched.
4. Record: `<URL pattern> -> <view file>:<line> -> <model> in <model file>:<line>`.

## Step 4 — Models

For each app in `profile.apps`:
1. Use `GetSymbolsOverview` on `<app>/models.py`.
2. Note the top-level model class names and their most important fields
   (do not read full bodies unless a field is ambiguous).

## Step 5 — Test conventions

1. Read `profile.base_test_class` file (e.g. `hc/test.py`) fully.
2. List the setUp fixture users/objects it creates and the custom assert helpers.
3. Open one representative test file (the one for the traced endpoint in Step 3).
4. Note: how a test class is declared, how setUp is overridden, which HTTP
   client methods are used.

## Step 6 — Run commands

From `profile.json` assemble the exact commands for this machine:
- Activate venv: `profile.venv_activate`
- Run full test suite: `profile.test_runner`
- Run one app: `profile.test_runner` + ` ` + `profile.app_root` + `.<app>`
- Run one test: `profile.test_runner` + ` <Module.Class.method>`
- Run server: derived from `manage.py` location

## Step 7 — Write CODEBASE_MAP.md

Write `docs/onramp/CODEBASE_MAP.md` with these sections:

```
# Codebase Map — <repo name>

## What This App Does
<two sentences>

## Layout
<table: directory -> purpose>

## URL -> View -> Model trace
<the trace from Step 3>

## Apps and Key Models
<per-app table>

## Test Conventions
<BaseTestCase fixtures, assert helpers, example test skeleton>

## Run Commands
<exact commands from Step 6>

## Key Files
<manage.py, settings, URL root, base test class, wsgi>
```

Every file reference must include the relative path. Every model or view
reference must include the file and the line number where the class/function
is defined.
