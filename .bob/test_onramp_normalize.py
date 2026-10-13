"""Tests for onramp_normalize.py (Claude Code). Baseline: executed {A,B,C,F1,F2}, failing {F1,F2}."""
import json
import tempfile
import unittest
from pathlib import Path

import onramp_normalize as on


def log(results: dict, ran: int | None = None, terminal: str | None = None, doc_for: str = "") -> str:
    lines = []
    for tid, st in results.items():
        name = tid.split(".")[-1]
        if tid == doc_for:
            lines.append(f"{name} (m.C.{name})\nA docstring line. ... {st}")
        else:
            lines.append(f"{name} (m.C.{name}) ... {st}")
    n = len(results) if ran is None else ran
    fails = sum(1 for s in results.values() if s in ("FAIL", "ERROR"))
    term = terminal if terminal is not None else ("OK" if not fails else f"FAILED (failures={fails})")
    out = "\n".join(lines) + "\n\n" + "-" * 70 + f"\nRan {n} tests in 0.1s\n\n{term}\n"
    return out


BASE = {"A": "ok", "B": "ok", "C": "ok", "F1": "FAIL", "F2": "ERROR"}


def run(results, **kw):
    return on.normalize(log(results, **kw))


class Classification(unittest.TestCase):
    def setUp(self):
        self.base = run(BASE)

    def test_full_run_unchanged(self):
        r = on.classify(self.base, run(BASE))
        self.assertEqual((r["scope"], len(r["inherited"]), r["fixed"], r["regression"], len(r["unchanged_pass"])), ("FULL", 2, [], [], 3))

    def test_targeted_run_never_reports_fixed(self):
        r = on.classify(self.base, run({"A": "ok"}))
        self.assertEqual(r["scope"], "TARGETED")
        self.assertEqual(r["fixed"], [])
        self.assertEqual(sorted(r["not_run"]), ["m.C.B", "m.C.C", "m.C.F1", "m.C.F2"])

    def test_new_failure_is_regression(self):
        r = on.classify(self.base, run({**BASE, "B": "FAIL"}))
        self.assertEqual(r["regression"], ["m.C.B"])

    def test_fixed_only_when_ran_and_passed(self):
        r = on.classify(self.base, run({**BASE, "F1": "ok"}))
        self.assertEqual((r["fixed"], r["inherited"]), (["m.C.F1"], ["m.C.F2"]))

    def test_empty_output_inconclusive(self):
        r = on.classify(self.base, on.normalize(""))
        self.assertFalse(r["valid"])
        self.assertEqual((r["fixed"], r["regression"]), ([], []))

    def test_crashed_run_inconclusive(self):
        text = log({"A": "ok", "B": "ok"}).split("\n\n")[0]
        self.assertFalse(on.classify(self.base, on.normalize(text))["valid"])

    def test_count_mismatch_inconclusive(self):
        self.assertFalse(run(BASE, ran=9)["valid"])

    def test_utf16_and_bom_read(self):
        with tempfile.TemporaryDirectory() as d:
            p16, p8 = Path(d, "a.txt"), Path(d, "b.txt")
            p16.write_bytes(log(BASE).encode("utf-16"))
            p8.write_bytes(b"\xef\xbb\xbf" + log(BASE).encode("utf-8"))
            self.assertTrue(on.normalize(on.read_text(p16))["valid"])
            self.assertTrue(on.normalize(on.read_text(p8))["valid"])

    def test_discovery_change_keeps_new_failure_separate(self):
        cur = run({"A": "ok", "B": "ok", "C2": "ok", "F1": "FAIL", "F3": "FAIL"})
        r = on.classify(self.base, cur)
        self.assertEqual(r["new_failure"], ["m.C.F3"])
        self.assertEqual(r["regression"], [])
        self.assertEqual(r["new_test"], ["m.C.C2"])
        self.assertEqual(sorted(r["not_run"]), ["m.C.C", "m.C.F2"])
        self.assertEqual(r["scope"], "TARGETED")

    def test_docstring_line_is_parsed(self):
        n = run({"A": "ok"}, doc_for="A")
        self.assertTrue(n["valid"], n["problems"])
        self.assertEqual(n["outcomes"], {"m.C.A": "PASS"})

    def test_unsupported_schema_rejected(self):
        bad = dict(run(BASE), schema_version="onramp.run/99")
        self.assertFalse(on.classify(self.base, bad)["valid"])

    def test_init_profile_flask_and_django(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "app").mkdir(); (root / "app" / "__init__.py").write_text("")
            (root / "tests").mkdir()
            p = on.init_profile(root)
            self.assertEqual((p["framework"], p["app_root"]), ("unittest", "app"))
            (root / "manage.py").write_text("")
            (root / "proj").mkdir(); (root / "proj" / "settings.py").write_text("")
            p = on.init_profile(root)
            self.assertEqual((p["framework"], p["settings_module"]), ("django", "proj.settings"))


class EdgeCases(unittest.TestCase):
    """R1 edge cases from the v3 directive (Claude Code)."""

    def setUp(self):
        self.base = run(BASE)

    def test_skipped_tests_are_neither_fixed_nor_regressed(self):
        cur = run({**BASE, "F1": "skipped 'needs linux'", "A": "skipped 'slow'"})
        r = on.classify(self.base, cur)
        self.assertEqual(sorted(r["skipped"]), ["m.C.A", "m.C.F1"])
        self.assertNotIn("m.C.F1", r["fixed"])

    def test_expected_failure_and_unexpected_success(self):
        n = on.normalize(log({"A": "expected failure", "B": "unexpected success"}, terminal="FAILED (unexpected successes=1)"))
        self.assertEqual(n["outcomes"], {"m.C.A": "PASS", "m.C.B": "FAIL"})

    def test_terminal_status_disagreeing_with_results_is_inconclusive(self):
        self.assertFalse(run(BASE, terminal="OK")["valid"])

    def test_warning_printed_mid_line(self):
        text = "A (m.C.A) ... C:\\x\\base.py:63: UserWarning: no static dir\n  warnings.warn(msg)\nok\n\n" + "-" * 70 + "\nRan 1 test in 0.1s\n\nOK\n"
        n = on.normalize(text)
        self.assertTrue(n["valid"], n["problems"])
        self.assertEqual(n["outcomes"], {"m.C.A": "PASS"})

    def test_timeout_output_without_summary_is_inconclusive(self):
        text = "A (m.C.A) ... ok\nB (m.C.B) ... \n*** timed out after 600s ***\n"
        r = on.classify(self.base, on.normalize(text))
        self.assertFalse(r["valid"])
        self.assertEqual((r["fixed"], r["regression"], r["not_run"]), ([], [], []))

    def test_baseline_problems_also_block_a_verdict(self):
        bad_base = on.normalize("")
        self.assertFalse(on.classify(bad_base, run(BASE))["valid"])

    def test_json_written_by_powershell_redirect_is_readable(self):
        with tempfile.TemporaryDirectory() as d:
            for enc, raw in (("utf8-bom", b"\xef\xbb\xbf" + json.dumps(self.base).encode()),
                             ("utf16", json.dumps(self.base).encode("utf-16"))):
                p = Path(d, enc + ".json")
                p.write_bytes(raw)
                self.assertEqual(on.load_run(p), self.base, enc)

    def test_crlf_and_lf_give_identical_normalization(self):
        t = log(BASE)
        self.assertEqual(on.normalize(t), on.normalize(t.replace("\n", "\r\n")))


class UnknownStatusTests(unittest.TestCase):
    def _runs(self, cur_status):
        base = {"schema_version": "onramp.run/1", "problems": [], "outcomes": {"t.a": "FAIL", "t.b": "PASS"}}
        cur = {"schema_version": "onramp.run/1", "problems": [], "outcomes": {"t.a": cur_status, "t.b": "PASS"}}
        return on.classify(base, cur)

    def test_null_outcome_is_inconclusive_not_fixed(self):
        r = self._runs(None)
        self.assertFalse(r["valid"])
        self.assertEqual(r["fixed"], [])

    def test_unknown_status_is_inconclusive_not_fixed(self):
        r = self._runs("CRASH")
        self.assertFalse(r["valid"])
        self.assertIn("unknown status", r["problems"][0])

    def test_missing_outcomes_is_inconclusive(self):
        base = {"schema_version": "onramp.run/1", "problems": [], "outcomes": {"t.a": "PASS"}}
        r = on.classify(base, {"schema_version": "onramp.run/1", "problems": []})
        self.assertFalse(r["valid"])


if __name__ == "__main__":
    unittest.main()
