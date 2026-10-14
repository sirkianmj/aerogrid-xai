"""Anonymous starting-point presets for satellite and drone designs.

Every preset here is a set of physical or orbital parameters only. No
preset names a real satellite, drone, country, or manufacturer. The
labels are class descriptors ("LEO smallsat", "micro UAV"); the
identifiers are neutral ("SAT-A1", "UAV-A1"). A user picks a preset to
prefill a form, then edits any field. The preset is a convenience, not
a ceiling.

The values are chosen from published aerodynamic, structural, and
aerospace-engineering ranges, rounded to defensible figures. They are
NOT validated against any specific flight hardware.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SatellitePreset:
    """A satellite design starting point: orbit + bus parameters."""

    id: str
    label: str
    # Mean Keplerian elements, TLE convention
    a_km: float
    e: float
    i_deg: float
    raan_deg: float
    argp_deg: float
    m0_deg: float
    # Bus parameters that map to MissionConfig
    transmitter_power_w: float
    wavelength_nm: float
    transmitter_aperture_m: float


@dataclass(frozen=True)
class DronePreset:
    """A drone design starting point: hardware only."""

    id: str
    label: str
    mass_kg: float
    wingspan_m: float
    battery_wh: float
    receiver_aperture_m2: float
    receiver_type: str
    battery_efficiency: float
    thermal_limit_c: float


SATELLITE_PRESETS: tuple[SatellitePreset, ...] = (
    SatellitePreset(
        id="SAT-A1",
        label="LEO smallsat",
        a_km=6771.0,
        e=0.0,
        i_deg=51.6,
        raan_deg=0.0,
        argp_deg=0.0,
        m0_deg=0.0,
        transmitter_power_w=10_000.0,
        wavelength_nm=1064.0,
        transmitter_aperture_m=0.02,
    ),
    SatellitePreset(
        id="SAT-A2",
        label="MEO relay",
        a_km=26_560.0,
        e=0.0,
        i_deg=55.0,
        raan_deg=0.0,
        argp_deg=0.0,
        m0_deg=0.0,
        transmitter_power_w=20_000.0,
        wavelength_nm=1064.0,
        transmitter_aperture_m=0.05,
    ),
    SatellitePreset(
        id="SAT-A3",
        label="GEO power platform",
        a_km=42_164.0,
        e=0.0,
        i_deg=0.05,
        raan_deg=0.0,
        argp_deg=0.0,
        m0_deg=0.0,
        transmitter_power_w=50_000.0,
        wavelength_nm=1064.0,
        transmitter_aperture_m=0.10,
    ),
    SatellitePreset(
        id="SAT-A4",
        label="Sun-synchronous",
        a_km=7071.0,
        e=0.0,
        i_deg=98.2,
        raan_deg=0.0,
        argp_deg=0.0,
        m0_deg=0.0,
        transmitter_power_w=15_000.0,
        wavelength_nm=1064.0,
        transmitter_aperture_m=0.03,
    ),
    SatellitePreset(
        id="SAT-A5",
        label="Highly elliptical",
        a_km=26_560.0,
        e=0.74,
        i_deg=63.4,
        raan_deg=0.0,
        argp_deg=270.0,
        m0_deg=0.0,
        transmitter_power_w=25_000.0,
        wavelength_nm=1064.0,
        transmitter_aperture_m=0.05,
    ),
)


DRONE_PRESETS: tuple[DronePreset, ...] = (
    DronePreset(
        id="UAV-A1",
        label="Micro UAV",
        mass_kg=1.0,
        wingspan_m=0.5,
        battery_wh=20.0,
        receiver_aperture_m2=0.05,
        receiver_type="laser_photovoltaic",
        battery_efficiency=0.92,
        thermal_limit_c=70.0,
    ),
    DronePreset(
        id="UAV-A2",
        label="Small UAV",
        mass_kg=5.0,
        wingspan_m=1.5,
        battery_wh=100.0,
        receiver_aperture_m2=0.2,
        receiver_type="laser_photovoltaic",
        battery_efficiency=0.92,
        thermal_limit_c=80.0,
    ),
    DronePreset(
        id="UAV-A3",
        label="Tactical UAV",
        mass_kg=30.0,
        wingspan_m=4.0,
        battery_wh=500.0,
        receiver_aperture_m2=0.5,
        receiver_type="laser_photovoltaic",
        battery_efficiency=0.92,
        thermal_limit_c=85.0,
    ),
    DronePreset(
        id="UAV-A4",
        label="MALE UAV",
        mass_kg=500.0,
        wingspan_m=15.0,
        battery_wh=2000.0,
        receiver_aperture_m2=1.0,
        receiver_type="laser_photovoltaic",
        battery_efficiency=0.92,
        thermal_limit_c=90.0,
    ),
    DronePreset(
        id="UAV-A5",
        label="HALE UAV",
        mass_kg=1500.0,
        wingspan_m=25.0,
        battery_wh=4000.0,
        receiver_aperture_m2=2.0,
        receiver_type="laser_photovoltaic",
        battery_efficiency=0.92,
        thermal_limit_c=95.0,
    ),
    DronePreset(
        id="UAV-A6",
        label="Loitering airframe",
        mass_kg=3.0,
        wingspan_m=1.0,
        battery_wh=50.0,
        receiver_aperture_m2=0.15,
        receiver_type="laser_photovoltaic",
        battery_efficiency=0.92,
        thermal_limit_c=75.0,
    ),
)
