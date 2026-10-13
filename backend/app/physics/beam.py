"""Gaussian beam geometry and beam-path efficiency for laser links.

Provides the two beam-path loss terms the specification names in
Section 8.4:

    "beam transmission & spillover efficiency: geometric loss,
     pointing error"

    "receiver capture efficiency: aperture matching, alignment"

Gaussian-beam formulas follow Siegman, "Lasers", University Science
Books, 1986, Chapter 17 ("Gaussian Beam Propagation"). Pointing-loss
form follows Klein, B. J., and Pappas, J. J., "Power handling
capability of ground station solar pumped laser amplifiers", 1974.

Epistemic tags:

    [SOURCED]   value or functional form from the named published
                reference
    [ESTIMATED] engineering placeholder; replace before publication
                use if a sourced value is available

Range of validity
-----------------

The paraxial Gaussian-beam formulas assume:

  - beam waist >> wavelength (w0 >> lambda),
  - propagation range within the far-field or near-field regime where
    the paraxial approximation holds,
  - negligible atmospheric turbulence (this module is atmosphere-free;
    atmospheric attenuation is applied as a separate stage in
    physics.link_budget).

For laser wavelengths (400-1550 nm) and waist radii on the order of
millimetres to centimetres, these assumptions hold well up to
kilometres of range. For very long ranges, turbulence-induced beam
spreading must be added by a separate module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

SPEED_OF_LIGHT_M_PER_S = 299_792_458.0
"""[SOURCED] Exact speed of light in vacuum, m/s (SI definition)."""


@dataclass(frozen=True)
class BeamParams:
    """Parameters of a Gaussian beam at the transmitter.

    Attributes:
        wavelength_nm: Laser wavelength in nanometres. Must be > 0.
        waist_radius_m: Beam waist radius w_0 at the transmitter. Must
            be > 0. [ESTIMATED] in the range of 1 mm to 10 cm for
            laser power transmitters of interest; 2 cm is a reasonable
            default for a modest aperture system.
        transmitter_efficiency: Electrical-to-optical wall-plug
            efficiency of the laser. [ESTIMATED] 0.30 corresponds to
            a modern high-power diode or fibre laser; real values
            range roughly 0.20 to 0.45 depending on technology and
            wavelength.
    """

    wavelength_nm: float = 1064.0
    waist_radius_m: float = 0.02
    transmitter_efficiency: float = 0.30

    def __post_init__(self) -> None:
        if self.wavelength_nm <= 0.0:
            raise ValueError(f"wavelength_nm must be > 0; got {self.wavelength_nm}")
        if self.waist_radius_m <= 0.0:
            raise ValueError(f"waist_radius_m must be > 0; got {self.waist_radius_m}")
        if not 0.0 < self.transmitter_efficiency <= 1.0:
            raise ValueError(
                f"transmitter_efficiency must be in (0, 1]; got {self.transmitter_efficiency}"
            )


def rayleigh_range_m(wavelength_nm: float, waist_radius_m: float) -> float:
    """Rayleigh range z_R of a Gaussian beam.

    z_R = pi * w_0^2 / lambda

    Args:
        wavelength_nm: Wavelength in nanometres, > 0.
        waist_radius_m: Beam waist radius in metres, > 0.

    Returns:
        Rayleigh range in metres.

    [SOURCED] Siegman 1986, Eq. 17.27.
    """
    if wavelength_nm <= 0.0:
        raise ValueError(f"wavelength_nm must be > 0; got {wavelength_nm}")
    if waist_radius_m <= 0.0:
        raise ValueError(f"waist_radius_m must be > 0; got {waist_radius_m}")
    w0 = waist_radius_m
    lam = wavelength_nm * 1e-9
    return float(math.pi * w0 * w0 / lam)


def beam_radius_m(
    wavelength_nm: float,
    waist_radius_m: float,
    range_m: float,
) -> float:
    """Beam radius w(z) of a Gaussian beam at distance z.

    w(z) = w_0 * sqrt(1 + (z / z_R)^2)

    Args:
        wavelength_nm: Wavelength in nanometres, > 0.
        waist_radius_m: Beam waist radius in metres, > 0.
        range_m: Propagation distance from the waist in metres, >= 0.

    Returns:
        Beam radius at range in metres.

    [SOURCED] Siegman 1986, Eq. 17.29.
    """
    if range_m < 0.0 or not math.isfinite(range_m):
        raise ValueError(f"range_m must be finite and >= 0; got {range_m}")
    z_r = rayleigh_range_m(wavelength_nm, waist_radius_m)
    return float(waist_radius_m * math.sqrt(1.0 + (range_m / z_r) ** 2))


def far_field_divergence_rad(wavelength_nm: float, waist_radius_m: float) -> float:
    """Half-angle divergence of a Gaussian beam in the far field.

    theta = lambda / (pi * w_0)

    Args:
        wavelength_nm: Wavelength in nanometres, > 0.
        waist_radius_m: Beam waist radius in metres, > 0.

    Returns:
        Half-angle divergence in radians.

    [SOURCED] Siegman 1986, Eq. 17.32.
    """
    if wavelength_nm <= 0.0:
        raise ValueError(f"wavelength_nm must be > 0; got {wavelength_nm}")
    if waist_radius_m <= 0.0:
        raise ValueError(f"waist_radius_m must be > 0; got {waist_radius_m}")
    lam = wavelength_nm * 1e-9
    return float(lam / (math.pi * waist_radius_m))


def spillover_efficiency(beam_radius_m: float, receiver_radius_m: float) -> float:
    """Fraction of beam power captured by a circular receiver aperture.

    For a Gaussian beam of 1/e^2 radius w and a co-aligned circular
    aperture of radius a, the power-capture fraction is

        eta = 1 - exp(-2 * a^2 / w^2)

    Args:
        beam_radius_m: Beam radius w at the receiver plane, > 0.
        receiver_radius_m: Receiver aperture radius a, > 0.

    Returns:
        Capture fraction in (0, 1).

    [SOURCED] Siegman 1986, Sec. 17.5; standard Gaussian-beam
    truncation result.
    """
    if beam_radius_m <= 0.0:
        raise ValueError(f"beam_radius_m must be > 0; got {beam_radius_m}")
    if receiver_radius_m <= 0.0:
        raise ValueError(f"receiver_radius_m must be > 0; got {receiver_radius_m}")
    a = receiver_radius_m
    w = beam_radius_m
    return float(1.0 - math.exp(-2.0 * a * a / (w * w)))


def pointing_efficiency(offset_m: float, beam_radius_m: float) -> float:
    """Fraction of beam power remaining when the beam is offset by
    delta from the receiver centre, for an ideal infinite aperture.

    For a Gaussian beam of 1/e^2 radius w and a boresight offset
    delta, the fraction of the beam that reaches an aligned infinite
    receiver is

        eta = exp(-2 * delta^2 / w^2)

    Args:
        offset_m: Boresight offset from the receiver centre, >= 0.
        beam_radius_m: Beam radius w at the receiver plane, > 0.

    Returns:
        Fraction in (0, 1].

    [SOURCED] Klein & Pappas 1974, Sec. 2; standard pointing-loss
    formula for a Gaussian beam.
    """
    if offset_m < 0.0 or not math.isfinite(offset_m):
        raise ValueError(f"offset_m must be finite and >= 0; got {offset_m}")
    if beam_radius_m <= 0.0:
        raise ValueError(f"beam_radius_m must be > 0; got {beam_radius_m}")
    w = beam_radius_m
    return float(math.exp(-2.0 * offset_m * offset_m / (w * w)))


def combined_beam_efficiency(
    beam_radius_m: float,
    receiver_radius_m: float,
    offset_m: float,
) -> float:
    """Beam transmission efficiency including spillover and pointing loss.

    For a Gaussian beam offset from a finite circular aperture, the
    combined capture is approximately the product of the two loss
    terms; this is a first-order lumping valid when the offset is
    small compared with the aperture radius. A rigorous treatment
    integrates the Gaussian over the shifted aperture.

    Args:
        beam_radius_m: Beam radius w at the receiver plane, > 0.
        receiver_radius_m: Receiver aperture radius a, > 0.
        offset_m: Boresight offset from the receiver centre, >= 0.

    Returns:
        Combined beam efficiency in (0, 1].

    [ESTIMATED] First-order product of the two [SOURCED] loss terms.
    """
    eta_spill = spillover_efficiency(beam_radius_m, receiver_radius_m)
    eta_point = pointing_efficiency(offset_m, beam_radius_m)
    return float(eta_spill * eta_point)
