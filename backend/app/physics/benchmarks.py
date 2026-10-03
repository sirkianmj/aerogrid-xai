"""TRL-tagged benchmark table for wireless power transmission.

Every entry is sourced from a specific, citable real-world demonstration,
carries a Technology Readiness Level (TRL) tag, and states precisely which
efficiency or performance figure it reports. Both the favorable and the
unfavorable figures are recorded when they exist - see Section 6 of the
specification.

Reference:
    AeroGrid-XAI Final Comprehensive Specification (Rev. 6), Section 6
    "Real-World Benchmark Data - TRL-Tagged and Fully Scoped".
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Benchmark:
    """A single TRL-tagged real-world benchmark."""

    name: str
    organization: str
    modality: str
    trl: int
    reported_figures: tuple[tuple[str, float, str], ...]
    scope_note: str
    citation: str


BENCHMARKS: tuple[Benchmark, ...] = (
    Benchmark(
        name="PowerLight ground-to-air laser to UAV",
        organization="PowerLight Technologies / Kraus Hamdani Aerospace (DoD PTROL-UAS)",
        modality="laser",
        trl=6,
        reported_figures=(
            ("Delivered power to UAV in flight", 1000.0, "W"),
            ("Maximum altitude", 1524.0, "m"),
        ),
        scope_note=(
            "Single ground transmitter, single cooperative moving target, "
            "active optical tracking. Sustained flight for hours. Charging "
            "stations would be placed every 125-185 miles."
        ),
        citation="DoD PTROL-UAS program, Shaw AFB; see spec Section 6.",
    ),
    Benchmark(
        name="Xidian microwave to moving drone",
        organization="Xidian University",
        modality="microwave",
        trl=5,
        reported_figures=(
            ("On-target DC-to-DC efficiency (stationary)", 0.208, "fraction"),
            ("Overall system efficiency (moving drone)", 0.05, "fraction"),
            ("Beam collection efficiency", 0.880, "fraction"),
        ),
        scope_note=(
            "Critical distinction: 20.8% is on-target DC-to-DC at well-aligned "
            "power; 3-5% is the true wall-plug-to-battery efficiency including "
            "beam spillover and tracking loss. Both must always be reported."
        ),
        citation="Xidian University; see spec Section 6.",
    ),
    Benchmark(
        name="Overview Energy airborne laser to ground",
        organization="Overview Energy",
        modality="laser",
        trl=5,
        reported_figures=(("Transmitter altitude", 5000.0, "m"),),
        scope_note=(
            "Ground-receiver architecture analog, NOT satellite-to-mobile-UAV. "
            "The transmitter platform moved; the receiver was stationary."
        ),
        citation="Overview Energy demonstration, Pennsylvania; see spec Section 6.",
    ),
    Benchmark(
        name="DARPA POWER laser record",
        organization="Naval Research Laboratory / DARPA POWER",
        modality="laser",
        trl=5,
        reported_figures=(
            ("Delivered power", 800.0, "W"),
            ("Link distance", 8600.0, "m"),
            ("Transmission duration", 30.0, "s"),
        ),
        scope_note=(
            "Fixed ground-to-ground demonstration. Validates long-range beam "
            "propagation and tracking but not moving-platform dynamics."
        ),
        citation="DARPA POWER program, White Sands Missile Range; see spec Section 6.",
    ),
    Benchmark(
        name="Han et al. perovskite-thermoelectric tandem laser receiver",
        organization="Tsinghua University / Civil Aviation University of China",
        modality="laser",
        trl=3,
        reported_figures=(
            ("Champion power conversion efficiency", 0.3849, "fraction"),
            ("Wavelength", 520.0, "nm"),
            ("Input power density", 1.2, "W/cm^2"),
        ),
        scope_note=(
            "Bench-mounted stationary drone wing model. Not flight-tested. "
            "Efficiency degrades with temperature due to increased Urbach "
            "energy and stronger electron-phonon scattering."
        ),
        citation="Han et al., Matter & Light, 2026; see spec Section 6.",
    ),
)
