"""Mission state HTTP route."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.discovery.generator import (
    LINK_PARAM_RANGES,
    NODE_PARAM_RANGES,
)
from app.discovery.grammar import LinkInstance, NodeInstance, Terminal
from app.mission.state import (
    MissionConfig,
    MissionState,
    SatelliteElements,
    SelectedArchitecture,
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
    wavelength_nm: float = Query(1064.0, gt=0.0, le=10_000.0),
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
            wavelength_nm=wavelength_nm,
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


# --- POST variant -----------------------------------------------------------
# The GET route accepts configuration as query parameters and is limited
# to what fits in a URL. A selected architecture with dozens of nodes
# and links cannot be expressed that way. The POST route accepts the
# same configuration fields in a JSON body, plus an optional
# selected_architecture that replaces the mission's generated one.


class SelectedNodeBody(BaseModel):
    node_id: str
    kind: str
    params: dict[str, float] = {}


class SelectedLinkBody(BaseModel):
    link_id: str
    kind: str
    source_id: str
    target_id: str


class SelectedArchitectureBody(BaseModel):
    node_list: list[SelectedNodeBody]
    link_list: list[SelectedLinkBody]


class UavHardwareBody(BaseModel):
    """Per-UAV hardware sent from the design studio."""

    receiver_aperture_m2: float = 0.5
    receiver_type: str = "laser_photovoltaic"
    battery_efficiency: float = 0.92
    mass_kg: float = 5.0
    wingspan_m: float = 2.0
    battery_wh: float = 100.0
    thermal_limit_c: float = 80.0


class MissionStateRequest(BaseModel):
    """Body for POST /mission/state. Mirrors the GET query parameters."""

    seed: int = 20261014
    satellite_key: str | None = None
    a_km: float | None = None
    e: float | None = None
    i_deg: float | None = None
    raan_deg: float | None = None
    argp_deg: float | None = None
    m0_deg: float | None = None
    elements_epoch_utc: datetime | None = None
    n_uavs: int = 6
    ground_lat_deg: float = 40.798
    ground_lon_deg: float = -77.860
    transmitter_power_w: float = 10_000.0
    wavelength_nm: float = 1064.0
    visibility_km: float = 10.0
    cloud_factor: float = 0.0
    transmitter_aperture_m: float = 0.02
    uav_alt_m: float = 1_000.0
    uav_receiver_aperture_m2: float = 0.5
    uav_receiver_type: str = "laser_photovoltaic"
    t_utc: datetime | None = None
    selected_architecture: SelectedArchitectureBody | None = None
    uav_hardware_list: list[UavHardwareBody] | None = None


def _default_params_for_kind(
    kind: Terminal,
    supplied: dict[str, float],
    ranges: dict[Terminal, dict[str, tuple[float, float]]],
) -> dict[str, float]:
    """Return supplied params merged with mid-range defaults for any
    parameter the topology omits.

    A node or link that a user hand-constructs may not carry every
    parameter the encoder requires (for example ``capacity_factor`` on
    a laser link). Filling the missing ones from the mid-point of the
    generator's range keeps the encoder total without fabricating a
    value that is out of bounds. Explicit user values always win.
    """
    out = dict(supplied)
    defaults = ranges.get(kind, {})
    for name, (lo, hi) in defaults.items():
        if name not in out:
            out[name] = 0.5 * (lo + hi)
    return out


def _selected_from_body(
    body: SelectedArchitectureBody | None,
) -> SelectedArchitecture | None:
    if body is None:
        return None
    try:
        nodes = tuple(
            NodeInstance(
                node_id=n.node_id,
                kind=Terminal(n.kind),
                params=_default_params_for_kind(Terminal(n.kind), n.params, NODE_PARAM_RANGES),
            )
            for n in body.node_list
        )
        links = tuple(
            LinkInstance(
                link_id=ln.link_id,
                kind=Terminal(ln.kind),
                source_id=ln.source_id,
                target_id=ln.target_id,
                params=_default_params_for_kind(Terminal(ln.kind), {}, LINK_PARAM_RANGES),
            )
            for ln in body.link_list
        )
        return SelectedArchitecture(nodes=nodes, links=links)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"selected_architecture invalid: {exc}",
        ) from exc


@router.post("/state", response_model=MissionState)
async def post_mission_state(req: MissionStateRequest) -> MissionState:
    """Compute mission state from a JSON body.

    Same physics as GET /mission/state. The body form exists because a
    selected architecture with dozens of nodes and links cannot fit in
    a URL. When ``selected_architecture`` is present, the mission's own
    encoder evaluates that topology and the resulting ArchitectureSummary
    reflects the user's selection.
    """
    from app.mission.state import UavHardware

    element_fields = (
        req.a_km,
        req.e,
        req.i_deg,
        req.raan_deg,
        req.argp_deg,
        req.m0_deg,
        req.elements_epoch_utc,
    )
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
    if n_elements == 7 and req.satellite_key is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="satellite_key and custom orbit elements are mutually exclusive",
        )

    elements: SatelliteElements | None = None
    if n_elements == 7:
        elements = SatelliteElements(
            epoch_utc=req.elements_epoch_utc,  # type: ignore[arg-type]
            a_km=req.a_km,  # type: ignore[arg-type]
            e=req.e,  # type: ignore[arg-type]
            i_deg=req.i_deg,  # type: ignore[arg-type]
            raan_deg=req.raan_deg,  # type: ignore[arg-type]
            argp_deg=req.argp_deg,  # type: ignore[arg-type]
            m0_deg=req.m0_deg,  # type: ignore[arg-type]
        )

    selected = _selected_from_body(req.selected_architecture)

    cfg = MissionConfig(
        seed=req.seed,
        satellite_key=req.satellite_key or "iss",
        satellite_elements=elements,
        n_uavs=req.n_uavs,
        ground_lat_deg=req.ground_lat_deg,
        ground_lon_deg=req.ground_lon_deg,
        transmitter_power_w=req.transmitter_power_w,
        wavelength_nm=req.wavelength_nm,
        visibility_km=req.visibility_km,
        cloud_factor=req.cloud_factor,
        transmitter_aperture_m=req.transmitter_aperture_m,
        uav_alt_m=req.uav_alt_m,
        uav_hardware=UavHardware(
            receiver_aperture_m2=req.uav_receiver_aperture_m2,
            receiver_type=req.uav_receiver_type,
        ),
        uav_hardware_list=(
            tuple(
                UavHardware(
                    receiver_aperture_m2=h.receiver_aperture_m2,
                    receiver_type=h.receiver_type,
                    battery_efficiency=h.battery_efficiency,
                    mass_kg=h.mass_kg,
                    wingspan_m=h.wingspan_m,
                    battery_wh=h.battery_wh,
                    thermal_limit_c=h.thermal_limit_c,
                )
                for h in req.uav_hardware_list
            )
            if req.uav_hardware_list is not None
            else None
        ),
        selected_architecture=selected,
    )
    try:
        return compute_mission_state(cfg, t_utc=req.t_utc)
    except KeyError as exc:
        # A KeyError from compute_mission_state is a catalogue lookup
        # failure, not an arbitrary internal error. Anything else
        # propagates.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"satellite key not found: {exc}",
        ) from exc
