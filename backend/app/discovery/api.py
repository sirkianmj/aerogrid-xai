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


class DiscoveredArchitectureModel(BaseModel):
    generation: int
    nodes: int
    links: int
    objectives: list[float]


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
            )
            for ind in result.final_population
        ],
    )
