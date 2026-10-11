# Evidence Report — webhook-205

## Summary
- **Bug:** See pre_fix_webhook-205.txt
- **Fix:** See diff_webhook-205.txt
- **Test:** `hc.integrations.webhook.tests.test_notify.NotifyWebhookTestCase.test_webhooks_accept_http_205`
- **Diff size:** 23 lines changed across 1 file(s)

## Pre-Fix Test Run
- **Result:** FAIL
- **Tests run:** 1
- **Failure reason:** AssertionError: 3 != 1
- **Raw output:** `<repo>\docs\onramp\evidence/pre_fix_webhook-205.txt`

## Post-Fix Test Run
- **Result:** PASS
- **Tests run:** 1
- **Raw output:** `<repo>\docs\onramp\evidence/post_fix_webhook-205.txt`

## Regression Check
- **Pre-existing failures (baseline):** 29
- **Inherited failures (still failing):** 0
- **Regressions introduced:** 0
- **Fixed pre-existing failures:** 29
- **Unchanged passes (approx):** 0


## Diff
- **File(s) changed:** hc/integrations/webhook/tests/test_notify.py
- **Raw diff:** `<repo>\docs\onramp\evidence/diff_webhook-205.txt`

## Verification Flags
- [x] Test existed before fix and was FAIL
- [x] Test passes after fix
- [x] No new failures in app suite (regression check: 0)
- [ ] Diff is minimal (only the files the test implicates) — human review required
- [x] Test contains at least one assertion

## Upstream Comparison (0a9bff9)

### Root cause (identical)
Both fixes agree: `HttpTransport._request` used an explicit tuple `(200, 201, 202, 204)` which excluded HTTP 205. The upstream commit title ("accept HTTP 205 responses") confirms the same diagnosis.

### Files and lines changed

| | This fix | Upstream |
|---|---|---|
| `hc/api/transports.py` | 1 line | 1 line |
| `hc/integrations/webhook/tests/test_notify.py` | +21 lines (new test) | +26 lines (new test + strengthen existing `test_webhook`→`test_it_works`) |
| `CHANGELOG.md` | not touched | +1 line |

### Semantics of the production change

**This fix:** `r.status_code not in range(200, 300)` — accepts **all** 2xx codes (200–299).

**Upstream fix:** `r.status_code not in (200, 201, 202, 204, 205)` — adds **only** 205 to the existing explicit set.

The upstream choice is conservative: it fixes the reported code and nothing more, leaving 203, 206–299 still treated as errors. This is intentional for `HttpTransport`, which is the shared base for every HTTP integration (Slack, Discord, Mattermost, PagerDuty, OpsGenie, Gotify, and ~20 others). Those integrations' APIs only return 200/201/204 on success; a 206 or 299 from them most likely signals an unexpected partial-content or non-standard response that genuinely warrants an error. The upstream author therefore preferred surgical precision over broad acceptance.

**Broader impact of this fix's wider range:** by accepting 200–299, any integration whose remote endpoint returns an unusual 2xx (e.g. Twilio 201 already accepted, but also hypothetical 206 from a proxied service) would silently succeed. For the specific bug (205 webhook), both fixes are functionally equivalent. For future robustness across all integrations, the upstream approach is safer.

### Tests added

| | Test name | Assertions |
|---|---|---|
| This fix | `test_webhooks_accept_http_205` | `call_count == 1`, `n.error == ""` |
| Upstream | `test_it_handles_http_205` | `error == ""`, `assert_called_once`, URL check |

Upstream's test also checks the request URL and uses `channel.notify` return value directly (cleaner); ours checks `Notification.objects.get()` which exercises the DB path.

