"""Tests for the Tier 1 interpretable decision core.

Roadmap task s5-1: Tier 1 rule list / GAM / bounded tree.
Gate: Every decision has a literal computation trace.
"""

from __future__ import annotations

import pytest

from app.control.tier1 import (
    DecisionKind,
    DecisionTrace,
    Rule,
    SparseRuleList,
    TraceBuilder,
    decide_charge_uav,
    default_charge_rule_list,
)

# -- Rule validation ---------------------------------------------------------


def test_rule_rejects_empty_family_name() -> None:
    with pytest.raises(ValueError, match="family_name must be non-empty"):
        Rule("", lambda x: True, 1.0)


def test_rule_rejects_non_finite_weight() -> None:
    with pytest.raises(ValueError, match="weight must be finite"):
        Rule("r", lambda x: True, float("inf"))
    with pytest.raises(ValueError, match="weight must be finite"):
        Rule("r", lambda x: True, float("nan"))


# -- SparseRuleList validation ----------------------------------------------


def test_rule_list_rejects_empty_name() -> None:
    with pytest.raises(ValueError, match="name must be non-empty"):
        SparseRuleList(name="")


def test_rule_list_rejects_duplicate_family_names() -> None:
    rules = (
        Rule("a", lambda x: True, 1.0),
        Rule("a", lambda x: False, 2.0),
    )
    with pytest.raises(ValueError, match="Duplicate rule family_name 'a'"):
        SparseRuleList(name="dup", rules=rules)


# -- Scoring -----------------------------------------------------------------


def test_empty_rule_list_scores_zero() -> None:
    rl = SparseRuleList(name="empty")
    builder = TraceBuilder(DecisionKind.CHARGE)
    score = rl.score_and_trace({}, builder)
    assert score == 0.0
    assert builder.steps() == ()


def test_matching_rule_contributes_weight() -> None:
    rl = SparseRuleList(
        name="simple",
        rules=(Rule("is_high", lambda x: x.get("v", 0.0) > 10.0, 2.0),),
    )
    builder = TraceBuilder(DecisionKind.CHARGE)
    score = rl.score_and_trace({"v": 20.0}, builder)
    assert score == 2.0


def test_non_matching_rule_contributes_zero() -> None:
    rl = SparseRuleList(
        name="simple",
        rules=(Rule("is_high", lambda x: x.get("v", 0.0) > 10.0, 2.0),),
    )
    builder = TraceBuilder(DecisionKind.CHARGE)
    score = rl.score_and_trace({"v": 5.0}, builder)
    assert score == 0.0


def test_multiple_rules_sum_weights() -> None:
    rl = SparseRuleList(
        name="multi",
        rules=(
            Rule("r1", lambda x: True, 1.0),
            Rule("r2", lambda x: True, 2.0),
            Rule("r3", lambda x: False, 100.0),
            Rule("r4", lambda x: True, -0.5),
        ),
    )
    builder = TraceBuilder(DecisionKind.CHARGE)
    score = rl.score_and_trace({}, builder)
    assert score == pytest.approx(2.5)


# -- Trace faithfulness (the s5-1 gate) --------------------------------------


def test_trace_score_equals_sum_of_step_weights() -> None:
    """The trace is faithful iff the sum of recorded step weights
    equals the reported score. This is the operational form of the
    s5-1 gate."""
    rl = default_charge_rule_list()
    builder = TraceBuilder(DecisionKind.CHARGE)
    candidate = {
        "uav_id": 32.0,
        "battery_pct": 19.0,
        "mission_priority": 0.9,
        "network_centrality": 0.8,
        "coverage_contribution": 0.084,
        "workload_urgency": 0.9,
        "thermal_headroom_c": 38.0,
        "atmospheric_factor": 0.95,
        "beam_alignment": 0.94,
        "transfer_loss": 0.11,
    }
    reported_score = rl.score_and_trace(candidate, builder)
    sum_of_weights = sum(step.weight for step in builder.steps())
    assert reported_score == pytest.approx(sum_of_weights)


def test_trace_records_one_step_per_rule() -> None:
    rl = default_charge_rule_list()
    builder = TraceBuilder(DecisionKind.CHARGE)
    rl.score_and_trace({"battery_pct": 15.0}, builder)
    assert len(builder.steps()) == len(rl.rules)


def test_trace_steps_are_in_rule_order() -> None:
    rl = default_charge_rule_list()
    builder = TraceBuilder(DecisionKind.CHARGE)
    rl.score_and_trace({}, builder)
    labels = [step.label for step in builder.steps()]
    expected = [f"{rl.name}.{r.family_name}" for r in rl.rules]
    assert labels == expected


def test_missing_input_produces_skipped_step() -> None:
    """A rule whose predicate raises KeyError must produce a skipped
    step, not an exception."""
    rl = SparseRuleList(
        name="needs_v",
        rules=(Rule("needs_v", lambda x: x["v"] > 0.0, 1.0),),
    )
    builder = TraceBuilder(DecisionKind.CHARGE)
    score = rl.score_and_trace({}, builder)
    assert score == 0.0
    steps = builder.steps()
    assert len(steps) == 1
    assert steps[0].result == "skipped"


def test_replay_reproduces_score() -> None:
    """A caller can replay a trace: re-running the same rule
    predicates against the same inputs yields the same score."""
    rl = default_charge_rule_list()
    candidate = {
        "battery_pct": 19.0,
        "mission_priority": 0.9,
        "network_centrality": 0.8,
        "coverage_contribution": 0.084,
        "workload_urgency": 0.9,
        "thermal_headroom_c": 38.0,
        "atmospheric_factor": 0.95,
        "beam_alignment": 0.94,
        "transfer_loss": 0.11,
    }
    builder_a = TraceBuilder(DecisionKind.CHARGE)
    score_a = rl.score_and_trace(candidate, builder_a)

    builder_b = TraceBuilder(DecisionKind.CHARGE)
    score_b = rl.score_and_trace(candidate, builder_b)

    assert score_a == score_b
    assert builder_a.steps() == builder_b.steps()


def test_trace_is_deterministic_across_calls() -> None:
    rl = default_charge_rule_list()
    candidate = {"battery_pct": 15.0, "mission_priority": 0.8}
    t1 = decide_charge_uav([candidate], rl)
    t2 = decide_charge_uav([candidate], rl)
    assert t1 == t2


# -- decide_charge_uav ------------------------------------------------------


def test_decide_charge_uav_rejects_empty() -> None:
    with pytest.raises(ValueError, match="candidates must be non-empty"):
        decide_charge_uav([], default_charge_rule_list())


def test_decide_charge_uav_picks_highest_score() -> None:
    rl = default_charge_rule_list()
    candidates = [
        {"uav_id": 1.0, "battery_pct": 45.0},
        {
            "uav_id": 32.0,
            "battery_pct": 19.0,
            "mission_priority": 0.9,
            "network_centrality": 0.8,
            "coverage_contribution": 0.084,
            "workload_urgency": 0.9,
            "thermal_headroom_c": 38.0,
            "atmospheric_factor": 0.95,
            "beam_alignment": 0.94,
            "transfer_loss": 0.11,
        },
        {"uav_id": 3.0, "battery_pct": 20.0},
    ]
    trace = decide_charge_uav(candidates, rl)
    assert trace.selected_action == "charge_uav_32"
    assert trace.decision_kind == DecisionKind.CHARGE


def test_decide_charge_uav_tie_break_is_input_order() -> None:
    rl = SparseRuleList(name="all_tie", rules=())
    candidates = [
        {"uav_id": 1.0},
        {"uav_id": 2.0},
    ]
    trace = decide_charge_uav(candidates, rl)
    assert trace.selected_action == "charge_uav_1"


def test_decide_charge_uav_records_alternative() -> None:
    rl = default_charge_rule_list()
    candidates = [
        {
            "uav_id": 32.0,
            "battery_pct": 19.0,
            "mission_priority": 0.9,
            "network_centrality": 0.8,
            "coverage_contribution": 0.084,
            "workload_urgency": 0.9,
            "thermal_headroom_c": 38.0,
            "atmospheric_factor": 0.95,
            "beam_alignment": 0.94,
            "transfer_loss": 0.11,
        },
        {"uav_id": 18.0, "battery_pct": 25.0, "mission_priority": 0.5},
    ]
    trace = decide_charge_uav(candidates, rl)
    assert trace.alternative_action == "charge_uav_18"


def test_decide_charge_uav_single_candidate_has_no_alternative() -> None:
    rl = default_charge_rule_list()
    trace = decide_charge_uav([{"uav_id": 7.0}], rl)
    assert trace.alternative_action == ""
    assert trace.confidence == 1.0


def test_decide_charge_uav_merges_estimates() -> None:
    """Estimates from Tier 2 are merged into the candidate inputs
    before scoring, so rules can reference them."""
    rl = SparseRuleList(
        name="needs_estimate",
        rules=(
            Rule(
                "atmospheric_factor_high",
                lambda x: x["atmospheric_factor"] >= 0.8,
                5.0,
            ),
        ),
    )
    candidates = [{"uav_id": 1.0}]
    estimates = {"atmospheric_factor": 0.9}
    trace = decide_charge_uav(candidates, rl, estimates=estimates)
    assert trace.score == 5.0


def test_candidate_without_uav_id_uses_index() -> None:
    rl = SparseRuleList(name="all_tie", rules=())
    trace = decide_charge_uav([{}], rl)
    assert trace.selected_action == "charge_uav_0"


# -- Confidence --------------------------------------------------------------


def test_confidence_in_unit_interval() -> None:
    rl = default_charge_rule_list()
    candidates = [
        {
            "uav_id": 32.0,
            "battery_pct": 19.0,
            "mission_priority": 0.9,
            "network_centrality": 0.8,
            "coverage_contribution": 0.084,
            "workload_urgency": 0.9,
            "thermal_headroom_c": 38.0,
            "atmospheric_factor": 0.95,
            "beam_alignment": 0.94,
            "transfer_loss": 0.11,
        },
        {"uav_id": 18.0},
    ]
    trace = decide_charge_uav(candidates, rl)
    assert 0.0 <= trace.confidence <= 1.0
    assert trace.confidence > 0.0


def test_confidence_is_zero_when_scores_tie() -> None:
    rl = SparseRuleList(name="all_tie", rules=())
    candidates = [{"uav_id": 1.0}, {"uav_id": 2.0}]
    trace = decide_charge_uav(candidates, rl)
    assert trace.confidence == 1.0  # both scores zero -> special case


# -- render() ----------------------------------------------------------------


def test_render_contains_decision_line() -> None:
    rl = default_charge_rule_list()
    trace = decide_charge_uav([{"uav_id": 7.0}], rl)
    text = trace.render()
    assert "DECISION charge_uav_7" in text


def test_render_labels_confidence_as_rule_confidence() -> None:
    rl = default_charge_rule_list()
    trace = decide_charge_uav([{"uav_id": 7.0}], rl)
    text = trace.render()
    assert "rule-confidence" in text
    assert "not a physical-reality guarantee" in text


def test_render_contains_alternative_when_present() -> None:
    rl = default_charge_rule_list()
    trace = decide_charge_uav([{"uav_id": 1.0, "battery_pct": 10.0}, {"uav_id": 2.0}], rl)
    text = trace.render()
    assert "ALTERNATIVE" in text
    assert "charge_uav_2" in text


# -- Fixture sanity ---------------------------------------------------------


def test_default_charge_rule_list_is_deterministic() -> None:
    a = default_charge_rule_list()
    b = default_charge_rule_list()
    assert a.name == b.name
    assert len(a.rules) == len(b.rules)
    assert [r.family_name for r in a.rules] == [r.family_name for r in b.rules]


def test_decision_trace_is_frozen() -> None:
    from dataclasses import FrozenInstanceError

    rl = SparseRuleList(name="x", rules=())
    trace = decide_charge_uav([{"uav_id": 1.0}], rl)
    with pytest.raises(FrozenInstanceError):
        trace.selected_action = "other"  # type: ignore[misc]


# -- Trace builder ----------------------------------------------------------


def test_trace_builder_steps_are_read_only_tuple() -> None:
    builder = TraceBuilder(DecisionKind.CHARGE)
    builder.record(
        label="x",
        observed={"v": 1.0},
        comparison="v > 0",
        result="match",
        weight=1.0,
    )
    steps = builder.steps()
    assert isinstance(steps, tuple)


def test_trace_builder_finalize_produces_trace() -> None:
    builder = TraceBuilder(DecisionKind.HOLD)
    builder.record(
        label="x",
        observed={},
        comparison="no-op",
        result="match",
        weight=0.0,
    )
    trace = builder.finalize(selected_action="hold_uav_5", score=0.0)
    assert isinstance(trace, DecisionTrace)
    assert trace.decision_kind == DecisionKind.HOLD
    assert trace.selected_action == "hold_uav_5"
