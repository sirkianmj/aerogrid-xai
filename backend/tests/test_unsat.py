"""Tests for unsat-core extraction and minimality verification.

Roadmap task s4-3: UNSAT-core extraction (z3.get_unsat_core()).
Gate: Core is minimal - all proper subsets are SAT.
"""

from __future__ import annotations

import random

import pytest
import z3

from app.discovery.unsat import (
    MAX_EXHAUSTIVE_CORE_SIZE,
    CoreResult,
    NamedConstraint,
    UnsatCoreExtractor,
    verify_core_minimality_exhaustive,
    verify_core_minimality_removal,
)


def _c(name: str, expr: z3.BoolRef) -> NamedConstraint:
    return NamedConstraint(family_name=name, expression=expr)


# -- NamedConstraint validation ---------------------------------------------


def test_named_constraint_rejects_empty_name() -> None:
    with pytest.raises(ValueError, match="family_name must be non-empty"):
        NamedConstraint(family_name="", expression=z3.BoolVal(True))


def test_named_constraint_rejects_non_bool_expression() -> None:
    with pytest.raises(ValueError, match="must be Boolean"):
        NamedConstraint(
            family_name="bad",
            expression=z3.RealVal(1.0),
        )


# -- Extractor: SAT paths ---------------------------------------------------


def test_extractor_empty_returns_sat() -> None:
    ext = UnsatCoreExtractor()
    result = ext.check()
    assert result.status == "sat"
    assert result.core_names == ()


def test_extractor_single_satisfiable_constraint() -> None:
    x = z3.Real("x_single")
    ext = UnsatCoreExtractor()
    ext.add(_c("x_positive", x >= 0.0))
    result = ext.check()
    assert result.status == "sat"
    assert result.core_names == ()
    assert result.all_family_names == ("x_positive",)


def test_extractor_multiple_consistent_constraints() -> None:
    x = z3.Real("x_multi")
    ext = UnsatCoreExtractor()
    ext.add(_c("lo", x >= 0.0))
    ext.add(_c("hi", x <= 10.0))
    ext.add(_c("even", x == 4.0))
    result = ext.check()
    assert result.status == "sat"
    assert result.core_names == ()


# -- Extractor: UNSAT paths -------------------------------------------------


def test_extractor_detects_contradiction() -> None:
    x = z3.Real("x_contradict")
    ext = UnsatCoreExtractor()
    ext.add(_c("lo", x >= 10.0))
    ext.add(_c("hi", x <= 5.0))
    result = ext.check()
    assert result.status == "unsat"
    assert set(result.core_names) == {"lo", "hi"}


def test_extractor_core_is_subset_of_all() -> None:
    x = z3.Real("x_subset")
    ext = UnsatCoreExtractor()
    ext.add(_c("hi", x <= 5.0))
    ext.add(_c("lo", x >= 10.0))
    ext.add(_c("unrelated", x > -100.0))
    result = ext.check()
    assert result.status == "unsat"
    assert "unrelated" not in result.core_names or len(result.core_names) == 3


def test_extractor_result_core_names_are_sorted() -> None:
    """Sorting makes core extraction deterministic, which the s4-8
    determinism gate depends on."""
    x = z3.Real("x_sorted")
    ext = UnsatCoreExtractor()
    ext.add(_c("zebra", x >= 10.0))
    ext.add(_c("alpha", x <= 5.0))
    result = ext.check()
    assert result.status == "unsat"
    assert result.core_names == tuple(sorted(result.core_names))


def test_extractor_rejects_duplicate_family_name() -> None:
    x = z3.Real("x_dup")
    ext = UnsatCoreExtractor()
    ext.add(_c("dup", x >= 0.0))
    with pytest.raises(ValueError, match="already added"):
        ext.add(_c("dup", x <= 5.0))


def test_core_result_size_property() -> None:
    x = z3.Real("x_size")
    ext = UnsatCoreExtractor()
    ext.add(_c("a", x >= 10.0))
    ext.add(_c("b", x <= 5.0))
    result = ext.check()
    assert result.core_size == len(result.core_names)


# -- Minimality: removal check ----------------------------------------------


def test_removal_check_confirms_minimal_two_element_core() -> None:
    x = z3.Real("x_two_min")
    constraints = (
        _c("lo", x >= 10.0),
        _c("hi", x <= 5.0),
    )
    assert verify_core_minimality_removal(
        constraints=constraints,
        core_names=("hi", "lo"),
    )


def test_removal_check_rejects_non_minimal_core() -> None:
    """A core that contains a redundant clause fails the check because
    removing the redundant clause keeps the system UNSAT."""
    x = z3.Real("x_nonmin")
    constraints = (
        _c("a", x >= 10.0),
        _c("b", x <= 5.0),
        _c("redundant_also_forbids_x_at_least_10", x >= 8.0),
    )
    # The pair (a, b) is UNSAT; c is implied by a, so the triple is
    # also UNSAT but the triple is not minimal (removing c leaves a
    # UNSAT pair).
    assert not verify_core_minimality_removal(
        constraints=constraints,
        core_names=("a", "b", "redundant_also_forbids_x_at_least_10"),
    )


def test_removal_check_rejects_unknown_name() -> None:
    x = z3.Real("x_unk")
    constraints = (_c("a", x >= 0.0),)
    with pytest.raises(ValueError, match="names not present"):
        verify_core_minimality_removal(
            constraints=constraints,
            core_names=("a", "ghost"),
        )


def test_removal_check_rejects_sat_core() -> None:
    x = z3.Real("x_sat_core")
    constraints = (_c("a", x >= 0.0),)
    with pytest.raises(ValueError, match="not UNSAT"):
        verify_core_minimality_removal(
            constraints=constraints,
            core_names=("a",),
        )


# -- Minimality: exhaustive check -------------------------------------------


def test_exhaustive_confirms_two_element_core() -> None:
    x = z3.Real("x_exh2")
    constraints = (
        _c("lo", x >= 10.0),
        _c("hi", x <= 5.0),
    )
    assert verify_core_minimality_exhaustive(
        constraints=constraints,
        core_names=("hi", "lo"),
    )


def test_exhaustive_confirms_three_element_core() -> None:
    """A three-constraint system with no satisfiable proper subset
    that is itself UNSAT requires all three constraints to be jointly
    contradictory. Example: x >= 0, y >= 0, x + y <= -1."""
    x = z3.Real("x_exh3a")
    y = z3.Real("y_exh3a")
    constraints = (
        _c("x_nonneg", x >= 0.0),
        _c("y_nonneg", y >= 0.0),
        _c("sum_negative", x + y <= -1.0),
    )
    assert verify_core_minimality_exhaustive(
        constraints=constraints,
        core_names=("x_nonneg", "y_nonneg", "sum_negative"),
    )


def test_exhaustive_rejects_non_minimal_core() -> None:
    x = z3.Real("x_exh_nonmin")
    constraints = (
        _c("a", x >= 10.0),
        _c("b", x <= 5.0),
        _c("redundant", x >= 8.0),
    )
    assert not verify_core_minimality_exhaustive(
        constraints=constraints,
        core_names=("a", "b", "redundant"),
    )


def test_exhaustive_rejects_oversize_core() -> None:
    x = z3.Real("x_oversize")
    constraints = tuple(_c(f"c{i}", x >= 0.0) for i in range(10))
    with pytest.raises(ValueError, match="exceeds max_core_size"):
        verify_core_minimality_exhaustive(
            constraints=constraints,
            core_names=tuple(f"c{i}" for i in range(10)),
        )


def test_exhaustive_rejects_sat_core() -> None:
    x = z3.Real("x_exh_sat")
    constraints = (_c("a", x >= 0.0),)
    with pytest.raises(ValueError, match="not UNSAT"):
        verify_core_minimality_exhaustive(
            constraints=constraints,
            core_names=("a",),
        )


# -- Cross-check: both verifications agree ----------------------------------


def test_both_checks_agree_on_random_minimal_cores() -> None:
    """Fuzz: generate random small systems, extract the core, and
    confirm both minimality checks agree. If removal says minimal,
    exhaustive says minimal, and vice versa."""
    rng = random.Random(20261009)
    for _ in range(40):
        x = z3.Real("x_cross")
        # Always add a contradictory pair.
        lo = rng.uniform(5.0, 20.0)
        hi = rng.uniform(0.0, 4.0)
        constraints_list = [
            _c(f"lo_{_}", x >= lo),
            _c(f"hi_{_}", x <= hi),
        ]
        # Add 0-3 unrelated constraints that are satisfiable.
        for k in range(rng.randint(0, 3)):
            constraints_list.append(_c(f"unrel_{k}_{_}", x >= -1000.0))
        constraints = tuple(constraints_list)
        ext = UnsatCoreExtractor()
        for c in constraints:
            ext.add(c)
        result = ext.check()
        assert result.status == "unsat"

        removal = verify_core_minimality_removal(
            constraints=constraints,
            core_names=result.core_names,
        )
        exhaustive = verify_core_minimality_exhaustive(
            constraints=constraints,
            core_names=result.core_names,
        )
        assert removal == exhaustive, (
            f"Removal and exhaustive checks disagree; core = {result.core_names}"
        )
        # The core must be minimal because we constructed it that way.
        assert removal


# -- Constants --------------------------------------------------------------


def test_max_exhaustive_core_size() -> None:
    assert MAX_EXHAUSTIVE_CORE_SIZE == 8


# -- CoreResult structure ---------------------------------------------------


def test_core_result_defaults() -> None:
    r = CoreResult(status="sat")
    assert r.core_names == ()
    assert r.all_family_names == ()
    assert r.core_size == 0
