"""HTTP endpoints for the Digital Twin.

Exposes the physics models in app.physics.thermal and app.physics.receiver
and the discrepancy tracker in app.refinement.discrepancy. This is the
backend half of Sprint 7 s7-5 (Digital Twin state view).

Package placement
-----------------

This module lives in app.digital_twin, not in app.refinement, because
it imports app.physics. The Stage E causality audit (s6-5) forbids any
module under app/refinement/ from importing app.physics: the causal
arrow runs from operational data into the refinement layer, and the
refinement layer must not fabricate observations from the physics model
it is meant to refine. That rule is enforced by
app.refinement.causality.ast_audit_refinement_imports and by the test
test_ast_audit_finds_no_physics_imports_in_refinement.

The Digital Twin HTTP layer is a transport shim, not a Stage E module.
It reads from both the physics side (for the predicted state) and the
refinement side (for the discrepancy tracker) and presents the result
to the frontend. Placing it in a separate package keeps the Stage E
invariant intact while still exposing the endpoints the UI needs.

Three endpoints:

  POST /digital-twin/state         steady state and safety margin
  POST /digital-twin/trajectory    transient response of the two-node model
  POST /digital-twin/discrepancy   predicted-vs-observed discrepancy records

Epistemic category
------------------

Everything returned here is a model output, not a physical measurement.
The Section 21 category is simulation_result. The state response carries
that tag explicitly so the frontend can display it alongside the numbers.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.physics.receiver import eta_total
from app.physics.thermal import ThermalModel, default_model
from app.refinement.discrepancy import (
    DigitalTwinMonitor,
    DiscrepancyRecord,
    FieldThreshold,
)

router = APIRouter(prefix="/digital-twin", tags=["digital-twin"])

MAX_TRAJECTORY_SAMPLES = 2_000
"""Upper bound on the number of samples in one trajectory response. At
2,000 points the JSON payload is roughly 200 kB, appropriate for a
single page render. A query above the cap is rejected with 400 rather
than silently truncated."""


class StateRequest(BaseModel):
    incident_power_w: float = Field(
        ..., ge=0.0, description="Incident laser power at the receiver, W."
    )
    airflow_m_per_s: float = Field(..., ge=0.0, description="Airflow speed over the airframe, m/s.")
    ambient_temperature_k: float = Field(..., gt=0.0, description="Ambient temperature, K.")


class SteadyState(BaseModel):
    t_plc_k: float
    t_te_k: float
    t_plc_c: float
    t_te_c: float


class StateResponse(BaseModel):
    epistemic_tag: str = "simulation_result"
    incident_power_w: float
    airflow_m_per_s: float
    ambient_temperature_k: float
    steady_state: SteadyState | None
    thermal_runaway_power_w: float
    safety_margin_w: float
    safety_margin_fraction: float
    receiver_efficiency: float | None
    receiver_efficiency_source: str


@router.post("/state", response_model=StateResponse)
async def state(request: StateRequest) -> StateResponse:
    """Return the steady-state digital-twin state for a set of conditions.

    Raises:
        HTTPException 400 if the thermal model has no safe steady state
            even at infinitesimal power, which would indicate a broken
            model.
    """
    model = default_model()

    try:
        runaway_w = model.thermal_runaway_boundary(
            v_m_per_s=request.airflow_m_per_s,
            t_amb_k=request.ambient_temperature_k,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ss = model.steady_state(
        p_incident_w=request.incident_power_w,
        v_m_per_s=request.airflow_m_per_s,
        t_amb_k=request.ambient_temperature_k,
    )

    steady = None
    eta = None
    eta_source = "no steady state at these conditions"
    if ss is not None:
        t_plc, t_te = ss
        steady = SteadyState(
            t_plc_k=t_plc,
            t_te_k=t_te,
            t_plc_c=t_plc - 273.15,
            t_te_c=t_te - 273.15,
        )
        # eta_total takes (t_plc, t_hot, t_cold). Cold side is ambient.
        eta = eta_total(t_plc, t_te, request.ambient_temperature_k)
        eta_source = (
            "physics.receiver.eta_total at the steady-state temperatures; "
            "first-order lumped PV-TE approximation"
        )

    margin_w = runaway_w - request.incident_power_w
    margin_frac = margin_w / runaway_w if runaway_w > 0.0 else 0.0

    return StateResponse(
        incident_power_w=request.incident_power_w,
        airflow_m_per_s=request.airflow_m_per_s,
        ambient_temperature_k=request.ambient_temperature_k,
        steady_state=steady,
        thermal_runaway_power_w=runaway_w,
        safety_margin_w=margin_w,
        safety_margin_fraction=margin_frac,
        receiver_efficiency=eta,
        receiver_efficiency_source=eta_source,
    )


class TrajectoryRequest(BaseModel):
    incident_power_w: float = Field(..., ge=0.0)
    airflow_m_per_s: float = Field(..., ge=0.0)
    ambient_temperature_k: float = Field(..., gt=0.0)
    t_end_s: float = Field(..., gt=0.0, le=10_000.0)
    n_samples: int = Field(200, ge=2, le=MAX_TRAJECTORY_SAMPLES)


class TrajectorySample(BaseModel):
    time_s: float
    t_plc_k: float
    t_te_k: float


class TrajectoryResponse(BaseModel):
    epistemic_tag: str = "simulation_result"
    t_end_s: float
    n_samples: int
    samples: list[TrajectorySample]


@router.post("/trajectory", response_model=TrajectoryResponse)
async def trajectory(request: TrajectoryRequest) -> TrajectoryResponse:
    """Return the transient response of the two-node thermal model.

    The integration starts from the ambient temperature at both nodes,
    which models a cold-start at the given conditions.

    Raises:
        HTTPException 400 if the ODE integrator fails.
    """
    model: ThermalModel = default_model()
    try:
        snaps = model.simulate_trajectory(
            p_incident_w=request.incident_power_w,
            v_m_per_s=request.airflow_m_per_s,
            t_amb_k=request.ambient_temperature_k,
            t_plc_initial_k=request.ambient_temperature_k,
            t_te_initial_k=request.ambient_temperature_k,
            t_end_s=request.t_end_s,
            n_samples=request.n_samples,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return TrajectoryResponse(
        t_end_s=request.t_end_s,
        n_samples=len(snaps),
        samples=[
            TrajectorySample(time_s=s.time_s, t_plc_k=s.t_plc_k, t_te_k=s.t_te_k) for s in snaps
        ],
    )


class Observation(BaseModel):
    field_name: str
    predicted: float
    observed: float


class DiscrepancyRequest(BaseModel):
    observations: list[Observation] = Field(..., min_length=1)


class DiscrepancyRecordModel(BaseModel):
    field_name: str
    predicted: float
    observed: float
    absolute_error: float
    relative_error: float
    triggered: bool
    step: int


class DiscrepancyResponse(BaseModel):
    epistemic_tag: str = "simulation_result"
    n_observations: int
    n_triggered: int
    triggered_fields: list[str]
    should_refine: bool
    threshold_summary: dict[str, dict[str, float | None]]
    records: list[DiscrepancyRecordModel]


DEFAULT_THRESHOLDS: dict[str, FieldThreshold] = {
    "temperature_k": FieldThreshold(absolute=2.0),
    "efficiency": FieldThreshold(relative=0.05),
    "received_power_w": FieldThreshold(relative=0.10),
}
"""Default thresholds for the three state fields the Digital Twin tracks.

These match the examples in the discrepancy module docstring. A future
iteration can make the thresholds caller-configurable; the current
endpoint uses these fixed values so the response shape is stable.
"""


@router.post("/discrepancy", response_model=DiscrepancyResponse)
async def discrepancy(request: DiscrepancyRequest) -> DiscrepancyResponse:
    """Record discrepancies between predicted and observed values.

    Every observation is checked against the field's configured threshold.
    A field with no threshold configured (one not in DEFAULT_THRESHOLDS)
    is rejected with 400.

    Raises:
        HTTPException 400 for an unknown field name or non-finite input.
    """
    monitor = DigitalTwinMonitor(DEFAULT_THRESHOLDS)
    records: list[DiscrepancyRecord] = []
    for i, obs in enumerate(request.observations):
        try:
            records.append(
                monitor.observe(
                    field_name=obs.field_name,
                    predicted=obs.predicted,
                    observed=obs.observed,
                )
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"observation {i}: {exc}",
            ) from exc

    thresholds_out: dict[str, dict[str, float | None]] = {}
    for name, t in DEFAULT_THRESHOLDS.items():
        thresholds_out[name] = {"absolute": t.absolute, "relative": t.relative}

    return DiscrepancyResponse(
        n_observations=len(records),
        n_triggered=sum(1 for r in records if r.triggered),
        triggered_fields=list(monitor.triggered_fields()),
        should_refine=monitor.should_refine(),
        threshold_summary=thresholds_out,
        records=[
            DiscrepancyRecordModel(
                field_name=r.field_name,
                predicted=r.predicted,
                observed=r.observed,
                absolute_error=r.absolute_error,
                relative_error=r.relative_error,
                triggered=r.triggered,
                step=r.step,
            )
            for r in records
        ],
    )
