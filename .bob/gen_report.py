"""
OnRamp evidence-report generator and baseline manager.
Stdlib only.  No third-party dependencies.

Sub-commands
------------
  report <slug>
      Read pre_fix_<slug>.txt, post_fix_<slug>.txt, diff_<slug>.txt from the
      evidence directory and write REPORT_<slug>.md.

  capture-baseline [--command CMD]
      Run the test suite, record results as JSON, write evidence/baseline.json.

  classify <slug>
      Compare a run output file against the baseline and print a classification
      table (REGRESSION / INHERITED FAILURE / FIXED / UNCHANGED PASS / NOT RUN).

  seal-benchmark <slug> --brief-file PATH [--allowed INFO] [--withheld INFO]
      Record a blind-benchmark envelope before work starts.
      Writes evidence/benchmark_<slug>.json.

  attach-patch <slug> --patch-file PATH
      Attach a reference patch to an existing benchmark record after the fix
      is committed.  Adds patch diff stats to the benchmark JSON.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent          # .bob/
REPO_ROOT = SCRIPT_DIR.parent               # repo root
PROFILE_PATH = REPO_ROOT / "docs" / "onramp" / "profile.json"
EVIDENCE_DIR_DEFAULT = REPO_ROOT / "docs" / "onramp" / "evidence"


def _load_profile() -> dict[str, Any]:
    try:
        return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def _evidence_dir(profile: dict[str, Any]) -> Path:
    raw = profile.get("evidence_dir", "docs/onramp/evidence")
    p = Path(raw)
    return p if p.is_absolute() else REPO_ROOT / p


# ---------------------------------------------------------------------------
# Test-output parser (Django and plain unittest)
#
# Both emit the same "Ran N test(s)" line and "OK" / "FAILED" summary.
# Failure/error lines may be:
#   Django:          FAIL: test_foo (pkg.Module.test_foo)
#   plain unittest:  FAIL: test_foo
# We parse both formats.
# ---------------------------------------------------------------------------

_RESULT_RE = re.compile(r"^(OK|FAIL(?:ED)?)", re.MULTILINE)
_RAN_RE = re.compile(r"Ran (\d+) tests?")
# Captures:  group(1) = bare token,  group(2) = dotted ID inside parens (optional)
_FAIL_ID_RE = re.compile(
    r"^(?:FAIL|ERROR): (\S+)(?: \((\S+)\))?",
    re.MULTILINE,
)
_ERROR_TYPE_RE = re.compile(
    r"(AssertionError|AttributeError|TypeError|ValueError|Error)[:\s]"
)
_FAILURES_SUMMARY_RE = re.compile(r"FAILED \((?:failures=(\d+))?,?\s*(?:errors=(\d+))?\)")


def _parse_fail_ids(raw: str) -> list[str]:
    """Return fully-qualified test IDs from runner output.

    Django:         FAIL: test_foo (pkg.Module.test_foo)  -> "pkg.Module.test_foo"
    plain unittest: FAIL: test_foo                        -> "test_foo"
    """
    ids: list[str] = []
    for m in _FAIL_ID_RE.finditer(raw):
        ids.append(m.group(2) if m.group(2) else m.group(1))
    return ids


class RunResult:
    """Parsed result of a test runner output (Django or plain unittest)."""

    def __init__(self, raw: str) -> None:
        self.raw = raw
        m = _RAN_RE.search(raw)
        self.tests_run: int = int(m.group(1)) if m else 0
        rm = _RESULT_RE.search(raw)
        self.passed: bool = bool(rm and rm.group(1) == "OK")
        self.fail_ids: list[str] = _parse_fail_ids(raw)
        self._raw_upper = raw.upper()

    def first_error_type(self) -> str:
        m = _ERROR_TYPE_RE.search(self.raw)
        return m.group(1) if m else "Unknown"

    def summary_line(self) -> str:
        lines = [l for l in self.raw.splitlines() if l.strip()]
        return lines[-1] if lines else ""


# ---------------------------------------------------------------------------
# Diff parser
# ---------------------------------------------------------------------------

def _parse_diff(diff_text: str) -> tuple[int, int]:
    """Return (files_changed, lines_changed) from a unified diff."""
    file_count = len(re.findall(r"^diff --git", diff_text, re.MULTILINE))
    line_count = sum(
        1
        for line in diff_text.splitlines()
        if line.startswith(("+", "-"))
        and not line.startswith(("+++", "---"))
    )
    return file_count, line_count


# ---------------------------------------------------------------------------
# Baseline  (evidence/baseline.json)
# ---------------------------------------------------------------------------

BASELINE_VERSION = 1


def _git_commit(cwd: Path) -> str:
    # Try common git locations, then fall back to PATH
    git_candidates = [
        "git",
        r"C:\Program Files\Git\bin\git.exe",
        r"C:\Program Files (x86)\Git\bin\git.exe",
    ]
    for git in git_candidates:
        try:
            r = subprocess.run(
                [git, "rev-parse", "HEAD"],
                capture_output=True, text=True, cwd=str(cwd), timeout=10,
            )
            if r.returncode == 0:
                return r.stdout.strip()
        except (FileNotFoundError, OSError):
            continue
    return "unknown"


def capture_baseline(
    command: str | None,
    evidence_dir: Path,
    cwd: Path,
    profile: dict[str, Any],
) -> dict[str, Any]:
    """Run the test suite, parse output, write baseline.json, return record."""
    if command is None:
        command = profile.get("test_runner", "python manage.py test")

    evidence_dir.mkdir(parents=True, exist_ok=True)
    commit = _git_commit(cwd)

    print(f"[baseline] running: {command}", flush=True)
    t0 = datetime.now(timezone.utc)
    proc = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        cwd=str(cwd),
        timeout=600,
    )
    t1 = datetime.now(timezone.utc)
    output = proc.stdout + proc.stderr
    duration_s = (t1 - t0).total_seconds()

    result = RunResult(output)
    output_hash = hashlib.sha256(output.encode()).hexdigest()

    # Parse per-test failure details
    failing: list[dict[str, str]] = []
    for fid in result.fail_ids:
        # Try to find the error type from the traceback block for this test.
        # The FAIL/ERROR header may be in Django style:
        #   FAIL: test_foo (pkg.Module.test_foo)
        # or plain unittest -v style (same format), or bare:
        #   FAIL: test_foo
        # fid is the dotted form (pkg.Module.test_foo); match either position.
        block_re = re.compile(
            rf"(?:FAIL|ERROR): (?:\S+ \()?{re.escape(fid)}\)?.*?(?=(?:FAIL|ERROR): |\Z)",
            re.DOTALL,
        )
        bm = block_re.search(output)
        block_text = bm.group(0) if bm else ""
        etm = _ERROR_TYPE_RE.search(block_text)
        error_type = etm.group(1) if etm else "Unknown"
        failing.append({"id": fid, "error_type": error_type})

    record: dict[str, Any] = {
        "version": BASELINE_VERSION,
        "commit": commit,
        "os": platform.system(),
        "python": sys.version,
        "command": command,
        "tests_run": result.tests_run,
        "failing": failing,
        "exit_status": proc.returncode,
        "duration_s": round(duration_s, 3),
        "timestamp": t0.isoformat(),
        "output_hash": output_hash,
    }

    baseline_path = evidence_dir / "baseline.json"
    baseline_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"[baseline] wrote {baseline_path}", flush=True)
    print(
        f"[baseline] tests_run={result.tests_run}  "
        f"failing={len(failing)}  exit={proc.returncode}",
        flush=True,
    )

    # Also print the counts by category
    _print_baseline_counts(record)
    return record


def _print_baseline_counts(record: dict[str, Any]) -> None:
    failing = record.get("failing", [])
    total = record.get("tests_run", 0)
    n_fail = len(failing)
    n_pass = total - n_fail
    print(
        f"\n[baseline] Baseline counts:\n"
        f"  Total tests run : {total}\n"
        f"  Passing         : {n_pass}\n"
        f"  Pre-existing failures: {n_fail}\n"
        f"    breakdown:"
    )
    by_type: dict[str, int] = {}
    for f in failing:
        by_type[f["error_type"]] = by_type.get(f["error_type"], 0) + 1
    for etype, count in sorted(by_type.items()):
        print(f"      {etype}: {count}")


def load_baseline(evidence_dir: Path) -> dict[str, Any] | None:
    path = evidence_dir / "baseline.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Run classification
# ---------------------------------------------------------------------------

CLASSIFICATION_INHERITED = "INHERITED FAILURE"
CLASSIFICATION_REGRESSION = "REGRESSION"
CLASSIFICATION_FIXED = "FIXED PRE-EXISTING FAILURE"
CLASSIFICATION_PASS = "UNCHANGED PASS"
CLASSIFICATION_NOT_RUN = "NOT RUN"


def classify_run(
    run_output: str,
    baseline: dict[str, Any],
) -> dict[str, Any]:
    """
    Compare a test-run output against the baseline record.

    Returns a dict with keys:
      - inherited:  list of test IDs that failed before and still fail
      - regressions: list of test IDs that passed before and now fail
      - fixed:       list of test IDs that failed before and now pass
      - unchanged_pass: count of tests that passed before and still pass
      - not_run:     list of baseline test IDs that did not appear in this run
      - summary: dict of counts
    """
    baseline_failing_ids: set[str] = {f["id"] for f in baseline.get("failing", [])}
    run_result = RunResult(run_output)
    run_failing_ids: set[str] = set(run_result.fail_ids)

    inherited = sorted(baseline_failing_ids & run_failing_ids)
    regressions = sorted(run_failing_ids - baseline_failing_ids)
    fixed = sorted(baseline_failing_ids - run_failing_ids)

    baseline_total = baseline.get("tests_run", 0)
    baseline_pass_count = baseline_total - len(baseline_failing_ids)
    run_pass_count = run_result.tests_run - len(run_failing_ids)
    # For unchanged_pass we use the intersection of passing tests.
    # Since we don't have per-test pass IDs (only fail IDs), we approximate:
    # unchanged_pass ≈ min passing count minus newly fixed tests
    unchanged_pass = max(0, min(baseline_pass_count, run_pass_count) - len(fixed))

    # not_run: baseline failing tests that did not appear at all in output
    not_run: list[str] = []
    for fid in baseline_failing_ids:
        # If a test ID does not appear anywhere in the output it was not run
        if fid not in run_output:
            not_run.append(fid)

    result = {
        "inherited": inherited,
        "regressions": regressions,
        "fixed": fixed,
        "unchanged_pass": unchanged_pass,
        "not_run": sorted(not_run),
        "summary": {
            CLASSIFICATION_INHERITED: len(inherited),
            CLASSIFICATION_REGRESSION: len(regressions),
            CLASSIFICATION_FIXED: len(fixed),
            CLASSIFICATION_PASS: unchanged_pass,
            CLASSIFICATION_NOT_RUN: len(not_run),
        },
    }
    return result


# ---------------------------------------------------------------------------
# Blind benchmark support
# ---------------------------------------------------------------------------

def seal_benchmark(
    slug: str,
    brief_file: Path,
    evidence_dir: Path,
    cwd: Path,
    allowed: str,
    withheld: str,
) -> dict[str, Any]:
    """
    Seal a blind benchmark before work starts.
    Records: baseline commit, SHA-256 of the bug brief, allowed/withheld info,
    and the seal time.
    Writes evidence/benchmark_<slug>.json.
    """
    brief_bytes = brief_file.read_bytes()
    brief_hash = hashlib.sha256(brief_bytes).hexdigest()

    commit = _git_commit(cwd)
    record: dict[str, Any] = {
        "slug": slug,
        "sealed_at": datetime.now(timezone.utc).isoformat(),
        "baseline_commit": commit,
        "brief_sha256": brief_hash,
        "allowed_information": allowed,
        "withheld_information": withheld,
        "patch_attached": False,
        "patch_stats": None,
    }

    evidence_dir.mkdir(parents=True, exist_ok=True)
    out = evidence_dir / f"benchmark_{slug}.json"
    out.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"[benchmark] sealed → {out}", flush=True)
    return record


def attach_patch(
    slug: str,
    patch_file: Path,
    evidence_dir: Path,
) -> dict[str, Any]:
    """
    Attach a reference patch to an existing benchmark record after the fix
    is committed.  Reads the patch, computes diff stats, updates the JSON.
    """
    bench_path = evidence_dir / f"benchmark_{slug}.json"
    if not bench_path.exists():
        raise FileNotFoundError(f"Benchmark record not found: {bench_path}")

    record: dict[str, Any] = json.loads(bench_path.read_text(encoding="utf-8"))
    patch_text = patch_file.read_text(encoding="utf-8")
    files_changed, lines_changed = _parse_diff(patch_text)

    # Count test files added/modified
    test_files = [
        line[len("diff --git a/"):].split()[0]
        for line in patch_text.splitlines()
        if re.match(r"diff --git a/.*(test_|_test\.py)", line)
    ]

    record["patch_attached"] = True
    record["patch_stats"] = {
        "files_changed": files_changed,
        "lines_changed": lines_changed,
        "test_files": test_files,
        "tests_added": len(test_files),
    }
    bench_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"[benchmark] patch attached → {bench_path}", flush=True)
    return record


# ---------------------------------------------------------------------------
# Report generator
# ---------------------------------------------------------------------------

_REPORT_TEMPLATE = """\
# Evidence Report — {slug}

## Summary
- **Bug:** {bug_summary}
- **Fix:** {fix_summary}
- **Test:** `{test_name}`
- **Diff size:** {diff_lines} lines changed across {diff_files} file(s)

## Pre-Fix Test Run
- **Result:** {pre_result}
- **Tests run:** {pre_tests_run}
- **Failure reason:** {failure_reason}
- **Raw output:** `{evidence_dir}/pre_fix_{slug}.txt`

## Post-Fix Test Run
- **Result:** {post_result}
- **Tests run:** {post_tests_run}
- **Raw output:** `{evidence_dir}/post_fix_{slug}.txt`

## Regression Check
- **Pre-existing failures (baseline):** {baseline_fail_count}
- **Inherited failures (still failing):** {inherited_count}
- **Regressions introduced:** {regression_count}
- **Fixed pre-existing failures:** {fixed_count}
- **Unchanged passes (approx):** {unchanged_pass}

{anomalies_section}
## Diff
- **File(s) changed:** {diff_file_list}
- **Raw diff:** `{evidence_dir}/diff_{slug}.txt`

## Verification Flags
- [{flag_pre_fail}] Test existed before fix and was FAIL
- [{flag_post_pass}] Test passes after fix
- [{flag_no_regression}] No new failures in app suite (regression check: {regression_count})
- [ ] Diff is minimal (only the files the test implicates) — human review required
- [{flag_has_assertion}] Test contains at least one assertion
"""


def _extract_test_name(run_result: RunResult) -> str:
    if run_result.fail_ids:
        return run_result.fail_ids[0]
    # Try OK path: "test_<name> (<Module>) ... ok"
    m = re.search(r"(\w+) \((\S+)\) \.\.\. ok", run_result.raw)
    if m:
        return f"{m.group(2)}.{m.group(1)}"
    return "unknown"


def _extract_failure_reason(raw: str) -> str:
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith(("AssertionError:", "Error:", "AttributeError:", "TypeError:")):
            return stripped[:200]
    # Fall back to first non-empty line after "---" separator
    in_block = False
    for line in raw.splitlines():
        if line.startswith("---"):
            in_block = True
            continue
        if in_block and line.strip():
            return line.strip()[:200]
    return "see raw output"


def _extract_diff_files(diff_text: str) -> list[str]:
    files: list[str] = []
    for line in diff_text.splitlines():
        m = re.match(r"diff --git a/(\S+)", line)
        if m:
            files.append(m.group(1))
    return files


def generate_report(slug: str, evidence_dir: Path) -> Path:
    """
    Read pre/post fix and diff artefacts, compare against baseline, write report.
    Returns the path to the written report file.
    """
    pre_path = evidence_dir / f"pre_fix_{slug}.txt"
    post_path = evidence_dir / f"post_fix_{slug}.txt"
    diff_path = evidence_dir / f"diff_{slug}.txt"

    if not pre_path.exists():
        raise FileNotFoundError(f"Missing: {pre_path}")
    if not post_path.exists():
        raise FileNotFoundError(f"Missing: {post_path}")
    if not diff_path.exists():
        raise FileNotFoundError(f"Missing: {diff_path}")

    pre_text = pre_path.read_text(encoding="utf-8")
    post_text = post_path.read_text(encoding="utf-8")
    diff_text = diff_path.read_text(encoding="utf-8")

    pre_result = RunResult(pre_text)
    post_result = RunResult(post_text)

    diff_files, diff_lines = _parse_diff(diff_text)
    diff_file_list_str = ", ".join(_extract_diff_files(diff_text)) or "(none)"

    test_name = _extract_test_name(pre_result) or _extract_test_name(post_result)
    failure_reason = _extract_failure_reason(pre_text)

    # Baseline comparison
    baseline = load_baseline(evidence_dir)
    classification = classify_run(post_text, baseline) if baseline else None

    baseline_fail_count = len(baseline.get("failing", [])) if baseline else "N/A"
    if classification:
        inherited_count = len(classification["inherited"])
        regression_count = len(classification["regressions"])
        fixed_count = len(classification["fixed"])
        unchanged_pass = classification["unchanged_pass"]
    else:
        inherited_count = regression_count = fixed_count = unchanged_pass = "N/A"

    # Anomaly detection
    anomalies: list[str] = []
    if pre_result.passed:
        anomalies.append("ANOMALY: Test was already passing before fix — bug may not be reproduced.")
    if regression_count not in ("N/A", 0):
        anomalies.append(
            f"ANOMALY: Regression detected — {regression_count} new failure(s) in post-fix run."
        )
    # Check for assertion keywords in pre_fix text (heuristic)
    has_assertion = bool(
        re.search(r"\b(assertEqual|assertIn|assertRaises|assertTrue|assertFalse|assert)\b", pre_text)
    )
    if not has_assertion:
        anomalies.append("ANOMALY: No assertions detected in test body — test may pass vacuously.")

    anomalies_section = ""
    if anomalies:
        anomalies_section = "## Anomalies\n" + "\n".join(f"- {a}" for a in anomalies) + "\n\n"

    # Verification flags
    flag_pre_fail = "x" if not pre_result.passed else " "
    flag_post_pass = "x" if post_result.passed else " "
    flag_no_regression = "x" if regression_count in ("N/A", 0) else " "
    flag_has_assertion = "x" if has_assertion else " "

    report_text = _REPORT_TEMPLATE.format(
        slug=slug,
        bug_summary=f"See pre_fix_{slug}.txt",
        fix_summary=f"See diff_{slug}.txt",
        test_name=test_name,
        diff_lines=diff_lines,
        diff_files=diff_files,
        pre_result="FAIL" if not pre_result.passed else "PASS (unexpected — see anomalies)",
        pre_tests_run=pre_result.tests_run,
        failure_reason=failure_reason,
        post_result="PASS" if post_result.passed else "FAIL",
        post_tests_run=post_result.tests_run,
        baseline_fail_count=baseline_fail_count,
        inherited_count=inherited_count,
        regression_count=regression_count,
        fixed_count=fixed_count,
        unchanged_pass=unchanged_pass,
        anomalies_section=anomalies_section,
        diff_file_list=diff_file_list_str,
        evidence_dir=str(evidence_dir),
        flag_pre_fail=flag_pre_fail,
        flag_post_pass=flag_post_pass,
        flag_no_regression=flag_no_regression,
        flag_has_assertion=flag_has_assertion,
    )

    out_path = evidence_dir / f"REPORT_{slug}.md"
    out_path.write_text(report_text, encoding="utf-8")
    print(f"[gen_report] wrote {out_path}", flush=True)
    return out_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_report(args: argparse.Namespace) -> int:
    profile = _load_profile()
    ev_dir = _evidence_dir(profile)
    try:
        out = generate_report(args.slug, ev_dir)
        print(f"Report: {out}")
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


def _cmd_capture_baseline(args: argparse.Namespace) -> int:
    profile = _load_profile()
    ev_dir = _evidence_dir(profile)
    capture_baseline(
        command=getattr(args, "command", None),
        evidence_dir=ev_dir,
        cwd=REPO_ROOT,
        profile=profile,
    )
    return 0


def _cmd_classify(args: argparse.Namespace) -> int:
    profile = _load_profile()
    ev_dir = _evidence_dir(profile)
    baseline = load_baseline(ev_dir)
    if baseline is None:
        print("ERROR: no baseline.json found. Run capture-baseline first.", file=sys.stderr)
        return 1
    run_output_path = Path(args.run_file)
    if not run_output_path.exists():
        print(f"ERROR: {run_output_path} not found", file=sys.stderr)
        return 1
    run_output = run_output_path.read_text(encoding="utf-8")
    c = classify_run(run_output, baseline)
    print("\nClassification summary")
    print("======================")
    for label, count in c["summary"].items():
        print(f"  {label:<30}: {count}")
    if c["regressions"]:
        print("\nRegressions:")
        for tid in c["regressions"]:
            print(f"  REGRESSION: {tid}")
    if c["fixed"]:
        print("\nFixed pre-existing failures:")
        for tid in c["fixed"]:
            print(f"  FIXED: {tid}")
    return 0


def _cmd_seal_benchmark(args: argparse.Namespace) -> int:
    profile = _load_profile()
    ev_dir = _evidence_dir(profile)
    brief_path = Path(args.brief_file)
    if not brief_path.exists():
        print(f"ERROR: {brief_path} not found", file=sys.stderr)
        return 1
    seal_benchmark(
        slug=args.slug,
        brief_file=brief_path,
        evidence_dir=ev_dir,
        cwd=REPO_ROOT,
        allowed=getattr(args, "allowed", ""),
        withheld=getattr(args, "withheld", ""),
    )
    return 0


def _cmd_attach_patch(args: argparse.Namespace) -> int:
    profile = _load_profile()
    ev_dir = _evidence_dir(profile)
    patch_path = Path(args.patch_file)
    if not patch_path.exists():
        print(f"ERROR: {patch_path} not found", file=sys.stderr)
        return 1
    try:
        attach_patch(
            slug=args.slug,
            patch_file=patch_path,
            evidence_dir=ev_dir,
        )
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gen_report.py",
        description="OnRamp evidence-report generator and baseline manager.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # report
    p_report = sub.add_parser("report", help="Generate REPORT_<slug>.md")
    p_report.add_argument("slug", help="Bug slug (e.g. ping_empty_body)")
    p_report.set_defaults(func=_cmd_report)

    # capture-baseline
    p_cap = sub.add_parser("capture-baseline", help="Run suite and save baseline.json")
    p_cap.add_argument("--command", default=None, help="Override test command")
    p_cap.set_defaults(func=_cmd_capture_baseline)

    # classify
    p_cls = sub.add_parser("classify", help="Classify a run output against baseline")
    p_cls.add_argument("run_file", help="Path to the test run output file")
    p_cls.set_defaults(func=_cmd_classify)

    # seal-benchmark
    p_seal = sub.add_parser("seal-benchmark", help="Seal a blind benchmark before work starts")
    p_seal.add_argument("slug", help="Benchmark slug")
    p_seal.add_argument("--brief-file", required=True, help="Path to the bug brief file")
    p_seal.add_argument("--allowed", default="", help="Information allowed to the solver")
    p_seal.add_argument("--withheld", default="", help="Information withheld from the solver")
    p_seal.set_defaults(func=_cmd_seal_benchmark)

    # attach-patch
    p_patch = sub.add_parser("attach-patch", help="Attach reference patch to a benchmark")
    p_patch.add_argument("slug", help="Benchmark slug")
    p_patch.add_argument("--patch-file", required=True, help="Path to the patch/diff file")
    p_patch.set_defaults(func=_cmd_attach_patch)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
