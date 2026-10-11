# /evidence

Assemble or regenerate the evidence report for a completed fix.

**Usage:** `/evidence <slug>`

where `<slug>` is the short snake_case identifier used for the artefact files
(e.g. `ping_empty_body` for `pre_fix_ping_empty_body.txt`).

---

## Steps Bob follows when you run /evidence <slug>

### 1 — Read the profile

Read `docs/onramp/profile.json`. Extract `evidence_dir`.

### 2 — Check artefacts

Confirm these files exist in `<evidence_dir>`:
- `pre_fix_<slug>.txt`
- `post_fix_<slug>.txt`
- `diff_<slug>.txt`
- `baseline.txt`

If any are missing, tell the user which skill produces each one:
- `pre_fix_<slug>.txt` — bug-to-test skill
- `post_fix_<slug>.txt` and `diff_<slug>.txt` — verify-change skill
- `baseline.txt` — captured once by running `python .bob/gen_report.py capture-baseline`

### 3 — Run the generator

Run:
```
python .bob/gen_report.py report <slug>
```

If the script exits non-zero, print the error and stop.

### 4 — Surface the report

Read `<evidence_dir>/REPORT_<slug>.md` and print:
1. The five verification flags and whether each is checked.
2. Any `ANOMALY:` lines.
3. Diff size summary.

### 5 — Resolve anomalies

For each unresolved anomaly, tell the user which skill to run to fix it:
- Missing pre-fix failure -> re-run bug-to-test skill
- No assertions -> edit the test, re-run bug-to-test skill
- Regression -> fix the regression, re-run verify-change skill
- Diff scope too wide -> review with user, update diff_<slug>.txt manually
  or re-run verify-change after reverting unrelated changes

### 6 — Final status

If all five flags are set and no anomalies remain:
"Evidence report complete. Ready to commit in Agent mode."

If flags are missing:
"Report incomplete. See anomalies above."
