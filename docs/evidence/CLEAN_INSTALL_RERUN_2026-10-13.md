# Clean-install re-run, 2026-10-13 (the team)

Written by the team. This re-runs the quick-start path in untouched clones with the **committed** kit, after the normalizer changed that day. Local paths are omitted.

## Procedure (each repository)
1. Fresh `git clone`, then checkout of the pinned commit. Confirmed untouched: 0 changed files, no OnRamp profile present.
2. Copy the kit's `.bob/` with `git archive` from the onramp repo (committed state only).
3. `python .bob/onramp_normalize.py init-profile --write`
4. Run the suite verbosely, capturing stdout and stderr together.
5. `normalize` the log, then `classify` the run against itself.
6. **Fail-closed check:** give one baseline failure an unknown status (`CRASH`) and classify again. This must be INCONCLUSIVE, never "fixed".

## Result
| Repository | Pinned commit | First attempt (kit 658689e) | Re-run (kit a888e6f) |
|---|---|---|---|
| Healthchecks (Django) | upstream `0968fa2` | **Inconclusive**: 1,760 of 1,761 results parsed (see below) | **Valid, FULL**: 1,761 parsed, 29 inherited, 0 regressions, 1,732 unchanged |
| TaskFlow (Flask, unittest) | `a380909` | Valid, FULL: 4 tests, 1 inherited | Valid, FULL: 4 tests, 1 inherited, 3 unchanged |

- **Fail-closed check:** in both repositories the injected unknown status made the result INCONCLUSIVE, with 0 tests counted as fixed.
- **No tracked files modified:** installing the kit changed no tracked file in either repository.

## The bug the first attempt found
On a fresh Healthchecks checkout, Django printed a migration progress line with no trailing newline. One test header was appended to it:

```
Applying sessions.0001_initial...test_it_rejects_get (hc.accounts.tests...) ... <UserWarning: No directory at ...static>
ok
```

The parser expected each header at the start of a line, so it missed that test. "Ran 1761" did not match the 1,760 parsed results, so the run was reported as inconclusive. That is the intended fail-closed behaviour, but a new user would hit it.

Fix in commit a888e6f: a header may also directly follow `...`. A regression test reproduces the exact interleaving, bringing the suite to 24 tests. Bob's `gen_report.py` is unchanged.
