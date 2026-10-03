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
