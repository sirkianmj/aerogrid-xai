"""Tests for the Tier 2 trajectory surrogate.

Roadmap task s5-3: Tier 2 surrogate - trajectory prediction.
Gate: Position error < 100 m at 30 s horizon.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.control.trajectory import (
    MIN_CALIBRATION_SIZE,
    TrajectoryEstimate,
    TrajectorySurrogate,
    UAVState,
    constant_velocity_predict,
    euclidean_distance,
)

# -- UAVState validation ----------------------------------------------------


def test_state_rejects_wrong_arity() -> None:
    with pytest.raises(ValueError, match="must be a 3-tuple"):
        UAVState(position_m=(1.0, 2.0), velocity_m_per_s=(0.0, 0.0, 0.0))  # type: ignore[arg-type]


def test_state_rejects_non_finite() -> None:
    with pytest.raises(ValueError, match="must be finite"):
        UAVState(
            position_m=(float("nan"), 0.0, 0.0),
            velocity_m_per_s=(0.0, 0.0, 0.0),
        )


def test_state_accepts_valid() -> None:
    s = UAVState(position_m=(0.0, 0.0, 100.0), velocity_m_per_s=(20.0, 0.0, 0.0))
    assert s.position_m == (0.0, 0.0, 100.0)


# -- constant_velocity_predict ----------------------------------------------


def test_predict_rejects_zero_horizon() -> None:
    s = UAVState(position_m=(0.0, 0.0, 0.0), velocity_m_per_s=(1.0, 0.0, 0.0))
    with pytest.raises(ValueError, match="horizon_s must be > 0"):
        constant_velocity_predict(s, 0.0)


def test_predict_rejects_negative_horizon() -> None:
    s = UAVState(position_m=(0.0, 0.0, 0.0), velocity_m_per_s=(1.0, 0.0, 0.0))
    with pytest.raises(ValueError, match="horizon_s must be > 0"):
        constant_velocity_predict(s, -1.0)


def test_predict_straight_line() -> None:
    s = UAVState(position_m=(0.0, 0.0, 0.0), velocity_m_per_s=(10.0, 0.0, 0.0))
    p = constant_velocity_predict(s, 30.0)
    assert p == (300.0, 0.0, 0.0)


def test_predict_3d_motion() -> None:
    s = UAVState(position_m=(100.0, 200.0, 300.0), velocity_m_per_s=(5.0, -2.0, 1.0))
    p = constant_velocity_predict(s, 10.0)
    assert p == (150.0, 180.0, 310.0)


# -- euclidean_distance -----------------------------------------------------


def test_distance_zero() -> None:
    assert euclidean_distance((1.0, 2.0, 3.0), (1.0, 2.0, 3.0)) == 0.0


def test_distance_axis_aligned() -> None:
    assert euclidean_distance((0.0, 0.0, 0.0), (3.0, 0.0, 0.0)) == pytest.approx(3.0)


def test_distance_3_4_5() -> None:
    assert euclidean_distance((0.0, 0.0, 0.0), (3.0, 4.0, 0.0)) == pytest.approx(5.0)


# -- TrajectoryEstimate -----------------------------------------------------


def test_estimate_rejects_negative_radius() -> None:
    with pytest.raises(ValueError, match="radius_m must be finite and non-negative"):
        TrajectoryEstimate(
            position_m=(0.0, 0.0, 0.0),
            radius_m=-1.0,
            horizon_s=30.0,
            nominal_coverage=0.9,
            model_name="m",
        )


def test_estimate_rejects_bad_horizon() -> None:
    with pytest.raises(ValueError, match="horizon_s must be finite and positive"):
        TrajectoryEstimate(
            position_m=(0.0, 0.0, 0.0),
            radius_m=1.0,
            horizon_s=0.0,
            nominal_coverage=0.9,
            model_name="m",
        )


def test_estimate_contains_inside_and_outside() -> None:
    e = TrajectoryEstimate(
        position_m=(0.0, 0.0, 0.0),
        radius_m=10.0,
        horizon_s=30.0,
        nominal_coverage=0.9,
        model_name="m",
    )
    assert e.contains((5.0, 0.0, 0.0))
    assert e.contains((10.0, 0.0, 0.0))
    assert not e.contains((11.0, 0.0, 0.0))


# -- Surrogate state --------------------------------------------------------


def test_surrogate_is_uncalibrated_initially() -> None:
    s = TrajectorySurrogate()
    assert not s.is_calibrated
    assert s.calibration_size == 0


def test_surrogate_raises_before_calibration() -> None:
    s = TrajectorySurrogate()
    state = UAVState(position_m=(0.0, 0.0, 0.0), velocity_m_per_s=(10.0, 0.0, 0.0))
    with pytest.raises(RuntimeError, match="before calibrate"):
        s.estimate_trajectory(state, 30.0)


def test_surrogate_calibrate_rejects_mismatch() -> None:
    s = TrajectorySurrogate()
    with pytest.raises(ValueError, match="same length"):
        s.calibrate(
            calibration_states=[
                UAVState(position_m=(0.0, 0.0, 0.0), velocity_m_per_s=(1.0, 0.0, 0.0))
            ]
            * 20,
            calibration_true_positions=[(0.0, 0.0, 0.0)] * 10,
            horizon_s=30.0,
        )


def test_surrogate_calibrate_rejects_too_small() -> None:
    s = TrajectorySurrogate()
    n = MIN_CALIBRATION_SIZE - 1
    with pytest.raises(ValueError, match="at least"):
        s.calibrate(
            calibration_states=[
                UAVState(position_m=(0.0, 0.0, 0.0), velocity_m_per_s=(1.0, 0.0, 0.0))
            ]
            * n,
            calibration_true_positions=[(0.0, 0.0, 0.0)] * n,
            horizon_s=30.0,
        )


def test_surrogate_calibrate_rejects_bad_coverage() -> None:
    s = TrajectorySurrogate()
    with pytest.raises(ValueError, match="nominal_coverage must be in"):
        s.calibrate(
            calibration_states=[
                UAVState(position_m=(0.0, 0.0, 0.0), velocity_m_per_s=(1.0, 0.0, 0.0))
            ]
            * 20,
            calibration_true_positions=[(0.0, 0.0, 0.0)] * 20,
            horizon_s=30.0,
            nominal_coverage=1.5,
        )


def test_surrogate_calibrate_rejects_bad_horizon() -> None:
    s = TrajectorySurrogate()
    with pytest.raises(ValueError, match="horizon_s must be > 0"):
        s.calibrate(
            calibration_states=[
                UAVState(position_m=(0.0, 0.0, 0.0), velocity_m_per_s=(1.0, 0.0, 0.0))
            ]
            * 20,
            calibration_true_positions=[(0.0, 0.0, 0.0)] * 20,
            horizon_s=0.0,
        )


def test_surrogate_estimate_is_deterministic() -> None:
    rng = np.random.default_rng(0)
    states = _sample_states(rng, 100)
    true_pos = _true_positions(states, 30.0, rng)
    s = TrajectorySurrogate()
    s.calibrate(states, true_pos, horizon_s=30.0)
    state = UAVState(position_m=(0.0, 0.0, 100.0), velocity_m_per_s=(20.0, 0.0, 0.0))
    e1 = s.estimate_trajectory(state, 30.0)
    e2 = s.estimate_trajectory(state, 30.0)
    assert e1 == e2


# -- Synthetic trajectory generation ----------------------------------------


def _sample_states(rng: np.random.Generator, n: int) -> list[UAVState]:
    """Return n UAV states with speeds around 20 m/s."""
    states: list[UAVState] = []
    for _ in range(n):
        speed = rng.uniform(15.0, 25.0)
        heading = rng.uniform(0.0, 2.0 * math.pi)
        vx = speed * math.cos(heading)
        vy = speed * math.sin(heading)
        states.append(
            UAVState(
                position_m=(
                    float(rng.uniform(-500.0, 500.0)),
                    float(rng.uniform(-500.0, 500.0)),
                    float(rng.uniform(50.0, 300.0)),
                ),
                velocity_m_per_s=(vx, vy, 0.0),
            )
        )
    return states


def _true_positions(
    states: list[UAVState],
    horizon_s: float,
    rng: np.random.Generator,
    turn_rate_rad_per_s: float = 0.005,
) -> list[tuple[float, float, float]]:
    """Return true positions at t = horizon_s.

    The ground truth is a constant-turn trajectory: the UAV flies at
    constant speed but its heading rotates at ``turn_rate_rad_per_s``
    around the vertical axis. The point predictor ignores the turn,
    so a systematic residual accumulates over the horizon. Gaussian
    position noise of 5 m is added.
    """
    truth: list[tuple[float, float, float]] = []
    for s in states:
        px, py, pz = s.position_m
        vx, vy, vz = s.velocity_m_per_s
        speed = math.hypot(vx, vy)
        heading = math.atan2(vy, vx)
        omega = turn_rate_rad_per_s
        # Integrate constant-turn kinematics analytically.
        # x(t) = x0 + (v/omega) * (sin(heading + omega*t) - sin(heading))
        # y(t) = y0 - (v/omega) * (cos(heading + omega*t) - cos(heading))
        r = speed / omega
        new_heading = heading + omega * horizon_s
        tx = px + r * (math.sin(new_heading) - math.sin(heading))
        ty = py - r * (math.cos(new_heading) - math.cos(heading))
        tz = pz + vz * horizon_s
        noise = rng.normal(0.0, 5.0, size=3)
        truth.append((tx + float(noise[0]), ty + float(noise[1]), tz + float(noise[2])))
    return truth


# -- Gate -------------------------------------------------------------------


def test_gate_mean_position_error_under_100m_at_30s() -> None:
    """The s5-3 gate, first form: the mean point-prediction error at
    a 30 s horizon is under 100 m on the holdout set."""
    rng = np.random.default_rng(20261009)
    cal_states = _sample_states(rng, 300)
    cal_true = _true_positions(cal_states, 30.0, rng)
    test_states = _sample_states(rng, 200)
    test_true = _true_positions(test_states, 30.0, rng)

    s = TrajectorySurrogate()
    s.calibrate(cal_states, cal_true, horizon_s=30.0, nominal_coverage=0.90)

    errors = [
        euclidean_distance(
            s.estimate_trajectory(st, 30.0).position_m,
            tp,
        )
        for st, tp in zip(test_states, test_true, strict=True)
    ]
    mean_error = sum(errors) / len(errors)
    print(f"Mean position error at 30 s: {mean_error:.2f} m (gate 100 m)")
    assert mean_error < 100.0, f"Mean position error {mean_error:.2f} m exceeds 100 m gate"


def test_gate_90pct_coverage_at_least_85pct() -> None:
    """The s5-3 gate, second form: the conformal ball covers the true
    position at >= 85 percent of holdout points."""
    rng = np.random.default_rng(20261009)
    cal_states = _sample_states(rng, 300)
    cal_true = _true_positions(cal_states, 30.0, rng)
    test_states = _sample_states(rng, 200)
    test_true = _true_positions(test_states, 30.0, rng)

    s = TrajectorySurrogate()
    s.calibrate(cal_states, cal_true, horizon_s=30.0, nominal_coverage=0.90)

    covered = sum(
        1
        for st, tp in zip(test_states, test_true, strict=True)
        if s.estimate_trajectory(st, 30.0).contains(tp)
    )
    coverage = covered / len(test_states)
    print(f"Holdout coverage: {coverage:.3f} (nominal 0.90, gate 0.85)")
    assert coverage >= 0.85


def test_average_coverage_over_20_seeds() -> None:
    """Stronger check: mean coverage over 20 independent splits."""
    coverages: list[float] = []
    for seed in range(20):
        rng = np.random.default_rng(seed)
        cal_states = _sample_states(rng, 200)
        cal_true = _true_positions(cal_states, 30.0, rng)
        test_states = _sample_states(rng, 100)
        test_true = _true_positions(test_states, 30.0, rng)

        s = TrajectorySurrogate()
        s.calibrate(cal_states, cal_true, horizon_s=30.0, nominal_coverage=0.90)
        covered = sum(
            1
            for st, tp in zip(test_states, test_true, strict=True)
            if s.estimate_trajectory(st, 30.0).contains(tp)
        )
        coverages.append(covered / len(test_states))

    mean_cov = sum(coverages) / len(coverages)
    print(
        f"Mean coverage over 20 seeds: {mean_cov:.3f} "
        f"(min {min(coverages):.3f}, max {max(coverages):.3f})"
    )
    assert mean_cov >= 0.85
