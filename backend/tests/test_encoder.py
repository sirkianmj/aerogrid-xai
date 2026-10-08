"""Tests for the PWL-to-Z3 encoder.

Roadmap task:
    s3-3 Incremental Linearization encoding -> SMT-LIB.
    Gate: Z3 returns SAT/UNSAT correctly for known cases.

Prior art: the encoding applied here is Incremental Linearization
(Cimatti et al.). Tests exercise correctness of the encoding, not
novelty of the technique.
"""

from __future__ import annotations

import pytest
import z3

from app.verification.encoder import (
    ConstraintSession,
    ConstraintSpec,
    SolverResult,
    build_constraint_spec,
    pwl_to_z3_expr,
)
from app.verification.pwl import pwl_approximate


def _linear_slope_1(x: float) -> float:
    return x


def _linear_slope_minus_1(x: float) -> float:
    return -x


def _shifted_by_minus_3(x: float) -> float:
    return x - 3.0


def _shifted_by_minus_17(x: float) -> float:
    return 17.0 - x


def _quadratic_plus_1(x: float) -> float:
    return x * x + 1.0


# pwl_to_z3_expr: encoding correctness


def test_z3_expr_at_breakpoints_matches_python_evaluate() -> None:
    approx = pwl_approximate(_linear_slope_1, (0.0, 10.0), 5, "identity")
    x = z3.Real("x_test_bp")
    expr = pwl_to_z3_expr(x, approx)
    for x_val in (0.0, 1.0, 2.5, 5.0, 7.5, 9.0, 10.0):
        solver = z3.Solver()
        solver.add(x == z3.RealVal(repr(x_val)))
        assert solver.check() == z3.sat
        model = solver.model()
        z3_val = model.eval(expr, model_completion=True)
        z3_float = float(z3_val.as_fraction())
        py_val = approx.evaluate(x_val)
        assert abs(z3_float - py_val) < 1e-9, f"x={x_val}: z3={z3_float} vs python={py_val}"


def test_z3_expr_single_segment() -> None:
    approx = pwl_approximate(lambda x: 7.5, (0.0, 10.0), 1, "constant")
    x = z3.Real("x_single")
    expr = pwl_to_z3_expr(x, approx)
    solver = z3.Solver()
    solver.add(x == z3.RealVal(5.0))
    solver.check()
    val = float(solver.model().eval(expr, model_completion=True).as_fraction())
    assert abs(val - 7.5) < 1e-9


def test_z3_expr_rejects_empty_approx() -> None:
    approx = pwl_approximate(_linear_slope_1, (0.0, 1.0), 1, "x")
    stripped = type(approx)(
        family_name="empty",
        segments=(),
        epsilon=0.0,
        x_min=0.0,
        x_max=1.0,
    )
    x = z3.Real("x_empty")
    with pytest.raises(ValueError):
        pwl_to_z3_expr(x, stripped)


# ConstraintSession: SAT / UNSAT on known cases


def test_session_sat_on_single_satisfiable_constraint() -> None:
    approx = pwl_approximate(lambda x: x - 5.0, (0.0, 20.0), 20, "x_le_5")
    session = ConstraintSession()
    session.add_constraint(ConstraintSpec("x_le_5", approx, "le"))
    result = session.check()
    assert isinstance(result, SolverResult)
    assert result.status == "sat"
    assert result.x_value is not None
    assert 0.0 <= result.x_value <= 20.0


def test_session_unsat_on_disjoint_constraints() -> None:
    """x <= 3 and x >= 17 are disjoint. PWL over-approximation keeps
    them disjoint because the approximation interval is narrow enough:
    segments of width 1 give a slack of at most 1 on each side, so the
    over-approximated regions are [0, 4] and [16, 20], still disjoint.
    """
    approx_low = pwl_approximate(_shifted_by_minus_3, (0.0, 20.0), 20, "x_le_3")
    approx_high = pwl_approximate(_shifted_by_minus_17, (0.0, 20.0), 20, "x_ge_17")
    session = ConstraintSession()
    session.add_constraint(ConstraintSpec("x_le_3", approx_low, "le"))
    session.add_constraint(ConstraintSpec("x_ge_17", approx_high, "le"))
    result = session.check()
    assert result.status == "unsat"
    assert result.x_value is None


def test_session_unsat_core_contains_both_families() -> None:
    approx_low = pwl_approximate(_shifted_by_minus_3, (0.0, 20.0), 20, "x_le_3")
    approx_high = pwl_approximate(_shifted_by_minus_17, (0.0, 20.0), 20, "x_ge_17")
    session = ConstraintSession()
    session.add_constraint(ConstraintSpec("x_le_3", approx_low, "le"))
    session.add_constraint(ConstraintSpec("x_ge_17", approx_high, "le"))
    result = session.check()
    assert result.status == "unsat"
    assert "x_le_3" in result.unsat_core
    assert "x_ge_17" in result.unsat_core


def test_session_with_quadratic_plus_1_is_unsat() -> None:
    """x^2 + 1 <= 0 is unsatisfiable for real x. The PWL approximation
    of x^2 + 1 on [0, 10] with 5 segments has strictly positive minima
    on every segment, so the constraint is UNSAT for all x in domain.
    """
    approx = pwl_approximate(_quadratic_plus_1, (0.0, 10.0), 5, "x2_plus_1_le_0")
    session = ConstraintSession()
    session.add_constraint(ConstraintSpec("x2_plus_1_le_0", approx, "le"))
    result = session.check()
    assert result.status == "unsat"


def test_session_ge_sense_is_satisfiable() -> None:
    """With sense='ge', a strictly negative constant PWL encodes
    f_hat(x) >= 0 as unsat for all x in domain (constant is negative
    everywhere). Test the positive case: f = x - 5 on [0, 20], sense
    'ge', which requires x - 5 >= 0 over-approximated by the PWL.
    """
    approx = pwl_approximate(lambda x: x - 5.0, (0.0, 20.0), 20, "x_minus_5")
    session = ConstraintSession()
    session.add_constraint(ConstraintSpec("x_minus_5", approx, "ge"))
    result = session.check()
    assert result.status == "sat"
    assert result.x_value is not None
    # The PWL over-approximation of x - 5 on [0, 20] with 20 segments is
    # f_hat(x) = floor(x) - 5. f_hat(x) >= 0 requires floor(x) >= 5,
    # so x in [5, 6). Check the SAT witness is in that range.
    assert 5.0 <= result.x_value < 6.5


def test_session_rejects_duplicate_family_name() -> None:
    approx_a = pwl_approximate(_shifted_by_minus_3, (0.0, 20.0), 5, "dup")
    approx_b = pwl_approximate(_shifted_by_minus_17, (0.0, 20.0), 5, "dup")
    session = ConstraintSession()
    session.add_constraint(ConstraintSpec("dup", approx_a, "le"))
    with pytest.raises(ValueError):
        session.add_constraint(ConstraintSpec("dup", approx_b, "le"))


# SolverResult: epsilon reporting (Section 34.2)


def test_solver_result_reports_per_family_epsilon() -> None:
    approx_a = pwl_approximate(_shifted_by_minus_3, (0.0, 20.0), 10, "family_a")
    approx_b = pwl_approximate(_shifted_by_minus_17, (0.0, 20.0), 10, "family_b")
    session = ConstraintSession()
    session.add_constraint(ConstraintSpec("family_a", approx_a, "le"))
    session.add_constraint(ConstraintSpec("family_b", approx_b, "le"))
    result = session.check()
    names = {r.family_name for r in result.epsilon_reports}
    assert names == {"family_a", "family_b"}
    assert result.max_epsilon > 0.0
    for r in result.epsilon_reports:
        assert r.epsilon > 0.0


def test_solver_result_epsilon_is_zero_on_constant() -> None:
    approx = pwl_approximate(lambda x: 5.0, (0.0, 1.0), 1, "constant")
    session = ConstraintSession()
    session.add_constraint(ConstraintSpec("constant", approx, "le"))
    result = session.check()
    assert result.max_epsilon == pytest.approx(0.0, abs=1e-12)


# session state


def test_session_family_names_sorted() -> None:
    session = ConstraintSession()
    session.add_constraint(
        ConstraintSpec(
            "zeta",
            pwl_approximate(_shifted_by_minus_3, (0.0, 20.0), 5, "zeta"),
            "le",
        )
    )
    session.add_constraint(
        ConstraintSpec(
            "alpha",
            pwl_approximate(_shifted_by_minus_17, (0.0, 20.0), 5, "alpha"),
            "le",
        )
    )
    assert session.family_names == ("alpha", "zeta")


def test_session_variable_is_real() -> None:
    session = ConstraintSession()
    assert z3.is_real(session.variable)


# build_constraint_spec: epsilon targeting


def test_build_constraint_spec_default_returns_spec() -> None:
    spec = build_constraint_spec("smooth", _shifted_by_minus_3, (0.0, 20.0), 5)
    assert isinstance(spec, ConstraintSpec)
    assert spec.family_name == "smooth"
    assert spec.sense == "le"


def test_build_constraint_spec_targets_epsilon() -> None:
    spec = build_constraint_spec(
        "targeted",
        _linear_slope_1,
        (0.0, 20.0),
        5,
        epsilon_target=0.5,
    )
    assert spec.approx.epsilon <= 0.5


def test_build_constraint_spec_targets_tight_epsilon() -> None:
    spec = build_constraint_spec(
        "tight",
        _linear_slope_1,
        (0.0, 20.0),
        5,
        epsilon_target=0.01,
    )
    assert spec.approx.epsilon <= 0.01


def test_build_constraint_spec_rejects_impossible_epsilon() -> None:
    """On a quadratic, achieving epsilon < 1e-12 would need an enormous
    number of segments; the doubling budget should exhaust first."""
    with pytest.raises(RuntimeError):
        build_constraint_spec(
            "impossible",
            _quadratic_plus_1,
            (0.0, 10.0),
            5,
            epsilon_target=1e-12,
            max_segment_doublings=3,
        )


# integration: the two Stage A constraint families from Section 33.5,
# expressed as a joint feasibility problem


def test_session_thermal_and_efficiency_joint_sat_at_low_power() -> None:
    """A 20 W incident power at 5 m/s airflow is inside the thermal
    runaway boundary (P_max ~ 25 W at 5 m/s from Sprint 2b). Combined
    with a modest efficiency floor, this is SAT. The PWL families are
    built from a physics-derived shape, not the full thermal model, to
    keep the test fast; the point is to exercise the encoder, not the
    physics."""
    # Thermal family: P - 25 <= 0, encoded as a function of P.
    approx_thermal = pwl_approximate(lambda p: p - 25.0, (0.0, 100.0), 20, "thermal_runaway")
    # Efficiency family: eta_floor - eta(P) >= 0 approximated as
    # 0.10 - 0.002 * P >= 0, i.e., P <= 50. Encode as P - 50 <= 0.
    approx_efficiency = pwl_approximate(lambda p: p - 50.0, (0.0, 100.0), 20, "efficiency_floor")
    session = ConstraintSession()
    session.add_constraint(ConstraintSpec("thermal_runaway", approx_thermal, "le"))
    session.add_constraint(ConstraintSpec("efficiency_floor", approx_efficiency, "le"))
    result = session.check()
    assert result.status == "sat"
    # The binding constraint is thermal_runaway (25 W); efficiency
    # permits up to 50 W. SAT witness should be at or below 25 W.
    assert result.x_value is not None
    assert result.x_value <= 26.0


def test_session_thermal_conflict_with_min_power_demand() -> None:
    """Thermal runaway forbids P > 25 W; a minimum-power demand
    requires P >= 40 W. Jointly UNSAT. This is the pattern that
    Stage B will detect for real receiver configurations in Sprint 3c."""
    approx_thermal = pwl_approximate(lambda p: p - 25.0, (0.0, 100.0), 20, "thermal_runaway")
    approx_demand = pwl_approximate(lambda p: 40.0 - p, (0.0, 100.0), 20, "min_power_demand")
    session = ConstraintSession()
    session.add_constraint(ConstraintSpec("thermal_runaway", approx_thermal, "le"))
    session.add_constraint(ConstraintSpec("min_power_demand", approx_demand, "le"))
    result = session.check()
    assert result.status == "unsat"
    assert "thermal_runaway" in result.unsat_core
    assert "min_power_demand" in result.unsat_core
    # Epsilon reports must accompany the UNSAT verdict (Section 34.2).
    assert len(result.epsilon_reports) == 2
