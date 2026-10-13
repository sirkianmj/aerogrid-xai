"""Tier 2 atmospheric-loss surrogate with conformal calibration.

Roadmap task s5-2: Tier 2 surrogate - atmospheric loss.
Gate: Calibrated 90% CI coverage >= 85% on holdout.

Reference:
    AeroGrid-XAI Final Comprehensive Specification (Rev. 6),
    Section 15.3 (Tier 2 model classes), Section 17 (Uncertainty-Aware
    AI), Section 18 (Predictive Beam Tracking).

Point model: physics.atmosphere
-------------------------------

The point estimate is produced by app.physics.atmosphere.transmission,
which implements Beer-Lambert transmittance with a Kruse (1962) /
Kim et al. (2001) aerosol extinction model and configurable molecular
and cloud terms. That module is the single source of truth for
atmospheric transmittance across the platform. Before this rewire,
tier2.py carried its own duplicate parametric model with unsourced
coefficients; the duplication has been removed so that any change to
the atmospheric physics is made in one place.

The AtmosphereConfig accepted by this module is the same config type
that physics.atmosphere and physics.link_budget accept, so callers
can pass one config and have it take effect everywhere.

Uncertainty: split conformal prediction
---------------------------------------

Given n calibration pairs (X_i, Y_i), compute residuals
r_i = |f(X_i) - Y_i|, sort, and take the ceil((n+1)(1-alpha))-th
smallest residual as the conformal quantile q_hat. Under
exchangeability, for a fresh test point (X, Y),

    P(|f(X) - Y| <= q_hat) >= 1 - alpha

with no assumption about f being correct. The guarantee holds even if
the point model is systematically biased, which is what makes it
appropriate here: physics.atmosphere is a first-order approximation,
and its coefficients carry epistemic tags ([SOURCED] for the Kruse-Kim
aerosol term, [ESTIMATED] for the molecular and cloud terms). The
conformal layer absorbs the resulting bias without requiring the model
to be right.

Why not PyTorch: the calibration guarantee is a property of the
conformal wrapper, not of the point model. A neural network inside
the wrapper would not improve the coverage bound; it would only
change the interval widths, and only if the network out-performs
the parametric model on data we do not have in-repo. The interface
fixed by Section 15.3 is implementation-agnostic.

Interface convention (Section 15.3)
-----------------------------------

Tier 2 classes expose methods named estimate_* that return
(value, uncertainty_interval). In this module, AtmosphericSurrogate
exposes estimate_atmospheric_loss. The static analyzer in s5-4
relies on the naming convention to verify that no Tier 2 method is
reachable from the Tier 1 action interface.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from app.physics.atmosphere import AtmosphereConfig
from app.physics.atmosphere import transmission as atmospheric_transmission

Inputs = Mapping[str, float]

MIN_CALIBRATION_SIZE = 10
"""Below this size the conformal quantile is too coarse to be useful."""


@dataclass(frozen=True)
class UncertaintyInterval:
    """A closed interval with a nominal coverage probability.

    Attributes:
        low: Lower endpoint.
        high: Upper endpoint. Must be >= low.
        nominal_coverage: Target coverage probability in (0, 1). This
            is the coverage the calibration procedure aims for; the
            empirical coverage on a holdout set is a separate
            quantity and may differ by finite-sample noise.
    """

    low: float
    high: float
    nominal_coverage: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.low) or not math.isfinite(self.high):
            raise ValueError(f"interval endpoints must be finite; got [{self.low}, {self.high}]")
        if self.low > self.high:
            raise ValueError(f"low ({self.low}) must be <= high ({self.high})")
        if not 0.0 < self.nominal_coverage < 1.0:
            raise ValueError(f"nominal_coverage must be in (0, 1); got {self.nominal_coverage}")

    def contains(self, value: float) -> bool:
        return self.low <= value <= self.high

    def width(self) -> float:
        return self.high - self.low


@dataclass(frozen=True)
class Tier2Estimate:
    """A Tier 2 output: point estimate plus uncertainty interval.

    The tuple shape required by Section 15.3 is (value, interval);
    this dataclass is a typed wrapper around that pair.
    """

    value: float
    interval: UncertaintyInterval
    model_name: str

    def __post_init__(self) -> None:
        if not math.isfinite(self.value):
            raise ValueError(f"value must be finite; got {self.value}")
        if not self.interval.contains(self.value):
            raise ValueError(
                f"value {self.value} not inside interval "
                f"[{self.interval.low}, {self.interval.high}]"
            )
        if not self.model_name:
            raise ValueError("model_name must be non-empty")


class AtmosphericSurrogate:
    """Tier 2 atmospheric-loss surrogate with conformal calibration.

    The point model is app.physics.atmosphere.transmission. Calibration
    fits a split-conformal quantile on the residuals between the point
    model's predictions and observed transmission values. The quantile
    is the half-width of the uncertainty interval returned by
    estimate_atmospheric_loss.

    Usage:

        surrogate = AtmosphericSurrogate()
        surrogate.calibrate(inputs, targets, nominal_coverage=0.90)
        estimate = surrogate.estimate_atmospheric_loss({"wavelength_nm": 1064.0, ...})
        # estimate.value, estimate.interval.low, estimate.interval.high

    The surrogate must be calibrated before estimate_atmospheric_loss
    is called. Calling estimate_atmospheric_loss on an uncalibrated
    instance raises RuntimeError, which is a programming error, not a
    data error.
    """

    def __init__(self, config: AtmosphereConfig | None = None) -> None:
        self._config = config if config is not None else AtmosphereConfig()
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
            raise RuntimeError("surrogate is not calibrated")
        return self._residual_quantile

    def _predict(self, inputs: Inputs) -> float:
        """Evaluate the physics.atmosphere point model on one input mapping."""
        try:
            return atmospheric_transmission(
                wavelength_nm=float(inputs["wavelength_nm"]),
                path_length_m=float(inputs["path_m"]),
                visibility_km=float(inputs["visibility_km"]),
                cloud_factor=float(inputs["cloud_factor"]),
                config=self._config,
            )
        except KeyError as exc:
            raise ValueError(f"missing input key {exc}") from exc

    def calibrate(
        self,
        calibration_inputs: Sequence[Inputs],
        calibration_targets: Sequence[float],
        nominal_coverage: float = 0.90,
    ) -> None:
        """Fit the conformal quantile on a calibration set.

        Args:
            calibration_inputs: n input mappings.
            calibration_targets: n target values in [0, 1].
            nominal_coverage: Desired coverage probability.

        Raises:
            ValueError: length mismatch, empty or too-small set,
                invalid nominal coverage, or non-finite target.
        """
        if len(calibration_inputs) != len(calibration_targets):
            raise ValueError(
                f"inputs and targets must have the same length; got "
                f"{len(calibration_inputs)} vs {len(calibration_targets)}"
            )
        n = len(calibration_inputs)
        if n < MIN_CALIBRATION_SIZE:
            raise ValueError(
                f"calibration set must have at least {MIN_CALIBRATION_SIZE} samples; got {n}"
            )
        if not 0.0 < nominal_coverage < 1.0:
            raise ValueError(f"nominal_coverage must be in (0, 1); got {nominal_coverage}")

        residuals = np.empty(n, dtype=float)
        for i, (inp, tgt) in enumerate(zip(calibration_inputs, calibration_targets, strict=True)):
            target_float = float(tgt)
            if not math.isfinite(target_float):
                raise ValueError(f"calibration target {i} is not finite: {tgt}")
            residuals[i] = abs(self._predict(inp) - target_float)

        # Split conformal finite-sample corrected quantile.
        # k = ceil((n+1) * coverage), capped at n when the requested
        # coverage is so high that the guarantee cannot be met with
        # finite samples; in that case we use the maximum residual.
        k = math.ceil((n + 1) * nominal_coverage)
        k = min(k, n)
        sorted_residuals = np.sort(residuals)
        self._residual_quantile = float(sorted_residuals[k - 1])
        self._nominal_coverage = nominal_coverage
        self._calibration_size = n

    def estimate_atmospheric_loss(self, inputs: Inputs) -> Tier2Estimate:
        """Return a point estimate and calibrated uncertainty interval.

        Follows the Section 15.3 Tier 2 naming convention
        estimate_*(*) -> (value, uncertainty_interval).

        The interval is [value - q_hat, value + q_hat] clamped to
        [0, 1], where q_hat is the conformal quantile from the
        calibration set and value is physics.atmosphere's transmission.

        Raises:
            RuntimeError: if the surrogate has not been calibrated.
            ValueError: if required input keys are missing.
        """
        if self._residual_quantile is None or self._nominal_coverage is None:
            raise RuntimeError(
                "AtmosphericSurrogate.estimate_atmospheric_loss called "
                "before calibrate(); calibrate the surrogate first."
            )
        value = self._predict(inputs)
        q = self._residual_quantile
        low = max(0.0, value - q)
        high = min(1.0, value + q)
        interval = UncertaintyInterval(
            low=low,
            high=high,
            nominal_coverage=self._nominal_coverage,
        )
        return Tier2Estimate(
            value=value,
            interval=interval,
            model_name="atmospheric_surrogate_conformal",
        )
