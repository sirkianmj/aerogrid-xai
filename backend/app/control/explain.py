"""Explanation generation for Tier 1 decisions.

Roadmap task s5-5: Explanation generator (literal trace output).
Gate: Human-readable; matches computation path exactly.

Reference:
    AeroGrid-XAI Final Comprehensive Specification (Rev. 6),
    Section 15.5 (Example Explanation), Section 21 (Epistemic
    Hierarchy), Section 26 (Counterfactual Explainability).

Scope
-----

This module turns a DecisionTrace (produced by tier1.py) into three
output forms:

  1. Section 15.5 text rendering.
  2. A structured dictionary suitable for API responses.
  3. A JSON string for wire transport.

It also provides the counterfactual capability named in Section 26:
"exact statements of the form 'If UAV-32 battery were > 45 percent,
UAV-18 would become the preferred target' are literal facts about the
Tier 1 rule structure".

Counterfactual form
-------------------

Section 26's example counterfactual is a statement about a specific
input crossing a threshold. Computing that exactly requires inverting
the predicate, which is not decidable for arbitrary callables. This
module provides a different exact form: rule ablation. For each rule
that fired on the winner, we re-run the full decision with that rule
disabled and report whether the winner changed. The re-run uses the
same tier1.py evaluation path, so the resulting counterfactual is a
literal fact about the model's arithmetic, not a statistical
approximation. The docstring of rule_ablation_counterfactuals states
this scope explicitly.

Epistemic tag
-------------

Every rendered explanation carries the epistemic tag
"tier1_decision_trace" per Section 21. The tag denotes that the
content is a record of the Tier 1 model's own arithmetic, not a
claim about physical reality. The tag is included in the text
rendering, the structured dict, and the JSON output.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.control.tier1 import (
    DecisionTrace,
    Rule,
    SparseRuleList,
    TraceBuilder,
    decide_charge_uav,
)

EPISTEMIC_TAG = "tier1_decision_trace"
"""Section 21 category of every output from this module: a record of
the Tier 1 model's own arithmetic, not a physical-reality claim."""


@dataclass(frozen=True)
class CounterfactualResult:
    """One rule-ablation counterfactual.

    Attributes:
        removed_rule: family_name of the rule that was disabled.
        original_selected: The action originally selected.
        would_select: The action that would have been selected with
            the rule disabled.
        changed: True if would_select differs from original_selected.
        original_winner_score: Score of the original winner.
        original_runner_up_score: Score of the original runner-up.
        ablated_winner_score: Score of the winner under the ablated
            rule set. When would_select is a different candidate
            from original_selected, this is the score of that new
            candidate.
    """

    removed_rule: str
    original_selected: str
    would_select: str
    changed: bool
    original_winner_score: float
    original_runner_up_score: float
    ablated_winner_score: float


def to_structured_dict(trace: DecisionTrace) -> dict[str, object]:
    """Return a structured dict in the shape of Section 15.5.

    Sections:

      - "epistemic_tag": the Section 21 tag.
      - "decision": the selected action identifier.
      - "decision_kind": the category (charge, hold, defer).
      - "primary_reasons": list of steps that matched, in order.
      - "consulted_rules": list of every step, matched or not.
      - "alternative": the runner-up action, if any.
      - "confidence": the tier 1 rule-confidence value.
      - "confidence_note": the mandatory Section 15.5 scope
        statement.
    """
    matched = [s for s in trace.steps if s.result == "match"]
    primary_reasons = [
        {
            "label": step.label,
            "comparison": step.comparison,
            "weight": step.weight,
        }
        for step in matched
    ]
    consulted = [
        {
            "label": step.label,
            "comparison": step.comparison,
            "result": step.result,
        }
        for step in trace.steps
    ]
    alternative: dict[str, object] | None = None
    if trace.alternative_action:
        alternative = {
            "action": trace.alternative_action,
            "score": trace.alternative_score,
        }
    return {
        "epistemic_tag": EPISTEMIC_TAG,
        "decision": trace.selected_action,
        "decision_kind": trace.decision_kind.value,
        "primary_reasons": primary_reasons,
        "consulted_rules": consulted,
        "alternative": alternative,
        "confidence": trace.confidence,
        "confidence_note": (
            "Tier 1 rule-confidence; not a physical-reality guarantee (Section 15.5)."
        ),
    }


def to_json(trace: DecisionTrace, *, indent: int | None = 2) -> str:
    """Return the structured form as a JSON string."""
    return json.dumps(to_structured_dict(trace), indent=indent, sort_keys=True)


def render(trace: DecisionTrace) -> str:
    """Render the trace in the Section 15.5 text format.

    The rendering is a pure function of the trace. It cannot diverge
    from the trace because it reads only the trace's own fields.
    """
    lines: list[str] = [f"DECISION {trace.selected_action}"]
    lines.append("PRIMARY REASONS (Tier 1 decision core, exact computation trace)")
    for step in trace.steps:
        if step.result != "match":
            continue
        lines.append(f"  {step.label} (weight {step.weight:+.2f})")
    if trace.alternative_action:
        lines.append(
            f"ALTERNATIVE {trace.alternative_action} (score {trace.alternative_score:+.3f})"
        )
    lines.append(
        f"DECISION CONFIDENCE {trace.confidence * 100:.1f}% "
        "(Tier 1 rule-confidence, not a physical-reality guarantee)"
    )
    lines.append(f"EPISTEMIC TAG {EPISTEMIC_TAG}")
    return "\n".join(lines)


def rule_ablation_counterfactuals(
    trace: DecisionTrace,
    rule_list: SparseRuleList,
    candidates: Sequence[Mapping[str, float]],
    *,
    estimates: Mapping[str, float] | None = None,
) -> tuple[CounterfactualResult, ...]:
    """Return one counterfactual per rule that fired on the winner.

    For each rule that fired on the winner of the original decision,
    this function rebuilds the rule list with that rule removed,
    re-runs the same decision, and reports whether the winner changed.

    The re-run uses the same tier1.py evaluation path as the original
    decision, so the reported outcome is an exact consequence of the
    model's arithmetic under the modified rule set. It is a literal
    fact about the model, not a statistical approximation (Section
    26).

    Section 26 also names a different counterfactual form ("If UAV-32
    battery were > 45 percent ..."). That form requires inverting the
    rule predicate, which is not decidable for arbitrary callables.
    This module provides the ablation form because it is exact and
    requires no assumptions about the predicates.
    """
    original_action = trace.selected_action
    fired_labels = {step.label for step in trace.steps if step.result == "match"}

    results: list[CounterfactualResult] = []
    for rule in rule_list.rules:
        full_label = f"{rule_list.name}.{rule.family_name}"
        if full_label not in fired_labels:
            continue
        ablated = SparseRuleList(
            name=rule_list.name,
            rules=tuple(r for r in rule_list.rules if r.family_name != rule.family_name),
        )
        ablated_trace = decide_charge_uav(
            candidates,
            ablated,
            estimates=estimates,
        )
        results.append(
            CounterfactualResult(
                removed_rule=rule.family_name,
                original_selected=original_action,
                would_select=ablated_trace.selected_action,
                changed=ablated_trace.selected_action != original_action,
                original_winner_score=trace.score,
                original_runner_up_score=trace.alternative_score,
                ablated_winner_score=ablated_trace.score,
            )
        )
    return tuple(results)


def counterfactuals_to_text(
    counterfactuals: Sequence[CounterfactualResult],
) -> str:
    """Return a human-readable summary of a set of counterfactuals."""
    if not counterfactuals:
        return "(no rules fired on the winner; no counterfactuals available)"
    lines: list[str] = ["COUNTERFACTUALS (rule ablation, exact)"]
    for cf in counterfactuals:
        if cf.changed:
            lines.append(
                f"  If rule '{cf.removed_rule}' had not fired, "
                f"decision would change from {cf.original_selected} "
                f"to {cf.would_select}"
            )
        else:
            lines.append(
                f"  If rule '{cf.removed_rule}' had not fired, "
                f"decision would remain {cf.original_selected}"
            )
    return "\n".join(lines)


def _unused(_: Rule, __: TraceBuilder) -> None:
    """Keep Rule and TraceBuilder in the public import surface for
    callers that build custom rule lists and traces. The type
    checker otherwise flags the imports as unused."""
