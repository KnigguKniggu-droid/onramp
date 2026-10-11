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
- **Raw output:** `C:\Users\ganes\hc-bob\docs\onramp\evidence/pre_fix_webhook-205.txt`

## Post-Fix Test Run
- **Result:** PASS
- **Tests run:** 1
- **Raw output:** `C:\Users\ganes\hc-bob\docs\onramp\evidence/post_fix_webhook-205.txt`

## Regression Check
- **Pre-existing failures (baseline):** 29
- **Inherited failures (still failing):** 0
- **Regressions introduced:** 0
- **Fixed pre-existing failures:** 29
- **Unchanged passes (approx):** 0


## Diff
- **File(s) changed:** hc/integrations/webhook/tests/test_notify.py
- **Raw diff:** `C:\Users\ganes\hc-bob\docs\onramp\evidence/diff_webhook-205.txt`

## Verification Flags
- [x] Test existed before fix and was FAIL
- [x] Test passes after fix
- [x] No new failures in app suite (regression check: 0)
- [ ] Diff is minimal (only the files the test implicates) — human review required
- [x] Test contains at least one assertion
