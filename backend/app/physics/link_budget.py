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
