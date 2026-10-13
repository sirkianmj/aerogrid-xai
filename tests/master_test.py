#!/usr/bin/env python3
"""Master test harness (Sprint 9 s9-1).

Runs three phases against the repository root:

  1. backend    -- ``pytest -q`` from backend/, parses the pytest summary
  2. frontend   -- ``npm test`` from frontend/, parses the vitest summary
  3. notebooks  -- structural integrity of every notebooks/*.ipynb:
                   executed code cells, no error outputs, kernel metadata

Exit code is 0 iff every enabled phase passes. A phase passes iff:
  - the subprocess exits 0,
  - zero failures and zero errors were reported, and
  - (with --require-db) zero skips were reported.

Design notes
------------

* Structural notebook verification, not re-execution. Re-execution takes
  minutes and rewrites committed outputs on every CI run; a test should
  not mutate the tree. Notebook re-execution is Sprint 9 s9-6's job
  (``notebook-repro.yml``, nightly, papermill/nbconvert).

* ``--require-db`` is opt-in. Local development runs without PostgreSQL;
  the harness must not fail for that reason. The CI ``master-test`` job
  runs a PostgreSQL service container, applies migrations, and passes
  ``--require-db`` so that a DB-backed test that skipped due to
  configuration drift is treated as a failure.

* Root ``tests/`` path. The roadmap names ``tests/master_test.py``
  literally. Unit tests for the harness live in ``backend/tests/`` so
  pytest's ``testpaths`` continues to apply to them; the harness itself
  is not a pytest module and is never collected by pytest.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"
NOTEBOOKS_DIR = REPO_ROOT / "notebooks"

# pytest prints lines such as:
#   "990 passed in 5.42s"
#   "981 passed, 9 skipped in 5.68s"
#   "1 failed, 5 passed in 1.23s"
_PYTEST_SUMMARY = re.compile(
    r"(?P<count>\d+)\s+(?P<kind>passed|failed|error[s]?|skipped)",
    re.IGNORECASE,
)

# vitest prints:
#   " Tests  163 passed (163)"
_VITEST_SUMMARY = re.compile(r"Tests\s+(?P<count>\d+)\s+passed", re.IGNORECASE)

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


@dataclass
class PhaseResult:
    name: str
    passed: bool
    detail: str
    raw_tail: list[str] = field(default_factory=list)


def _strip_ansi(text: str) -> str:
    return _ANSI.sub("", text)


def _run(cmd: list[str], cwd: Path, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def parse_pytest_summary(text: str) -> dict[str, int]:
    """Parse a pytest output string for counts of passed/failed/skipped/errors.

    Returns a dict with keys ``passed``, ``failed``, ``skipped``, ``errors``.
    Missing categories are 0. The input is ANSI-stripped first so a coloured
    pytest run parses identically to a plain one.
    """
    counts = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
    for match in _PYTEST_SUMMARY.finditer(_strip_ansi(text)):
        kind = match.group("kind").lower()
        if kind == "error":
            kind = "errors"
        elif kind != "errors" and not kind.endswith("s"):
            # pytest prints "1 failed", not "1 faileds"; keep singular forms.
            pass
        if kind == "failed":
            counts["failed"] += int(match.group("count"))
        elif kind == "skipped":
            counts["skipped"] += int(match.group("count"))
        elif kind == "errors":
            counts["errors"] += int(match.group("count"))
        elif kind == "passed":
            counts["passed"] += int(match.group("count"))
    return counts


def parse_vitest_summary(text: str) -> dict[str, int]:
    """Parse vitest's ``Tests  N passed (N)`` line."""
    counts = {"passed": 0, "failed": 0}
    for match in _VITEST_SUMMARY.finditer(_strip_ansi(text)):
        counts["passed"] += int(match.group("count"))
    if re.search(r"\b[1-9]\d*\s+failed\b", _strip_ansi(text)):
        m = re.search(r"\b(\d+)\s+failed\b", _strip_ansi(text))
        if m is not None:
            counts["failed"] = int(m.group(1))
    return counts


def check_notebook_structure(path: Path) -> tuple[bool, str]:
    """Verify one notebook's structural integrity.

    A notebook is valid when: it parses as JSON; ``nbformat`` is 4; it
    declares a kernel; it contains at least one code cell; every code
    cell has a non-null ``execution_count``; and no code cell contains
    an error output. Re-execution is out of scope -- see module docstring.
    """
    try:
        nb = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        return False, f"invalid JSON: {exc}"
    if nb.get("nbformat") != 4:
        return False, f"nbformat must be 4, got {nb.get('nbformat')!r}"
    kernel = nb.get("metadata", {}).get("kernelspec", {}).get("name")
    if not kernel:
        return False, "metadata.kernelspec.name is missing"
    cells = nb.get("cells", [])
    code_cells = [c for c in cells if c.get("cell_type") == "code"]
    if not code_cells:
        return False, "no code cells"
    unexecuted = [
        i
        for i, c in enumerate(cells)
        if c.get("cell_type") == "code" and c.get("execution_count") is None
    ]
    if unexecuted:
        return False, f"unexecuted code cells at indices {unexecuted}"
    errored: list[int] = []
    for i, c in enumerate(cells):
        if c.get("cell_type") != "code":
            continue
        for out in c.get("outputs", []):
            if out.get("output_type") == "error":
                errored.append(i)
                break
    if errored:
        return False, f"error outputs in code cells at indices {errored}"
    return True, f"{len(code_cells)} code cells, executed, no errors"


def run_backend_phase(require_db: bool) -> PhaseResult:
    proc = _run(["pytest", "-q", "--no-header"], cwd=BACKEND_DIR)
    out = _strip_ansi(proc.stdout + "\n" + proc.stderr)
    tail = out.splitlines()[-8:]
    counts = parse_pytest_summary(out)
    detail = (
        f"passed={counts['passed']} failed={counts['failed']} "
        f"errors={counts['errors']} skipped={counts['skipped']} rc={proc.returncode}"
    )
    if proc.returncode != 0:
        return PhaseResult("backend", False, f"pytest exit {proc.returncode}; {detail}", tail)
    if counts["failed"] > 0 or counts["errors"] > 0:
        return PhaseResult("backend", False, f"failures reported; {detail}", tail)
    if require_db and counts["skipped"] > 0:
        return PhaseResult(
            "backend",
            False,
            f"--require-db set but {counts['skipped']} test(s) skipped; {detail}",
            tail,
        )
    return PhaseResult("backend", True, detail, tail)


def run_frontend_phase() -> PhaseResult:
    proc = _run(["npm", "test"], cwd=FRONTEND_DIR)
    out = _strip_ansi(proc.stdout + "\n" + proc.stderr)
    tail = out.splitlines()[-8:]
    counts = parse_vitest_summary(out)
    detail = f"passed={counts['passed']} failed={counts['failed']} rc={proc.returncode}"
    if proc.returncode != 0:
        return PhaseResult("frontend", False, f"npm test exit {proc.returncode}; {detail}", tail)
    if counts["failed"] > 0:
        return PhaseResult("frontend", False, f"failures reported; {detail}", tail)
    if counts["passed"] == 0:
        return PhaseResult("frontend", False, f"no tests reported; {detail}", tail)
    return PhaseResult("frontend", True, detail, tail)


def run_notebook_phase() -> PhaseResult:
    paths = sorted(NOTEBOOKS_DIR.glob("*.ipynb"))
    if not paths:
        return PhaseResult("notebooks", False, "no notebooks found")
    failures: list[str] = []
    for p in paths:
        ok, reason = check_notebook_structure(p)
        if not ok:
            failures.append(f"{p.name}: {reason}")
    if failures:
        return PhaseResult("notebooks", False, f"{len(failures)} invalid", failures)
    return PhaseResult("notebooks", True, f"{len(paths)} verified", [])


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="master_test.py",
        description="Master test harness (Sprint 9 s9-1).",
    )
    p.add_argument("--backend", action="store_true", help="run only the backend phase")
    p.add_argument("--frontend", action="store_true", help="run only the frontend phase")
    p.add_argument("--notebooks", action="store_true", help="run only the notebook phase")
    p.add_argument(
        "--require-db",
        action="store_true",
        help="fail the backend phase if any pytest skip is observed",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    run_all = not (args.backend or args.frontend or args.notebooks)

    phases: list[PhaseResult] = []
    if run_all or args.backend:
        phases.append(run_backend_phase(args.require_db))
    if run_all or args.frontend:
        phases.append(run_frontend_phase())
    if run_all or args.notebooks:
        phases.append(run_notebook_phase())

    print("=" * 60)
    print("Master test harness -- summary")
    print("=" * 60)
    for r in phases:
        flag = "PASS" if r.passed else "FAIL"
        print(f"  {r.name:<10s} {flag}  {r.detail}")
    print("=" * 60)
    all_ok = all(r.passed for r in phases)
    print(f"RESULT: {'PASS' if all_ok else 'FAIL'}")

    if not all_ok:
        for r in phases:
            if r.passed:
                continue
            print()
            print(f"--- tail of {r.name} output ---")
            for line in r.raw_tail:
                print(line)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
