"""Tier 2 trajectory surrogate with conformal calibration.

Roadmap task s5-3: Tier 2 surrogate - trajectory prediction.
Gate: Position error < 100 m at 30 s horizon.

Reference:
    AeroGrid-XAI Final Comprehensive Specification (Rev. 6),
    Section 18 (Predictive Beam Tracking), Section 15.3 (Tier 2
    model classes), Section 17 (Uncertainty-Aware AI).

Model
-----

Point predictor: constant-velocity extrapolation from a UAV state
(position and velocity in metres and metres per second) to a future
time. This is the standard first-order predictor for beam pointing
under Section 18: a UAV with a commanded heading maintains it over
short horizons, and any sustained acceleration is captured as
residual uncertainty rather than as a fitted model term.

Uncertainty: split conformal, identical in method to the atmospheric
surrogate in tier2.py. Calibration residuals are the Euclidean
position error at a specified horizon; the conformal quantile is a
scalar radius such that the true position lies within that radius of
the point prediction with the nominal probability. Because the
underlying model ignores turning, the residual distribution has a
heavy tail for manoeuvring UAVs; conformal handles that without any
distributional assumption.

Interface (Section 15.3)
------------------------

Tier 2 modules expose estimate_* functions returning a value plus
an uncertainty interval. For a 3D position, the value is a 3-tuple
in metres and the interval is a scalar radius in metres, giving a
closed ball centred on the point prediction. This shape is captured
by TrajectoryEstimate.

The static analyzer in s5-4 verifies that no estimate_* function in
this module reaches any decide_* function.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

MIN_CALIBRATION_SIZE = 10

Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class UAVState:
    """UAV kinematic state at a reference time.

    Attributes:
        position_m: (x, y, z) position in metres.
        velocity_m_per_s: (vx, vy, vz) velocity in metres per second.
    """

    position_m: Vec3
    velocity_m_per_s: Vec3

    def __post_init__(self) -> None:
        for name, values in (
            ("position_m", self.position_m),
            ("velocity_m_per_s", self.velocity_m_per_s),
        ):
            if len(values) != 3:
                raise ValueError(f"{name} must be a 3-tuple; got {values}")
            for i, v in enumerate(values):
                if not math.isfinite(v):
                    raise ValueError(f"{name}[{i}] must be finite; got {v}")


@dataclass(frozen=True)
class TrajectoryEstimate:
    """A Tier 2 trajectory prediction.

    Attributes:
        position_m: Predicted (x, y, z) position in metres.
        radius_m: Conformal uncertainty radius in metres. The true
            position is claimed to lie within this radius of the
            prediction with the nominal coverage probability. The
            claim is a finite-sample guarantee under exchangeability
            between calibration and deployment trajectories.
        horizon_s: The prediction horizon in seconds.
        nominal_coverage: The coverage probability the calibration
            aimed for.
        model_name: Always "trajectory_surrogate_conformal" for this
            class.
    """

    position_m: Vec3
    radius_m: float
    horizon_s: float
    nominal_coverage: float
    model_name: str

    def __post_init__(self) -> None:
        if not math.isfinite(self.radius_m) or self.radius_m < 0.0:
            raise ValueError(f"radius_m must be finite and non-negative; got {self.radius_m}")
        if not math.isfinite(self.horizon_s) or self.horizon_s <= 0.0:
            raise ValueError(f"horizon_s must be finite and positive; got {self.horizon_s}")
        if not 0.0 < self.nominal_coverage < 1.0:
            raise ValueError(f"nominal_coverage must be in (0, 1); got {self.nominal_coverage}")
        if not self.model_name:
            raise ValueError("model_name must be non-empty")

    def contains(self, position_m: Vec3) -> bool:
        """True iff the point lies inside the uncertainty ball."""
        return euclidean_distance(self.position_m, position_m) <= self.radius_m


def euclidean_distance(a: Vec3, b: Vec3) -> float:
    """Return the Euclidean distance between two 3D points in metres."""
    return float(math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2))


def constant_velocity_predict(state: UAVState, horizon_s: float) -> Vec3:
    """Return the constant-velocity extrapolation of a UAV state.

    Args:
        state: Initial UAV state.
        horizon_s: Prediction horizon in seconds. Must be > 0.

    Returns:
        Predicted position in metres.
    """
    if not math.isfinite(horizon_s) or horizon_s <= 0.0:
        raise ValueError(f"horizon_s must be > 0; got {horizon_s}")
    p = state.position_m
    v = state.velocity_m_per_s
    return (p[0] + v[0] * horizon_s, p[1] + v[1] * horizon_s, p[2] + v[2] * horizon_s)


class TrajectorySurrogate:
    """Tier 2 trajectory surrogate with conformal calibration.

    Usage:

        s = TrajectorySurrogate()
        s.calibrate(cal_states, cal_true_positions, horizon_s=30.0)
        est = s.estimate_trajectory(state, horizon_s=30.0)
        # est.position_m, est.radius_m

    The surrogate must be calibrated before estimate_trajectory is
    called. Calling before calibration raises RuntimeError.
    """

    def __init__(self) -> None:
        self._residual_quantile: float | None = None
        self._nominal_coverage: float | None = None
        self._calibration_size: int = 0

    @property
    def is_calibrated(self) -> bool:
        return self._residual_quantile is not None

    @property
    def calibration_size(self) -> int:
        return self._calibration_size

    @property
    def residual_quantile(self) -> float:
        if self._residual_quantile is None:
            raise RuntimeError("trajectory surrogate is not calibrated")
        return self._residual_quantile

    def calibrate(
        self,
        calibration_states: Sequence[UAVState],
        calibration_true_positions: Sequence[Vec3],
        horizon_s: float,
        nominal_coverage: float = 0.90,
    ) -> None:
        """Fit the conformal radius on a calibration set.

        Args:
            calibration_states: n UAV states at t = 0.
            calibration_true_positions: n actual positions at t = horizon_s.
            horizon_s: The prediction horizon used in calibration.
            nominal_coverage: Target coverage probability.

        Raises:
            ValueError on length mismatch, too-small set, bad inputs.
        """
        if len(calibration_states) != len(calibration_true_positions):
            raise ValueError(
                f"states and true positions must have the same length; "
                f"got {len(calibration_states)} vs "
                f"{len(calibration_true_positions)}"
            )
        n = len(calibration_states)
        if n < MIN_CALIBRATION_SIZE:
            raise ValueError(
                f"calibration set must have at least {MIN_CALIBRATION_SIZE} samples; got {n}"
            )
        if not 0.0 < nominal_coverage < 1.0:
            raise ValueError(f"nominal_coverage must be in (0, 1); got {nominal_coverage}")
        if not math.isfinite(horizon_s) or horizon_s <= 0.0:
            raise ValueError(f"horizon_s must be > 0; got {horizon_s}")

        residuals = np.empty(n, dtype=float)
        for i, (state, true_pos) in enumerate(
            zip(calibration_states, calibration_true_positions, strict=True)
        ):
            predicted = constant_velocity_predict(state, horizon_s)
            residuals[i] = euclidean_distance(predicted, true_pos)

        k = math.ceil((n + 1) * nominal_coverage)
        k = min(k, n)
        sorted_residuals = np.sort(residuals)
        self._residual_quantile = float(sorted_residuals[k - 1])
        self._nominal_coverage = nominal_coverage
        self._calibration_size = n

    def estimate_trajectory(self, state: UAVState, horizon_s: float) -> TrajectoryEstimate:
        """Return a predicted position and conformal uncertainty radius.

        Follows Section 15.3 Tier 2 naming: estimate_*(*) -> value
        plus uncertainty interval. For a 3D position the interval is
        a ball characterised by a scalar radius.

        Raises:
            RuntimeError: not calibrated.
            ValueError: invalid horizon.
        """
        if self._residual_quantile is None or self._nominal_coverage is None:
            raise RuntimeError(
                "TrajectorySurrogate.estimate_trajectory called before "
                "calibrate(); calibrate the surrogate first."
            )
        predicted = constant_velocity_predict(state, horizon_s)
        return TrajectoryEstimate(
            position_m=predicted,
            radius_m=self._residual_quantile,
            horizon_s=horizon_s,
            nominal_coverage=self._nominal_coverage,
            model_name="trajectory_surrogate_conformal",
        )
