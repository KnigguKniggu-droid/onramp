"""
Unit tests for .bob/gen_report.py
Run with:  python .bob/test_gen_report.py
"""
from __future__ import annotations

import json
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

# Plain unittest output (no class/module in the FAIL: line)
_PLAIN_OK_OUTPUT = textwrap.dedent("""\
    .
    ----------------------------------------------------------------------
    Ran 1 test in 0.001s

    OK
""")

_PLAIN_FAIL_OUTPUT = textwrap.dedent("""\
    F
    ======================================================================
    FAIL: test_divide_by_zero (test_math.MathTestCase.test_divide_by_zero)
    ----------------------------------------------------------------------
    Traceback (most recent call last):
      File "test_math.py", line 8, in test_divide_by_zero
        self.assertEqual(divide(1, 0), 0)
    AssertionError: ZeroDivisionError raised
    ----------------------------------------------------------------------
    Ran 1 test in 0.002s

    FAILED (failures=1)
""")

# Plain unittest without class context (older pattern)
_PLAIN_FAIL_NO_CLASS = textwrap.dedent("""\
    FAIL: test_something
    AssertionError: 1 != 2
    ----------------------------------------------------------------------
    Ran 1 test in 0.001s

    FAILED (failures=1)
""")

# Plain unittest -v output: bare method name first, full dotted ID in parens
# This is the exact format produced by:
#   python -m unittest tests.test_tasks -v
# with the FAIL header line as printed to stderr.
_PLAIN_VERBOSE_FAIL_OUTPUT = textwrap.dedent("""\
    test_overdue_task_is_detected (tests.test_tasks.TaskApiTestCase.test_overdue_task_is_detected) ... FAIL

    ======================================================================
    FAIL: test_overdue_task_is_detected (tests.test_tasks.TaskApiTestCase.test_overdue_task_is_detected)
    ----------------------------------------------------------------------
    Traceback (most recent call last):
      File "tests/test_tasks.py", line 20, in test_overdue_task_is_detected
        self.assertTrue(task.is_overdue())
    AssertionError: False is not true
    ----------------------------------------------------------------------
    Ran 1 test in 0.003s

    FAILED (failures=1)
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


def _make_baseline(tests_run: int = 10, failing_ids: list[str] | None = None) -> dict:
    """Return a minimal baseline dict. IDs are dotted module paths as extracted
    by _FAIL_ID_RE: 'Module.Class.test_method' (the part in parentheses)."""
    failing = [{"id": fid, "error_type": "AssertionError"} for fid in (failing_ids or [])]
    return {
        "version": 1,
        "commit": "abc123",
        "os": "Windows",
        "python": "3.13.0",
        "command": ".venv/Scripts/python.exe manage.py test",
        "tests_run": tests_run,
        "failing": failing,
        "exit_status": 1 if failing else 0,
        "duration_s": 1.0,
        "timestamp": "2025-01-01T00:00:00+00:00",
        "output_hash": "deadbeef",
    }


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

    def test_empty_output(self):
        r = gr.RunResult("")
        self.assertFalse(r.passed)
        self.assertEqual(r.tests_run, 0)
        self.assertEqual(r.fail_ids, [])

    def test_first_error_type_assertionerror(self):
        r = gr.RunResult(_FAIL_OUTPUT)
        self.assertIn("AssertionError", r.first_error_type())

    def test_first_error_type_attributeerror(self):
        r = gr.RunResult(_ERROR_OUTPUT)
        self.assertIn("Error", r.first_error_type())

    # --- plain unittest format ---

    def test_plain_ok_passed(self):
        r = gr.RunResult(_PLAIN_OK_OUTPUT)
        self.assertTrue(r.passed)
        self.assertEqual(r.tests_run, 1)
        self.assertEqual(r.fail_ids, [])

    def test_plain_fail_detected(self):
        r = gr.RunResult(_PLAIN_FAIL_OUTPUT)
        self.assertFalse(r.passed)
        self.assertEqual(r.tests_run, 1)
        self.assertIn("test_math.MathTestCase.test_divide_by_zero", r.fail_ids)

    def test_plain_fail_no_class_detected(self):
        r = gr.RunResult(_PLAIN_FAIL_NO_CLASS)
        self.assertFalse(r.passed)
        self.assertIn("test_something", r.fail_ids)

    def test_plain_fail_error_type(self):
        r = gr.RunResult(_PLAIN_FAIL_OUTPUT)
        self.assertIn("AssertionError", r.first_error_type())

    # --- plain unittest -v (verbose) format: short name first, full ID in parens ---

    def test_plain_verbose_fail_id_extracted(self):
        r = gr.RunResult(_PLAIN_VERBOSE_FAIL_OUTPUT)
        self.assertFalse(r.passed)
        self.assertEqual(r.tests_run, 1)
        self.assertIn(
            "tests.test_tasks.TaskApiTestCase.test_overdue_task_is_detected",
            r.fail_ids,
        )

    def test_plain_verbose_fail_error_type(self):
        r = gr.RunResult(_PLAIN_VERBOSE_FAIL_OUTPUT)
        self.assertIn("AssertionError", r.first_error_type())


# ---------------------------------------------------------------------------
# capture_baseline error-type extraction (block_re fix)
# ---------------------------------------------------------------------------

class TestCaptureBaselineErrorType(unittest.TestCase):
    """Verify that the traceback block is found for the plain unittest -v format
    where fid appears inside parens, not at the start of the FAIL: line."""

    def _error_type_for(self, output: str, fid: str) -> str:
        import re as _re
        block_re = _re.compile(
            rf"(?:FAIL|ERROR): (?:\S+ \()?{_re.escape(fid)}\)?.*?(?=(?:FAIL|ERROR): |\Z)",
            _re.DOTALL,
        )
        bm = block_re.search(output)
        block_text = bm.group(0) if bm else ""
        etm = gr._ERROR_TYPE_RE.search(block_text)
        return etm.group(1) if etm else "Unknown"

    def test_verbose_format_block_found(self):
        fid = "tests.test_tasks.TaskApiTestCase.test_overdue_task_is_detected"
        et = self._error_type_for(_PLAIN_VERBOSE_FAIL_OUTPUT, fid)
        self.assertEqual(et, "AssertionError")

    def test_django_format_block_found(self):
        fid = "hc.api.tests.test_ping.PingTestCase.test_ping_empty"
        et = self._error_type_for(_FAIL_OUTPUT, fid)
        self.assertEqual(et, "AssertionError")

    def test_bare_name_not_in_parens_returns_unknown(self):
        # fid is the dotted form, but raw output only has bare name — no block match
        fid = "tests.test_tasks.TaskApiTestCase.test_overdue_task_is_detected"
        bare_output = (
            "FAIL: test_overdue_task_is_detected\n"
            "AssertionError: False is not true\n"
            "Ran 1 test in 0.003s\nFAILED (failures=1)\n"
        )
        # bare output only has short name; fid won't match — error_type is Unknown
        et = self._error_type_for(bare_output, fid)
        self.assertEqual(et, "Unknown")


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

    def test_excludes_header_lines(self):
        diff = "diff --git a/f.py b/f.py\n--- a/f.py\n+++ b/f.py\n+actual change\n"
        files, lines = gr._parse_diff(diff)
        self.assertEqual(files, 1)
        self.assertEqual(lines, 1)


# ---------------------------------------------------------------------------
# _extract_failure_reason
# ---------------------------------------------------------------------------

class TestExtractFailureReason(unittest.TestCase):

    def test_extracts_assertion_error(self):
        reason = gr._extract_failure_reason(_FAIL_OUTPUT)
        self.assertIn("AssertionError", reason)

    def test_extracts_attribute_error(self):
        reason = gr._extract_failure_reason(_ERROR_OUTPUT)
        self.assertIn("AttributeError", reason)

    def test_fallback_on_empty(self):
        reason = gr._extract_failure_reason("")
        self.assertEqual(reason, "see raw output")


# ---------------------------------------------------------------------------
# _extract_diff_files
# ---------------------------------------------------------------------------

class TestExtractDiffFiles(unittest.TestCase):

    def test_one_file(self):
        files = gr._extract_diff_files(_DIFF_ONE_FILE)
        self.assertEqual(files, ["hc/api/views.py"])

    def test_two_files(self):
        files = gr._extract_diff_files(_DIFF_TWO_FILES)
        self.assertEqual(set(files), {"hc/api/views.py", "hc/api/tests/test_ping.py"})

    def test_empty_diff(self):
        self.assertEqual(gr._extract_diff_files(""), [])


# ---------------------------------------------------------------------------
# load_baseline
# ---------------------------------------------------------------------------

class TestLoadBaseline(unittest.TestCase):

    def test_parses_ids(self):
        with tempfile.TemporaryDirectory() as td:
            ev = Path(td)
            record = _make_baseline(
                tests_run=5,
                failing_ids=["hc.api.tests.T.test_a",
                              "hc.api.tests.T.test_b"],
            )
            (ev / "baseline.json").write_text(json.dumps(record), encoding="utf-8")
            loaded = gr.load_baseline(ev)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["tests_run"], 5)
        ids = {f["id"] for f in loaded["failing"]}
        self.assertIn("hc.api.tests.T.test_a", ids)

    def test_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            result = gr.load_baseline(Path(td))
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# classify_run
# Baseline IDs are dotted paths extracted by _FAIL_ID_RE, e.g.:
#   "hc.api.tests.T.test_method"  (the text inside the parentheses)
# ---------------------------------------------------------------------------

class TestClassifyRun(unittest.TestCase):

    def test_inherited_failure(self):
        baseline = _make_baseline(
            tests_run=10,
            failing_ids=["hc.api.tests.T.test_a"],
        )
        run_output = (
            "FAIL: test_a (hc.api.tests.T.test_a)\n"
            "Ran 10 tests\nFAILED (failures=1)\n"
        )
        c = gr.classify_run(run_output, baseline)
        self.assertIn("hc.api.tests.T.test_a", c["inherited"])
        self.assertEqual(c["regressions"], [])
        self.assertEqual(c["summary"][gr.CLASSIFICATION_INHERITED], 1)

    def test_regression_detected(self):
        baseline = _make_baseline(tests_run=10, failing_ids=[])
        run_output = (
            "FAIL: test_new (hc.api.tests.T.test_new)\n"
            "Ran 10 tests\nFAILED (failures=1)\n"
        )
        c = gr.classify_run(run_output, baseline)
        self.assertIn("hc.api.tests.T.test_new", c["regressions"])
        self.assertEqual(c["summary"][gr.CLASSIFICATION_REGRESSION], 1)

    def test_fixed_failure(self):
        baseline = _make_baseline(
            tests_run=10,
            failing_ids=["hc.api.tests.T.test_old"],
        )
        c = gr.classify_run(_OK_OUTPUT, baseline)
        self.assertIn("hc.api.tests.T.test_old", c["fixed"])
        self.assertEqual(c["inherited"], [])
        self.assertEqual(c["regressions"], [])
        self.assertEqual(c["summary"][gr.CLASSIFICATION_FIXED], 1)

    def test_not_run(self):
        failing_id = "hc.api.tests.T.test_absent"
        baseline = _make_baseline(tests_run=10, failing_ids=[failing_id])
        # Run output does not mention the absent test at all
        run_output = "Ran 5 tests in 0.500s\n\nOK\n"
        c = gr.classify_run(run_output, baseline)
        self.assertIn(failing_id, c["not_run"])
        self.assertEqual(c["summary"][gr.CLASSIFICATION_NOT_RUN], 1)

    def test_baseline_failure_not_regression(self):
        baseline = _make_baseline(
            tests_run=10,
            failing_ids=["hc.api.tests.T.test_old"],
        )
        run_out = (
            "FAIL: test_old (hc.api.tests.T.test_old)\n"
            "Ran 5 tests in 0.1s\nFAILED (failures=1)\n"
        )
        c = gr.classify_run(run_out, baseline)
        self.assertIn("hc.api.tests.T.test_old", c["inherited"])
        self.assertEqual(c["regressions"], [])

    def test_mixed_classification(self):
        baseline = _make_baseline(
            tests_run=20,
            failing_ids=[
                "M.C.test_inherited",
                "M.C.test_fixed",
            ],
        )
        run_output = textwrap.dedent("""\
            FAIL: test_inherited (M.C.test_inherited)
            FAIL: test_regression (M.C.test_regression)
            Ran 20 tests in 2.000s
            FAILED (failures=2)
        """)
        c = gr.classify_run(run_output, baseline)
        self.assertIn("M.C.test_inherited", c["inherited"])
        self.assertIn("M.C.test_regression", c["regressions"])
        self.assertIn("M.C.test_fixed", c["fixed"])


# ---------------------------------------------------------------------------
# generate_report (integration-level with temp directory)
# ---------------------------------------------------------------------------

class TestGenerateReport(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ev_dir = Path(self.tmp.name)
        self.slug = "ping_empty"

    def tearDown(self):
        self.tmp.cleanup()

    def _write_fixtures(self, pre=None, post=None, diff=None, baseline=None):
        (self.ev_dir / f"pre_fix_{self.slug}.txt").write_text(
            pre if pre is not None else _FAIL_OUTPUT, encoding="utf-8"
        )
        (self.ev_dir / f"post_fix_{self.slug}.txt").write_text(
            post if post is not None else _OK_OUTPUT, encoding="utf-8"
        )
        (self.ev_dir / f"diff_{self.slug}.txt").write_text(
            diff if diff is not None else _DIFF_ONE_FILE, encoding="utf-8"
        )
        if baseline is not None:
            (self.ev_dir / "baseline.json").write_text(
                json.dumps(baseline), encoding="utf-8"
            )

    def test_clean_report_all_flags(self):
        self._write_fixtures()
        out = gr.generate_report(self.slug, self.ev_dir)
        text = out.read_text(encoding="utf-8")
        self.assertIn(self.slug, text)
        self.assertIn("[x] Test existed before fix and was FAIL", text)
        self.assertIn("[x] Test passes after fix", text)
        self.assertIn("[x] No new failures in app suite", text)
        self.assertIn("[ ] Diff is minimal", text)

    def test_pre_fail_flag_set(self):
        self._write_fixtures()
        text = gr.generate_report(self.slug, self.ev_dir).read_text(encoding="utf-8")
        self.assertIn("[x] Test existed before fix and was FAIL", text)

    def test_post_pass_flag_set(self):
        self._write_fixtures()
        text = gr.generate_report(self.slug, self.ev_dir).read_text(encoding="utf-8")
        self.assertIn("[x] Test passes after fix", text)

    def test_anomaly_pre_was_passing(self):
        self._write_fixtures(pre=_OK_OUTPUT)
        text = gr.generate_report(self.slug, self.ev_dir).read_text(encoding="utf-8")
        self.assertIn("ANOMALY", text)
        self.assertIn("[ ] Test existed before fix", text)

    def test_diff_minimal_always_unchecked(self):
        self._write_fixtures()
        text = gr.generate_report(self.slug, self.ev_dir).read_text(encoding="utf-8")
        self.assertIn("[ ] Diff is minimal", text)

    def test_regression_flag_clear_when_no_baseline(self):
        self._write_fixtures()  # no baseline written
        text = gr.generate_report(self.slug, self.ev_dir).read_text(encoding="utf-8")
        # No baseline → N/A → treated as no regression
        self.assertIn("[x] No new failures in app suite", text)

    def test_regression_detected_with_baseline(self):
        baseline = _make_baseline(tests_run=10, failing_ids=[])
        self._write_fixtures(post=_FAIL_OUTPUT, baseline=baseline)
        text = gr.generate_report(self.slug, self.ev_dir).read_text(encoding="utf-8")
        self.assertIn("ANOMALY: Regression", text)
        self.assertIn("[ ] No new failures", text)

    def test_missing_pre_fix_raises(self):
        (self.ev_dir / f"post_fix_{self.slug}.txt").write_text(_OK_OUTPUT, encoding="utf-8")
        (self.ev_dir / f"diff_{self.slug}.txt").write_text(_DIFF_ONE_FILE, encoding="utf-8")
        with self.assertRaises(FileNotFoundError):
            gr.generate_report(self.slug, self.ev_dir)

    def test_diff_file_list_in_report(self):
        self._write_fixtures()
        text = gr.generate_report(self.slug, self.ev_dir).read_text(encoding="utf-8")
        self.assertIn("hc/api/views.py", text)

    def test_report_contains_diff_stats(self):
        self._write_fixtures(diff=_DIFF_TWO_FILES)
        text = gr.generate_report(self.slug, self.ev_dir).read_text(encoding="utf-8")
        self.assertIn("2", text)  # 2 files changed


# ---------------------------------------------------------------------------
# seal_benchmark / attach_patch
# ---------------------------------------------------------------------------

class TestBenchmark(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ev_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_seal_creates_file(self):
        brief = self.ev_dir / "brief.txt"
        brief.write_text("Bug: ping returns 200 on empty body.\n", encoding="utf-8")
        record = gr.seal_benchmark(
            slug="test_seal",
            brief_file=brief,
            evidence_dir=self.ev_dir,
            cwd=Path("."),
            allowed="source code",
            withheld="reference patch",
        )
        out = self.ev_dir / "benchmark_test_seal.json"
        self.assertTrue(out.exists())
        self.assertEqual(record["slug"], "test_seal")
        self.assertFalse(record["patch_attached"])
        self.assertEqual(len(record["brief_sha256"]), 64)

    def test_attach_patch_updates_record(self):
        brief = self.ev_dir / "brief.txt"
        brief.write_text("Bug brief.\n", encoding="utf-8")
        gr.seal_benchmark(
            slug="test_attach",
            brief_file=brief,
            evidence_dir=self.ev_dir,
            cwd=Path("."),
            allowed="",
            withheld="",
        )
        patch_file = self.ev_dir / "my.patch"
        patch_file.write_text(_DIFF_ONE_FILE, encoding="utf-8")
        updated = gr.attach_patch(
            slug="test_attach",
            patch_file=patch_file,
            evidence_dir=self.ev_dir,
        )
        self.assertTrue(updated["patch_attached"])
        self.assertIsNotNone(updated["patch_stats"])
        self.assertEqual(updated["patch_stats"]["files_changed"], 1)

    def test_attach_patch_missing_benchmark_raises(self):
        patch_file = self.ev_dir / "p.patch"
        patch_file.write_text(_DIFF_ONE_FILE, encoding="utf-8")
        with self.assertRaises(FileNotFoundError):
            gr.attach_patch("nonexistent", patch_file, self.ev_dir)


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
