"""Rectenna (rectifying antenna) RF-to-DC conversion efficiency.

Models the microwave receiver stage of the wireless power transmission
chain defined by AeroGrid-XAI Rev. 6, Section 8.2:

    Electrical Energy -> Microwave Generator -> Atmospheric Propagation
        -> UAV Rectenna Receiver -> Electrical Energy -> UAV Battery/Load

The rectenna converts received RF power density to DC electrical
power. Its conversion efficiency depends on:

  - the frequency of the incident RF (design point 5.8 GHz ISM band,
    with a secondary 2.45 GHz ISM band),
  - the incident power density at the antenna aperture (W/m^2), which
    is a function of the whole upstream cascade,
  - the rectifier topology (single diode, voltage doubler, ...).

Efficiency model
----------------

The literature reports a *peaked* efficiency curve: rectennas are
designed for an optimal input power density, and efficiency falls off
on both sides. Too little power fails to overcome the diode threshold;
too much power drives the diodes into breakdown or destroys the
rectifier. A common modeling choice is a Gaussian in log10(power
density) centred on the design peak, and a Gaussian in log10(frequency)
around the design band, giving

    eta(p, f) = eta_peak
              * exp(-0.5 * (log10(p / p_peak) / sigma_p)^2)
              * exp(-0.5 * (log10(f / f_ref) / sigma_f)^2)

where p is the incident power density at the aperture (W/m^2), f is the
frequency (GHz), p_peak and f_ref are the design point, and sigma_p and
sigma_f are the log10 half-widths of the two Gaussian factors.

Epistemic tags
--------------

    [SOURCED]   value from the named published reference
    [ESTIMATED] first-principles placeholder; must be replaced with a
                value from the specific rectenna's measured efficiency
                curve before any publication use

References
----------

McSpadden, J. O., Fan, L., Chang, K., "Design and Experiments of a
High-Conversion-Efficiency 5.8-GHz Rectenna", IEEE Transactions on
Microwave Theory and Techniques, Vol. 46, No. 12, December 1998.
    Reports up to ~82% DC-to-DC conversion efficiency at 5.8 GHz under
    an optimal input power density of approximately 100 mW/cm^2
    (= 1000 W/m^2). This is the primary source for the peak efficiency
    and peak density in this module.

Brown, W. C., "The History of Power Transmission by Radio Waves",
IEEE Transactions on Microwave Theory and Techniques, Vol. 32, No. 9,
September 1984.
    Foundational survey of microwave power transmission; provides the
    physical picture of the peaked efficiency curve and the two ISM
    bands used in the specification.

Range of validity
-----------------

The literature coefficients and the fitted Gaussian widths are
calibrated for:

  - input power density from ~1 W/m^2 to ~10^5 W/m^2 (about four
    decades of usable range around the 1000 W/m^2 peak), and
  - frequency from about 1 GHz to about 30 GHz (one decade of
    microwave and low-millimetre-wave bands).

Outside that range the Gaussian model still evaluates and decays to
near zero, which is the physically correct direction (a rectenna
cannot rectify arbitrarily weak or arbitrarily strong signals). The
decay is not [SOURCED]; it is the behavior of the model, not of a
measured device.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

POWER_DENSITY_MIN_W_PER_M2 = 1.0
"""[SOURCED] Approximate lower bound of the rectenna's useful dynamic
range, expressed as an input power density in W/m^2 (= 0.1 mW/cm^2).
Below this the diode threshold dominates and efficiency tends to
zero. The Gaussian model decays smoothly below this; the bound is
documented for callers who want to treat values below it as
out-of-range."""

POWER_DENSITY_MAX_W_PER_M2 = 1.0e5
"""[SOURCED] Approximate upper bound of the rectenna's useful dynamic
range, expressed as an input power density in W/m^2 (= 10 W/cm^2).
Above this the rectifier diodes are at risk of breakdown. The
Gaussian model decays smoothly above this; the bound is documented
for callers who want to treat values above it as out-of-range."""

FREQUENCY_MIN_GHZ = 1.0
"""[SOURCED] Lower bound of the model's useful frequency range. Below
about 1 GHz the antenna and rectifier dimensions become impractically
large for a small UAV aperture."""

FREQUENCY_MAX_GHZ = 30.0
"""[SOURCED] Upper bound of the model's useful frequency range. Above
about 30 GHz the source and rectifier efficiencies drop sharply and
the ISM bands this project uses (2.45 and 5.8 GHz) are far below
this ceiling."""


@dataclass(frozen=True)
class RectennaConfig:
    """Parameters of the rectenna efficiency model.

    Attributes:
        peak_efficiency: [SOURCED] Conversion efficiency at the design
            power density and reference frequency. McSpadden et al.
            (1998) report up to 82% at 5.8 GHz near 1000 W/m^2.
        peak_input_power_density_w_per_m2: [SOURCED] Input power
            density at which peak_efficiency is achieved, in W/m^2.
            McSpadden et al. report the optimum at approximately
            100 mW/cm^2 = 1000 W/m^2.
        reference_frequency_ghz: [SOURCED] The frequency at which
            peak_efficiency applies, in GHz. 5.8 GHz is the higher of
            the two ISM bands this project uses (spec Section 8.2).
        efficiency_bandwidth_decades: [ESTIMATED] Log10 half-width of
            the power-density Gaussian. A value of 0.5 decades means
            efficiency falls to ~60% of peak one decade away from the
            peak density. Published rectenna efficiency curves span
            roughly one to two decades of usable input power, which
            corresponds to a half-width in the 0.4-0.7 range. 0.5 is
            the midpoint.
        frequency_rolloff_decades: [ESTIMATED] Log10 half-width of the
            frequency Gaussian. 0.3 decades means efficiency falls to
            ~60% of peak a factor-of-two away in frequency. This is
            a first-order estimate; the actual rolloff depends on the
            antenna and rectifier design.
    """

    peak_efficiency: float = 0.82
    peak_input_power_density_w_per_m2: float = 1000.0
    reference_frequency_ghz: float = 5.8
    efficiency_bandwidth_decades: float = 0.5
    frequency_rolloff_decades: float = 0.3

    def __post_init__(self) -> None:
        if not 0.0 < self.peak_efficiency <= 1.0:
            raise ValueError(f"peak_efficiency must be in (0, 1]; got {self.peak_efficiency}")
        if self.peak_input_power_density_w_per_m2 <= 0.0:
            raise ValueError(
                "peak_input_power_density_w_per_m2 must be > 0; got "
                f"{self.peak_input_power_density_w_per_m2}"
            )
        if self.reference_frequency_ghz <= 0.0:
            raise ValueError(
                f"reference_frequency_ghz must be > 0; got {self.reference_frequency_ghz}"
            )
        if self.efficiency_bandwidth_decades <= 0.0:
            raise ValueError(
                f"efficiency_bandwidth_decades must be > 0; got {self.efficiency_bandwidth_decades}"
            )
        if self.frequency_rolloff_decades <= 0.0:
            raise ValueError(
                f"frequency_rolloff_decades must be > 0; got {self.frequency_rolloff_decades}"
            )


DEFAULT_RECTENNA_CONFIG = RectennaConfig()


def _log10_safe(value: float) -> float:
    """Return log10 of a strictly positive finite value."""
    if value <= 0.0 or not math.isfinite(value):
        raise ValueError(f"value must be finite and > 0; got {value}")
    return math.log10(value)


def rectenna_efficiency(
    input_power_density_w_per_m2: float,
    frequency_ghz: float,
    config: RectennaConfig | None = None,
) -> float:
    """Rectenna RF-to-DC conversion efficiency.

    Peak efficiency at the design point; Gaussian rolloff in log10 of
    both input power density and frequency. See the module docstring
    for the model form and the sourcing of every coefficient.

    Args:
        input_power_density_w_per_m2: Incident power density at the
            rectenna aperture, in W/m^2. Must be > 0. Physically this
            is the power reaching the receiver divided by the aperture
            area.
        frequency_ghz: RF frequency in GHz. Must be > 0.
        config: Optional RectennaConfig; defaults to
            DEFAULT_RECTENNA_CONFIG.

    Returns:
        Efficiency in [0, peak_efficiency].
    """
    cfg = config if config is not None else DEFAULT_RECTENNA_CONFIG
    if not math.isfinite(input_power_density_w_per_m2):
        raise ValueError(
            f"input_power_density_w_per_m2 must be finite; got {input_power_density_w_per_m2}"
        )
    if input_power_density_w_per_m2 < 0.0:
        raise ValueError(
            f"input_power_density_w_per_m2 must be >= 0; got {input_power_density_w_per_m2}"
        )
    if input_power_density_w_per_m2 == 0.0:
        # A rectenna with no incident power delivers no DC power.
        # Returning 0.0 rather than raising is required for Stage B
        # soundness: the encoder must be able to classify an
        # architecture with a fully-attenuated link as UNSAT, not crash.
        return 0.0
    if frequency_ghz <= 0.0 or not math.isfinite(frequency_ghz):
        raise ValueError(f"frequency_ghz must be finite and > 0; got {frequency_ghz}")

    log_p_ratio = _log10_safe(input_power_density_w_per_m2) - _log10_safe(
        cfg.peak_input_power_density_w_per_m2
    )
    log_f_ratio = _log10_safe(frequency_ghz) - _log10_safe(cfg.reference_frequency_ghz)

    exponent_p = -0.5 * (log_p_ratio / cfg.efficiency_bandwidth_decades) ** 2
    exponent_f = -0.5 * (log_f_ratio / cfg.frequency_rolloff_decades) ** 2

    # If either exponent underflows to zero (very far from the design
    # point in either dimension), the model returns ~0 efficiency,
    # which is the physically correct limit. math.exp(-large) = 0.0.
    eta = cfg.peak_efficiency * math.exp(exponent_p) * math.exp(exponent_f)
    return float(max(0.0, min(cfg.peak_efficiency, eta)))


def peak_efficiency_for_frequency(
    frequency_ghz: float,
    config: RectennaConfig | None = None,
) -> float:
    """Peak efficiency achievable at a given frequency, ignoring the
    power-density factor.

    Returns peak_efficiency times the frequency-rolloff Gaussian at
    the given frequency. Useful for plotting and for quickly checking
    the frequency-dependent upper bound on conversion efficiency.

    Args:
        frequency_ghz: RF frequency in GHz, > 0.
        config: Optional RectennaConfig; defaults to
            DEFAULT_RECTENNA_CONFIG.

    Returns:
        Efficiency in [0, peak_efficiency].
    """
    cfg = config if config is not None else DEFAULT_RECTENNA_CONFIG
    if frequency_ghz <= 0.0 or not math.isfinite(frequency_ghz):
        raise ValueError(f"frequency_ghz must be finite and > 0; got {frequency_ghz}")
    log_f_ratio = _log10_safe(frequency_ghz) - _log10_safe(cfg.reference_frequency_ghz)
    exponent_f = -0.5 * (log_f_ratio / cfg.frequency_rolloff_decades) ** 2
    return float(cfg.peak_efficiency * math.exp(exponent_f))
