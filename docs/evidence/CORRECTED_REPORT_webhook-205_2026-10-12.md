# Corrected evidence report: webhook-205 (written by the team, 2026-10-12)

This supersedes the classification section of `docs/onramp/evidence/REPORT_webhook-205.md`. That original report is kept unchanged as historical evidence. It wrongly counted 29 tests that never ran as "fixed", because the old classifier subtracted failing-ID sets.

## What changed in the classification
| Run | Original report (old classifier) | Corrected |
|---|---|---|
| `post_fix_webhook-205.txt`, a 1-test run of `test_webhooks_accept_http_205` | 29 fixed, 0 inherited | **No verdict on the 29 baseline failures: none of them ran.** IBM Bob's corrected classifier (`gen_report.py`, ec3473d) reports the run as INCONCLUSIVE, with NOT RUN = 29. Its parser does not read this test's docstring line (a known limitation). `onramp_normalize.py` (the team) reports the run as TARGETED: valid, 1 new passing test, 1,761 baseline tests not run, 0 fixed. |
| Full verbose suite after Bob's fix and feature (1,767 tests, captured 2026-10-11 by the team) | n/a | **FULL: 29 inherited, 0 fixed, 0 regressions, 0 new failures, 6 new passing tests, 1,732 unchanged passes.** |

## Sources
All files are published with the Evidence Explorer: https://github.com/KnigguKniggu-droid/onramp-evidence

| What | Normalized data | Raw log | SHA-256 of normalized text (first 12) |
|---|---|---|---|
| Baseline at upstream 0968fa2, verbose (1,761 tests) | `data/baseline_run.json` | `fixtures/baseline_run.txt` | 301ef23d2511 |
| Full run after the fix | `data/full_run_after_fix.json` | `fixtures/full_run_after_fix.txt` | a26a5bc2f499 |
| Targeted run | `data/targeted_run.json` | `fixtures/targeted_run.txt` | c072c1ccc02a |

The classifications come from `onramp_normalize.classify`. They match the browser classifier exactly, which CI (`parity` workflow) checks on every push.

## What did not change
- The blind benchmark: sealed brief, failing test first, Bob's 1-line fix in 5f16187, and the comparison with upstream 0a9bff9.
- The conclusion that the fix introduced **no regressions**. It is supported by the full-suite run above, not by the targeted run.
