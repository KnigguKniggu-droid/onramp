# Linux reproduction, 2026-10-19

Written by the team, as an independent check (IBM Bob did not run it). It is a re-run of the webhook-205 evidence on Linux, from a fresh clone of this repository, to check the Windows results and the re-typed pre-fix artefact.

**Environment:** Linux, Python 3.13, Django 6.1.1, `pip install -r requirements.txt -r requirements-dev.txt`, SQLite test database. Each case ran in its own `git worktree`.

| Case | How it was set up | Command | Result |
|---|---|---|---|
| Pre-fix code, Bob's test | `2c7a863` (before the fix) plus `test_notify.py` from `5f16187` | `manage.py test hc.integrations.webhook.tests.test_notify.NotifyWebhookTestCase.test_webhooks_accept_http_205` | `FAIL`, `AssertionError: 3 != 1`, raised at `test_notify.py` line 555 |
| Pre-fix webhook suite | `2c7a863` unchanged | `manage.py test hc.integrations.webhook` | 47 tests, OK |
| Bob's first attempt | `5f16187` with line 161 set back to `if not (200 <= r.status_code < 300):` | `manage.py test hc.integrations.webhook` | 48 tests, `FAILED (errors=22)` |
| Bob's committed fix | `5f16187` | `manage.py test hc.integrations.webhook` | 48 tests, OK |
| Bob's committed fix | `5f16187` | `manage.py test hc.api` | 431 tests, OK |
| Upstream pin | `0968fa2` | `manage.py test --parallel 1` | 1,761 tests, OK |
| After fix and feature | `main` at `877bb35` (identical file tree to the commit used for the run) | `manage.py test --parallel 1` | 1,767 tests, OK |

## What this confirms
- The failing-first test fails on the unfixed code for the reason recorded in `pre_fix_webhook-205.txt` (same assertion, same line). The re-typed artefact matches a real run.
- Bob's first attempt causes exactly 22 errors in the webhook suite, as Bob's session records.
- The committed fix and the #1090 feature introduce no failures in the full suite. The 6 extra tests (1,767 against 1,761) are Bob's webhook test and its 5 feature tests.
- The 29 baseline failures are Windows-only: none of them fail on Linux.

## Also observed
- Running `node .bob/hooks/run-app-tests.mjs` with an `apply_diff` payload for `hc/api/transports.py` on Bob's first attempt reports `hc.api: PASS`. The hook runs only the edited file's app, so it cannot see the 22 errors in `hc.integrations.webhook`.
- `gen_report.py classify` on the published fixtures: full run, 29 inherited and 0 regressions; synthetic new failure, 1 regression. On the crashed and targeted runs, `classify_run()` returns INCONCLUSIVE, but the command prints only `NOT RUN: 29` and `REGRESSION: 0` and exits 0.
