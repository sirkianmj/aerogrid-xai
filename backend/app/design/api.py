"""Design evaluation endpoints.

Section 22 capability applied to the design process: the user varies
a satellite's orbit and bus or a drone's hardware, and the platform
runs the physics on that single design and reports whether the link
closes. This is the design agent — every verdict comes from the same
cascade that produces the mission's own delivered-power numbers.

The presets endpoint exposes the anonymous starting points so the
frontend can offer a dropdown without a hardcoded list. The preset
values are convenience only; every field they fill is fully editable.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.mission.state import (
    MissionConfig,
    SatelliteElements,
    UavHardware,
    compute_mission_state,
)
from app.physics.design_presets import DRONE_PRESETS, SATELLITE_PRESETS

router = APIRouter(prefix="/design", tags=["design"])


# --- request/response models ------------------------------------------------


class SatelliteDesignRequest(BaseModel):
    a_km: float = Field(..., gt=0.0, le=1e6)
    e: float = Field(..., ge=0.0, lt=1.0)
    i_deg: float = Field(..., ge=0.0, le=180.0)
    raan_deg: float = Field(..., ge=0.0, lt=360.0)
    argp_deg: float = Field(..., ge=0.0, lt=360.0)
    m0_deg: float = Field(..., ge=0.0, lt=360.0)
    epoch_utc: datetime
    transmitter_power_w: float = Field(10_000.0, gt=0.0, le=1e9)
    wavelength_nm: float = Field(1064.0, gt=0.0, le=10_000.0)
    transmitter_aperture_m: float = Field(0.02, gt=0.0, le=10.0)
    # Mission context where the design is evaluated.
    ground_lat_deg: float = Field(40.798, ge=-90.0, le=90.0)
    ground_lon_deg: float = Field(-77.86, ge=-180.0, le=180.0)
    n_uavs: int = Field(1, ge=1, le=20)
    uav_alt_m: float = Field(1000.0, ge=10.0, le=20_000.0)
    uav_receiver_aperture_m2: float = Field(0.5, gt=0.0, le=100.0)
    uav_receiver_type: str = Field("laser_photovoltaic")
    visibility_km: float = Field(10.0, gt=0.0, le=100.0)
    cloud_factor: float = Field(0.0, ge=0.0, le=1.0)


class DroneDesignRequest(BaseModel):
    receiver_aperture_m2: float = Field(0.5, gt=0.0, le=100.0)
    receiver_type: str = Field("laser_photovoltaic")
    battery_efficiency: float = Field(0.92, gt=0.0, le=1.0)
    mass_kg: float = Field(5.0, gt=0.0, le=100_000.0)
    wingspan_m: float = Field(2.0, gt=0.0, le=200.0)
    battery_wh: float = Field(100.0, gt=0.0, le=1e7)
    thermal_limit_c: float = Field(80.0, gt=0.0, le=500.0)
    # Mission context.
    satellite_key: str = Field("iss")
    ground_lat_deg: float = Field(40.798, ge=-90.0, le=90.0)
    ground_lon_deg: float = Field(-77.86, ge=-180.0, le=180.0)
    uav_alt_m: float = Field(1000.0, ge=10.0, le=20_000.0)
    transmitter_power_w: float = Field(10_000.0, gt=0.0, le=1e9)
    wavelength_nm: float = Field(1064.0, gt=0.0, le=10_000.0)
    transmitter_aperture_m: float = Field(0.02, gt=0.0, le=10.0)
    visibility_km: float = Field(10.0, gt=0.0, le=100.0)
    cloud_factor: float = Field(0.0, ge=0.0, le=1.0)


class FeasibilityReport(BaseModel):
    """Result of evaluating one design against the mission physics."""

    epistemic_tag: str = "simulation_result"
    verdict: str  # "feasible" | "infeasible"
    delivered_power_w: float
    notes: list[str]
    metrics: dict[str, float]


class PresetResponse(BaseModel):
    satellites: list[dict[str, object]]
    drones: list[dict[str, object]]


# --- endpoints --------------------------------------------------------------


@router.get("/presets", response_model=PresetResponse)
async def get_presets() -> PresetResponse:
    """Return the anonymous satellite and drone starting points."""
    sats = [
        {
            "id": s.id,
            "label": s.label,
            "a_km": s.a_km,
            "e": s.e,
            "i_deg": s.i_deg,
            "raan_deg": s.raan_deg,
            "argp_deg": s.argp_deg,
            "m0_deg": s.m0_deg,
            "transmitter_power_w": s.transmitter_power_w,
            "wavelength_nm": s.wavelength_nm,
            "transmitter_aperture_m": s.transmitter_aperture_m,
        }
        for s in SATELLITE_PRESETS
    ]
    drones = [
        {
            "id": d.id,
            "label": d.label,
            "mass_kg": d.mass_kg,
            "wingspan_m": d.wingspan_m,
            "battery_wh": d.battery_wh,
            "receiver_aperture_m2": d.receiver_aperture_m2,
            "receiver_type": d.receiver_type,
            "battery_efficiency": d.battery_efficiency,
            "thermal_limit_c": d.thermal_limit_c,
        }
        for d in DRONE_PRESETS
    ]
    return PresetResponse(satellites=sats, drones=drones)


def _verdict_and_notes(
    delivered_power_w: float,
    lift_feasible: bool,
    thermal_ok: bool,
) -> tuple[str, list[str]]:
    notes: list[str] = []
    if not lift_feasible:
        notes.append("wing loading exceeds the rule-of-thumb lift threshold")
    if not thermal_ok:
        notes.append("receiver operating temperature exceeds the thermal limit")
    if delivered_power_w <= 0.0:
        notes.append("the link does not close: zero delivered power at the aperture")
    verdict = (
        "feasible" if (lift_feasible and thermal_ok and delivered_power_w > 0.0) else "infeasible"
    )
    return verdict, notes


@router.post("/satellite", response_model=FeasibilityReport)
async def evaluate_satellite(req: SatelliteDesignRequest) -> FeasibilityReport:
    """Evaluate one satellite design in the mission physics."""
    if req.epoch_utc.tzinfo is None:
        req.epoch_utc = req.epoch_utc.replace(tzinfo=UTC)

    try:
        elements = SatelliteElements(
            epoch_utc=req.epoch_utc,
            a_km=req.a_km,
            e=req.e,
            i_deg=req.i_deg,
            raan_deg=req.raan_deg,
            argp_deg=req.argp_deg,
            m0_deg=req.m0_deg,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    cfg = MissionConfig(
        seed=20261014,
        satellite_elements=elements,
        n_uavs=req.n_uavs,
        ground_lat_deg=req.ground_lat_deg,
        ground_lon_deg=req.ground_lon_deg,
        transmitter_power_w=req.transmitter_power_w,
        wavelength_nm=req.wavelength_nm,
        transmitter_aperture_m=req.transmitter_aperture_m,
        uav_alt_m=req.uav_alt_m,
        uav_hardware=UavHardware(
            receiver_aperture_m2=req.uav_receiver_aperture_m2,
            receiver_type=req.uav_receiver_type,
        ),
        visibility_km=req.visibility_km,
        cloud_factor=req.cloud_factor,
    )
    state = compute_mission_state(cfg)

    total = sum(u.delivered_power_w for u in state.uavs)
    lift_feasible = all(u.lift_feasible for u in state.uavs)
    thermal_ok = True  # placeholder; thermal margin from UavState is a follow-up
    verdict, notes = _verdict_and_notes(total, lift_feasible, thermal_ok)

    metrics = {
        "transmittance": state.atmosphere.transmittance,
        "slant_range_km": state.transmission.slant_range_m / 1000.0,
        "elevation_deg": state.transmission.elevation_deg,
        "n_uavs": float(len(state.uavs)),
        "sat_verdict": float(0),  # placeholder; the verdict is the string below
    }
    return FeasibilityReport(
        verdict=verdict,
        delivered_power_w=total,
        notes=notes,
        metrics=metrics,
    )


@router.post("/drone", response_model=FeasibilityReport)
async def evaluate_drone(req: DroneDesignRequest) -> FeasibilityReport:
    """Evaluate one drone design in the mission physics."""
    try:
        hardware = UavHardware(
            receiver_aperture_m2=req.receiver_aperture_m2,
            receiver_type=req.receiver_type,
            battery_efficiency=req.battery_efficiency,
            mass_kg=req.mass_kg,
            wingspan_m=req.wingspan_m,
            battery_wh=req.battery_wh,
            thermal_limit_c=req.thermal_limit_c,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    cfg = MissionConfig(
        seed=20261014,
        satellite_key=req.satellite_key,
        n_uavs=1,
        ground_lat_deg=req.ground_lat_deg,
        ground_lon_deg=req.ground_lon_deg,
        transmitter_power_w=req.transmitter_power_w,
        wavelength_nm=req.wavelength_nm,
        transmitter_aperture_m=req.transmitter_aperture_m,
        uav_alt_m=req.uav_alt_m,
        uav_hardware=hardware,
        visibility_km=req.visibility_km,
        cloud_factor=req.cloud_factor,
    )
    try:
        state = compute_mission_state(cfg)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"satellite key not found: {exc}") from exc

    uav = state.uavs[0]
    lift_feasible = uav.lift_feasible
    thermal_ok = uav.receiver_efficiency > 0.0  # proxy; a real thermal check is a follow-up
    verdict, notes = _verdict_and_notes(uav.delivered_power_w, lift_feasible, thermal_ok)

    metrics = {
        "delivered_power_w": uav.delivered_power_w,
        "received_power_w": uav.received_power_w,
        "receiver_efficiency": uav.receiver_efficiency,
        "wing_loading_kg_per_m2": uav.wing_loading_kg_per_m2,
        "link_slant_range_km": uav.link_slant_range_m / 1000.0,
        "link_elevation_deg": uav.link_elevation_deg,
        "battery_charge_time_h": (
            uav.battery_wh / uav.delivered_power_w / 3600.0 if uav.delivered_power_w > 0.0 else 0.0
        ),
    }
    return FeasibilityReport(
        verdict=verdict,
        delivered_power_w=uav.delivered_power_w,
        notes=notes,
        metrics=metrics,
    )
