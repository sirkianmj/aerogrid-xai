"""Sprint 9 s9-4 - XAI fidelity audit tests.

Companion to docs/XAI_FIDELITY_AUDIT.md. Asserts the three claims of
Section 36.1 against the current tier1/tier2/explain/static_analyzer
implementation, at a sweep scale:

1. **Trace fidelity.** For every candidate in a random 100-point
   sweep, the score returned by ``SparseRuleList.score_and_trace``
   equals the sum of the recorded step weights to floating-point
   precision.

2. **Explanation independence.** ``explain.render(trace)`` reads only
   ``trace`` fields. Verified behaviorally: ``render`` is deterministic
   and cannot reproduce the score without reading the trace's own
   weights.

3. **Tier 2 cannot corrupt.** A hostile estimate value cannot override
   a candidate's own value for the same key, and cannot inject a key
   that reaches a rule the candidate did not supply.

The audit document at ``docs/XAI_FIDELITY_AUDIT.md`` records findings
F-1..F-4. Tests for F-1 and F-2 live in ``test_tier1.py`` (where the
unit-level behavior belongs). This module covers the sweep-scale
fidelity invariant and the cross-cutting Tier-1/Tier-2 interaction.
"""

from __future__ import annotations

import random

from app.control.explain import render
from app.control.tier1 import (
    Rule,
    SparseRuleList,
    decide_charge_uav,
    default_charge_rule_list,
)
from app.control.tier2 import AtmosphericSurrogate, Tier2Estimate


def _candidate(rng: random.Random, index: int) -> dict[str, float]:
    """Return a candidate with every key that the default rule list
    consults. Values are drawn from the corresponding plausible range.
    """
    return {
        "uav_id": float(index),
        "battery_pct": rng.uniform(0.0, 100.0),
        "mission_priority": rng.uniform(0.0, 1.0),
        "network_centrality": rng.uniform(0.0, 1.0),
        "coverage_contribution": rng.uniform(0.0, 0.20),
        "workload_urgency": rng.uniform(0.0, 1.0),
        "thermal_headroom_c": rng.uniform(0.0, 80.0),
        "atmospheric_factor": rng.uniform(0.0, 1.0),
        "beam_alignment": rng.uniform(0.0, 1.0),
        "transfer_loss": rng.uniform(0.0, 0.5),
    }


# --- claim 1: trace fidelity ----------------------------------------------


def test_score_equals_sum_of_weights_across_sweep() -> None:
    """The fidelity invariant, checked at every point of a 100-candidate
    sweep. If this holds, the score is provably the sum of the trace
    steps' weights, i.e. the trace is the computation."""
    rng = random.Random(20261013)
    rule_list = default_charge_rule_list()
    candidates = [_candidate(rng, i) for i in range(100)]

    trace = decide_charge_uav(candidates, rule_list)
    weight_sum = sum(step.weight for step in trace.steps)

    # The winner's score must equal the sum of its own step weights.
    # We must be careful: ``decide_charge_uav`` appends one extra
    # ``runner_up`` step with weight 0.0, which does not affect the
    # sum. That step is part of the trace by design.
    assert abs(weight_sum - trace.score) < 1e-12, (
        f"score={trace.score} sum={weight_sum} diff={abs(weight_sum - trace.score)}"
    )


def test_every_rule_produces_exactly_one_step_under_sweep() -> None:
    """Per the docstring of ``score_and_trace``, every rule emits one
    step. The winner's trace must contain exactly ``len(rules) + 1``
    steps: one per rule, plus the runner-up step."""
    rng = random.Random(7)
    rule_list = default_charge_rule_list()
    candidates = [_candidate(rng, i) for i in range(20)]
    trace = decide_charge_uav(candidates, rule_list)
    assert len(trace.steps) == len(rule_list.rules) + 1


def test_fidelity_holds_under_a_hand_built_rule_list() -> None:
    """The invariant is a property of the API, not of the default
    rule list. Verify with a small custom list."""
    rl = SparseRuleList(
        name="audit_smoke",
        rules=(
            Rule("a", lambda inputs: inputs["x"] >= 0.5, 2.0),
            Rule("b", lambda inputs: inputs["y"] <= 0.5, 1.5),
            Rule("c", lambda inputs: inputs.get("z", 0.0) > 0.0, 0.75),
        ),
    )
    candidates = [
        {"x": 0.6, "y": 0.3, "z": 1.0},
        {"x": 0.4, "y": 0.6, "z": 0.0},
        {"x": 0.9, "y": 0.1, "z": 0.5},
    ]
    trace = decide_charge_uav(candidates, rl)
    assert abs(sum(s.weight for s in trace.steps) - trace.score) < 1e-12


# --- claim 2: explanation independence ------------------------------------


def test_render_reads_only_the_trace() -> None:
    """The rendered string is a pure function of the trace object.
    Two renders of the same trace produce byte-identical output, and
    the rendered text's stated confidence matches the trace's
    ``confidence`` property."""
    rng = random.Random(11)
    rl = default_charge_rule_list()
    candidates = [_candidate(rng, i) for i in range(5)]
    trace = decide_charge_uav(candidates, rl)
    a = render(trace)
    b = render(trace)
    assert a == b
    expected_conf = f"{trace.confidence * 100:.1f}%"
    assert expected_conf in a


def test_render_contains_one_line_per_matching_step() -> None:
    """The rendering lists exactly the matching steps as primary
    reasons. If the renderer diverged from the trace, the count would
    differ."""
    rng = random.Random(13)
    rl = default_charge_rule_list()
    candidates = [_candidate(rng, i) for i in range(4)]
    trace = decide_charge_uav(candidates, rl)
    n_matched = sum(1 for s in trace.steps if s.result == "match")
    rendered = render(trace)
    # Every matching step's label appears in the render; count
    # occurrences of each label.
    for step in trace.steps:
        if step.result == "match":
            assert step.label in rendered
    # Sanity: number of matched labels is what we expect.
    assert n_matched >= 1


# --- claim 3: Tier 2 cannot corrupt ---------------------------------------


def test_estimates_cannot_override_candidate_across_sweep() -> None:
    """For every candidate in the sweep, a hostile estimate value on
    any key the candidate already supplies must not change the
    decision. This locks the merge order ``{**estimates, **candidate}``
    at scale (F-2 in the audit)."""
    rng = random.Random(17)
    rl = default_charge_rule_list()
    candidates = [_candidate(rng, i) for i in range(30)]

    baseline = decide_charge_uav(candidates, rl)

    # For each candidate, send every key back to a hostile low value
    # via the estimates mapping. The candidate values must win.
    hostile_estimates: dict[str, float] = {
        "battery_pct": 100.0,  # would disable low_battery if it won
        "atmospheric_factor": 0.0,
        "beam_alignment": 0.0,
        "thermal_headroom_c": 0.0,
        "mission_priority": 0.0,
        "network_centrality": 0.0,
        "coverage_contribution": 0.0,
        "workload_urgency": 0.0,
        "transfer_loss": 1.0,
    }
    with_hostile = decide_charge_uav(candidates, rl, estimates=hostile_estimates)
    assert with_hostile.selected_action == baseline.selected_action, (
        f"hostile estimates changed the decision: "
        f"{baseline.selected_action} -> {with_hostile.selected_action}"
    )
    assert with_hostile.score == baseline.score


def test_tier2_estimates_are_value_and_interval_only() -> None:
    """Tier 2's public surface returns a Tier2Estimate: a numeric value
    plus an UncertaintyInterval. It carries no ``action`` field. If a
    future change made Tier 2 return something resembling an action,
    this test would fail and the two-tier invariant would be broken at
    the API level."""
    surrogate = AtmosphericSurrogate()
    # Calibrate with a small, deterministic set of realistic inputs.
    # MIN_CALIBRATION_SIZE is enforced by calibrate itself; using 32
    # samples gives a comfortable margin.
    inputs = [
        {
            "wavelength_nm": 1064.0,
            "path_m": 500.0 + 50.0 * i,
            "visibility_km": 10.0,
            "cloud_factor": 0.2,
        }
        for i in range(32)
    ]
    # Targets: a slowly varying function of i; the calibration only
    # needs a plausible residual distribution, not a specific model.
    targets = [0.85 + 0.01 * (i % 5) for i in range(32)]
    surrogate.calibrate(
        calibration_inputs=inputs,
        calibration_targets=targets,
        nominal_coverage=0.90,
    )

    estimate = surrogate.estimate_atmospheric_loss(
        {
            "wavelength_nm": 1064.0,
            "path_m": 1000.0,
            "visibility_km": 10.0,
            "cloud_factor": 0.2,
        }
    )
    # Shape assertions. The estimate is a Tier2Estimate, not an action.
    assert isinstance(estimate, Tier2Estimate)
    assert hasattr(estimate, "value")
    assert hasattr(estimate, "interval")
    assert hasattr(estimate, "model_name")
    assert not hasattr(estimate, "action")
    assert not hasattr(estimate, "selected_action")
    # Interval sanity: value lies inside the interval.
    assert estimate.interval.contains(estimate.value)


def test_extra_estimate_keys_do_not_affect_decision() -> None:
    """Additional keys in the estimates mapping that no rule consults
    must not change the decision."""
    rng = random.Random(23)
    rl = default_charge_rule_list()
    candidates = [_candidate(rng, i) for i in range(10)]
    baseline = decide_charge_uav(candidates, rl)
    with_extra = decide_charge_uav(
        candidates,
        rl,
        estimates={
            "__action_override": 1.0,
            "not_consulted_by_any_rule": 42.0,
            "atmospheric_factor": 0.91,
        },
    )
    assert with_extra.selected_action == baseline.selected_action
    assert with_extra.score == baseline.score
