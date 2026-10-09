"""Tests for the Tier 1 explanation generator.

Roadmap task s5-5: Explanation generator (literal trace output).
Gate: Human-readable; matches computation path exactly.
"""

from __future__ import annotations

import json

import pytest

from app.control.explain import (
    EPISTEMIC_TAG,
    CounterfactualResult,
    counterfactuals_to_text,
    render,
    rule_ablation_counterfactuals,
    to_json,
    to_structured_dict,
)
from app.control.tier1 import (
    Rule,
    SparseRuleList,
    decide_charge_uav,
    default_charge_rule_list,
)


def _sample_trace() -> tuple[object, SparseRuleList, list[dict[str, float]]]:
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
    return trace, rl, candidates


# -- structured dict --------------------------------------------------------


def test_structured_dict_has_epistemic_tag() -> None:
    trace, _, _ = _sample_trace()
    d = to_structured_dict(trace)  # type: ignore[arg-type]
    assert d["epistemic_tag"] == EPISTEMIC_TAG


def test_structured_dict_decision_fields() -> None:
    trace, _, _ = _sample_trace()
    d = to_structured_dict(trace)  # type: ignore[arg-type]
    assert d["decision"] == "charge_uav_32"
    assert d["decision_kind"] == "charge"


def test_structured_dict_primary_reasons_only_matched() -> None:
    trace, _, _ = _sample_trace()
    d = to_structured_dict(trace)  # type: ignore[arg-type]
    reasons = d["primary_reasons"]
    assert isinstance(reasons, list)
    for r in reasons:
        assert isinstance(r, dict)
        assert "label" in r and "weight" in r


def test_structured_dict_consulted_includes_all() -> None:
    trace, _, _ = _sample_trace()
    d = to_structured_dict(trace)  # type: ignore[arg-type]
    consulted = d["consulted_rules"]
    assert isinstance(consulted, list)
    assert len(consulted) == len(trace.steps)  # type: ignore[attr-defined]


def test_structured_dict_alternative() -> None:
    trace, _, _ = _sample_trace()
    d = to_structured_dict(trace)  # type: ignore[arg-type]
    alt = d["alternative"]
    assert isinstance(alt, dict)
    assert alt["action"] == "charge_uav_18"


def test_structured_dict_confidence_in_unit_interval() -> None:
    trace, _, _ = _sample_trace()
    d = to_structured_dict(trace)  # type: ignore[arg-type]
    c = d["confidence"]
    assert isinstance(c, float)
    assert 0.0 <= c <= 1.0


def test_structured_dict_single_candidate_no_alternative() -> None:
    rl = default_charge_rule_list()
    trace = decide_charge_uav([{"uav_id": 7.0}], rl)
    d = to_structured_dict(trace)
    assert d["alternative"] is None


# -- JSON -------------------------------------------------------------------


def test_json_is_valid() -> None:
    trace, _, _ = _sample_trace()
    s = to_json(trace)  # type: ignore[arg-type]
    parsed = json.loads(s)
    assert parsed["epistemic_tag"] == EPISTEMIC_TAG
    assert parsed["decision"] == "charge_uav_32"


def test_json_is_deterministic() -> None:
    trace, _, _ = _sample_trace()
    a = to_json(trace)  # type: ignore[arg-type]
    b = to_json(trace)  # type: ignore[arg-type]
    assert a == b


# -- render -----------------------------------------------------------------


def test_render_contains_decision_header() -> None:
    trace, _, _ = _sample_trace()
    text = render(trace)  # type: ignore[arg-type]
    assert "DECISION charge_uav_32" in text


def test_render_lists_primary_reasons() -> None:
    trace, _, _ = _sample_trace()
    text = render(trace)  # type: ignore[arg-type]
    assert "PRIMARY REASONS" in text
    assert "charge_ranking.low_battery" in text


def test_render_alternative_line() -> None:
    trace, _, _ = _sample_trace()
    text = render(trace)  # type: ignore[arg-type]
    assert "ALTERNATIVE charge_uav_18" in text


def test_render_contains_epistemic_tag() -> None:
    trace, _, _ = _sample_trace()
    text = render(trace)  # type: ignore[arg-type]
    assert EPISTEMIC_TAG in text


def test_render_contains_confidence_disclaimer() -> None:
    trace, _, _ = _sample_trace()
    text = render(trace)  # type: ignore[arg-type]
    assert "rule-confidence" in text
    assert "not a physical-reality guarantee" in text


# -- Counterfactuals --------------------------------------------------------


def test_counterfactual_ablating_decisive_rule_flips_decision() -> None:
    """Construct a two-candidate decision where each candidate wins
    on a single decisive rule, and confirm that ablating the winner's
    decisive rule flips the decision."""
    rl = SparseRuleList(
        name="decisive_pair",
        rules=(
            Rule("uav_1_high", lambda x: x.get("v", 0.0) > 5.0, 10.0),
            Rule("uav_2_high", lambda x: x.get("w", 0.0) > 5.0, 8.0),
        ),
    )
    candidates = [
        {"uav_id": 1.0, "v": 10.0},
        {"uav_id": 2.0, "w": 10.0},
    ]
    trace = decide_charge_uav(candidates, rl)
    assert trace.selected_action == "charge_uav_1"
    cfs = rule_ablation_counterfactuals(trace, rl, candidates)
    by_rule = {cf.removed_rule: cf for cf in cfs}
    assert by_rule["uav_1_high"].changed is True
    assert by_rule["uav_1_high"].would_select == "charge_uav_2"


def test_counterfactual_ablating_tied_rule_does_not_flip() -> None:
    """Removing a rule whose removal leaves the winner tied with the
    runner-up does not flip the decision, because the tie-break is
    input order and the winner is at index 0."""
    trace, rl, candidates = _sample_trace()
    cfs = rule_ablation_counterfactuals(trace, rl, candidates)  # type: ignore[arg-type]
    by_rule = {cf.removed_rule: cf for cf in cfs}
    assert "low_battery" in by_rule
    low_batt = by_rule["low_battery"]
    assert low_batt.changed is False
    assert low_batt.would_select == "charge_uav_32"


def test_counterfactual_returns_one_per_fired_rule() -> None:
    trace, rl, candidates = _sample_trace()
    cfs = rule_ablation_counterfactuals(trace, rl, candidates)  # type: ignore[arg-type]
    fired = [s for s in trace.steps if s.result == "match"]  # type: ignore[attr-defined]
    assert len(cfs) == len(fired)


def test_counterfactual_alternate_rule_does_not_flip() -> None:
    """Removing a rule that does not change the ranking reports
    changed=False."""
    rl = SparseRuleList(
        name="two_rules",
        rules=(
            Rule("decisive", lambda x: x.get("v", 0.0) > 5.0, 10.0),
            Rule("irrelevant", lambda x: True, 1.0),
        ),
    )
    candidates = [{"uav_id": 1.0, "v": 10.0}, {"uav_id": 2.0, "v": 0.0}]
    trace = decide_charge_uav(candidates, rl)
    cfs = rule_ablation_counterfactuals(trace, rl, candidates)
    by_rule = {cf.removed_rule: cf for cf in cfs}
    assert by_rule["irrelevant"].changed is False
    assert by_rule["decisive"].changed is False  # winner still wins


def test_counterfactual_text_summary() -> None:
    trace, rl, candidates = _sample_trace()
    cfs = rule_ablation_counterfactuals(trace, rl, candidates)  # type: ignore[arg-type]
    text = counterfactuals_to_text(cfs)
    assert "COUNTERFACTUALS" in text


def test_counterfactual_text_empty() -> None:
    text = counterfactuals_to_text(())
    assert "no rules fired" in text


def test_counterfactual_result_is_frozen() -> None:
    from dataclasses import FrozenInstanceError

    cf = CounterfactualResult(
        removed_rule="r",
        original_selected="a",
        would_select="b",
        changed=True,
        original_winner_score=1.0,
        original_runner_up_score=0.5,
        ablated_winner_score=0.8,
    )
    with pytest.raises(FrozenInstanceError):
        cf.changed = False  # type: ignore[misc]


# -- Determinism ------------------------------------------------------------


def test_render_is_deterministic() -> None:
    trace, _, _ = _sample_trace()
    assert render(trace) == render(trace)  # type: ignore[arg-type]


def test_counterfactuals_are_deterministic() -> None:
    trace, rl, candidates = _sample_trace()
    a = rule_ablation_counterfactuals(trace, rl, candidates)  # type: ignore[arg-type]
    b = rule_ablation_counterfactuals(trace, rl, candidates)  # type: ignore[arg-type]
    assert a == b
