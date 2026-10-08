"""Tests for the PWL over-approximation builder and the error tracker.

Roadmap tasks:
    s3-1 PWL approximation builder.
        Gate: SOund over-approximation, f_hat <= f everywhere on range.
    s3-2 Error tracker (epsilon per constraint family).
        Gate: epsilon reported alongside every verification result.
"""

from __future__ import annotations

import math

import pytest

from app.physics.receiver import eta_plc
from app.verification.pwl import (
    ErrorTracker,
    PWLApproximation,
    PWLSegment,
    pwl_approximate,
    verify_lower_bound,
)


def _exp_decay(x: float) -> float:
    return math.exp(-x)


def _sqrt_positive(x: float) -> float:
    return math.sqrt(max(x, 1e-12))


def _quadratic(x: float) -> float:
    return x * x


def _linear(x: float) -> float:
    return 2.0 * x + 1.0


# s3-1: PWL approximation builder


def test_pwl_returns_approximation_with_family_name() -> None:
    approx = pwl_approximate(_quadratic, (0.0, 1.0), 5, "quadratic")
    assert isinstance(approx, PWLApproximation)
    assert approx.family_name == "quadratic"
    assert len(approx.segments) == 5
    assert approx.x_min == 0.0
    assert approx.x_max == 1.0


def test_pwl_is_lower_bound_on_convex_function() -> None:
    approx = pwl_approximate(_exp_decay, (0.0, 5.0), 20, "exp_decay")
    verify_lower_bound(approx, _exp_decay)


def test_pwl_is_lower_bound_on_concave_function() -> None:
    approx = pwl_approximate(_sqrt_positive, (0.01, 4.0), 20, "sqrt_root")
    verify_lower_bound(approx, _sqrt_positive)


def test_pwl_is_lower_bound_on_linear_function() -> None:
    approx = pwl_approximate(_linear, (0.0, 10.0), 20, "linear_test")
    verify_lower_bound(approx, _linear)


def test_pwl_epsilon_decreases_with_more_segments() -> None:
    e10 = pwl_approximate(_exp_decay, (0.0, 5.0), 10, "e10").epsilon
    e20 = pwl_approximate(_exp_decay, (0.0, 5.0), 20, "e20").epsilon
    e40 = pwl_approximate(_exp_decay, (0.0, 5.0), 40, "e40").epsilon
    assert e20 < e10
    assert e40 < e20
    assert e40 > 0.0


def test_pwl_on_constant_function_has_zero_epsilon() -> None:
    approx = pwl_approximate(lambda x: 7.5, (0.0, 5.0), 5, "constant")
    assert approx.epsilon == pytest.approx(0.0, abs=1e-12)


def test_pwl_on_eta_plc_has_small_epsilon() -> None:
    """eta_plc is linear in temperature over [280, 350] K. With a
    constant-per-segment approximation, the per-segment error is bounded
    by (segment width) * |d eta_plc / dT| = 7 * 3.75e-4 = 2.6e-3."""
    approx = pwl_approximate(eta_plc, (280.0, 350.0), 10, "eta_plc_temperature")
    assert 0.0 < approx.epsilon < 0.003


def test_pwl_on_eta_plc_with_many_segments_has_tiny_epsilon() -> None:
    approx = pwl_approximate(eta_plc, (280.0, 350.0), 200, "eta_plc_temperature")
    assert approx.epsilon < 2e-4


def test_pwl_evaluate_inside_domain() -> None:
    approx = pwl_approximate(_linear, (0.0, 10.0), 5, "identity")
    for x in (0.0, 2.5, 5.0, 7.5, 10.0):
        val = approx.evaluate(x)
        assert isinstance(val, float)
        assert val <= _linear(x) + 1e-9


def test_pwl_evaluate_outside_domain_raises() -> None:
    approx = pwl_approximate(_linear, (0.0, 10.0), 5, "identity")
    with pytest.raises(ValueError):
        approx.evaluate(-1.0)
    with pytest.raises(ValueError):
        approx.evaluate(11.0)


def test_pwl_rejects_inverted_range() -> None:
    with pytest.raises(ValueError):
        pwl_approximate(_linear, (10.0, 0.0), 5, "bad")


def test_pwl_rejects_zero_segments() -> None:
    with pytest.raises(ValueError):
        pwl_approximate(_linear, (0.0, 10.0), 0, "bad")


def test_pwl_rejects_bad_validation_samples() -> None:
    with pytest.raises(ValueError):
        pwl_approximate(
            _linear,
            (0.0, 10.0),
            5,
            "bad",
            n_validation_samples=1,
        )


def test_pwl_segment_evaluate() -> None:
    seg = PWLSegment(x_lo=0.0, x_hi=1.0, slope=2.0, intercept=3.0)
    assert seg.evaluate(0.0) == 3.0
    assert seg.evaluate(0.5) == 4.0
    assert seg.evaluate(1.0) == 5.0


def test_pwl_is_lower_bound_at_method() -> None:
    approx = pwl_approximate(_exp_decay, (0.0, 3.0), 10, "exp")
    for x in (0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0):
        assert approx.is_lower_bound_at(x, _exp_decay)


def test_pwl_rejects_missing_segment() -> None:
    approx = pwl_approximate(_linear, (0.0, 10.0), 5, "identity")
    with pytest.raises(ValueError):
        approx.evaluate(float("nan"))


# s3-2: Error tracker


def test_error_tracker_empty() -> None:
    tracker = ErrorTracker()
    assert tracker.reports() == ()
    assert tracker.max_epsilon() == 0.0
    assert tracker.summary() == "(no constraint families tracked)"


def test_error_tracker_add_and_report() -> None:
    tracker = ErrorTracker()
    approx = pwl_approximate(_exp_decay, (0.0, 5.0), 10, "exp_decay")
    tracker.add(approx)
    reports = tracker.reports()
    assert len(reports) == 1
    assert reports[0].family_name == "exp_decay"
    assert reports[0].epsilon == approx.epsilon


def test_error_tracker_rejects_duplicate_family() -> None:
    tracker = ErrorTracker()
    approx = pwl_approximate(_linear, (0.0, 1.0), 5, "dup")
    tracker.add(approx)
    with pytest.raises(ValueError):
        tracker.add(approx)


def test_error_tracker_max_epsilon() -> None:
    tracker = ErrorTracker()
    approx_small = pwl_approximate(lambda x: 1.0, (0.0, 1.0), 5, "constant")
    approx_large = pwl_approximate(_exp_decay, (0.0, 5.0), 4, "exp_coarse")
    tracker.add(approx_small)
    tracker.add(approx_large)
    assert tracker.max_epsilon() == pytest.approx(approx_large.epsilon, rel=1e-12)


def test_error_tracker_summary_format() -> None:
    tracker = ErrorTracker()
    approx = pwl_approximate(_linear, (0.0, 1.0), 5, "identity")
    tracker.add(approx)
    summary = tracker.summary()
    assert "identity" in summary
    assert "epsilon" in summary
    assert "max epsilon" in summary


def test_error_tracker_with_two_families() -> None:
    """Exercise the tracker with two distinct constraint families, as
    required by Section 34.2 for the per-family epsilon report."""
    tracker = ErrorTracker()
    approx_plc = pwl_approximate(eta_plc, (280.0, 350.0), 10, "eta_plc_temperature")
    approx_decay = pwl_approximate(_exp_decay, (0.0, 5.0), 20, "pmax_boundary_shape")
    tracker.add(approx_plc)
    tracker.add(approx_decay)
    reports = tracker.reports()
    assert len(reports) == 2
    names = {r.family_name for r in reports}
    assert names == {"eta_plc_temperature", "pmax_boundary_shape"}
    assert tracker.max_epsilon() > 0.0


def test_error_tracker_summary_multiline() -> None:
    tracker = ErrorTracker()
    tracker.add(pwl_approximate(_linear, (0.0, 1.0), 5, "family_a"))
    tracker.add(pwl_approximate(_linear, (0.0, 1.0), 5, "family_b"))
    summary = tracker.summary()
    assert summary.count(chr(10)) == 2
