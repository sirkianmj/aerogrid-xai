"""Regulatory constraint encoding for laser and RF safety.

Roadmap task s3-5: Regulatory constraint encoding (ANSI Z136.1 MPE +
FCC Part 18).
Gate: MPE-violating architecture -> UNSAT by construction.

Reference:
    AeroGrid-XAI Final Comprehensive Specification (Rev. 6),
    Section 16 (Regulatory and Safety Modeling) and Section 34.3
    (hierarchical decomposition into which these constraints feed).

Every constant in this module is sourced. If a constant is not
sourced, it is marked [UNSOURCED] and must be treated as provisional.

Laser safety: ANSI Z136.1 Maximum Permissible Exposure
------------------------------------------------------

ANSI Z136.1 defines MPE as a function of wavelength, exposure
duration, and beam geometry. The values used here are the widely
cited CW intrabeam MPE limits at the two wavelengths this project
uses:

  - 1064 nm (near-infrared, Nd:YAG). The 2026 revision of ANSI
    Z136.1 reduced the near-infrared (1030-1080 nm) MPE by 15-22%
    relative to the previous edition (PrecisionLase summary of the
    2026 revision, 2026-03-06). The values below are the
    pre-2026-revision values; the 2026 revision makes them
    approximately 20% lower. Callers requiring the 2026 numbers
    should apply the 0.80 factor explicitly. [SOURCED]
  - 520 nm (visible green; the CsPbBr3 perovskite laser receiver
    operates at this wavelength per spec Section 33.1). Visible
    MPE for 0.25 s exposure is the ANSI fixed value 2.55 mW/cm^2.
    [SOURCED]

MPE values (CW, intrabeam, 7 mm limiting aperture):

    Wavelength    Exposure duration    MPE (mW/cm^2)   Source
    1064 nm       0.25 s               2.55            Patents citing Z136.1 Table 5
    1064 nm       10 s                 1.0             Same
    520 nm        0.25 s               2.55            ANSI fixed visible value
    520 nm        10 s                 1.0             Same

The 0.25 s value is the "worst-case ocular" MPE; the 10 s value is
for prolonged viewing. For beam-safety analysis of a wireless power
installation where a person might walk through the beam, 0.25 s is
the appropriate exposure duration (the blink reflex).

RF safety: FCC Part 1.1310 and ICNIRP 2020
------------------------------------------

FCC Part 1.1310 Table 1 lists the power-density MPE for the
frequency band 1500-100000 MHz as 1.0 mW/cm^2 for general
population / uncontrolled exposure, averaged over 30 minutes.
This is the binding limit for the 2.45 GHz and 5.8 GHz ISM bands
this project uses (spec Section 8.2). [SOURCED]

ICNIRP 2020 gives 10 W/m^2 at 2.4 GHz for whole-body averaged
exposure. 10 W/m^2 = 1.0 mW/cm^2, so the FCC and ICNIRP limits
coincide at these frequencies. This module uses 1.0 mW/cm^2.
[SOURCED]

Note on FCC Part 18.305: ISM equipment operating on a designated
ISM frequency is permitted unlimited radiated energy in the ISM
band. That exemption applies to the *band allocation*, not to the
human-exposure limit; the Part 1.1310 MPE still applies to any
location accessible to an unshielded person. [SOURCED]

What this module is not
-----------------------

This module does not implement the full ANSI Z136.1 correction-
factor chain (CA, CB, CP, CE, CC, S, etc.). It implements the
worst-case CW MPE at the two wavelengths of interest. Extending it
to the full chain is a Sprint 3c task if the discovered
architectures require wavelength sweeps or pulsed operation.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.verification.hierarchical import ConstraintEntry

M_PER_CM = 0.01
"""Converts mW/cm^2 to W/m^2: 1 mW/cm^2 = 10 W/m^2. The factor is
10, not 1; a mW/cm^2 is ten times a W/m^2."""

MW_PER_CM2_TO_W_PER_M2 = 10.0


@dataclass(frozen=True)
class LaserMPE:
    """Maximum Permissible Exposure for one laser configuration.

    Attributes:
        wavelength_nm: Laser wavelength in nanometres.
        exposure_duration_s: Exposure duration in seconds.
        mpe_mw_per_cm2: MPE in mW/cm^2.
        source: Citation for the value.
    """

    wavelength_nm: float
    exposure_duration_s: float
    mpe_mw_per_cm2: float
    source: str

    def mpe_w_per_m2(self) -> float:
        return self.mpe_mw_per_cm2 * MW_PER_CM2_TO_W_PER_M2

    def intensity_limit_w_per_m2(self) -> float:
        """Alias for mpe_w_per_m2; kept explicit for callers reading
        the beam-safety code."""
        return self.mpe_w_per_m2()


def laser_mpe(wavelength_nm: float, exposure_duration_s: float = 0.25) -> LaserMPE:
    """Return the ANSI Z136.1 CW MPE for a laser configuration.

    Supported wavelengths and durations:

      - 1064 nm at 0.25 s or 10 s
      - 520 nm at 0.25 s or 10 s

    Other combinations raise ValueError. The values are the pre-2026
    ANSI numbers; the 2026 revision reduces the 1064 nm value by
    15-22%.

    Args:
        wavelength_nm: 1064 or 520 (exact match required).
        exposure_duration_s: 0.25 or 10.0.

    Raises:
        ValueError on unsupported combinations.
    """
    table: dict[tuple[float, float], tuple[float, str]] = {
        (1064.0, 0.25): (
            2.55,
            "ANSI Z136.1 CW intrabeam MPE at 1064 nm, 0.25 s exposure "
            "(pre-2026 values; 2026 revision reduces by 15-22%)",
        ),
        (1064.0, 10.0): (
            1.0,
            "ANSI Z136.1 CW intrabeam MPE at 1064 nm, 10 s exposure",
        ),
        (520.0, 0.25): (
            2.55,
            "ANSI Z136.1 visible-band fixed MPE for 0.25 s exposure",
        ),
        (520.0, 10.0): (
            1.0,
            "ANSI Z136.1 visible-band long-exposure MPE",
        ),
    }
    key = (float(wavelength_nm), float(exposure_duration_s))
    if key not in table:
        supported = sorted(table)
        raise ValueError(f"No MPE table entry for {key}; supported combinations are {supported}")
    mpe, source = table[key]
    return LaserMPE(
        wavelength_nm=key[0],
        exposure_duration_s=key[1],
        mpe_mw_per_cm2=mpe,
        source=source,
    )


@dataclass(frozen=True)
class RFExposureLimit:
    """RF power-density MPE for one frequency band.

    Attributes:
        frequency_ghz: Centre frequency.
        limit_mw_per_cm2: Power-density limit in mW/cm^2.
        averaging_time_min: Averaging time in minutes.
        source: Citation.
    """

    frequency_ghz: float
    limit_mw_per_cm2: float
    averaging_time_min: float
    source: str

    def limit_w_per_m2(self) -> float:
        return self.limit_mw_per_cm2 * MW_PER_CM2_TO_W_PER_M2


RF_LIMIT_GENERAL_POPULATION = RFExposureLimit(
    frequency_ghz=2.45,
    limit_mw_per_cm2=1.0,
    averaging_time_min=30.0,
    source=(
        "FCC 47 CFR 1.1310 Table 1, 1500-100000 MHz, general "
        "population/uncontrolled: 1.0 mW/cm^2 averaged over 30 min. "
        "ICNIRP 2020 gives 10 W/m^2 = 1.0 mW/cm^2 at 2.4 GHz, which "
        "is the same value."
    ),
)
"""The binding RF MPE for the 2.45 GHz and 5.8 GHz ISM bands used by
this project. FCC and ICNIRP coincide at these frequencies."""


def laser_constraint(
    family_name: str,
    intensity_var: str,
    wavelength_nm: float,
    *,
    exposure_duration_s: float = 0.25,
    safety_margin: float = 1.0,
) -> ConstraintEntry:
    """Build a ConstraintEntry encoding "intensity <= MPE / margin".

    The constraint references a single variable, interpreted as the
    beam intensity at the point of interest in W/m^2. The encoded
    inequality is

        intensity_var <= MPE_w_per_m2 / safety_margin

    A safety_margin of 2.0 encodes the constraint that the intensity
    must be at most half the MPE. The default margin of 1.0 encodes
    the raw MPE.

    Args:
        family_name: Constraint family name for the unsat core.
        intensity_var: Name of the intensity variable in the
            enclosing HierarchicalModel.
        wavelength_nm: 1064 or 520.
        exposure_duration_s: 0.25 or 10.0.
        safety_margin: Positive divisor applied to the MPE.
    """
    if safety_margin <= 0.0:
        raise ValueError(f"safety_margin must be > 0; got {safety_margin}")
    mpe = laser_mpe(wavelength_nm, exposure_duration_s)
    limit_w_per_m2 = mpe.mpe_w_per_m2() / safety_margin

    import z3

    def fn(v: dict[str, z3.ArithRef]) -> z3.BoolRef:
        return v[intensity_var] <= z3.RealVal(repr(limit_w_per_m2))

    return ConstraintEntry(
        family_name=family_name,
        variables=frozenset({intensity_var}),
        fn=fn,
        epsilon=0.0,
    )


def rf_constraint(
    family_name: str,
    power_density_var: str,
    *,
    safety_margin: float = 1.0,
) -> ConstraintEntry:
    """Build a ConstraintEntry encoding "power density <= FCC limit".

    The constraint references a single variable, interpreted as the
    RF power density at the point of interest in W/m^2.

    Args:
        family_name: Constraint family name for the unsat core.
        power_density_var: Name of the power-density variable.
        safety_margin: Positive divisor applied to the FCC limit.
    """
    if safety_margin <= 0.0:
        raise ValueError(f"safety_margin must be > 0; got {safety_margin}")
    limit_w_per_m2 = RF_LIMIT_GENERAL_POPULATION.limit_w_per_m2() / safety_margin

    import z3

    def fn(v: dict[str, z3.ArithRef]) -> z3.BoolRef:
        return v[power_density_var] <= z3.RealVal(repr(limit_w_per_m2))

    return ConstraintEntry(
        family_name=family_name,
        variables=frozenset({power_density_var}),
        fn=fn,
        epsilon=0.0,
    )
