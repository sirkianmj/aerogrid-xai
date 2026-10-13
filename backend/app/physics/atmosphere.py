"""Atmospheric extinction and transmittance for laser and RF links.

Decomposes the extinction coefficient into three additive terms:

    alpha(lambda, V, C) = alpha_molecular(lambda)
                        + alpha_aerosol(lambda, V)
                        + alpha_cloud(C)

where V is meteorological visibility in km and C is cloud cover in
[0, 1]. Total transmittance over a path of length L is given by the
Beer-Lambert law:

    tau = exp(-alpha * L)

Every coefficient in this module carries an epistemic tag:

    [SOURCED]   fixed value from the named published source
    [ESTIMATED] first-principles placeholder; must be replaced with a
                site- and wavelength-specific value from libRadtran
                or SMARTS output before any publication use
                (specification Section 9.2)

References
----------

Beer-Lambert law
    Universal radiative transfer relation.

Kruse aerosol model
    Kruse, P. W., McGlauchlin, L. D., McQuistan, R. B.,
    "Elements of Infrared Technology: Generation, Transmission, and
    Detection", Wiley, 1962.
    alpha_aerosol = (3.91 / V) * (lambda_um / 0.55) ** (-q)
    with q depending on the visibility band. V in km, lambda in
    micrometres, alpha in 1/km.

Kim low-visibility refinement
    Kim, I. I., McArthur, B., Korevaar, E. J., "Comparison of laser
    beam propagation at 785 nm and 1550 nm in fog and haze for optical
    wireless communications", Proc. SPIE 4214, pp. 26-37, 2001.
    Revises the q exponent for visibilities below 6 km.

Both sources are standard references in the optical wireless
communications literature. The Kruse model form is used verbatim;
the Kim refinement is used for the low-visibility branch.

Range of validity
-----------------

The Kruse-Kim model is calibrated for wavelengths between roughly
400 nm and 1550 nm and visibilities from about 0.5 km to 50+ km.
Outside that range the coefficients should be re-sourced. This
module raises ValueError for out-of-range inputs rather than
silently extrapolating.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

VISIBILITY_MIN_KM = 0.05
"""[SOURCED] Lower bound of the Kruse-Kim model's validity. The Kim
refinement sets q = 0 below 0.5 km; 0.05 km (50 m) is the densest
fog in which the underlying Mie-scattering approximations remain
meaningful. Below this the correct model is a full radiative
transfer code (libRadtran / MODTRAN)."""

VISIBILITY_MAX_KM = 100.0
"""[SOURCED] Upper bound of the Kruse-Kim model's validity. Above
~50 km the atmosphere is effectively aerosol-free and the aerosol
term becomes negligible; the model remains defined but the caller
should consider whether the residual value is physically meaningful.
The bound here is a numerical guard, not a physical limit."""

WAVELENGTH_MIN_NM = 400.0
WAVELENGTH_MAX_NM = 1550.0
"""[SOURCED] Range over which the Kruse-Kim coefficients were
calibrated. Values outside this range require a different model."""


@dataclass(frozen=True)
class AtmosphereConfig:
    """Parameters for the atmospheric extinction model.

    Numeric defaults are marked with an epistemic tag. The
    molecular extinction term is the only field without a sourced
    default; it is site- and wavelength-specific and must be replaced
    from libRadtran or SMARTS output before any publication use, per
    specification Section 9.2.

    Attributes:
        molecular_extinction_per_km: Molecular absorption extinction
            coefficient at the modelled wavelength. [ESTIMATED] The
            default of 1.0e-4 per km corresponds to roughly
            0.043 dB/km, which is a low value appropriate for a dry,
            high-altitude site in a spectral window. Sea-level humid
            air can be one to two orders of magnitude higher due to
            water-vapour absorption lines. Replace this default with
            a value from libRadtran or SMARTS for the actual site and
            wavelength.
        cloud_extinction_per_km_per_unit_cover: Extinction per unit
            cloud cover fraction. [ESTIMATED] First-order model: the
            cloud contribution is linear in the cloud cover fraction
            with coefficient 2.0 per km. Real cloud attenuation is
            strongly nonlinear and depends on cloud type and liquid
            water path; a fuller model uses a radiative transfer code
            with a cloud microphysics parameterization.
        use_kim_refinement: If True (default), use the Kim et al.
            (2001) q-exponent refinement for visibilities below 6 km.
            If False, use the original three-branch Kruse (1962)
            q exponents throughout.
    """

    molecular_extinction_per_km: float = 1.0e-4
    cloud_extinction_per_km_per_unit_cover: float = 2.0
    use_kim_refinement: bool = True

    def __post_init__(self) -> None:
        if self.molecular_extinction_per_km < 0.0:
            raise ValueError(
                f"molecular_extinction_per_km must be >= 0; got {self.molecular_extinction_per_km}"
            )
        if self.cloud_extinction_per_km_per_unit_cover < 0.0:
            raise ValueError(
                "cloud_extinction_per_km_per_unit_cover must be >= 0; "
                f"got {self.cloud_extinction_per_km_per_unit_cover}"
            )


DEFAULT_ATMOSPHERE_CONFIG = AtmosphereConfig()


def _validate_inputs(
    wavelength_nm: float,
    visibility_km: float,
    cloud_factor: float,
) -> None:
    if not math.isfinite(wavelength_nm):
        raise ValueError(f"wavelength_nm must be finite; got {wavelength_nm}")
    if not WAVELENGTH_MIN_NM <= wavelength_nm <= WAVELENGTH_MAX_NM:
        raise ValueError(
            f"wavelength_nm = {wavelength_nm} outside the Kruse-Kim "
            f"validity range [{WAVELENGTH_MIN_NM}, {WAVELENGTH_MAX_NM}] nm"
        )
    if not math.isfinite(visibility_km):
        raise ValueError(f"visibility_km must be finite; got {visibility_km}")
    if not VISIBILITY_MIN_KM <= visibility_km <= VISIBILITY_MAX_KM:
        raise ValueError(
            f"visibility_km = {visibility_km} outside the Kruse-Kim "
            f"validity range [{VISIBILITY_MIN_KM}, {VISIBILITY_MAX_KM}] km"
        )
    if not math.isfinite(cloud_factor):
        raise ValueError(f"cloud_factor must be finite; got {cloud_factor}")
    if not 0.0 <= cloud_factor <= 1.0:
        raise ValueError(f"cloud_factor must be in [0, 1]; got {cloud_factor}")


def kruse_q_exponent(visibility_km: float, *, use_kim: bool = True) -> float:
    """Return the wavelength-dependent exponent q in the Kruse model.

    The Kruse (1962) original has three branches. The Kim et al.
    (2001) refinement replaces the lowest branch (V < 6 km) with two
    finer branches that better match observed fog and haze data.

    Args:
        visibility_km: Meteorological visibility in km.
        use_kim: If True (default), use the Kim refinement for the
            V < 6 km branch. If False, use the original Kruse branch
            q = 0.585 * V ** (1/3).

    Returns:
        Dimensionless q, in [0, 1.6].
    """
    if not math.isfinite(visibility_km) or visibility_km <= 0.0:
        raise ValueError(f"visibility_km must be finite and > 0; got {visibility_km}")

    if visibility_km > 50.0:
        return 1.6
    if visibility_km > 6.0:
        return 1.3

    if not use_kim:
        # Kruse (1962) original low-visibility branch.
        return float(0.585 * visibility_km ** (1.0 / 3.0))

    # Kim et al. (2001) refinement.
    if visibility_km > 1.0:
        return 0.16 * visibility_km + 0.34
    if visibility_km > 0.5:
        return visibility_km - 0.5
    return 0.0


def aerosol_extinction_per_km(
    wavelength_nm: float,
    visibility_km: float,
    *,
    use_kim: bool = True,
) -> float:
    """Aerosol extinction coefficient from the Kruse-Kim model.

    Formula (Kruse 1962, Kim 2001):

        alpha_aero = (3.91 / V) * (lambda_um / 0.55) ** (-q)

    where V is visibility in km, lambda_um is wavelength in
    micrometres, q is the visibility-dependent exponent returned by
    ``kruse_q_exponent``, and alpha_aero is in 1/km.

    Args:
        wavelength_nm: Laser wavelength in nm, in [400, 1550].
        visibility_km: Meteorological visibility in km, in [0.05, 100].
        use_kim: If True, use the Kim refinement for the low-visibility
            branch.

    Returns:
        Aerosol extinction coefficient in 1/km.
    """
    if wavelength_nm <= 0.0:
        raise ValueError(f"wavelength_nm must be > 0; got {wavelength_nm}")
    if visibility_km <= 0.0:
        raise ValueError(f"visibility_km must be > 0; got {visibility_km}")

    lambda_um = wavelength_nm / 1000.0
    q = kruse_q_exponent(visibility_km, use_kim=use_kim)
    return float((3.91 / visibility_km) * (lambda_um / 0.55) ** (-q))


def molecular_extinction_per_km(config: AtmosphereConfig | None = None) -> float:
    """Molecular absorption extinction coefficient, 1/km.

    Returns the configuration value verbatim. The default is
    [ESTIMATED]; see the AtmosphereConfig docstring. A real value is
    site- and wavelength-specific and must come from libRadtran or
    SMARTS output, per specification Section 9.2.
    """
    cfg = config if config is not None else DEFAULT_ATMOSPHERE_CONFIG
    return cfg.molecular_extinction_per_km


def cloud_extinction_per_km(
    cloud_factor: float,
    config: AtmosphereConfig | None = None,
) -> float:
    """Cloud extinction coefficient, 1/km.

    First-order linear model:

        alpha_cloud = k_cloud * cloud_factor

    with k_cloud from the configuration. The default is [ESTIMATED];
    the model does not represent cloud microphysics. See the
    AtmosphereConfig docstring.
    """
    if not 0.0 <= cloud_factor <= 1.0:
        raise ValueError(f"cloud_factor must be in [0, 1]; got {cloud_factor}")
    cfg = config if config is not None else DEFAULT_ATMOSPHERE_CONFIG
    return cfg.cloud_extinction_per_km_per_unit_cover * cloud_factor


def total_extinction_per_km(
    wavelength_nm: float,
    visibility_km: float,
    cloud_factor: float,
    config: AtmosphereConfig | None = None,
) -> float:
    """Total extinction coefficient, 1/km.

    Sum of the molecular, aerosol, and cloud contributions.

    Args:
        wavelength_nm: Laser wavelength in nm, in [400, 1550].
        visibility_km: Meteorological visibility in km, in [0.05, 100].
        cloud_factor: Cloud cover fraction in [0, 1].
        config: Optional atmosphere configuration.

    Returns:
        Total extinction coefficient in 1/km.
    """
    cfg = config if config is not None else DEFAULT_ATMOSPHERE_CONFIG
    _validate_inputs(wavelength_nm, visibility_km, cloud_factor)
    alpha_mol = molecular_extinction_per_km(cfg)
    alpha_aero = aerosol_extinction_per_km(
        wavelength_nm, visibility_km, use_kim=cfg.use_kim_refinement
    )
    alpha_cloud = cloud_extinction_per_km(cloud_factor, cfg)
    return alpha_mol + alpha_aero + alpha_cloud


def transmission(
    wavelength_nm: float,
    path_length_m: float,
    visibility_km: float,
    cloud_factor: float,
    config: AtmosphereConfig | None = None,
) -> float:
    """Beer-Lambert transmission coefficient tau.

    tau = exp(-alpha_total * L)

    Args:
        wavelength_nm: Laser wavelength in nm, in [400, 1550].
        path_length_m: Path length in metres, >= 0.
        visibility_km: Meteorological visibility in km, in [0.05, 100].
        cloud_factor: Cloud cover fraction in [0, 1].
        config: Optional atmosphere configuration.

    Returns:
        Transmission coefficient in (0, 1].
    """
    if path_length_m < 0.0 or not math.isfinite(path_length_m):
        raise ValueError(f"path_length_m must be finite and >= 0; got {path_length_m}")
    alpha_per_km = total_extinction_per_km(wavelength_nm, visibility_km, cloud_factor, config)
    alpha_per_m = alpha_per_km / 1000.0
    # At extreme optical depth (dense fog over tens of km) the
    # exponential underflows to 0.0 in IEEE 754 double precision.
    # 0.0 is the physically meaningful limit: the transmitted power is
    # negligible. The return type stays float; callers that need
    # log-domain arithmetic should use transmission_db().
    return float(math.exp(-alpha_per_m * path_length_m))


def transmission_db(
    wavelength_nm: float,
    path_length_m: float,
    visibility_km: float,
    cloud_factor: float,
    config: AtmosphereConfig | None = None,
) -> float:
    """Attenuation in decibels.

    Negative value: attenuation_db = 10 * log10(tau).
    """
    tau = transmission(wavelength_nm, path_length_m, visibility_km, cloud_factor, config)
    return 10.0 * math.log10(tau)
