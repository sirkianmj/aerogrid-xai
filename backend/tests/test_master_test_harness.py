"""Unit tests for the master test harness (Sprint 9 s9-1).

The harness lives at tests/master_test.py (repo root) because it
composes pytest, vitest, and notebook verification in one entry point.
The parsing helpers and notebook validator are pure functions; this
module exercises them via direct import.

Path resolution: this file is at backend/tests/test_master_test_harness.py.
Its grandparent is the repository root; the harness is at
``<repo_root>/tests/master_test.py``. The harness module is imported by
adding ``<repo_root>/tests`` to ``sys.path``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HARNESS_DIR = REPO_ROOT / "tests"
if str(HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(HARNESS_DIR))

import master_test  # noqa: E402  # imported from tests/ at repo root

# --- parse_pytest_summary -------------------------------------------------


def test_pytest_summary_all_passed() -> None:
    counts = master_test.parse_pytest_summary("990 passed in 5.42s")
    assert counts == {"passed": 990, "failed": 0, "skipped": 0, "errors": 0}


def test_pytest_summary_with_skips() -> None:
    counts = master_test.parse_pytest_summary("981 passed, 9 skipped in 5.68s")
    assert counts == {"passed": 981, "failed": 0, "skipped": 9, "errors": 0}


def test_pytest_summary_with_failures() -> None:
    counts = master_test.parse_pytest_summary("1 failed, 5 passed in 1.23s")
    assert counts == {"passed": 5, "failed": 1, "skipped": 0, "errors": 0}


def test_pytest_summary_with_errors() -> None:
    counts = master_test.parse_pytest_summary("2 errors, 3 passed in 2.0s")
    assert counts == {"passed": 3, "failed": 0, "skipped": 0, "errors": 2}


def test_pytest_summary_strips_ansi() -> None:
    colored = "\x1b[32m990 passed\x1b[0m in 5.42s"
    counts = master_test.parse_pytest_summary(colored)
    assert counts["passed"] == 990


def test_pytest_summary_no_matches() -> None:
    counts = master_test.parse_pytest_summary("nothing here")
    assert counts == {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}


# --- parse_vitest_summary -------------------------------------------------


def test_vitest_summary_all_passed() -> None:
    counts = master_test.parse_vitest_summary(
        " Test Files  17 passed (17)\n     Tests  163 passed (163)"
    )
    assert counts["passed"] == 163
    assert counts["failed"] == 0


def test_vitest_summary_with_failures() -> None:
    counts = master_test.parse_vitest_summary("     Tests  160 passed (160)\n Tests  3 failed")
    assert counts["passed"] == 160
    assert counts["failed"] == 3


def test_vitest_summary_strips_ansi() -> None:
    colored = "\x1b[32m     Tests  163 passed (163)\x1b[0m"
    counts = master_test.parse_vitest_summary(colored)
    assert counts["passed"] == 163


# --- check_notebook_structure ---------------------------------------------


def _write_notebook(
    path: Path,
    cells: list[dict[str, object]],
    *,
    kernel: str | None = "python3",
    nbformat: int = 4,
) -> None:
    metadata: dict[str, object] = {}
    if kernel is not None:
        metadata["kernelspec"] = {"name": kernel}
    path.write_text(
        json.dumps(
            {"nbformat": nbformat, "nbformat_minor": 5, "metadata": metadata, "cells": cells}
        )
    )


def _code_cell(
    execution_count: int | None, outputs: list[dict[str, object]] | None = None
) -> dict[str, object]:
    return {
        "cell_type": "code",
        "execution_count": execution_count,
        "outputs": outputs or [],
        "source": ["print('x')"],
        "metadata": {},
    }


def _md_cell() -> dict[str, object]:
    return {"cell_type": "markdown", "source": ["# hi"], "metadata": {}}


def test_notebook_valid(tmp_path: Path) -> None:
    nb = tmp_path / "ok.ipynb"
    _write_notebook(nb, [_md_cell(), _code_cell(execution_count=1)])
    ok, reason = master_test.check_notebook_structure(nb)
    assert ok is True
    assert "1 code cells" in reason


def test_notebook_unexecuted_cell(tmp_path: Path) -> None:
    nb = tmp_path / "bad.ipynb"
    _write_notebook(nb, [_code_cell(execution_count=None)])
    ok, reason = master_test.check_notebook_structure(nb)
    assert ok is False
    assert "unexecuted" in reason


def test_notebook_error_output(tmp_path: Path) -> None:
    nb = tmp_path / "err.ipynb"
    _write_notebook(
        nb,
        [
            _code_cell(
                execution_count=1,
                outputs=[{"output_type": "error", "ename": "X", "evalue": "y", "traceback": []}],
            )
        ],
    )
    ok, reason = master_test.check_notebook_structure(nb)
    assert ok is False
    assert "error outputs" in reason


def test_notebook_no_code_cells(tmp_path: Path) -> None:
    nb = tmp_path / "empty.ipynb"
    _write_notebook(nb, [_md_cell()])
    ok, reason = master_test.check_notebook_structure(nb)
    assert ok is False
    assert "no code cells" in reason


def test_notebook_missing_kernel(tmp_path: Path) -> None:
    nb = tmp_path / "nokernel.ipynb"
    _write_notebook(nb, [_code_cell(execution_count=1)], kernel=None)
    ok, reason = master_test.check_notebook_structure(nb)
    assert ok is False
    assert "kernelspec" in reason


def test_notebook_wrong_nbformat(tmp_path: Path) -> None:
    nb = tmp_path / "old.ipynb"
    _write_notebook(nb, [_code_cell(execution_count=1)], nbformat=3)
    ok, reason = master_test.check_notebook_structure(nb)
    assert ok is False
    assert "nbformat" in reason


def test_notebook_invalid_json(tmp_path: Path) -> None:
    nb = tmp_path / "junk.ipynb"
    nb.write_text("{not json")
    ok, reason = master_test.check_notebook_structure(nb)
    assert ok is False
    assert "invalid JSON" in reason


# --- sanity: the repo's own notebooks satisfy the checker -----------------


def test_repo_notebooks_are_valid() -> None:
    """Every committed notebook must satisfy the harness's checker.

    If this test fails, either a notebook was committed unexecuted/with
    errors, or the checker has drifted from the convention. Both are
    actionable: fix the notebook, or adjust the checker with a rationale.
    """
    paths = sorted((REPO_ROOT / "notebooks").glob("*.ipynb"))
    assert len(paths) >= 10, f"expected >= 10 notebooks, found {len(paths)}"
    for p in paths:
        ok, reason = master_test.check_notebook_structure(p)
        assert ok is True, f"{p.name}: {reason}"


# --- __main__ argument parsing (smoke) -----------------------------------


def test_main_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        master_test.main(["--help"])
    assert info.value.code == 0
    out = capsys.readouterr().out
    assert "--require-db" in out
