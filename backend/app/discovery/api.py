"""HTTP endpoint for the CLEAR-D discovery loop.

Roadmap: the CLEAR-D live dashboard. Exposes the discovery loop over
HTTP so a client can watch the inventive mechanism at work:

  1. Architecture proposals are generated.
  2. Each is encoded as Stage B constraints and checked by Z3.
  3. UNSAT architectures produce an unsat core; the core's clauses are
     mapped back to the grammar features that generated them.
  4. Those features are marked conflict-prone; the next mutation
     biases away from them.

The response carries:
  - per-generation statistics (feasible / infeasible / conflict-prone
    features so far);
  - the hypervolume history (NSGA-II progress);
  - the conflict-prone table (every grammar feature that was ever
    implicated in an UNSAT, with its hit count);
  - the trace: one entry per classification, in order;
  - the discovered feasible architectures.

All values are the loop's own outputs. Nothing is fabricated.
"""

from __future__ import annotations

import random
from typing import cast

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.discovery.generator import GeneratorConfig, generate_architecture
from app.discovery.loop import ClearDLoopConfig, run_clear_d_loop
from app.discovery.nsga2 import synthetic_evaluator
from app.discovery.sensitivity import compute_sensitivity
from app.mission.api import MissionStateRequest
from app.mission.state import MissionConfig, UavHardware
from app.verification.architecture_encoder import encode_architecture

router = APIRouter(prefix="/discovery", tags=["discovery"])

MAX_POPULATION_SIZE = 64
MAX_GENERATIONS = 50
MAX_TRACE_EVENTS = 2000


class RunRequest(BaseModel):
    population_size: int = Field(12, ge=2, le=MAX_POPULATION_SIZE)
    n_generations: int = Field(10, ge=1, le=MAX_GENERATIONS)
    seed: int = Field(20261014, ge=0)
    min_nodes: int = Field(4, ge=2, le=20)
    max_nodes: int = Field(8, ge=2, le=30)
    max_links: int = Field(6, ge=1, le=40)
    use_conflict_directed: bool = True
    ground_station_lat_deg: float | None = Field(None, ge=-90.0, le=90.0)
    ground_station_lon_deg: float | None = Field(None, ge=-180.0, le=180.0)


class GenerationStatModel(BaseModel):
    generation: int
    n_feasible: int
    n_infeasible: int
    n_conflict_prone_features: int


class ConflictProneFeatureModel(BaseModel):
    kind: str
    identifier: str
    count: int


class TraceEventModel(BaseModel):
    generation: int
    individual_index: int
    status: str
    n_constraints: int
    conflict_prone: list[str]


class NodeInstanceModel(BaseModel):
    """One node of a discovered architecture.

    Fields mirror the pydantic MissionNode in app.mission.state; they
    are declared locally rather than imported to avoid a circular
    dependency (mission.state imports from discovery).
    """

    node_id: str
    kind: str
    params: dict[str, float] = Field(default_factory=dict)


class LinkInstanceModel(BaseModel):
    """One link of a discovered architecture."""

    link_id: str
    kind: str
    source_id: str
    target_id: str


class DiscoveredArchitectureModel(BaseModel):
    generation: int
    nodes: int
    links: int
    objectives: list[float]
    node_list: list[NodeInstanceModel] = Field(default_factory=list)
    link_list: list[LinkInstanceModel] = Field(default_factory=list)


class RunResponse(BaseModel):
    epistemic_tag: str = "simulation_result"
    population_size: int
    n_generations: int
    use_conflict_directed: bool
    generation_stats: list[GenerationStatModel]
    hypervolume_history: list[float]
    conflict_prone_table: list[ConflictProneFeatureModel]
    trace: list[TraceEventModel]
    trace_truncated: bool
    discovered: list[DiscoveredArchitectureModel]


@router.post("/run", response_model=RunResponse)
async def run(request: RunRequest) -> RunResponse:
    """Run the CLEAR-D discovery loop with full attribution trace.

    Raises:
        HTTPException 400 if the generator bounds are inconsistent
            (max_nodes < min_nodes) or the generator rejects a config.
    """
    if request.max_nodes < request.min_nodes:
        raise HTTPException(status_code=400, detail="max_nodes must be >= min_nodes")

    rng = random.Random(request.seed)
    seeds = []
    for i in range(request.population_size):
        try:
            seeds.append(
                generate_architecture(
                    GeneratorConfig(
                        min_nodes=request.min_nodes,
                        max_nodes=request.max_nodes,
                        max_links=request.max_links,
                        seed=request.seed + i,
                        ground_station_lat_deg=request.ground_station_lat_deg,
                        ground_station_lon_deg=request.ground_station_lon_deg,
                    )
                )
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    trace: list[dict[str, object]] = []
    cfg = ClearDLoopConfig(
        population_size=request.population_size,
        n_generations=request.n_generations,
        use_conflict_directed=request.use_conflict_directed,
    )
    result = run_clear_d_loop(
        seeds,
        encode_architecture,
        synthetic_evaluator(),
        cfg,
        rng,
        hypervolume_samples=128,
        trace=trace,
        max_trace=MAX_TRACE_EVENTS,
    )

    conflict_table = [
        ConflictProneFeatureModel(kind=f.kind.value, identifier=f.identifier, count=c)
        for f, c in result.conflict_prone_table.to_mapping().items()
    ]

    return RunResponse(
        population_size=request.population_size,
        n_generations=request.n_generations,
        use_conflict_directed=request.use_conflict_directed,
        generation_stats=[
            GenerationStatModel(
                generation=gs.generation,
                n_feasible=gs.n_feasible,
                n_infeasible=gs.n_infeasible,
                n_conflict_prone_features=gs.n_conflict_prone_features,
            )
            for gs in result.generation_stats
        ],
        hypervolume_history=list(result.hypervolume_history),
        conflict_prone_table=conflict_table,
        trace=[
            TraceEventModel(
                generation=cast("int", ev["generation"]),
                individual_index=cast("int", ev["individual_index"]),
                status=cast("str", ev["status"]),
                n_constraints=cast("int", ev["n_constraints"]),
                conflict_prone=list(cast("list[str]", ev["conflict_prone"])),
            )
            for ev in trace
        ],
        trace_truncated=len(trace) >= MAX_TRACE_EVENTS,
        discovered=[
            DiscoveredArchitectureModel(
                generation=ind.generation,
                nodes=len(ind.architecture.nodes),
                links=len(ind.architecture.links),
                objectives=list(ind.objectives.values),
                node_list=[
                    NodeInstanceModel(
                        node_id=n.node_id,
                        kind=n.kind.value,
                        params={k: float(v) for k, v in n.params.items()},
                    )
                    for n in ind.architecture.nodes
                ],
                link_list=[
                    LinkInstanceModel(
                        link_id=ln.link_id,
                        kind=ln.kind.value,
                        source_id=ln.source_id,
                        target_id=ln.target_id,
                    )
                    for ln in ind.architecture.links
                ],
            )
            for ind in result.final_population
        ],
    )


# --- Sensitivity analysis ---------------------------------------------------
# Section 22 capability: rank which parameters move the delivered power.


class SensitivityRequest(BaseModel):
    """Request body for POST /discovery/sensitivity."""

    base: MissionStateRequest
    perturb_fraction: float = Field(0.10, gt=0.0, lt=1.0)


class ParameterSensitivityModel(BaseModel):
    name: str
    base_value: float
    low_value: float
    high_value: float
    power_at_low_w: float
    power_at_high_w: float
    derivative_w_per_unit: float
    elasticity: float | None
    direction: str


class SensitivityResponse(BaseModel):
    epistemic_tag: str = "simulation_result"
    base_delivered_power_w: float
    base_sat_verdict: str
    parameters: list[ParameterSensitivityModel]


@router.post("/sensitivity", response_model=SensitivityResponse)
async def sensitivity(request: SensitivityRequest) -> SensitivityResponse:
    """Compute the sensitivity of delivered power to each parameter."""
    req = request.base

    from app.mission.api import _selected_from_body
    from app.mission.state import SatelliteElements

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
            status_code=400,
            detail="custom orbit: all seven element parameters required together",
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
        visibility_km=req.visibility_km,
        cloud_factor=req.cloud_factor,
        transmitter_aperture_m=req.transmitter_aperture_m,
        uav_alt_m=req.uav_alt_m,
        uav_hardware=UavHardware(
            receiver_aperture_m2=req.uav_receiver_aperture_m2,
            receiver_type=req.uav_receiver_type,
        ),
        selected_architecture=selected,
    )

    report = compute_sensitivity(cfg, perturb_fraction=request.perturb_fraction)

    return SensitivityResponse(
        base_delivered_power_w=report.base_delivered_power_w,
        base_sat_verdict=report.base_sat_verdict,
        parameters=[
            ParameterSensitivityModel(
                name=p.name,
                base_value=p.base_value,
                low_value=p.low_value,
                high_value=p.high_value,
                power_at_low_w=p.power_at_low_w,
                power_at_high_w=p.power_at_high_w,
                derivative_w_per_unit=p.derivative_w_per_unit,
                elasticity=p.elasticity,
                direction=p.direction,
            )
            for p in report.parameters
        ],
    )
