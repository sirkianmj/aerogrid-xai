"""Tier 1 interpretable decision core (Stage D of CLEAR-D).

Roadmap task s5-1: Tier 1 rule list / GAM / bounded tree.
Gate: Every decision has a literal computation trace.

Reference:
    AeroGrid-XAI Final Comprehensive Specification (Rev. 6),
    Section 15 (XAI Core - Strict Two-Tier Architecture) and
    Section 36 (Stage D - Two-Tier Explanation-Fidelity-Preserving
    Control).

Scope of this commit
--------------------

This commit establishes the Tier 1 API and the trace discipline with
one model class: SparseRuleList. The remaining Section 15.3 model
classes (GAM, bounded tree, transparent MPC) are added in later
commits on the same branch. Tier 2 surrogates (s5-2, s5-3) are not
implemented here; the Tier 1 API accepts numeric estimates as inputs
so the whole controller can be exercised before the surrogates exist.

The trace invariant
-------------------

Section 15.3: "Every action taken by this tier ... carries an
explanation that is, by construction, the literal computation path
used to reach the decision."

This is implemented by making the trace a *side effect of
evaluation*. A SparseRuleList does not have an `evaluate` method and
a separate `explain` method. It has a single `score_and_trace`
method that updates a shared TraceBuilder as it walks the rules and
returns the numeric score. There is no code path that produces a
score without also recording the trace steps that produced it.

A caller who wants to verify the trace can:

  1. Read the trace steps in order.
  2. Re-run the same rule predicates against the same inputs.
  3. Confirm the sum of the recorded weights equals the score.

If any of (1)-(3) fails, the trace is not faithful and the test
suite catches it (see test_tier1.py).

What the trace is not
---------------------

The trace is not a claim about physical reality (Section 15.5). It
is a record of the Tier 1 model's own arithmetic. It is not a
post-hoc reconstruction: the steps are recorded during evaluation,
in the order the model made them. Tier 2 estimates are inputs to
Tier 1; they are recorded as observed values when a rule consults
them, but the trace does not claim they are correct.

Function-name convention
------------------------

Section 15.3 fixes the naming convention for the two tiers:

  - Tier 2: ``estimate_*(*) -> (value, uncertainty_interval)``
  - Tier 1: ``decide_*(*, estimates) -> (action, explanation)``

Every public decision function in this module follows the Tier 1
convention. The static analyzer in s5-4 will rely on this naming to
verify that no Tier 2 function reaches the action interface.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

InputMapping = Mapping[str, float]
Predicate = Callable[[InputMapping], bool]
ObservedPairs = tuple[tuple[str, float], ...]


class DecisionKind(StrEnum):
    """The categories of Tier 1 decision issued by the controller."""

    CHARGE = "charge"
    HOLD = "hold"
    DEFER = "defer"


def _sorted_observed(inputs: Mapping[str, float]) -> ObservedPairs:
    """Return a deterministic, hashable snapshot of an input mapping."""
    return tuple(sorted((str(k), float(v)) for k, v in inputs.items()))


@dataclass(frozen=True)
class Rule:
    """A single numeric-comparison rule.

    Attributes:
        family_name: Short identifier (e.g. "low_battery").
        predicate: Callable receiving the input mapping and returning
            a bool. Predicates typically perform a bounded numeric
            comparison, but any pure function of the inputs is legal.
        weight: Score contribution when the rule matches. May be
            negative.
    """

    family_name: str
    predicate: Predicate
    weight: float

    def __post_init__(self) -> None:
        if not self.family_name:
            raise ValueError("Rule family_name must be non-empty")
        if not math.isfinite(self.weight):
            raise ValueError(f"Rule weight must be finite; got {self.weight}")


@dataclass(frozen=True)
class TraceStep:
    """A single step of a Tier 1 decision trace.

    Attributes:
        label: Dotted identifier of what was evaluated, e.g.
            "charge_ranking.low_battery".
        observed: Sorted (key, value) pairs of the input mapping at
            the moment the rule ran. Empty when the rule could not be
            evaluated due to a missing key.
        comparison: Human-readable description of the rule and its
            outcome.
        result: "match", "no_match", or "skipped".
        weight: Weight contributed to the score. Zero for
            non-matching and skipped steps.
    """

    label: str
    observed: ObservedPairs
    comparison: str
    result: str
    weight: float = 0.0


@dataclass(frozen=True)
class DecisionTrace:
    """The literal computation path of a Tier 1 decision.

    A DecisionTrace is produced as a byproduct of evaluation and
    cannot be reconstructed by inspecting the model after the fact.
    It is the exact record of every comparison the model made and
    every value it consumed.

    Attributes:
        decision_kind: The category of decision.
        selected_action: Identifier for what was selected, e.g.
            "charge_uav_32".
        steps: The ordered trace steps.
        score: Final numeric score of the winning candidate.
        alternative_action: Identifier for the runner-up candidate,
            or empty string when there is only one candidate.
        alternative_score: Score of the runner-up candidate.
    """

    decision_kind: DecisionKind
    selected_action: str
    steps: tuple[TraceStep, ...]
    score: float
    alternative_action: str = ""
    alternative_score: float = 0.0

    @property
    def confidence(self) -> float:
        """Tier 1 rule-confidence, not a physical-reality guarantee.

        Defined as the normalized margin between the winner's score
        and the runner-up's score. When there is no alternative, the
        confidence is 1.0. Section 15.5 requires this quantity to be
        labeled in the UI as a rule-confidence, not a claim about
        physical reality, and the render() output does so.
        """
        if not self.alternative_action:
            return 1.0
        w = self.score
        a = self.alternative_score
        denom = abs(w) + abs(a)
        if denom <= 1e-12:
            return 1.0
        raw = (w - a) / denom
        return max(0.0, min(1.0, raw))

    def render(self) -> str:
        """Human-readable rendering of the trace.

        The rendering is the same data as the trace, formatted for
        display. It adds no information and cannot diverge.
        """
        lines: list[str] = [f"DECISION {self.selected_action}"]
        for step in self.steps:
            weight_str = f" (weight {step.weight:+.2f})" if step.weight != 0.0 else ""
            lines.append(f"  {step.label}: {step.comparison} -> {step.result}{weight_str}")
        if self.alternative_action:
            lines.append(
                f"ALTERNATIVE {self.alternative_action} (score {self.alternative_score:+.3f})"
            )
        lines.append(
            f"DECISION CONFIDENCE {self.confidence * 100:.1f}% "
            "(Tier 1 rule-confidence, not a physical-reality guarantee)"
        )
        return "\n".join(lines)


class TraceBuilder:
    """Accumulator for building a DecisionTrace during evaluation.

    Passed through the evaluation as a mutable context so that every
    comparison performed by the model records itself to the trace as
    it happens. The trace cannot be built without also performing the
    evaluation, because the builder is the only path by which
    evaluation records its intermediate observations.
    """

    def __init__(self, kind: DecisionKind) -> None:
        self._kind = kind
        self._steps: list[TraceStep] = []

    def record(
        self,
        *,
        label: str,
        observed: Mapping[str, float],
        comparison: str,
        result: str,
        weight: float = 0.0,
    ) -> None:
        self._steps.append(
            TraceStep(
                label=label,
                observed=_sorted_observed(observed),
                comparison=comparison,
                result=result,
                weight=weight,
            )
        )

    def steps(self) -> tuple[TraceStep, ...]:
        return tuple(self._steps)

    def finalize(
        self,
        *,
        selected_action: str,
        score: float,
        alternative_action: str = "",
        alternative_score: float = 0.0,
    ) -> DecisionTrace:
        return DecisionTrace(
            decision_kind=self._kind,
            selected_action=selected_action,
            steps=self.steps(),
            score=score,
            alternative_action=alternative_action,
            alternative_score=alternative_score,
        )


@dataclass(frozen=True)
class SparseRuleList:
    """An ordered list of numeric-comparison rules.

    A SparseRuleList is a Tier 1 model class: its explanation is its
    computation. Rules are evaluated top-to-bottom; the score is the
    sum of weights of matching rules. Non-matching rules still emit a
    trace step, so the trace records exactly which rules were
    consulted and which fired.

    Attributes:
        name: Human-readable name used as a trace label prefix.
        rules: The ordered rules.
    """

    name: str
    rules: tuple[Rule, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("SparseRuleList name must be non-empty")
        seen: set[str] = set()
        for rule in self.rules:
            if rule.family_name in seen:
                raise ValueError(
                    f"Duplicate rule family_name '{rule.family_name}' "
                    f"in SparseRuleList '{self.name}'"
                )
            seen.add(rule.family_name)

    def score_and_trace(
        self,
        inputs: Mapping[str, float],
        builder: TraceBuilder,
    ) -> float:
        """Evaluate every rule against inputs and record the trace.

        Returns the total score (sum of weights of matching rules).
        Every rule produces exactly one TraceStep. The step's weight
        is the rule's weight if the rule matched, zero otherwise. The
        sum of step weights therefore equals the returned score
        exactly, and this equality is what makes the trace faithful:
        it can be verified by reading the trace and summing the
        weights.
        """
        total = 0.0
        for rule in self.rules:
            label = f"{self.name}.{rule.family_name}"
            try:
                matched = bool(rule.predicate(inputs))
            except (KeyError, TypeError):
                builder.record(
                    label=label,
                    observed={},
                    comparison=(
                        f"rule {rule.family_name} could not be evaluated "
                        "(missing or malformed input)"
                    ),
                    result="skipped",
                    weight=0.0,
                )
                continue
            if matched:
                total += rule.weight
                builder.record(
                    label=label,
                    observed=inputs,
                    comparison=f"rule {rule.family_name} matched",
                    result="match",
                    weight=rule.weight,
                )
            else:
                builder.record(
                    label=label,
                    observed=inputs,
                    comparison=f"rule {rule.family_name} did not match",
                    result="no_match",
                    weight=0.0,
                )
        return total


def decide_charge_uav(
    candidates: Sequence[Mapping[str, float]],
    rule_list: SparseRuleList,
    *,
    estimates: Mapping[str, float] | None = None,
) -> DecisionTrace:
    """Choose which UAV to charge from a list of candidates.

    Signature follows the Tier 1 convention of Section 15.3:
    ``decide_*(*, estimates) -> (action, explanation)``. The
    ``estimates`` mapping is nominally the output of Tier 2
    surrogates; here it is merged into each candidate's input so the
    rule predicates can reference keys like "atmospheric_factor" and
    "beam_alignment". When no estimates are provided, an empty
    mapping is used.

    Ranks every candidate by ``rule_list.score_and_trace``. The
    candidate with the highest score is selected. Ties are broken by
    the position of the candidate in the input sequence. The trace
    of the winning candidate is returned, with one additional step
    recording the runner-up.

    Raises:
        ValueError if candidates is empty.
    """
    if not candidates:
        raise ValueError("candidates must be non-empty")

    base: dict[str, float] = dict(estimates or {})

    results: list[tuple[int, float, TraceBuilder, Mapping[str, float]]] = []
    for idx, candidate in enumerate(candidates):
        merged: dict[str, float] = {**base, **dict(candidate)}
        builder = TraceBuilder(DecisionKind.CHARGE)
        score = rule_list.score_and_trace(merged, builder)
        results.append((idx, score, builder, merged))

    # Stable sort by descending score; ties preserve input order.
    results.sort(key=lambda triple: (-triple[1], triple[0]))

    winner_idx, winner_score, winner_builder, winner_inputs = results[0]
    winner_id = _candidate_id(winner_inputs, winner_idx)
    winner_action = f"charge_uav_{winner_id}"

    alternative_action = ""
    alternative_score = 0.0
    if len(results) > 1:
        alt_idx, alt_score, _, alt_inputs = results[1]
        alt_id = _candidate_id(alt_inputs, alt_idx)
        alternative_action = f"charge_uav_{alt_id}"
        alternative_score = alt_score
        winner_builder.record(
            label=f"{rule_list.name}.alternative",
            observed={
                "winner_score": winner_score,
                "alternative_score": alt_score,
            },
            comparison=(
                f"runner-up candidate {alt_id} has score "
                f"{alt_score:+.3f} vs winner {winner_score:+.3f}"
            ),
            result="runner_up",
            weight=0.0,
        )

    return winner_builder.finalize(
        selected_action=winner_action,
        score=winner_score,
        alternative_action=alternative_action,
        alternative_score=alternative_score,
    )


def _candidate_id(inputs: Mapping[str, float], fallback_index: int) -> str:
    """Extract a UAV identifier from a candidate mapping.

    Uses the "uav_id" key when present, otherwise the fallback index.
    """
    if "uav_id" in inputs:
        try:
            return str(int(inputs["uav_id"]))
        except (ValueError, OverflowError):
            return str(inputs["uav_id"])
    return str(fallback_index)


def default_charge_rule_list() -> SparseRuleList:
    """Return a demonstration charge-ranking rule list.

    The weights and thresholds here are chosen to match the structure
    of Section 15.5's example decision (charge the UAV with low
    battery, high mission priority, high network centrality, high
    coverage contribution, critical workload, adequate thermal
    headroom, favorable atmosphere, good beam alignment, low expected
    transfer loss). They are NOT calibrated against any physical
    measurement and are NOT part of the CLEAR-D method. They exist to
    exercise the trace discipline; they are a test fixture with a
    plausible shape, and any real deployment must supply its own rule
    list with sourced thresholds.
    """

    def has(key: str, op: Callable[[float], bool]) -> Predicate:
        def predicate(inputs: InputMapping) -> bool:
            if key not in inputs:
                raise KeyError(key)
            return op(float(inputs[key]))

        return predicate

    rules: tuple[Rule, ...] = (
        Rule("low_battery", has("battery_pct", lambda v: v < 20.0), 3.0),
        Rule("mission_priority_high", has("mission_priority", lambda v: v >= 0.7), 2.5),
        Rule("network_centrality_high", has("network_centrality", lambda v: v >= 0.6), 2.0),
        Rule("coverage_high", has("coverage_contribution", lambda v: v >= 0.05), 1.5),
        Rule("workload_critical", has("workload_urgency", lambda v: v >= 0.7), 2.0),
        Rule("thermal_headroom_ok", has("thermal_headroom_c", lambda v: v >= 30.0), 1.0),
        Rule("atmosphere_favorable", has("atmospheric_factor", lambda v: v >= 0.8), 1.0),
        Rule("beam_alignment_good", has("beam_alignment", lambda v: v >= 0.9), 1.5),
        Rule("transfer_loss_low", has("transfer_loss", lambda v: v <= 0.15), 1.0),
    )
    return SparseRuleList(name="charge_ranking", rules=rules)
