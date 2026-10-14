"""Mission state HTTP route."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status

from app.mission.state import (
    MissionConfig,
    MissionState,
    SatelliteElements,
    compute_mission_state,
    list_mission_satellites,
)

router = APIRouter(prefix="/mission", tags=["mission"])


@router.get("/state", response_model=MissionState)
async def get_mission_state(
    seed: int = Query(20261014, ge=0),
    satellite_key: str | None = Query(None),
    # User-supplied mean Keplerian elements. All seven must be provided
    # together, or none at all. When present, they override satellite_key
    # and the mission state is computed from the user's orbit.
    a_km: float | None = Query(None, gt=0.0, le=1e6),
    e: float | None = Query(None, ge=0.0, lt=1.0),
    i_deg: float | None = Query(None, ge=0.0, le=180.0),
    raan_deg: float | None = Query(None, ge=0.0, lt=360.0),
    argp_deg: float | None = Query(None, ge=0.0, lt=360.0),
    m0_deg: float | None = Query(None, ge=0.0, lt=360.0),
    elements_epoch_utc: datetime | None = Query(None),
    n_uavs: int = Query(6, ge=2, le=20),
    ground_lat_deg: float = Query(40.798, ge=-90.0, le=90.0),
    ground_lon_deg: float = Query(-77.860, ge=-180.0, le=180.0),
    transmitter_power_w: float = Query(10_000.0, gt=0.0, le=1e9),
    visibility_km: float = Query(
        10.0,
        gt=0.0,
        le=100.0,
        description=(
            "Meteorological visibility in km. Feeds the Kruse-Kim "
            "atmospheric transmittance model. Higher visibility means "
            "lower aerosol attenuation."
        ),
    ),
    cloud_factor: float = Query(
        0.0,
        ge=0.0,
        le=1.0,
        description=(
            "Cloud cover fraction in [0, 1]. 0 is clear sky, 1 is fully "
            "overcast. Contributes to atmospheric attenuation."
        ),
    ),
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
    element_fields = (a_km, e, i_deg, raan_deg, argp_deg, m0_deg, elements_epoch_utc)
    n_elements = sum(f is not None for f in element_fields)
    if 0 < n_elements < 7:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "custom orbit: all seven element parameters must be provided "
                "together (a_km, e, i_deg, raan_deg, argp_deg, m0_deg, "
                "elements_epoch_utc)"
            ),
        )
    if n_elements == 7 and satellite_key is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "satellite_key and custom orbit elements are mutually exclusive; "
                "omit satellite_key when supplying elements"
            ),
        )
    if n_elements == 0 and satellite_key is None:
        satellite_key = "iss"

    elements: SatelliteElements | None = None
    if n_elements == 7:
        # Narrow Optional via the runtime check above; mypy is not able
        # to prove the tuple entries are non-None after sum().
        assert a_km is not None and e is not None and i_deg is not None
        assert raan_deg is not None and argp_deg is not None
        assert m0_deg is not None and elements_epoch_utc is not None
        elements = SatelliteElements(
            epoch_utc=elements_epoch_utc,
            a_km=a_km,
            e=e,
            i_deg=i_deg,
            raan_deg=raan_deg,
            argp_deg=argp_deg,
            m0_deg=m0_deg,
        )

    try:
        cfg = MissionConfig(
            seed=seed,
            satellite_key=satellite_key or "iss",
            satellite_elements=elements,
            n_uavs=n_uavs,
            ground_lat_deg=ground_lat_deg,
            ground_lon_deg=ground_lon_deg,
            transmitter_power_w=transmitter_power_w,
            visibility_km=visibility_km,
            cloud_factor=cloud_factor,
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
