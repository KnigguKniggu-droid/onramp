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


if __name__ == "__main__":
    unittest.main()
