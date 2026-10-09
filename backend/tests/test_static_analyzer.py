"""Tests for the two-tier static analyzer.

Roadmap task s5-4: Static analyzer: Tier 2 never reaches action interface.
Gate: Build fails if a Tier 2 function reaches decide_*().
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from app.control.static_analyzer import (
    FunctionDefRecord,
    Violation,
    analyze_default_package,
    analyze_package,
    build_call_graph,
    parse_file,
    reachable_from,
)


def _write(tmp_path: Path, name: str, source: str) -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(source))
    return p


# -- parse_file ---------------------------------------------------------------


def test_parse_file_records_toplevel_functions(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        "m.py",
        """
        def decide_a():
            pass

        def estimate_b():
            pass
        """,
    )
    records = parse_file(p)
    names = sorted(r.name for r in records)
    assert names == ["decide_a", "estimate_b"]


def test_parse_file_ignores_nested_functions(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        "m.py",
        """
        def outer():
            def inner():
                pass
            return inner
        """,
    )
    records = parse_file(p)
    assert [r.name for r in records] == ["outer"]


def test_parse_file_collects_direct_calls(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        "m.py",
        """
        def decide_a():
            estimate_b()
            estimate_c()

        def estimate_b():
            pass

        def estimate_c():
            pass
        """,
    )
    records = {r.name: r for r in parse_file(p)}
    assert records["decide_a"].calls == frozenset({"estimate_b", "estimate_c"})


def test_parse_file_ignores_method_calls(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        "m.py",
        """
        def outer():
            obj.method()
            decide_x()
        """,
    )
    records = {r.name: r for r in parse_file(p)}
    assert records["outer"].calls == frozenset({"decide_x"})


# -- call graph --------------------------------------------------------------


def test_build_call_graph_filters_unknown_names() -> None:
    records = [
        FunctionDefRecord(
            name="a",
            file="f",
            line=1,
            calls=frozenset({"b", "external_module_func"}),
        ),
        FunctionDefRecord(name="b", file="f", line=5, calls=frozenset()),
    ]
    graph = build_call_graph(records)
    assert graph["a"] == {"b"}


def test_reachable_from_single() -> None:
    graph = {"a": {"b"}, "b": {"c"}, "c": set()}
    paths = reachable_from(graph, "a")
    assert set(paths.keys()) == {"a", "b", "c"}
    assert paths["c"] == ("a", "b", "c")


def test_reachable_from_handles_cycle() -> None:
    graph = {"a": {"b"}, "b": {"a"}}
    paths = reachable_from(graph, "a")
    assert set(paths.keys()) == {"a", "b"}


# -- analyze_package: clean case --------------------------------------------


def test_analyze_package_clean(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "a.py",
        """
        def decide_x():
            return estimate_y()

        def estimate_y():
            return 1.0
        """,
    )
    violations = analyze_package(tmp_path)
    assert violations == []


def test_analyze_package_clean_across_files(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "a.py",
        """
        def decide_x():
            return estimate_y()
        """,
    )
    _write(
        tmp_path,
        "b.py",
        """
        def estimate_y():
            return 1.0
        """,
    )
    violations = analyze_package(tmp_path)
    assert violations == []


# -- analyze_package: violation cases ---------------------------------------


def test_analyze_package_direct_violation(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "a.py",
        """
        def estimate_bad():
            decide_x()

        def decide_x():
            pass
        """,
    )
    violations = analyze_package(tmp_path)
    assert len(violations) == 1
    v = violations[0]
    assert v.offending_function == "decide_x"
    assert v.path == ("estimate_bad", "decide_x")


def test_analyze_package_transitive_violation(tmp_path: Path) -> None:
    """The check must be transitive: estimate -> helper -> decide is
    a violation even though no estimate_* function calls decide_*
    directly."""
    _write(
        tmp_path,
        "a.py",
        """
        def estimate_bad():
            helper()

        def helper():
            decide_x()

        def decide_x():
            pass
        """,
    )
    violations = analyze_package(tmp_path)
    assert len(violations) == 1
    assert violations[0].path == ("estimate_bad", "helper", "decide_x")


def test_analyze_package_two_violations(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "a.py",
        """
        def estimate_one():
            decide_a()

        def estimate_two():
            decide_b()

        def decide_a():
            pass

        def decide_b():
            pass
        """,
    )
    violations = analyze_package(tmp_path)
    assert len(violations) == 2
    assert {v.offending_function for v in violations} == {"decide_a", "decide_b"}


# -- the real control package ------------------------------------------------


def test_real_control_package_is_clean() -> None:
    """The s5-4 gate. The actual control package must have no
    violations. This test is what makes CI fail if a future commit
    introduces a Tier 2 -> Tier 1 call."""
    violations = analyze_default_package()
    assert violations == [], "Two-tier separation violated: " + "; ".join(
        f"{v.source_file}:{v.source_line} reaches {v.offending_function} via {' -> '.join(v.path)}"
        for v in violations
    )


def test_tier2_module_has_only_estimate_functions() -> None:
    """Sanity check on the current tier2.py: all public functions
    must follow the estimate_ naming convention or be private."""
    records = parse_file(Path(__file__).resolve().parents[1] / "app" / "control" / "tier2.py")
    public_names = [r.name for r in records if not r.name.startswith("_")]
    for name in public_names:
        # Helpers like extinction_coefficient and atmospheric_transmission
        # are pure mathematical functions, not Tier 2 estimates. They are
        # permitted; only the *surrogate* entry points must follow the
        # convention. This test documents which names are exempt.
        allowed_exempt = {
            "extinction_coefficient",
            "atmospheric_transmission",
        }
        if name in allowed_exempt:
            continue
        assert name.startswith("estimate_"), (
            f"public function {name} does not follow the Tier 2 naming convention"
        )


# -- Violation dataclass ------------------------------------------------------


def test_violation_is_frozen() -> None:
    from dataclasses import FrozenInstanceError

    v = Violation(
        source_file="f",
        source_line=1,
        offending_function="decide_x",
        path=("estimate_x", "decide_x"),
    )
    with pytest.raises(FrozenInstanceError):
        v.offending_function = "y"  # type: ignore[misc]
