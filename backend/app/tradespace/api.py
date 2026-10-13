"""HTTP endpoint for the Trade Space explorer.

Runs NSGA-II over a random initial population and returns the Pareto
front, so the frontend can plot it as a parallel-coordinates view. The
objectives are the six-component vector (C, R, E, N, T, U) from
specification Section 14, with U minimized and the rest maximized.

Endpoint
--------

    POST /tradespace/run

Request body carries the NSGA-II hyperparameters and the generator
bounds for the initial population. Everything has a default, so an
empty JSON body runs a small demo.

Authentication and metering
---------------------------

The endpoint requires a tenant JWT (minimum role: viewer). Each
successful call consumes one unit of the tenant's monthly
``tradespace_runs`` quota. The quota check happens after request
validation and after the generator-bounds consistency check, so a
request that would have been rejected with 400 or 422 does not consume
a unit.

Epistemic category
------------------

Every point in the Pareto front is the output of an optimizer running
on a synthetic evaluator. Section 21 category: simulation_result. The
response carries that tag and the objective labels so the frontend can
display the axes without hardcoding them.
"""

from __future__ import annotations

import random

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.discovery.generator import GeneratorConfig, generate_architecture
from app.discovery.nsga2 import (
    NEGATIVE_OBJECTIVES,
    OBJECTIVE_LABELS,
    NSGA2Config,
    run_nsga2,
    synthetic_evaluator,
)
from app.saas.auth import Role, TenantContext, require_role
from app.saas.quota import (
    Metric,
    Plan,
    QuotaStore,
    consume,
    get_quota_store,
    get_tenant_plan,
)

router = APIRouter(prefix="/tradespace", tags=["tradespace"])

MAX_POPULATION_SIZE = 200
MAX_GENERATIONS = 100
MAX_HYPERVOLUME_SAMPLES = 16_384
"""Upper bounds keep one request from occupying a worker for minutes.
The caps are conservative for the synthetic evaluator and can be raised
if a lighter evaluator replaces it later."""


class RunRequest(BaseModel):
    population_size: int = Field(30, ge=2, le=MAX_POPULATION_SIZE)
    n_generations: int = Field(10, ge=1, le=MAX_GENERATIONS)
    seed: int = Field(20261009, ge=0)
    min_nodes: int = Field(4, ge=2, le=20)
    max_nodes: int = Field(8, ge=2, le=30)
    max_links: int = Field(6, ge=1, le=40)
    hypervolume_samples: int = Field(2048, ge=64, le=MAX_HYPERVOLUME_SAMPLES)


class ParetoPoint(BaseModel):
    objectives: list[float]
    generation: int
    node_count: int
    link_count: int


class RunResponse(BaseModel):
    epistemic_tag: str = "simulation_result"
    objective_labels: list[str]
    negative_objectives: list[int]
    n_pareto: int
    n_final_population: int
    hypervolume_history: list[float]
    pareto_front: list[ParetoPoint]


@router.post("/run", response_model=RunResponse)
async def run(
    request: RunRequest,
    ctx: TenantContext = Depends(require_role(Role.VIEWER)),
    plan: Plan = Depends(get_tenant_plan),
    store: QuotaStore = Depends(get_quota_store),
) -> RunResponse:
    """Run NSGA-II and return the Pareto front.

    Requires an authenticated tenant. The call is metered: one unit of
    the tenant's monthly tradespace_runs quota per request. If the
    caller has already exceeded the plan limit, the request is rejected
    with 429 and a Retry-After header before any compute is performed.

    Raises:
        HTTPException 400 if max_nodes < min_nodes (Pydantic does not
            catch this cross-field constraint).
        HTTPException 401 if no Authorization header is present or the
            token is invalid.
        HTTPException 404 if the tenant row does not exist.
        HTTPException 429 if the caller has exceeded the plan quota.
    """
    if request.max_nodes < request.min_nodes:
        raise HTTPException(
            status_code=400,
            detail="max_nodes must be >= min_nodes",
        )

    consume(store, ctx.tenant_id, plan, Metric.TRADESPACE_RUNS)

    rng = random.Random(request.seed)
    initial = []
    for i in range(request.population_size):
        try:
            initial.append(
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

    result = run_nsga2(
        initial_population=initial,
        evaluator=synthetic_evaluator(),
        config=NSGA2Config(
            population_size=request.population_size,
            n_generations=request.n_generations,
        ),
        rng=rng,
        hypervolume_samples=request.hypervolume_samples,
    )

    return RunResponse(
        objective_labels=list(OBJECTIVE_LABELS),
        negative_objectives=sorted(NEGATIVE_OBJECTIVES),
        n_pareto=len(result.pareto_front),
        n_final_population=len(result.final_population),
        hypervolume_history=list(result.hypervolume_history),
        pareto_front=[
            ParetoPoint(
                objectives=list(ind.objectives.values),
                generation=ind.generation,
                node_count=len(ind.architecture.nodes),
                link_count=len(ind.architecture.links),
            )
            for ind in result.pareto_front
        ],
    )
