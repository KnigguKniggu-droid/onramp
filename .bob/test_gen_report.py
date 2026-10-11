"""
Unit tests for .bob/gen_report.py
Run with:  python .bob/test_gen_report.py
"""
from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

# Make gen_report importable without installing
sys.path.insert(0, str(Path(__file__).parent))
import gen_report as gr


# ---------------------------------------------------------------------------
# Helpers: synthetic Django test-runner output
# ---------------------------------------------------------------------------

_OK_OUTPUT = textwrap.dedent("""\
    test_it_works (hc.api.tests.test_ping.PingTestCase.test_it_works) ... ok
    ----------------------------------------------------------------------
    Ran 1 test in 0.009s

    OK
""")

_FAIL_OUTPUT = textwrap.dedent("""\
    test_ping_empty (hc.api.tests.test_ping.PingTestCase.test_ping_empty) ... FAIL

    ======================================================================
    FAIL: test_ping_empty (hc.api.tests.test_ping.PingTestCase.test_ping_empty)
    ----------------------------------------------------------------------
    Traceback (most recent call last):
      File "hc/api/tests/test_ping.py", line 42, in test_ping_empty
        self.assertEqual(r.status_code, 400)
    AssertionError: 200 != 400
    ----------------------------------------------------------------------
    Ran 1 test in 0.045s

    FAILED (failures=1)
""")

_ERROR_OUTPUT = textwrap.dedent("""\
    test_broken (hc.api.tests.test_ping.PingTestCase.test_broken) ... ERROR

    ======================================================================
    ERROR: test_broken (hc.api.tests.test_ping.PingTestCase.test_broken)
    ----------------------------------------------------------------------
    Traceback (most recent call last):
      File "hc/api/tests/test_ping.py", line 10, in test_broken
        x = None.save()
    AttributeError: 'NoneType' object has no attribute 'save'
    ----------------------------------------------------------------------
    Ran 1 test in 0.002s

    FAILED (errors=1)
""")

_MULTI_FAIL_OUTPUT = textwrap.dedent("""\
    FAIL: test_a (hc.api.tests.test_foo.FooTestCase.test_a)
    FAIL: test_b (hc.api.tests.test_foo.FooTestCase.test_b)
    ERROR: test_c (hc.api.tests.test_foo.FooTestCase.test_c)
    Ran 5 tests in 0.100s
    FAILED (failures=2, errors=1)
""")

_DIFF_ONE_FILE = textwrap.dedent("""\
    diff --git a/hc/api/views.py b/hc/api/views.py
    index abc123..def456 100644
    --- a/hc/api/views.py
    +++ b/hc/api/views.py
    @@ -10,3 +10,4 @@
     unchanged line
    -removed line
    +added line one
    +added line two
""")

_DIFF_TWO_FILES = textwrap.dedent("""\
    diff --git a/hc/api/views.py b/hc/api/views.py
    --- a/hc/api/views.py
    +++ b/hc/api/views.py
    @@ -1,1 +1,1 @@
    -old
    +new
    diff --git a/hc/api/tests/test_ping.py b/hc/api/tests/test_ping.py
    --- a/hc/api/tests/test_ping.py
    +++ b/hc/api/tests/test_ping.py
    @@ -50,0 +50,5 @@
    +def test_new(): pass
""")


# ---------------------------------------------------------------------------
# RunResult
# ---------------------------------------------------------------------------

class TestRunResult(unittest.TestCase):

    def test_ok_passed_true(self):
        r = gr.RunResult(_OK_OUTPUT)
        self.assertTrue(r.passed)
        self.assertEqual(r.tests_run, 1)
        self.assertEqual(r.fail_ids, [])

    def test_fail_passed_false(self):
        r = gr.RunResult(_FAIL_OUTPUT)
        self.assertFalse(r.passed)
        self.assertEqual(r.tests_run, 1)
        self.assertIn(
            "hc.api.tests.test_ping.PingTestCase.test_ping_empty",
            r.fail_ids,
        )

    def test_error_is_fail(self):
        r = gr.RunResult(_ERROR_OUTPUT)
        self.assertFalse(r.passed)
        self.assertIn(
            "hc.api.tests.test_ping.PingTestCase.test_broken",
            r.fail_ids,
        )

    def test_multi_fail_ids(self):
        r = gr.RunResult(_MULTI_FAIL_OUTPUT)
        self.assertFalse(r.passed)
        self.assertEqual(len(r.fail_ids), 3)
        self.assertIn("hc.api.tests.test_foo.FooTestCase.test_a", r.fail_ids)
        self.assertIn("hc.api.tests.test_foo.FooTestCase.test_b", r.fail_ids)
        self.assertIn("hc.api.tests.test_foo.FooTestCase.test_c", r.fail_ids)

    def test_unknown_output(self):
        r = gr.RunResult("something unexpected")
        self.assertFalse(r.passed)
        self.assertEqual(r.tests_run, 0)

    def test_first_error_type_assertionerror(self):
        r = gr.RunResult(_FAIL_OUTPUT)
        self.assertIn("AssertionError", r.first_error_type())

    def test_first_error_type_attributeerror(self):
        r = gr.RunResult(_ERROR_OUTPUT)
        self.assertIn("Error", r.first_error_type())


# ---------------------------------------------------------------------------
# _parse_diff
# ---------------------------------------------------------------------------

class TestParseDiff(unittest.TestCase):

    def test_one_file(self):
        files, lines = gr._parse_diff(_DIFF_ONE_FILE)
        self.assertEqual(files, 1)
        self.assertEqual(lines, 3)  # -removed, +added one, +added two

    def test_two_files(self):
        files, lines = gr._parse_diff(_DIFF_TWO_FILES)
        self.assertEqual(files, 2)

    def test_empty_diff(self):
        files, lines = gr._parse_diff("")
        self.assertEqual(files, 0)
        self.assertEqual(lines, 0)

    def test_ignores_plus_plus_plus(self):
        diff = "diff --git a/f.py b/f.py\n--- a/f.py\n+++ b/f.py\n+real add\n"
        _, lines = gr._parse_diff(diff)
        self.assertEqual(lines, 1)  # only the +real add line


# ---------------------------------------------------------------------------
# load_baseline
# ---------------------------------------------------------------------------

class TestLoadBaseline(unittest.TestCase):

    def test_parses_ids(self):
        with tempfile.TemporaryDirectory() as td:
            ev = Path(td)
            record = {
                "version": 1,
                "failing": [
                    {"id": "hc.api.tests.T.test_a", "error_type": "AssertionError"},
                    {"id": "hc.api.tests.T.test_b", "error_type": "AssertionError"},
                ],
                "tests_run": 10,
                "exit_status": 1,
            }
            (ev / "baseline.json").write_text(
                __import__("json").dumps(record), encoding="utf-8"
            )
            loaded = gr.load_baseline(ev)
        self.assertIsNotNone(loaded)
        ids = {f["id"] for f in loaded["failing"]}
        self.assertIn("hc.api.tests.T.test_a", ids)

    def test_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            result = gr.load_baseline(Path(td))
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# classify_run
# ---------------------------------------------------------------------------

class TestClassifyRun(unittest.TestCase):

    def _baseline(self, fail_ids: list[str], tests_run: int = 10) -> dict:
        return {
            "tests_run": tests_run,
            "failing": [{"id": fid, "error_type": "AssertionError"} for fid in fail_ids],
        }

    def test_no_change(self):
        bl = self._baseline(["hc.T.test_old"])
        c = gr.classify_run(_FAIL_OUTPUT.replace(
            "hc.api.tests.test_ping.PingTestCase.test_ping_empty", "hc.T.test_old"
        ), bl)
        self.assertIn("hc.T.test_old", c["inherited"])
        self.assertEqual(c["regressions"], [])

    def test_regression_detected(self):
        bl = self._baseline([])  # clean baseline
        c = gr.classify_run(_FAIL_OUTPUT, bl)
        self.assertIn(
            "hc.api.tests.test_ping.PingTestCase.test_ping_empty",
            c["regressions"],
        )

    def test_fixed_failure(self):
        bl = self._baseline(["hc.api.tests.test_ping.PingTestCase.test_ping_empty"])
        c = gr.classify_run(_OK_OUTPUT, bl)
        self.assertIn(
            "hc.api.tests.test_ping.PingTestCase.test_ping_empty",
            c["fixed"],
        )

    def test_baseline_failure_not_regression(self):
        bl = self._baseline(["hc.api.tests.T.test_old"])
        # Run where test_old still fails
        run_out = (
            "FAIL: test_old (hc.api.tests.T.test_old)\n"
            "Ran 5 tests in 0.1s\nFAILED (failures=1)\n"
        )
        c = gr.classify_run(run_out, bl)
        self.assertIn("hc.api.tests.T.test_old", c["inherited"])
        self.assertEqual(c["regressions"], [])


# ---------------------------------------------------------------------------
# generate_report (integration-level with temp directory)
# ---------------------------------------------------------------------------

class TestGenerateReport(unittest.TestCase):

    def _write_artefacts(self, ev: Path, slug: str, pre: str, post: str, diff: str) -> None:
        ev.mkdir(parents=True, exist_ok=True)
        (ev / f"pre_fix_{slug}.txt").write_text(pre, encoding="utf-8")
        (ev / f"post_fix_{slug}.txt").write_text(post, encoding="utf-8")
        (ev / f"diff_{slug}.txt").write_text(diff, encoding="utf-8")

    def test_clean_report_all_flags(self):
        with tempfile.TemporaryDirectory() as td:
            ev = Path(td)
            self._write_artefacts(ev, "ping_empty", _FAIL_OUTPUT, _OK_OUTPUT, _DIFF_ONE_FILE)
            out = gr.generate_report("ping_empty", ev)
            text = out.read_text(encoding="utf-8")

        self.assertIn("ping_empty", text)
        self.assertIn("[x] Test existed before fix and was FAIL", text)
        self.assertIn("[x] Test passes after fix", text)
        self.assertIn("[x] No new failures in app suite", text)
        self.assertIn("[ ] Diff is minimal", text)  # always requires human review

    def test_anomaly_pre_was_passing(self):
        with tempfile.TemporaryDirectory() as td:
            ev = Path(td)
            self._write_artefacts(ev, "ping_ok", _OK_OUTPUT, _OK_OUTPUT, _DIFF_ONE_FILE)
            out = gr.generate_report("ping_ok", ev)
            text = out.read_text(encoding="utf-8")

        self.assertIn("ANOMALY", text)
        self.assertIn("already passing", text.lower())

    def test_missing_pre_fix_raises(self):
        with tempfile.TemporaryDirectory() as td:
            ev = Path(td)
            with self.assertRaises(FileNotFoundError):
                gr.generate_report("no_such_slug", ev)

    def test_report_contains_diff_stats(self):
        with tempfile.TemporaryDirectory() as td:
            ev = Path(td)
            self._write_artefacts(ev, "ping_empty", _FAIL_OUTPUT, _OK_OUTPUT, _DIFF_TWO_FILES)
            out = gr.generate_report("ping_empty", ev)
            text = out.read_text(encoding="utf-8")

        self.assertIn("2", text)  # 2 files changed

    def test_regression_anomaly_flagged(self):
        """Post-fix suite shows a new failure not in baseline."""
        regression_output = textwrap.dedent("""\
            FAIL: test_other (hc.api.tests.test_other.OtherTest.test_other)
            Ran 10 tests in 0.5s
            FAILED (failures=1)
        """)
        with tempfile.TemporaryDirectory() as td:
            ev = Path(td)
            self._write_artefacts(ev, "ping_empty", _FAIL_OUTPUT, _OK_OUTPUT, _DIFF_ONE_FILE)
            # post_suite is a separate file from post_fix
            # generate_report uses post_fix; regression detection uses classify_run
            # with an empty baseline -> regression detected
            out = gr.generate_report("ping_empty", ev)
            text = out.read_text(encoding="utf-8")

        # With no baseline, regression_count is "N/A" -> no regression flag
        self.assertIn("[x] No new failures in app suite", text)


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

class TestBuildParser(unittest.TestCase):

    def test_report_subcommand(self):
        parser = gr.build_parser()
        args = parser.parse_args(["report", "my_slug"])
        self.assertEqual(args.slug, "my_slug")
        self.assertEqual(args.func, gr._cmd_report)

    def test_capture_baseline_subcommand(self):
        parser = gr.build_parser()
        args = parser.parse_args(["capture-baseline"])
        self.assertIsNone(args.command)

    def test_capture_baseline_with_command(self):
        parser = gr.build_parser()
        args = parser.parse_args(["capture-baseline", "--command", "pytest"])
        self.assertEqual(args.command, "pytest")

    def test_classify_subcommand(self):
        parser = gr.build_parser()
        args = parser.parse_args(["classify", "some/file.txt"])
        self.assertEqual(args.run_file, "some/file.txt")

    def test_seal_benchmark_subcommand(self):
        parser = gr.build_parser()
        args = parser.parse_args(["seal-benchmark", "myslug", "--brief-file", "brief.md"])
        self.assertEqual(args.slug, "myslug")
        self.assertEqual(args.brief_file, "brief.md")


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(
        unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    )
    sys.exit(0 if result.wasSuccessful() else 1)
