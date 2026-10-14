"""Sensitivity of delivered UAV power to each configurable parameter.

Section 22 of the specification lists sensitivity analysis as a
capability: rank which variables matter most for the outcome of
interest. For this platform the outcome of interest is the electrical
power delivered to the UAV battery. This module computes a
dimensionless elasticity of that quantity with respect to each
configurable parameter by finite differences on the mission-state
computation.

Elasticity E is the fractional change in delivered power per
fractional change in the parameter:

    E_i = (dP / dx_i) * (x_i / P)

E is dimensionless and comparable across parameters of different
units. E = 1 means "a 1% increase in this parameter gives a 1%
increase in delivered power" (linear coupling, as the cascade's
transmitter stage implies). E = -0.5 means "a 1% increase in this
parameter gives a 0.5% decrease in power".

For parameters whose base is zero (cloud_factor default is 0.0),
the relative form is undefined. Those are perturbed by an absolute
amount and only the absolute derivative is reported.

This module does not run CLEAR-D or Z3 verification on the perturbed
configs; delivered power depends only on the geometry, atmosphere,
and receiver. Skipping the expensive architecture step makes the
whole sensitivity analysis finish in seconds rather than minutes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from app.mission.state import (
    MissionConfig,
    compute_mission_state,
)


# Parameters varied by the analysis. Each is a (name, setter, getter)
# triple where setter returns a new MissionConfig with the parameter
# replaced. Only continuous parameters are included; the receiver-type
# enum is compared separately, and latitude/longitude are held fixed
# (moving the ground station changes the entire mission geometry, not
# a single knob).
def _param_transmitter_power(c: MissionConfig) -> float:
    return c.transmitter_power_w


def _set_transmitter_power(c: MissionConfig, v: float) -> MissionConfig:
    return replace(c, transmitter_power_w=v)


def _param_transmitter_aperture(c: MissionConfig) -> float:
    return c.transmitter_aperture_m


def _set_transmitter_aperture(c: MissionConfig, v: float) -> MissionConfig:
    return replace(c, transmitter_aperture_m=v)


def _param_uav_alt(c: MissionConfig) -> float:
    return c.uav_alt_m


def _set_uav_alt(c: MissionConfig, v: float) -> MissionConfig:
    return replace(c, uav_alt_m=v)


def _param_visibility(c: MissionConfig) -> float:
    return c.visibility_km


def _set_visibility(c: MissionConfig, v: float) -> MissionConfig:
    return replace(c, visibility_km=v)


def _param_cloud(c: MissionConfig) -> float:
    return c.cloud_factor


def _set_cloud(c: MissionConfig, v: float) -> MissionConfig:
    return replace(c, cloud_factor=v)


def _param_receiver_aperture(c: MissionConfig) -> float:
    return c.uav_hardware.receiver_aperture_m2


def _set_receiver_aperture(c: MissionConfig, v: float) -> MissionConfig:
    return replace(c, uav_hardware=replace(c.uav_hardware, receiver_aperture_m2=v))


def _param_wavelength(c: MissionConfig) -> float:
    return c.wavelength_nm


def _set_wavelength(c: MissionConfig, v: float) -> MissionConfig:
    return replace(c, wavelength_nm=v)


_PARAMS: tuple[
    tuple[str, Callable[[MissionConfig], float], Callable[[MissionConfig, float], MissionConfig]],
    ...,
] = (
    ("transmitter_power_w", _param_transmitter_power, _set_transmitter_power),
    ("transmitter_aperture_m", _param_transmitter_aperture, _set_transmitter_aperture),
    ("uav_alt_m", _param_uav_alt, _set_uav_alt),
    ("visibility_km", _param_visibility, _set_visibility),
    ("cloud_factor", _param_cloud, _set_cloud),
    ("uav_receiver_aperture_m2", _param_receiver_aperture, _set_receiver_aperture),
    ("wavelength_nm", _param_wavelength, _set_wavelength),
)


@dataclass(frozen=True)
class ParameterSensitivity:
    """Result for one parameter."""

    name: str
    base_value: float
    low_value: float
    high_value: float
    power_at_low_w: float
    power_at_high_w: float
    derivative_w_per_unit: float
    elasticity: float | None
    direction: str  # "increase" | "decrease" | "flat"


@dataclass(frozen=True)
class SensitivityReport:
    """Full sensitivity analysis for one base config."""

    base_delivered_power_w: float
    base_sat_verdict: str
    parameters: tuple[ParameterSensitivity, ...]


def _sum_delivered_power(cfg: MissionConfig) -> tuple[float, str]:
    """Return (sum of delivered power across UAVs, sat verdict).

    The verdict is informational and only meaningful for the base
    config; perturbed configs use the same architecture selection so
    their verdict equals the base's by construction. The base call is
    the only one that runs the encoder.
    """
    state = compute_mission_state(cfg)
    total = sum(u.delivered_power_w for u in state.uavs)
    return total, state.architecture.sat_verdict


def compute_sensitivity(
    cfg: MissionConfig,
    *,
    perturb_fraction: float = 0.10,
) -> SensitivityReport:
    """Return sensitivities of delivered power to each parameter.

    Perturbation: relative ±perturb_fraction for parameters with a
    non-zero base; absolute ±0.05 for zero-base parameters
    (cloud_factor).

    Derivative uses a central difference:
        dP/dx = (P(x+h) - P(x-h)) / (2h)

    Elasticity uses the central estimate of the log-log derivative:
        E = (dP/dx) * (x_base / P_base)
    """
    if not 0.0 < perturb_fraction < 1.0:
        raise ValueError(f"perturb_fraction must be in (0, 1); got {perturb_fraction}")

    base_power, base_verdict = _sum_delivered_power(cfg)

    results: list[ParameterSensitivity] = []
    for name, getter, setter in _PARAMS:
        base_val = getter(cfg)
        if base_val == 0.0:
            # Zero-base: absolute perturbation.
            h = 0.05
            low = base_val - h
            high = base_val + h
        else:
            h = base_val * perturb_fraction
            low = base_val - h
            high = base_val + h

        # Clamp to physically representable values where needed. A
        # negative transmitter power or wavelength is invalid; a
        # negative cloud_factor is invalid.
        if (
            name
            in {
                "transmitter_power_w",
                "transmitter_aperture_m",
                "uav_alt_m",
                "visibility_km",
                "uav_receiver_aperture_m2",
                "wavelength_nm",
            }
            and low <= 0.0
        ):
            # Shift the window so both samples are positive; use the
            # base value as the upper bound.
            low = base_val * 0.5
            high = base_val * 1.5
            h = base_val * 0.5
        if name == "cloud_factor":
            low = max(0.0, low)
            high = min(1.0, high)
            h = (high - low) / 2.0

        if h <= 0.0:
            # Parameter cannot be perturbed; report flat.
            results.append(
                ParameterSensitivity(
                    name=name,
                    base_value=base_val,
                    low_value=base_val,
                    high_value=base_val,
                    power_at_low_w=base_power,
                    power_at_high_w=base_power,
                    derivative_w_per_unit=0.0,
                    elasticity=None,
                    direction="flat",
                )
            )
            continue

        power_low, _ = _sum_delivered_power(setter(cfg, low))
        power_high, _ = _sum_delivered_power(setter(cfg, high))

        derivative = (power_high - power_low) / (high - low)

        elasticity: float | None
        if base_power != 0.0 and base_val != 0.0:
            elasticity = derivative * (base_val / base_power)
        else:
            elasticity = None

        if abs(derivative) < 1e-12:
            direction = "flat"
        elif derivative > 0.0:
            direction = "increase"
        else:
            direction = "decrease"

        results.append(
            ParameterSensitivity(
                name=name,
                base_value=base_val,
                low_value=low,
                high_value=high,
                power_at_low_w=power_low,
                power_at_high_w=power_high,
                derivative_w_per_unit=derivative,
                elasticity=elasticity,
                direction=direction,
            )
        )

    # Rank by |elasticity| where available, else |derivative| scaled.
    def rank_key(p: ParameterSensitivity) -> float:
        if p.elasticity is not None:
            return -abs(p.elasticity)
        # For parameters without elasticity (base zero), rank using
        # the derivative magnitude as a fallback.
        return -abs(p.derivative_w_per_unit)

    ordered = tuple(sorted(results, key=rank_key))

    return SensitivityReport(
        base_delivered_power_w=base_power,
        base_sat_verdict=base_verdict,
        parameters=ordered,
    )
