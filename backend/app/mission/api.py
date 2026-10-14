"""Mission state HTTP route."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status

from app.mission.state import (
    MissionConfig,
    MissionState,
    compute_mission_state,
    list_mission_satellites,
)

router = APIRouter(prefix="/mission", tags=["mission"])


@router.get("/state", response_model=MissionState)
async def get_mission_state(
    seed: int = Query(20261014, ge=0),
    satellite_key: str = Query("iss"),
    n_uavs: int = Query(6, ge=2, le=20),
    ground_lat_deg: float = Query(40.798, ge=-90.0, le=90.0),
    ground_lon_deg: float = Query(-77.860, ge=-180.0, le=180.0),
    transmitter_power_w: float = Query(10_000.0, gt=0.0, le=1e9),
    t_utc: datetime | None = Query(
        None,
        description=(
            "Mission time (ISO 8601). When omitted, the mission is computed "
            "at the TLE epoch, which is the only time at which the packaged "
            "demonstration TLEs propagate to physically meaningful altitudes."
        ),
    ),
) -> MissionState:
    """Return one coherent mission state.

    Every field is derived from a real backend computation: SGP4
    propagation of the packaged TLE, Kruse-Kim atmospheric
    transmittance at the current geometry, the real Stage B encoder
    with a Z3 SAT/UNSAT verdict, a single-generation CLEAR-D
    snapshot, and a Tier 1 decision trace over the UAVs.
    """
    try:
        cfg = MissionConfig(
            seed=seed,
            satellite_key=satellite_key,
            n_uavs=n_uavs,
            ground_lat_deg=ground_lat_deg,
            ground_lon_deg=ground_lon_deg,
            transmitter_power_w=transmitter_power_w,
        )
        return compute_mission_state(cfg, t_utc=t_utc)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"satellite key not found: {exc}",
        ) from exc


@router.get("/satellites", response_model=list[str])
async def list_satellites() -> list[str]:
    """Return packaged satellite keys, for a UI picker."""
    return list_mission_satellites()
