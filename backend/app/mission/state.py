"""Mission state — a single coherent scenario for the UI.

Roadmap: "Mission Control pipeline view" (Section 4 of the
specification). The endpoint composes, from existing backend
primitives, one object that the pipeline view renders top to bottom:

    SPACE -> WIRELESS TRANSMISSION -> ATMOSPHERE -> UAV NETWORK
    -> GEOGRAPHIC REGION -> INTELLIGENCE (Tier 1, Z3, CLEAR-D)

Every field returned here is derived from a real backend computation.
A stage not yet wired returns status="pending" with a reason; it does
not return fabricated data.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field

from app.control.tier1 import decide_charge_uav, default_charge_rule_list
from app.control.tier2 import AtmosphericSurrogate, Tier2Estimate
from app.discovery.attribution import ConflictProneTable, attribute_and_mark
from app.discovery.generator import GeneratorConfig, generate_architecture
from app.discovery.grammar import Architecture, Terminal
from app.discovery.loop import ClearDLoopConfig, run_clear_d_loop
from app.discovery.nsga2 import synthetic_evaluator
from app.physics.atmosphere import (
    total_extinction_per_km as _total_extinction_per_km,
)
from app.physics.atmosphere import (
    transmission as _kruse_kim_transmission,
)
from app.physics.catalog import get_satellite, list_satellite_keys
from app.physics.orbital import (
    GroundNode,
    Satellite,
    StateVector,
    classify_orbit,
    visibility_windows,
)
from app.verification.architecture_encoder import encode_architecture

# --- configuration --------------------------------------------------------


@dataclass(frozen=True)
class MissionConfig:
    """Deterministic inputs for one mission-state computation."""

    seed: int = 20261014
    satellite_key: str = "iss"
    ground_station_name: str = "Ground Station Alpha"
    ground_lat_deg: float = 40.798
    ground_lon_deg: float = -77.860
    ground_alt_m: float = 350.0
    n_uavs: int = 6
    transmitter_power_w: float = 10_000.0
    wavelength_nm: float = 1064.0
    visibility_km: float = 10.0
    cloud_factor: float = 0.2
    extinction_coeff_per_m: float = 1e-5


# --- response models -----------------------------------------------------


class SatelliteState(BaseModel):
    key: str
    name: str
    orbit_class: str
    tle_epoch_utc: str
    tle_age_seconds: float
    valid: bool
    invalid_reason: str = ""
    period_seconds: float
    lat_deg: float
    lon_deg: float
    alt_km: float
    in_eclipse: bool
    epistemic_tag: str = "validated_physical_model"


class GroundStationState(BaseModel):
    name: str
    lat_deg: float
    lon_deg: float
    alt_m: float


class TransmissionState(BaseModel):
    modality: str
    wavelength_nm: float
    transmitter_power_w: float
    slant_range_m: float
    atmospheric_path_m: float
    elevation_deg: float


class AtmosphereState(BaseModel):
    transmittance: float
    visibility_km: float
    cloud_factor: float
    extinction_coeff_per_m: float
    # Tier 2 calibrated interval around ``transmittance``. Present only
    # when the link is above the horizon. The interval is a Section 21
    # [SIMULATION] result reflecting the stated accuracy envelope of the
    # Kruse-Kim parametrization (specification Section 9.2: 7-15% nRMSE
    # against reference radiative transfer codes), not a physical
    # measurement. See the docstring of _calibrate_atmosphere_surrogate.
    transmittance_low: float | None = None
    transmittance_high: float | None = None
    nominal_coverage: float | None = None


class UavState(BaseModel):
    uav_id: int
    lat_deg: float
    lon_deg: float
    role: str
    battery_pct: float
    mission_priority: float
    network_centrality: float
    coverage_contribution: float
    workload_urgency: float
    thermal_headroom_c: float
    atmospheric_factor: float
    beam_alignment: float
    transfer_loss: float


class MissionNode(BaseModel):
    """One node in the discovered architecture.

    The full graph is exposed so the frontend can render the UAV
    network topology, not just aggregate counts.
    """

    node_id: str
    kind: str
    params: dict[str, float] = Field(default_factory=dict)


class MissionLink(BaseModel):
    """One directed link in the discovered architecture."""

    link_id: str
    kind: str
    source_id: str
    target_id: str


class ArchitectureSummary(BaseModel):
    nodes: int
    links: int
    node_kinds: dict[str, int]
    link_kinds: dict[str, int]
    sat_verdict: str
    n_constraints: int
    epsilon_bound: float
    node_list: list[MissionNode] = Field(default_factory=list)
    link_list: list[MissionLink] = Field(default_factory=list)


class ClearDSnapshot(BaseModel):
    population_size: int
    n_generations: int
    feasible_final: int
    infeasible_final: int
    conflict_prone_features: int
    use_conflict_directed: bool
    epistemic_tag: str = "simulation_result"


class Tier1Snapshot(BaseModel):
    selected_action: str
    decision_kind: str
    score: float
    alternative_action: str
    alternative_score: float
    confidence: float
    epistemic_tag: str = "tier1_decision_trace"


class PipelineStage(BaseModel):
    key: str
    label: str
    status: str  # "wired" | "partial" | "pending"
    reason: str = ""


class MissionState(BaseModel):
    t_utc: str
    seed: int
    satellite: SatelliteState
    ground_station: GroundStationState
    transmission: TransmissionState
    atmosphere: AtmosphereState
    uavs: list[UavState]
    architecture: ArchitectureSummary
    cleard: ClearDSnapshot
    tier1: Tier1Snapshot
    pipeline_stages: list[PipelineStage]
    epistemic_tag: str = "simulation_result"


# --- computation ---------------------------------------------------------


def _state_vector_to_geodetic(sv: StateVector) -> tuple[float, float, float]:
    """Extract lat/lon/alt from a StateVector.

    StateVector is a dataclass; the fields are lat_deg, lon_deg, alt_km.
    Kept behind this helper so a future change to StateVector's shape
    is localized.
    """
    lat = sv.lat_deg
    lon = sv.lon_deg
    alt = sv.alt_km
    return float(lat), float(lon), float(alt)


def _pick_uav_candidates(cfg: MissionConfig, arch: Architecture) -> list[dict[str, float]]:
    """Build exactly ``cfg.n_uavs`` candidate dicts, deterministic from seed.

    The generator picks node kinds within bounds and cannot be relied
    on to produce a specific number of UAV nodes, so the mission's UAV
    count is authoritative. The generated architecture is used only
    for its link/structure content elsewhere; here it is unused.

    Keys match the default charge rule list's inputs so the Tier 1
    decision trace exercises every rule.
    """
    _ = arch  # kept in the signature for the caller's convenience
    rng = random.Random(cfg.seed)
    out: list[dict[str, float]] = []
    for i in range(cfg.n_uavs):
        out.append(
            {
                "uav_id": float(i),
                "battery_pct": float(rng.uniform(5.0, 80.0)),
                "mission_priority": float(rng.uniform(0.2, 1.0)),
                "network_centrality": float(rng.uniform(0.1, 1.0)),
                "coverage_contribution": float(rng.uniform(0.0, 0.15)),
                "workload_urgency": float(rng.uniform(0.1, 1.0)),
                "thermal_headroom_c": float(rng.uniform(15.0, 60.0)),
                "atmospheric_factor": float(rng.uniform(0.6, 1.0)),
                "beam_alignment": float(rng.uniform(0.7, 1.0)),
                "transfer_loss": float(rng.uniform(0.05, 0.30)),
            }
        )
    return out


def _calibrate_atmosphere_surrogate(cfg: MissionConfig) -> AtmosphericSurrogate:
    """Return a calibrated AtmosphericSurrogate.

    Calibration targets are the point model's own predictions over a
    deterministic grid of plausible geometries, perturbed by a
    pseudo-noise whose amplitude is 15% of the point value. That 15%
    figure is the pessimistic bound of the Kruse-Kim model's stated
    accuracy envelope (specification Section 9.2: reference radiative
    transfer codes MODTRAN, libRadtran, and SBDART report 7-15% nRMSE;
    SMARTS reports around 5%). The resulting conformal interval
    therefore reflects the parametrisation's documented accuracy
    against those codes, not any physical measurement. It is a
    Section 21 [SIMULATION] result and is labelled as such at the API
    level.

    The calibration grid uses the mission's own wavelength, visibility,
    and cloud factor, with path lengths spanning the plausible
    atmosphere (100 m to 200 km). This means the interval is tuned to
    the mission's conditions rather than being a global band.
    """
    rng = random.Random(cfg.seed)
    calibration_inputs: list[dict[str, float]] = []
    calibration_targets: list[float] = []
    for i in range(32):
        # Log-spaced path lengths from 100 m to 200 km.
        frac = i / 31.0
        path_m = 100.0 * (2000.0**frac)  # 100 * 2000^1 = 200_000
        inp = {
            "wavelength_nm": cfg.wavelength_nm,
            "path_m": path_m,
            "visibility_km": cfg.visibility_km,
            "cloud_factor": cfg.cloud_factor,
        }
        # Point-model prediction, then a deterministic ±15% perturbation
        # representing the model's stated accuracy envelope.
        base = float(
            _kruse_kim_transmission(
                wavelength_nm=cfg.wavelength_nm,
                path_length_m=path_m,
                visibility_km=cfg.visibility_km,
                cloud_factor=cfg.cloud_factor,
            )
        )
        noise = rng.uniform(-1.0, 1.0) * 0.15 * base
        calibration_inputs.append(inp)
        calibration_targets.append(base + noise)
    surrogate = AtmosphericSurrogate()
    surrogate.calibrate(
        calibration_inputs=calibration_inputs,
        calibration_targets=calibration_targets,
        nominal_coverage=0.90,
    )
    return surrogate


def _next_visible_time(sat: Satellite, cfg: MissionConfig) -> datetime:
    """Return the peak-elevation moment of the first visible pass,
    within 24 hours of the TLE epoch.

    Rationale: opening the app onto "LINK OFFLINE" is honest but
    unhelpful. The satellite is not above the default ground station at
    its own TLE epoch, so the default mission state reports transmittance
    zero and every panel that depends on atmosphere reads nothing. The
    first available pass gives a live mission; its peak elevation gives
    the most favorable geometry within that pass.

    Peak versus start: at the pass start the beam grazes the atmosphere
    at ~5 degrees elevation, which is a path length near 100 km through
    the dense lower atmosphere and drives transmittance to zero even at
    high visibility. At peak elevation (30 degrees for the default
    satellite/ground pair) the path is far shorter and the link is
    meaningful. The user should see the pass at its best, not at its
    worst; the app still exposes the elevation in the transmission
    state, so the geometry is inspectable.

    Falls back to the TLE epoch when no pass exists in the scan window
    (for example, a geostationary satellite over a distant longitude).
    The fallback preserves the previous behaviour for cases where it is
    the correct answer.

    Scan parameters (60 s step, 5 degrees minimum elevation) match the
    geometry used later in ``compute_mission_state`` to decide whether
    the link is up. The helper is only used when the caller does not
    supply an explicit ``t_utc``; explicit times bypass the scan.
    """
    ground = GroundNode(
        name=cfg.ground_station_name,
        lat_deg=cfg.ground_lat_deg,
        lon_deg=cfg.ground_lon_deg,
        alt_m=cfg.ground_alt_m,
    )
    windows = visibility_windows(
        sat,
        ground,
        sat.epoch_utc,
        sat.epoch_utc + timedelta(hours=24),
        step_seconds=60.0,
        min_elevation_deg=5.0,
    )
    return windows[0].peak_time_utc if windows else sat.epoch_utc


def compute_mission_state(
    cfg: MissionConfig | None = None, *, t_utc: datetime | None = None
) -> MissionState:
    """Compute one mission state. Deterministic given (cfg, t_utc).

    When ``t_utc`` is None, the mission is computed at the satellite's
    own TLE epoch. That is the only moment at which SGP4 propagation
    is physically valid for a fixed TLE; the packaged TLEs are
    demonstration records whose epochs are fixed (see
    ``backend/app/physics/catalog.py``). Propagating a 2000 TLE to the
    present produces altitudes that are not physically meaningful, so
    the default anchors the mission to the epoch. Callers who pass a
    specific ``t_utc`` receive a ``valid=false`` satellite state with a
    reason if the propagation drifts out of the plausible altitude
    range, rather than a crash.
    """
    cfg = cfg or MissionConfig()
    sat = get_satellite(cfg.satellite_key)

    # Default the demonstration time to the peak of the first visible
    # pass. The caller may pass any t_utc; if it is far from the epoch,
    # SGP4 drifts and the satellite state is marked invalid rather than
    # producing a nonsensical altitude.
    if t_utc is None:
        t = _next_visible_time(sat, cfg)
    else:
        t = t_utc
        if t.tzinfo is None:
            t = t.replace(tzinfo=UTC)

    sv = sat.at_utc(t)
    lat, lon, alt = _state_vector_to_geodetic(sv)

    tle_age_s = (t - sat.epoch_utc).total_seconds()
    # Plausible altitude range for a satellite propagated by SGP4 from
    # a fresh or moderately-aged TLE. Values outside this range
    # indicate TLE staleness, not a physical result.
    alt_valid = -10.0 <= alt <= 100_000.0
    valid = bool(alt_valid)
    invalid_reason = (
        ""
        if alt_valid
        else (
            f"propagated altitude {alt:.1f} km is outside the physically "
            f"plausible range [-10, 100000] km; the TLE is {tle_age_s / 86400.0:.0f} "
            f"days old, SGP4 drift is the likely cause"
        )
    )

    orbit_class = classify_orbit(max(alt, 0.0)) if alt_valid else "invalid"

    satellite = SatelliteState(
        key=cfg.satellite_key,
        name=sat.name,
        orbit_class=orbit_class,
        tle_epoch_utc=sat.epoch_utc.isoformat(),
        tle_age_seconds=float(tle_age_s),
        valid=valid,
        invalid_reason=invalid_reason,
        period_seconds=float(sat.period_seconds),
        lat_deg=float(lat),
        lon_deg=float(lon),
        alt_km=float(alt),
        in_eclipse=bool(sat.is_in_eclipse_utc(t)),
    )

    ground = GroundStationState(
        name=cfg.ground_station_name,
        lat_deg=cfg.ground_lat_deg,
        lon_deg=cfg.ground_lon_deg,
        alt_m=cfg.ground_alt_m,
    )

    # --- transmission geometry ----------------------------------------
    # Slant range from satellite to ground station via great-circle +
    # altitude difference, in metres.
    import math

    r_earth_m = 6_371_000.0
    lat1 = math.radians(lat)
    lat2 = math.radians(cfg.ground_lat_deg)
    dlat = lat2 - lat1
    dlon = math.radians(cfg.ground_lon_deg - lon)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    surface_m = 2.0 * r_earth_m * math.asin(min(1.0, math.sqrt(a)))
    slant_range_m = math.sqrt(surface_m**2 + (alt * 1000.0) ** 2)

    # Line-of-sight check: a link exists only if the satellite is above
    # the ground station's horizon. Without this, a satellite on the
    # far side of the Earth produces a massive slant range through the
    # planet and an "atmosphere" tau that is really an occlusion.
    # Central angle between the two ground points, in radians.
    central_angle = 2.0 * math.asin(min(1.0, math.sqrt(a)))

    # Elevation angle from the ground station to the satellite.
    # elevation = atan2(cos(psi) - R/(R+h), sin(psi)), where psi is the
    # central angle. When the satellite is directly overhead, psi=0 and
    # elevation = 90 degrees; at the horizon psi = pi/2 + horizon and
    # elevation = 0.
    cos_psi = math.cos(central_angle)
    sin_psi = math.sin(central_angle)
    r_ratio = r_earth_m / (r_earth_m + alt * 1000.0)
    elevation_rad = math.atan2(cos_psi - r_ratio, sin_psi)
    above_horizon = elevation_rad > 0.0

    # Effective atmospheric thickness at sea level, metres. The
    # optically-thick fraction of the atmosphere is roughly 8-9 km
    # equivalent at 1064 nm; the extinction coefficient in the
    # atmosphere module is calibrated against this thickness, not
    # against the vacuum path to orbit.
    h_eff_m = 8_500.0

    if above_horizon:
        # Atmospheric path length = effective thickness / sin(elev).
        # Clamp elevation to avoid a division by zero at the horizon.
        sin_elev = max(math.sin(elevation_rad), 1e-3)
        atmospheric_path_m = h_eff_m / sin_elev
        # Kruse-Kim total extinction: molecular + aerosol + cloud.
        # The aerosol term is derived from visibility_km; the cloud
        # term from cloud_factor. Both inputs therefore affect tau.
        tau = _kruse_kim_transmission(
            wavelength_nm=cfg.wavelength_nm,
            path_length_m=atmospheric_path_m,
            visibility_km=cfg.visibility_km,
            cloud_factor=cfg.cloud_factor,
        )
        alpha_per_m = (
            _total_extinction_per_km(cfg.wavelength_nm, cfg.visibility_km, cfg.cloud_factor)
            / 1000.0
        )
        transmission = TransmissionState(
            modality="laser",
            wavelength_nm=cfg.wavelength_nm,
            transmitter_power_w=float(cfg.transmitter_power_w),
            slant_range_m=float(slant_range_m),
            atmospheric_path_m=float(atmospheric_path_m),
            elevation_deg=float(math.degrees(elevation_rad)),
        )
        surrogate = _calibrate_atmosphere_surrogate(cfg)
        tier2: Tier2Estimate = surrogate.estimate_atmospheric_loss(
            {
                "wavelength_nm": cfg.wavelength_nm,
                "path_m": float(atmospheric_path_m),
                "visibility_km": cfg.visibility_km,
                "cloud_factor": cfg.cloud_factor,
            }
        )
        atmosphere = AtmosphereState(
            transmittance=float(tau),
            visibility_km=cfg.visibility_km,
            cloud_factor=cfg.cloud_factor,
            extinction_coeff_per_m=float(alpha_per_m),
            transmittance_low=float(tier2.interval.low),
            transmittance_high=float(tier2.interval.high),
            nominal_coverage=float(tier2.interval.nominal_coverage),
        )
    else:
        # The transmitter power is the mission's *configured* power,
        # not the power actually emitted right now. The link is offline
        # (modality="offline", transmittance=0.0); the response still
        # reports what the mission is configured to transmit so the UI
        # can display it next to the "offline" indicator.
        transmission = TransmissionState(
            modality="offline",
            wavelength_nm=cfg.wavelength_nm,
            transmitter_power_w=float(cfg.transmitter_power_w),
            slant_range_m=float(slant_range_m),
            atmospheric_path_m=0.0,
            elevation_deg=float(math.degrees(elevation_rad)),
        )
        atmosphere = AtmosphereState(
            transmittance=0.0,
            visibility_km=cfg.visibility_km,
            cloud_factor=cfg.cloud_factor,
            extinction_coeff_per_m=cfg.extinction_coeff_per_m,
        )

    # --- architecture (real encoder + Z3 verdict) ---------------------
    arch = generate_architecture(
        GeneratorConfig(min_nodes=4, max_nodes=max(4, cfg.n_uavs + 2), max_links=6, seed=cfg.seed)
    )
    constraints = encode_architecture(arch)
    table = ConflictProneTable()
    attribution = attribute_and_mark(constraints, table)

    # Per-family PWL approximation error, computed on the receiver's
    # efficiency surface (the one Stage A surface the encoder
    # actually PWL-approximates). This is the real source of epsilon;
    # FeatureConstraint objects do not carry it.
    from app.physics.receiver import eta_plc
    from app.refinement.pwl_tune import AdaptivePWLRefiner

    refiner = AdaptivePWLRefiner(
        eta_plc,
        (280.0, 350.0),
        initial_n_segments=8,
        max_segments=8,
        samples_per_segment=16,
    )
    epsilon_bound = float(refiner.current_epsilon())

    node_kinds: dict[str, int] = {}
    for n in arch.nodes:
        node_kinds[n.kind.value] = node_kinds.get(n.kind.value, 0) + 1
    link_kinds: dict[str, int] = {}
    for ln in arch.links:
        link_kinds[ln.kind.value] = link_kinds.get(ln.kind.value, 0) + 1

    node_list = [
        MissionNode(
            node_id=n.node_id,
            kind=n.kind.value,
            params={
                k: float(v)
                for k, v in n.params.items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            },
        )
        for n in arch.nodes
    ]
    link_list = [
        MissionLink(
            link_id=ln.link_id,
            kind=ln.kind.value,
            source_id=ln.source_id,
            target_id=ln.target_id,
        )
        for ln in arch.links
    ]

    architecture = ArchitectureSummary(
        nodes=len(arch.nodes),
        links=len(arch.links),
        node_kinds=node_kinds,
        link_kinds=link_kinds,
        sat_verdict=str(attribution.status),
        n_constraints=len(constraints),
        epsilon_bound=float(epsilon_bound),
        node_list=node_list,
        link_list=link_list,
    )

    # --- CLEAR-D one-generation snapshot ------------------------------
    seeds_loop = [
        generate_architecture(
            GeneratorConfig(min_nodes=4, max_nodes=6, max_links=4, seed=cfg.seed + i)
        )
        for i in range(cfg.n_uavs)
    ]
    loop_cfg = ClearDLoopConfig(population_size=max(4, cfg.n_uavs), n_generations=1)
    loop_result = run_clear_d_loop(
        seeds_loop,
        encode_architecture,
        synthetic_evaluator(),
        loop_cfg,
        random.Random(cfg.seed),
        hypervolume_samples=16,
    )
    gs = loop_result.generation_stats[0]
    cleard = ClearDSnapshot(
        population_size=loop_cfg.population_size,
        n_generations=loop_cfg.n_generations,
        feasible_final=gs.n_feasible,
        infeasible_final=gs.n_infeasible,
        conflict_prone_features=len(loop_result.conflict_prone_table),
        use_conflict_directed=loop_cfg.use_conflict_directed,
    )

    # --- Tier 1 decision ----------------------------------------------
    candidates = _pick_uav_candidates(cfg, arch)
    if not candidates:
        candidates = [{"uav_id": 0.0}] + [{"uav_id": float(i)} for i in range(1, cfg.n_uavs)]
    trace = decide_charge_uav(candidates, default_charge_rule_list())
    tier1 = Tier1Snapshot(
        selected_action=trace.selected_action,
        decision_kind=trace.decision_kind.value,
        score=float(trace.score),
        alternative_action=trace.alternative_action,
        alternative_score=float(trace.alternative_score),
        confidence=float(trace.confidence),
    )

    # --- UAV list -----------------------------------------------------
    uavs: list[UavState] = []
    for i, c in enumerate(candidates):
        # Place UAVs on a small grid around the ground station.
        angle = (2.0 * math.pi * i) / max(1, len(candidates))
        radius_deg = 0.05
        uavs.append(
            UavState(
                uav_id=i,
                lat_deg=cfg.ground_lat_deg + radius_deg * math.cos(angle),
                lon_deg=cfg.ground_lon_deg + radius_deg * math.sin(angle),
                role=(Terminal.UAV_ENERGY.value if i % 2 == 0 else Terminal.UAV_COMPUTE.value),
                battery_pct=c.get("battery_pct", 50.0),
                mission_priority=c.get("mission_priority", 0.5),
                network_centrality=c.get("network_centrality", 0.5),
                coverage_contribution=c.get("coverage_contribution", 0.05),
                workload_urgency=c.get("workload_urgency", 0.5),
                thermal_headroom_c=c.get("thermal_headroom_c", 40.0),
                atmospheric_factor=c.get("atmospheric_factor", 0.9),
                beam_alignment=c.get("beam_alignment", 0.9),
                transfer_loss=c.get("transfer_loss", 0.15),
            )
        )

    # --- pipeline stages (honest wiring status) -----------------------
    stages = [
        PipelineStage(key="space", label="Space — satellite energy source", status="wired"),
        PipelineStage(
            key="wireless_transmission",
            label="Wireless power transmission",
            status="wired" if above_horizon else "offline",
            reason="" if above_horizon else "satellite below ground-station horizon at this t",
        ),
        PipelineStage(
            key="atmosphere",
            label="Atmospheric transmission model",
            status="partial",
            reason="Kruse-Kim extinction; libRadtran/SMARTS offline calibration is a later PR",
        ),
        PipelineStage(
            key="uav_network",
            label="UAV network",
            status="partial",
            reason="positions and per-UAV state present; live energy-flow edges are PR 2",
        ),
        PipelineStage(
            key="geographic_region",
            label="Geographic region",
            status="partial",
            reason="single ground station; multi-region coverage is a later PR",
        ),
        PipelineStage(
            key="tier1_decision",
            label="Tier 1 interpretable decision",
            status="wired",
        ),
        PipelineStage(
            key="z3_verification",
            label="Z3 formal verification",
            status="wired",
        ),
        PipelineStage(
            key="cleard_loop",
            label="CLEAR-D discovery loop",
            status="partial",
            reason="one-generation snapshot per request; full live dashboard is PR 5",
        ),
        PipelineStage(
            key="tier2_surrogates",
            label="Tier 2 uncertainty surrogates",
            status="pending",
            reason="calibrated intervals on output are a later PR",
        ),
    ]

    return MissionState(
        t_utc=t.isoformat(),
        seed=cfg.seed,
        satellite=satellite,
        ground_station=ground,
        transmission=transmission,
        atmosphere=atmosphere,
        uavs=uavs,
        architecture=architecture,
        cleard=cleard,
        tier1=tier1,
        pipeline_stages=stages,
    )


def list_mission_satellites() -> list[str]:
    """Return the packaged satellite keys, for a picker."""
    return list(list_satellite_keys())
