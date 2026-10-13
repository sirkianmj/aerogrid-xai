"""Cascaded link-budget model for wireless power transmission.

Implements the multiplicative stage decomposition required by Section 8.4 of
the AeroGrid-XAI Final Comprehensive Specification (Rev. 6). Every stage is
tracked as a separate factor so the end-to-end wall-plug-to-battery efficiency
is always the product of the individual stages, never a collapsed single
number.

Reference:
    AeroGrid-XAI Final Comprehensive Specification (Rev. 6),
    Section 8.4 "Link Budget Calculation - Dual Efficiency Reporting Required".
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.physics import atmosphere as _atmosphere
from app.physics import beam as _beam


@dataclass(frozen=True)
class Stage:
    """A single multiplicative stage in the cascaded link budget.

    Attributes:
        name: Human-readable stage name.
        efficiency: Dimensionless efficiency in [0, 1].
        source: Optional source citation or epistemic tag.
    """

    name: str
    efficiency: float
    source: str = ""

    def __post_init__(self) -> None:
        if not 0.0 <= self.efficiency <= 1.0:
            raise ValueError(
                f"Stage '{self.name}' efficiency must be in [0, 1]; got {self.efficiency}"
            )


@dataclass(frozen=True)
class LinkBudget:
    """Full cascaded link budget from transmitter input to battery output."""

    input_power_w: float
    stages: tuple[Stage, ...]
    notes: str = ""

    @property
    def end_to_end_efficiency(self) -> float:
        eff = 1.0
        for s in self.stages:
            eff *= s.efficiency
        return eff

    @property
    def output_power_w(self) -> float:
        return self.input_power_w * self.end_to_end_efficiency

    @property
    def power_at_each_stage(self) -> list[tuple[str, float]]:
        """Return (stage_name, power_after_stage_w) for every stage."""
        out: list[tuple[str, float]] = []
        p = self.input_power_w
        for s in self.stages:
            p = p * s.efficiency
            out.append((s.name, p))
        return out


def atmospheric_transmission(
    wavelength_nm: float,
    path_length_m: float,
    extinction_coeff_per_m: float,
) -> float:
    """Beer-Lambert atmospheric transmission tau = exp(-alpha * L).

    Args:
        wavelength_nm: Wavelength in nanometres. Retained for future
            wavelength-dependent alpha lookups; not used in this simple form.
        path_length_m: Path length in metres. Must be >= 0.
        extinction_coeff_per_m: Extinction coefficient alpha in 1/m.
            Must be >= 0. Clear-air 1 um laser propagation is typically
            1e-5 to 1e-4 per metre.

    Returns:
        Transmission coefficient tau in (0, 1].
    """
    if path_length_m < 0:
        raise ValueError(f"Path length must be >= 0; got {path_length_m}")
    if extinction_coeff_per_m < 0:
        raise ValueError(f"Extinction coefficient must be >= 0; got {extinction_coeff_per_m}")
    return float(np.exp(-extinction_coeff_per_m * path_length_m))


# --- Section 8.4 canonical cascade and dual-reporting invariant -------------

CANONICAL_STAGES: tuple[str, ...] = (
    "transmitter",
    "beam",
    "receiver",
    "battery",
)


@dataclass(frozen=True)
class DualEfficiencyReport:
    """A pair of efficiency figures that must always be reported together.

    Enforces the Section 6 dual-reporting invariant: the favorable stage
    efficiency and the unfavorable end-to-end efficiency must both be
    reported. Reporting the favorable figure alone is a specification
    violation.
    """

    favorable_label: str
    favorable_value: float
    unfavorable_label: str
    unfavorable_value: float
    source: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.unfavorable_value <= 1.0:
            raise ValueError(f"Unfavorable value must be in [0, 1]; got {self.unfavorable_value}")
        if not 0.0 <= self.favorable_value <= 1.0:
            raise ValueError(f"Favorable value must be in [0, 1]; got {self.favorable_value}")
        if self.favorable_value < self.unfavorable_value:
            raise ValueError(
                "Favorable value must be >= unfavorable value; "
                f"got favorable={self.favorable_value}, "
                f"unfavorable={self.unfavorable_value}"
            )

    def summary(self) -> str:
        return (
            f"{self.favorable_label}: {self.favorable_value * 100:.2f}% | "
            f"{self.unfavorable_label}: {self.unfavorable_value * 100:.2f}% | "
            f"source: {self.source}"
        )


XIDIAN_DUAL_REPORT = DualEfficiencyReport(
    favorable_label="on-target DC-to-DC",
    favorable_value=0.208,
    unfavorable_label="end-to-end wall-plug-to-battery (midpoint)",
    unfavorable_value=0.04,
    source="Xidian University (spec Section 6)",
)


def build_canonical_link_budget(
    input_power_w: float,
    transmitter_eff: float,
    beam_eff: float,
    receiver_eff: float,
    battery_eff: float,
    *,
    notes: str = "",
) -> LinkBudget:
    """Build a LinkBudget with the four canonical stages in the order
    required by Section 8.4: transmitter, beam, receiver, battery.

    This is the only sanctioned constructor for a full link budget. It
    enforces the cascade order and that every stage is explicitly named.
    """
    return LinkBudget(
        input_power_w=input_power_w,
        stages=(
            Stage("transmitter", transmitter_eff, source="Section 8.4 stage 1"),
            Stage("beam", beam_eff, source="Section 8.4 stage 2"),
            Stage("receiver", receiver_eff, source="Section 8.4 stage 3"),
            Stage("battery", battery_eff, source="Section 8.4 stage 4"),
        ),
        notes=notes,
    )


def build_physical_link_budget(
    input_power_w: float,
    wavelength_nm: float,
    waist_radius_m: float,
    transmitter_efficiency: float,
    range_m: float,
    receiver_aperture_radius_m: float,
    pointing_offset_m: float,
    visibility_km: float,
    cloud_factor: float,
    receiver_conversion_efficiency: float,
    battery_efficiency: float,
    *,
    atmosphere_config: _atmosphere.AtmosphereConfig | None = None,
    notes: str = "",
) -> LinkBudget:
    """Build a LinkBudget with every stage derived from physical inputs.

    Complements ``build_canonical_link_budget`` (which takes four bare
    efficiencies). This constructor derives the beam stage from
    Gaussian-beam geometry (physics.beam) and from Beer-Lambert
    atmospheric transmittance (physics.atmosphere), so the caller
    supplies physical geometry and environmental conditions rather than
    an already-evaluated efficiency per stage.

    The stage cascade is the same four canonical stages in the same
    order as Section 8.4:

        transmitter: electrical-to-optical wall-plug efficiency,
            supplied by the caller (a laser property).
        beam: combined geometric spillover, pointing loss, and
            atmospheric transmittance, computed from geometry and
            conditions.
        receiver: on-target DC-to-DC conversion efficiency of the
            receiver. For the Han et al. perovskite-TE tandem under
            520 nm illumination, the champion figure is 38.49% (spec
            Section 6). For a rectenna the corresponding figure must
            come from an RF model (not yet implemented).
        battery: battery charging efficiency, supplied by the caller
            (a cell property; Li-ion is typically 0.90-0.95).

    Args:
        input_power_w: Transmitter electrical input power, > 0.
        wavelength_nm: Laser wavelength, in [400, 1550] nm.
        waist_radius_m: Beam waist radius at the transmitter, > 0.
        transmitter_efficiency: Electrical-to-optical efficiency,
            in (0, 1].
        range_m: Transmitter-to-receiver propagation distance, >= 0.
        receiver_aperture_radius_m: Receiver aperture radius, > 0.
        pointing_offset_m: Boresight offset from the receiver centre
            at the receiver plane, >= 0.
        visibility_km: Meteorological visibility, in [0.05, 100] km.
        cloud_factor: Cloud cover fraction, in [0, 1].
        receiver_conversion_efficiency: On-target DC-to-DC conversion
            efficiency of the receiver, in (0, 1].
        battery_efficiency: Battery charging efficiency, in (0, 1].
        atmosphere_config: Optional atmosphere configuration; defaults
            to DEFAULT_ATMOSPHERE_CONFIG in physics.atmosphere.
        notes: Optional free-text notes attached to the LinkBudget.

    Returns:
        A LinkBudget with four physical stages.

    Raises:
        ValueError on any out-of-range or non-finite input.
    """
    if input_power_w <= 0.0 or not np.isfinite(input_power_w):
        raise ValueError(f"input_power_w must be finite and > 0; got {input_power_w}")

    # Stage 1: transmitter wall-plug efficiency (caller-supplied).
    if not 0.0 < transmitter_efficiency <= 1.0:
        raise ValueError(f"transmitter_efficiency must be in (0, 1]; got {transmitter_efficiency}")

    # Stage 2: beam stage = spillover * pointing * atmospheric transmittance.
    w_at_receiver = _beam.beam_radius_m(wavelength_nm, waist_radius_m, range_m)
    eta_beam = _beam.combined_beam_efficiency(
        beam_radius_m=w_at_receiver,
        receiver_radius_m=receiver_aperture_radius_m,
        offset_m=pointing_offset_m,
    )
    eta_atm = _atmosphere.transmission(
        wavelength_nm=wavelength_nm,
        path_length_m=range_m,
        visibility_km=visibility_km,
        cloud_factor=cloud_factor,
        config=atmosphere_config,
    )
    beam_stage_eff = float(eta_beam * eta_atm)

    # Stage 3: receiver conversion efficiency (caller-supplied).
    if not 0.0 < receiver_conversion_efficiency <= 1.0:
        raise ValueError(
            "receiver_conversion_efficiency must be in (0, 1]; got "
            f"{receiver_conversion_efficiency}"
        )

    # Stage 4: battery charging efficiency (caller-supplied).
    if not 0.0 < battery_efficiency <= 1.0:
        raise ValueError(f"battery_efficiency must be in (0, 1]; got {battery_efficiency}")

    return LinkBudget(
        input_power_w=input_power_w,
        stages=(
            Stage(
                "transmitter",
                transmitter_efficiency,
                source="caller-supplied electrical-to-optical efficiency",
            ),
            Stage(
                "beam",
                beam_stage_eff,
                source=(
                    "Gaussian spillover (Siegman 1986) * pointing loss "
                    "(Klein & Pappas 1974) * atmospheric transmittance "
                    "(physics.atmosphere, Kruse-Kim 1962/2001)"
                ),
            ),
            Stage(
                "receiver",
                receiver_conversion_efficiency,
                source="caller-supplied on-target DC-to-DC efficiency",
            ),
            Stage(
                "battery",
                battery_efficiency,
                source="caller-supplied battery charging efficiency",
            ),
        ),
        notes=notes,
    )
