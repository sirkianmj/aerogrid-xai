"""Simulation HTTP endpoints -- Step 5 of the workflow.

Wraps :func:`app.simulation.timestep.run_simulation` and returns a
serializable time series. Every sample carries the Section 21
epistemic tag ``simulation_result``.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.mission.state import MissionConfig
from app.simulation.timestep import run_simulation

router = APIRouter(prefix="/simulation", tags=["simulation"])


class SimulationRequest(BaseModel):
    preset: Literal["10min", "1hour", "1pass", "custom"] = "1hour"
    duration_s: float = Field(3600.0, gt=0.0, le=86400.0)
    step_s: float = Field(60.0, ge=1.0, le=3600.0)
    # Mission parameters -- mirror /mission/state query params.
    seed: int = 20261014
    satellite_key: str = "iss"
    n_uavs: int = Field(6, ge=2, le=20)
    ground_lat_deg: float = Field(40.798, ge=-90.0, le=90.0)
    ground_lon_deg: float = Field(-77.860, ge=-180.0, le=180.0)
    transmitter_power_w: float = Field(10000.0, gt=0.0, le=1e9)
    wavelength_nm: float = Field(1064.0, gt=0.0, le=10000.0)
    visibility_km: float = Field(10.0, gt=0.0, le=100.0)
    cloud_factor: float = Field(0.0, ge=0.0, le=1.0)
    # Transmitter source. Default 'satellite' preserves pre-existing
    # behavior. 'ground' uses a co-located ground transmitter at the
    # ground station position. Without this field, /simulation/run
    # always builds MissionConfig with the "satellite" default and
    # produces satellite-physics curves even for ground-mode missions.
    transmitter_type: str = "satellite"
    transmitter_min_elevation_deg: float = 5.0
    # Multi-hop relay chain. Ordered list of UAV IDs from source to
    # terminal. None = direct mode.
    relay_topology: list[int] | None = None
    relay_fraction: float = 0.7


class UavSnapshotOut(BaseModel):
    uav_id: int
    received_power_w: float
    delivered_power_w: float
    receiver_efficiency: float
    thermal_headroom_c: float
    relay_hop_index: int = -1
    thermal_runaway: bool = False


class SimulationSample(BaseModel):
    t_utc: str
    elapsed_s: float
    received_power_w: float
    delivered_power_w: float
    cumulative_energy_j: float
    atmospheric_transmittance: float
    satellite_elevation_deg: float
    link_status: str
    uavs: list[UavSnapshotOut]
    epistemic_tag: str = "simulation_result"


class SimulationResponse(BaseModel):
    epistemic_tag: str = "simulation_result"
    preset: str
    duration_s: float
    step_s: float
    n_samples: int
    config_summary: dict[str, object]
    warnings: list[str]
    samples: list[SimulationSample]


@router.post("/run", response_model=SimulationResponse)
async def run(request: SimulationRequest) -> SimulationResponse:
    """Run a time-stepping simulation of the mission.

    Every sample is a Section 21 [SIMULATION] result. This is the
    Digital Twin running validated or estimated physics models --
    not a physical measurement, not a formal verification verdict.
    """
    cfg = MissionConfig(
        transmitter_type=request.transmitter_type,
        transmitter_min_elevation_deg=request.transmitter_min_elevation_deg,
        relay_topology=(tuple(request.relay_topology) if request.relay_topology else None),
        relay_fraction=request.relay_fraction,
        seed=request.seed,
        satellite_key=request.satellite_key,
        n_uavs=request.n_uavs,
        ground_lat_deg=request.ground_lat_deg,
        ground_lon_deg=request.ground_lon_deg,
        transmitter_power_w=request.transmitter_power_w,
        wavelength_nm=request.wavelength_nm,
        visibility_km=request.visibility_km,
        cloud_factor=request.cloud_factor,
    )

    try:
        result = run_simulation(
            cfg,
            preset=request.preset,
            duration_s=request.duration_s,
            step_s=request.step_s,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SimulationResponse(
        preset=result.preset,
        duration_s=result.duration_s,
        step_s=result.step_s,
        n_samples=result.n_samples,
        config_summary=result.config_summary,
        warnings=list(result.warnings),
        samples=[
            SimulationSample(
                t_utc=s.t_utc,
                elapsed_s=s.elapsed_s,
                received_power_w=s.received_power_w,
                delivered_power_w=s.delivered_power_w,
                cumulative_energy_j=s.cumulative_energy_j,
                atmospheric_transmittance=s.atmospheric_transmittance,
                satellite_elevation_deg=s.satellite_elevation_deg,
                link_status=s.link_status,
                uavs=[
                    UavSnapshotOut(
                        uav_id=u.uav_id,
                        received_power_w=u.received_power_w,
                        delivered_power_w=u.delivered_power_w,
                        receiver_efficiency=u.receiver_efficiency,
                        thermal_headroom_c=u.thermal_headroom_c,
                        relay_hop_index=getattr(u, "relay_hop_index", -1),
                        thermal_runaway=getattr(u, "thermal_runaway", False),
                    )
                    for u in s.uavs
                ],
            )
            for s in result.samples
        ],
    )
