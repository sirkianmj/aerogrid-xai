"""HTTP endpoints for Tier 1 decisions.

The Tier 1 decision core lives in app.control.tier1. This module exposes
it over HTTP so the frontend can display decision traces. It contains no
decision logic; it is a transport layer.

POST /decisions/charge runs decide_charge_uav with the default
charge-ranking rule list (app.control.tier1.default_charge_rule_list)
and returns the structured trace produced by app.control.explain
to_structured_dict, which is the Section 15.5 format.

Every response carries the Section 21 epistemic tag
"tier1_decision_trace" (app.control.explain.EPISTEMIC_TAG), indicating
that the content is a record of the Tier 1 model's own arithmetic, not
a claim about physical reality.

Scope
-----

The rule list is fixed to the default demonstration rule list. A future
iteration can accept a caller-supplied rule list, or a list of rule
identifiers resolved server-side. For now the endpoint exposes exactly
one decision function with one rule list, because the frontend needs
only that shape to render a trace.

Tier 2 estimates are optional. When the caller passes an ``estimates``
mapping, it is merged into each candidate's inputs before the Tier 1
rules are evaluated, which is the same behaviour as calling
decide_charge_uav with ``estimates=...`` directly.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.control.explain import to_structured_dict
from app.control.tier1 import decide_charge_uav, default_charge_rule_list

router = APIRouter(prefix="/decisions", tags=["decisions"])


class ChargeDecisionRequest(BaseModel):
    """Request body for POST /decisions/charge.

    Attributes:
        candidates: One mapping per candidate UAV. Each mapping must
            contain a ``uav_id`` key; other keys are the rule inputs
            (battery_pct, mission_priority, network_centrality,
            coverage_contribution, workload_urgency, thermal_headroom_c,
            atmospheric_factor, beam_alignment, transfer_loss). Rules
            whose input key is missing are recorded as ``skipped`` in
            the trace, which is the same behaviour as the underlying
            Tier 1 evaluator.
        estimates: Optional Tier 2 surrogate outputs, merged into every
            candidate's inputs before evaluation.
    """

    candidates: list[dict[str, float]] = Field(..., min_length=1)
    estimates: dict[str, float] | None = None


class PrimaryReason(BaseModel):
    label: str
    comparison: str
    weight: float


class ConsultedRule(BaseModel):
    label: str
    comparison: str
    result: str


class Alternative(BaseModel):
    action: str
    score: float


class ChargeDecisionResponse(BaseModel):
    """Response body for POST /decisions/charge.

    Shape matches ``app.control.explain.to_structured_dict``; see
    specification Rev. 6, Section 15.5 for the field semantics.
    """

    epistemic_tag: str
    decision: str
    decision_kind: str
    primary_reasons: list[PrimaryReason]
    consulted_rules: list[ConsultedRule]
    alternative: Alternative | None
    confidence: float
    confidence_note: str


@router.post("/charge", response_model=ChargeDecisionResponse)
async def decide_charge(request: ChargeDecisionRequest) -> ChargeDecisionResponse:
    """Run the Tier 1 charge-ranking decision and return its trace.

    Raises:
        HTTPException 400 if any candidate is missing ``uav_id``.
    """
    for i, candidate in enumerate(request.candidates):
        if "uav_id" not in candidate:
            raise HTTPException(
                status_code=400,
                detail=f"candidate at index {i} is missing required key 'uav_id'",
            )

    trace = decide_charge_uav(
        candidates=request.candidates,
        rule_list=default_charge_rule_list(),
        estimates=request.estimates,
    )
    structured = to_structured_dict(trace)

    alternative: Alternative | None = None
    alt_raw = structured.get("alternative")
    if isinstance(alt_raw, dict):
        alt_action = alt_raw.get("action")
        alt_score = alt_raw.get("score")
        if isinstance(alt_action, str) and isinstance(alt_score, (int, float)):
            alternative = Alternative(action=alt_action, score=float(alt_score))

    primary_reasons: list[PrimaryReason] = []
    pr_raw = structured.get("primary_reasons")
    if isinstance(pr_raw, list):
        for item in pr_raw:
            if not isinstance(item, dict):
                continue
            label = item.get("label")
            comparison = item.get("comparison")
            weight = item.get("weight")
            if (
                isinstance(label, str)
                and isinstance(comparison, str)
                and isinstance(weight, (int, float))
            ):
                primary_reasons.append(
                    PrimaryReason(
                        label=label,
                        comparison=comparison,
                        weight=float(weight),
                    )
                )

    consulted_rules: list[ConsultedRule] = []
    cr_raw = structured.get("consulted_rules")
    if isinstance(cr_raw, list):
        for item in cr_raw:
            if not isinstance(item, dict):
                continue
            label = item.get("label")
            comparison = item.get("comparison")
            result = item.get("result")
            if isinstance(label, str) and isinstance(comparison, str) and isinstance(result, str):
                consulted_rules.append(
                    ConsultedRule(
                        label=label,
                        comparison=comparison,
                        result=result,
                    )
                )

    confidence_raw = structured.get("confidence")
    confidence = float(confidence_raw) if isinstance(confidence_raw, (int, float)) else 0.0

    return ChargeDecisionResponse(
        epistemic_tag=str(structured.get("epistemic_tag", "")),
        decision=str(structured.get("decision", "")),
        decision_kind=str(structured.get("decision_kind", "")),
        primary_reasons=primary_reasons,
        consulted_rules=consulted_rules,
        alternative=alternative,
        confidence=confidence,
        confidence_note=str(structured.get("confidence_note", "")),
    )
