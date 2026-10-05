"""Stage A - Coupled Electro-Thermal Receiver Physics.

Reference:
    AeroGrid-XAI Final Comprehensive Specification (Rev. 6),
    Section 33 "Stage A - Coupled Physics Constraint Generation (Corrected)".

Three-layer stack (Section 33.1):

    Layer 1 - CsPbBr3 perovskite laser cell (PLC)
        Converts 520 nm laser light to electricity. Efficiency degrades
        with temperature due to increased Urbach energy and stronger
        electron-phonon scattering.

    Layer 2 - Sb2Se3 nanocrystal thermal barrier
        Low thermal conductivity layer sandwiched between the PLC and the
        TE layer. Maintains the temperature gradient across the TE layer
        while lowering the PLC operating temperature. NOT a Seebeck-
        generating layer. Its thermal conductivity appears in the heat
        conduction equation (implemented in the thermal model), not in
        the efficiency product.

    Layer 3 - Bi2Te3 thermoelectric (TE) layer
        Generates additional power from the temperature differential
        across the TE component. Seebeck coefficient degrades at high
        temperature.

Epistemic tags (Section 21) are attached to every parameter:

    [MEASURED]   validated against physical measurement
    [VALIDATED]  model parameter fit against measurements
    [ESTIMATED]  engineering first principles, not yet validated
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Physical constants ----------------------------------------------------

SIGMA_SB_W_PER_M2_K4 = 5.670374419e-8
"""Stefan-Boltzmann constant, W / (m^2 K^4). [MEASURED] CODATA 2018."""

T_REF_K = 298.15
"""Reference temperature (25 C) used for efficiency parameterization. [MEASURED]"""


# --- Layer parameters ------------------------------------------------------


@dataclass(frozen=True)
class PLCParams:
    """CsPbBr3 perovskite laser cell parameters.

    Attributes:
        eta_ref: Reference conversion efficiency at T_REF_K.
            [ESTIMATED] 0.15 is a first-order estimate for a CsPbBr3 cell
            under 520 nm illumination. The Han et al. tandem device
            achieves 38.49% overall efficiency; the PLC contribution to
            that is not separately published, so we treat the split as
            an engineering estimate.
        beta_per_kelvin: Linear temperature coefficient of efficiency loss.
            [VALIDATED] Published perovskite solar cell studies report
            relative temperature coefficients in the range -0.2% to
            -0.3% per K. We use -0.25% / K = 0.0025 1/K, the midpoint.
        t_max_kelvin: Maximum operating temperature before material degradation.
            [MEASURED] The Han et al. device reached 80-90 C (353-363 K)
            under high-power laser testing, with one report specifying
            85.3 C (358.45 K) as the maximum measured temperature.
        urbach_ref_mev: Urbach energy at reference temperature.
            [ESTIMATED] 30 meV for CsPbBr3, a typical value from
            photoluminescence studies.
        urbach_dt_mev_per_kelvin: Rate of Urbach energy increase with
            temperature. [ESTIMATED] 0.05 meV / K, from the same studies.
    """

    eta_ref: float = 0.15
    beta_per_kelvin: float = 0.0025
    t_max_kelvin: float = 358.45
    urbach_ref_mev: float = 30.0
    urbach_dt_mev_per_kelvin: float = 0.05


@dataclass(frozen=True)
class ThermalBarrierParams:
    """Sb2Se3 thermal barrier parameters.

    Role: thermal_barrier (NOT seebeck). The Sb2Se3 layer controls the
    conduction path between the PLC and the TE layer. Its thermal
    conductivity k appears in the two-node lumped thermal model
    (Stage A thermal). It does NOT appear in eta_te.
    """

    material: str = "Sb2Se3"
    thermal_conductivity_w_per_m_k: float = 0.5
    """[MEASURED] Sb2Se3 thin-film thermal conductivity is widely reported
    in the 0.3 to 0.7 W/(m K) range; 0.5 is the midpoint."""
    thickness_m: float = 1e-6
    """[ESTIMATED] 1 um barrier layer, a typical nanocrystal film thickness."""
    role: str = "thermal_barrier"


@dataclass(frozen=True)
class TEParams:
    """Bi2Te3 thermoelectric layer parameters.

    Seebeck coefficient S(T) degrades at high temperature. The figure of
    merit ZT = S^2 * sigma * T / k peaks near 100 C and falls off at
    higher temperatures. Efficiency is computed from ZT and the hot/cold
    temperature difference via the standard thermoelectric efficiency
    formula (Goldsmid, "Introduction to Thermoelectricity", 2010):

        eta_te = (T_h - T_c) / T_h
                 * (sqrt(1 + ZT_avg) - 1)
                 / (sqrt(1 + ZT_avg) + T_c / T_h)
    """

    zt_peak: float = 1.0
    """[MEASURED] Peak ZT for Bi2Te3 alloys is ~1.0 near 100 C."""
    t_peak_k: float = 373.15
    """[MEASURED] 100 C is the standard Bi2Te3 ZT peak temperature."""
    zt_falloff_per_k2: float = 5e-5
    """[ESTIMATED] Quadratic falloff coefficient away from the peak.
    Chosen so that ZT(500 K) is ~0.3, consistent with published Bi2Te3
    data above 200 C."""
    thickness_m: float = 1e-6
    """[ESTIMATED] 1 um TE layer, typical thin-film thermoelectric."""


# --- Efficiency models -----------------------------------------------------


def eta_plc(t_plc_k: float, params: PLCParams | None = None) -> float:
    """CsPbBr3 perovskite laser cell conversion efficiency as a function
    of cell temperature.

    Monotonically decreasing with temperature over the operating range.
    Clamped to zero if the cell is above the material degradation limit.

    Returns a dimensionless efficiency in [0, 1].
    """
    p = params or PLCParams()
    if t_plc_k < 0.0:
        raise ValueError(f"Temperature must be non-negative; got {t_plc_k}")
    if t_plc_k >= p.t_max_kelvin:
        return 0.0
    eta = p.eta_ref * (1.0 - p.beta_per_kelvin * (t_plc_k - T_REF_K))
    return float(max(0.0, min(1.0, eta)))


def urbach_energy_mev(t_plc_k: float, params: PLCParams | None = None) -> float:
    """Urbach energy of CsPbBr3 as a function of temperature, meV.

    Increases linearly with T; the increase is the physical mechanism
    behind eta_plc degradation (Section 33.1).
    """
    p = params or PLCParams()
    return float(p.urbach_ref_mev + p.urbach_dt_mev_per_kelvin * (t_plc_k - T_REF_K))


def zt_avg_bi2te3(t_hot_k: float, params: TEParams | None = None) -> float:
    """Average ZT of Bi2Te3 between T_REF_K and t_hot_k.

    Peaks at t_peak_k and falls off quadratically away from the peak.
    """
    p = params or TEParams()
    if t_hot_k <= T_REF_K:
        return 0.0
    zt_hot = max(
        0.0,
        p.zt_peak - p.zt_falloff_per_k2 * (t_hot_k - p.t_peak_k) ** 2,
    )
    zt_ref = max(
        0.0,
        p.zt_peak - p.zt_falloff_per_k2 * (T_REF_K - p.t_peak_k) ** 2,
    )
    return float(0.5 * (zt_hot + zt_ref))


def eta_te(
    t_hot_k: float,
    t_cold_k: float,
    params: TEParams | None = None,
) -> float:
    """Bi2Te3 thermoelectric conversion efficiency from the temperature
    difference, using the standard thermoelectric efficiency formula
    (Goldsmid 2010, Ch. 2).

    Returns a dimensionless efficiency in [0, 1].

    IMPORTANT (corrected attribution, Section 33.1): the Sb2Se3 thermal
    barrier's thermal conductivity is NOT an input to this function.
    Sb2Se3 controls how the temperature gradient is distributed across
    the stack; it does not enter the Seebeck conversion formula for a
    given (T_hot, T_cold) pair.
    """
    p = params or TEParams()
    if t_cold_k < 0.0:
        raise ValueError(f"Temperature must be non-negative; got {t_cold_k}")
    if t_hot_k <= t_cold_k:
        # No usable temperature gradient for a thermoelectric generator:
        # either the temperature difference is exactly zero (a legitimate
        # boundary at the start of an ODE integration from ambient), or
        # it is negative (a heat-pump configuration, which does not
        # correspond to a generator efficiency). In both cases the
        # Seebeck conversion efficiency is zero. This must not raise,
        # because the adaptive-step ODE integrator may transiently
        # evaluate eta_te with t_hot < t_cold during stage evaluations.
        return 0.0

    zt = zt_avg_bi2te3(t_hot_k, p)
    numerator = (t_hot_k - t_cold_k) / t_hot_k
    root = float((1.0 + zt) ** 0.5)
    efficiency = numerator * (root - 1.0) / (root + t_cold_k / t_hot_k)
    return float(max(0.0, min(1.0, efficiency)))


# --- Receiver stack --------------------------------------------------------


@dataclass(frozen=True)
class ReceiverStack:
    """The three-layer laser receiver stack.

    Section 33.1 attribution:
        plc:       CsPbBr3 perovskite laser cell (electrical output)
        barrier:   Sb2Se3 thermal barrier (thermal conduction)
        te:        Bi2Te3 thermoelectric layer (electrical output)

    The barrier is a thermal element, not an electrical one. Its
    properties enter the thermal model only.
    """

    plc: PLCParams
    barrier: ThermalBarrierParams
    te: TEParams

    @classmethod
    def default(cls) -> ReceiverStack:
        return cls(
            plc=PLCParams(),
            barrier=ThermalBarrierParams(),
            te=TEParams(),
        )


def eta_total(
    t_plc_k: float,
    t_te_hot_k: float,
    t_te_cold_k: float,
    stack: ReceiverStack | None = None,
) -> float:
    """Total receiver efficiency as the product of PLC and TE efficiencies.

    Section 33.2 first-order lumped approximation:
        eta_total = eta_PLC(T_PLC) * eta_TE(T_hot, T_cold)

    LABELING REQUIREMENT (Section 33.2):
        This multiplicative form is a first-order lumped approximation.
        Real PV-TE tandem power extraction depends on circuit topology
        (series vs. independently-extracted junctions) and is not
        rigorously derivable as a simple product without justification.
        Users of this function must be aware of this limitation.
    """
    s = stack or ReceiverStack.default()
    return float(eta_plc(t_plc_k, s.plc) * eta_te(t_te_hot_k, t_te_cold_k, s.te))
