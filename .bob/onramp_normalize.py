"""OnRamp run normalizer and classifier (authored by Claude Code, labelled; complements Bob's gen_report.py).

Why this file exists: IBM Bob's plan allowance ran out before it could finish two review items, so Claude Code
added them here as a separate, clearly attributed module instead of rewriting Bob's code:
  * a normalizer that turns a verbose Django / unittest log into versioned JSON (handles docstring lines and
    warnings printed between a test's name and its result), failing closed on incomplete runs;
  * a classifier over normalized runs that keeps NEW FAILURE separate from REGRESSION;
  * `init-profile`, so /onramp works in a repository that has no docs/onramp/profile.json yet.

Usage:
  python .bob/onramp_normalize.py normalize RUN.log > run.json
  python .bob/onramp_normalize.py classify baseline.json run.json
  python .bob/onramp_normalize.py init-profile [--write]
Stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "onramp.run/1"
SUPPORTED = {SCHEMA_VERSION}

_HEADER = re.compile(r"^(\w+) \(([\w.]+)\)", re.M)
_HEADER_CONT = re.compile(r"[^\r\n]*\)(?: \.\.\.|\r?\n[^\r\n]* \.\.\.)")
_STATUS = re.compile(r"(?:\.\.\. |^)(ok|FAIL|ERROR|skipped[^\r\n]*|expected failure|unexpected success)\s*$", re.M)
_RAN = re.compile(r"^Ran (\d+) tests? in [\d.]+s\s*$", re.M)
_TERMINAL = re.compile(r"^(OK|FAILED)\b.*$", re.M)
_SEPARATOR = re.compile(r"^(?:={20,}|-{20,})\s*$", re.M)


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16").lstrip("﻿")
    if raw[:3] == b"\xef\xbb\xbf":
        raw = raw[3:]
    return raw.decode("utf-8", errors="replace").replace("\x00", "")


def normalize(text: str, source: str = "") -> dict[str, Any]:
    """Per-test outcomes from verbose runner output, with a fail-closed validity verdict."""
    text = text.lstrip("﻿").replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    end = _SEPARATOR.search(text)
    body = text[: end.start()] if end else text
    heads = [h for h in _HEADER.finditer(body) if _HEADER_CONT.match(body, h.start())]
    outcomes: dict[str, str] = {}
    for i, h in enumerate(heads):
        seg = body[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(body)]
        s = _STATUS.search(seg)
        if not s:
            continue
        raw = s.group(1)
        outcomes[h.group(2)] = ("PASS" if raw in ("ok", "expected failure") else "SKIP" if raw.startswith("skipped")
                                else "FAIL" if raw == "unexpected success" else raw)
    ran = _RAN.search(text)
    term = _TERMINAL.search(text)
    problems = []
    if not text.strip():
        problems.append("empty output")
    if not ran:
        problems.append('no "Ran N tests" line (crashed or aborted run?)')
    if not term:
        problems.append("no terminal OK/FAILED line")
    if ran and int(ran.group(1)) != len(outcomes):
        problems.append(f'"Ran {ran.group(1)}" but {len(outcomes)} per-test results parsed (use verbose output)')
    if ran and term:
        any_fail = any(v in ("FAIL", "ERROR") for v in outcomes.values())
        if (term.group(1) == "OK") == any_fail:
            problems.append("terminal status disagrees with per-test results")
    return {
        "schema_version": SCHEMA_VERSION,
        "source": source,
        "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "valid": not problems,
        "problems": problems,
        "tests_run": int(ran.group(1)) if ran else None,
        "outcomes": dict(sorted(outcomes.items())),
    }


_STATUSES = ("PASS", "FAIL", "ERROR", "SKIP")


def _check(run: dict[str, Any], label: str) -> list[str]:
    if run.get("schema_version") not in SUPPORTED:
        return [f"{label}: unsupported schema_version {run.get('schema_version')}"]
    out = [f"{label}: {p}" for p in run.get("problems", [])]
    outcomes = run.get("outcomes")
    if not isinstance(outcomes, dict):
        return out + [f"{label}: outcomes missing"]
    # fail closed: anything outside the normalizer's vocabulary (null, typos, CRASH...) is not trusted
    bad = sorted(t for t, v in outcomes.items() if v not in _STATUSES)
    if bad:
        out.append(f"{label}: {len(bad)} test(s) with an unknown status (first: {bad[0]})")
    return out


def classify(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """Classify only tests that ran. NOT RUN is never FIXED; NEW FAILURE is never called a REGRESSION."""
    problems = _check(baseline, "baseline") + _check(current, "current run")
    result: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "valid": not problems, "problems": problems, "scope": None,
                              **{k: [] for k in ("inherited", "fixed", "regression", "new_failure", "new_test",
                                                 "unchanged_pass", "not_run", "skipped")}}
    if problems:
        return result  # INCONCLUSIVE
    base, cur = baseline["outcomes"], current["outcomes"]
    for tid, b in base.items():
        c = cur.get(tid)
        if c is None:
            result["not_run"].append(tid)
            continue
        if c == "SKIP":
            result["skipped"].append(tid)
            continue
        b_fail, c_fail = b in ("FAIL", "ERROR"), c in ("FAIL", "ERROR")
        key = ("inherited" if b_fail and c_fail else "fixed" if b_fail else "regression" if c_fail else "unchanged_pass")
        result[key].append(tid)
    for tid, c in cur.items():
        if tid not in base and c != "SKIP":
            result["new_failure" if c in ("FAIL", "ERROR") else "new_test"].append(tid)
    result["scope"] = "FULL" if not result["not_run"] else "TARGETED"
    return result


def init_profile(root: Path) -> dict[str, Any]:
    """Discover a starting profile for an unfamiliar Python repository (review it before use)."""
    venv_py = next((str(p.relative_to(root)) for p in (root / ".venv" / "Scripts" / "python.exe",
                                                       root / ".venv" / "bin" / "python") if p.exists()), "python")
    if (root / "manage.py").exists():
        settings = next((str(p.parent.relative_to(root)).replace("\\", "/").replace("/", ".") + ".settings"
                         for p in root.glob("*/settings.py")), "")
        app_root = settings.split(".")[0] if settings else ""
        return {"_comment": "Generated by onramp_normalize.py init-profile; review before use.",
                "repo_name": root.name, "framework": "django",
                "test_runner": f"{venv_py} manage.py test", "verbose_flag": "-v 2",
                "settings_module": settings, "app_root": app_root, "source_roots": [app_root] if app_root else ["."],
                "test_file_pattern": f"{app_root}/**/tests/test_*.py" if app_root else "**/test_*.py",
                "evidence_dir": "docs/onramp/evidence"}
    tests_dir = next((d for d in ("tests", "test") if (root / d).is_dir()), None)
    pkgs = sorted(p.parent.name for p in root.glob("*/__init__.py") if p.parent.name not in (tests_dir, ".venv"))
    return {"_comment": "Generated by onramp_normalize.py init-profile; review before use.",
            "repo_name": root.name, "framework": "unittest",
            "test_runner": f"{venv_py} -m unittest discover -s {tests_dir or '.'} -t .", "verbose_flag": "-v",
            "app_root": pkgs[0] if pkgs else ".", "source_roots": (pkgs or ["."]) + ([tests_dir] if tests_dir else []),
            "test_file_pattern": f"{tests_dir or '.'}/test_*.py", "evidence_dir": "docs/onramp/evidence"}


def load_run(path: Path) -> dict[str, Any]:
    """Read a normalized run, tolerating a BOM (Windows PowerShell's `>` writes one) and UTF-16."""
    return json.loads(read_text(path))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("normalize"); n.add_argument("log")
    c = sub.add_parser("classify"); c.add_argument("baseline"); c.add_argument("current")
    i = sub.add_parser("init-profile"); i.add_argument("--root", default="."); i.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "normalize":
        print(json.dumps(normalize(read_text(Path(a.log)), source=Path(a.log).name), indent=1))
        return 0
    if a.cmd == "classify":
        r = classify(load_run(Path(a.baseline)), load_run(Path(a.current)))
        print(json.dumps(r, indent=1))
        return 0 if r["valid"] and not r["regression"] and not r["new_failure"] else 1
    root = Path(a.root).resolve()
    target = root / "docs" / "onramp" / "profile.json"
    if target.exists():
        print(f"profile already exists: {target}")
        return 0
    prof = init_profile(root)
    print(json.dumps(prof, indent=2))
    if a.write:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(prof, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
