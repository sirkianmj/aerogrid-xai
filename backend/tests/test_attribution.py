"""Tests for unsat-core-to-grammar-feature attribution.

Roadmap task s4-4: UNSAT-core-to-grammar-feature attribution
(inventive core).
Gate: Forced UNSAT correctly identifies laser link as conflict-prone.
"""

from __future__ import annotations

import random

import pytest
import z3

from app.discovery.attribution import (
    ConflictProneTable,
    FeatureConstraint,
    FeatureKind,
    GrammarFeature,
    attribute_and_mark,
    attribute_core,
    features_of_architecture,
    features_of_link,
    features_of_node,
)
from app.discovery.grammar import (
    Architecture,
    LinkInstance,
    NodeInstance,
    Terminal,
)


def _fc(
    name: str,
    expr: z3.BoolRef,
    features: set[GrammarFeature],
) -> FeatureConstraint:
    return FeatureConstraint(
        family_name=name,
        expression=expr,
        features=frozenset(features),
    )


def _node_feature(node_id: str) -> GrammarFeature:
    return GrammarFeature(FeatureKind.NODE_INSTANCE, node_id)


def _link_feature(link_id: str) -> GrammarFeature:
    return GrammarFeature(FeatureKind.LINK_INSTANCE, link_id)


def _link_type_feature(kind: Terminal) -> GrammarFeature:
    return GrammarFeature(FeatureKind.LINK_TYPE, kind.value)


# -- Feature construction ---------------------------------------------------


def test_grammar_feature_rejects_empty_identifier() -> None:
    with pytest.raises(ValueError, match="identifier must be non-empty"):
        GrammarFeature(FeatureKind.NODE_INSTANCE, "")


def test_features_of_node_returns_instance_and_type() -> None:
    n = NodeInstance(node_id="n0", kind=Terminal.UAV_ENERGY)
    feats = features_of_node(n)
    assert GrammarFeature(FeatureKind.NODE_INSTANCE, "n0") in feats
    assert GrammarFeature(FeatureKind.NODE_TYPE, Terminal.UAV_ENERGY.value) in feats
    assert len(feats) == 2


def test_features_of_link_returns_instance_and_type() -> None:
    ln = LinkInstance(
        link_id="l0",
        kind=Terminal.LASER_LINK,
        source_id="n0",
        target_id="n1",
    )
    feats = features_of_link(ln)
    assert GrammarFeature(FeatureKind.LINK_INSTANCE, "l0") in feats
    assert GrammarFeature(FeatureKind.LINK_TYPE, Terminal.LASER_LINK.value) in feats
    assert len(feats) == 2


def test_features_of_architecture_maps_every_id() -> None:
    arch = Architecture(
        nodes=(
            NodeInstance(node_id="n0", kind=Terminal.SATELLITE_LEO),
            NodeInstance(node_id="n1", kind=Terminal.UAV_ENERGY),
        ),
        links=(
            LinkInstance(
                link_id="l0",
                kind=Terminal.LASER_LINK,
                source_id="n0",
                target_id="n1",
            ),
        ),
    )
    mapping = features_of_architecture(arch)
    assert set(mapping.keys()) == {"n0", "n1", "l0"}
    assert GrammarFeature(FeatureKind.NODE_TYPE, Terminal.SATELLITE_LEO.value) in mapping["n0"]


# -- FeatureConstraint validation -------------------------------------------


def test_feature_constraint_rejects_empty_features() -> None:
    with pytest.raises(ValueError, match="no features"):
        FeatureConstraint(
            family_name="x",
            expression=z3.BoolVal(True),
            features=frozenset(),
        )


def test_feature_constraint_rejects_empty_name() -> None:
    with pytest.raises(ValueError, match="family_name must be non-empty"):
        FeatureConstraint(
            family_name="",
            expression=z3.BoolVal(True),
            features=frozenset({_node_feature("n0")}),
        )


def test_feature_constraint_rejects_non_bool_expression() -> None:
    with pytest.raises(ValueError, match="must be Boolean"):
        FeatureConstraint(
            family_name="x",
            expression=z3.RealVal(1.0),
            features=frozenset({_node_feature("n0")}),
        )


# -- Attribution: basic -----------------------------------------------------


def test_attribute_core_on_sat_case_returns_empty() -> None:
    x = z3.Real("x_sat")
    constraints = (
        _fc("a", x >= 0.0, {_node_feature("n0")}),
        _fc("b", x <= 10.0, {_node_feature("n0")}),
    )
    result = attribute_core(constraints, ())
    assert result.status == "sat"
    assert result.conflict_prone == ()
    assert result.conflict_count == 0
    assert result.is_empty


def test_attribute_core_maps_single_clause() -> None:
    x = z3.Real("x_single")
    f = _node_feature("n0")
    constraints = (_fc("only", x >= 0.0, {f}),)
    result = attribute_core(constraints, ("only",))
    assert result.status == "unsat"
    assert result.conflict_prone == (f,)


def test_attribute_core_maps_two_clauses_to_two_features() -> None:
    """The spec's example: a Laser_Link thermal constraint and a
    UAV_Energy node constraint jointly forbid the architecture."""
    x = z3.Real("x_two")
    laser = _link_type_feature(Terminal.LASER_LINK)
    uav = GrammarFeature(FeatureKind.NODE_TYPE, Terminal.UAV_ENERGY.value)
    constraints = (
        _fc("thermal_laser", x >= 10.0, {laser}),
        _fc("power_uav", x <= 5.0, {uav}),
    )
    result = attribute_core(constraints, ("power_uav", "thermal_laser"))
    assert result.status == "unsat"
    # Both features must be present; sorted order determined by
    # (kind, identifier).
    assert set(result.conflict_prone) == {laser, uav}
    assert len(result.conflict_prone) == 2


def test_attribute_core_deduplicates_shared_features() -> None:
    """Two clauses about the same link should mark that link once,
    not twice, in the conflict-prone tuple."""
    x = z3.Real("x_dedup")
    laser_inst = _link_feature("l7")
    constraints = (
        _fc("thermal_l7_a", x >= 10.0, {laser_inst}),
        _fc("thermal_l7_b", x <= 5.0, {laser_inst}),
    )
    result = attribute_core(constraints, ("thermal_l7_a", "thermal_l7_b"))
    assert result.conflict_prone == (laser_inst,)
    # But the clause_to_features traceback preserves both clauses.
    assert len(result.clause_to_features) == 2


def test_attribute_core_rejects_unknown_name() -> None:
    x = z3.Real("x_unk")
    constraints = (_fc("a", x >= 0.0, {_node_feature("n0")}),)
    with pytest.raises(ValueError, match="names not present in constraints"):
        attribute_core(constraints, ("a", "ghost"))


def test_attribute_core_clause_to_features_is_sorted() -> None:
    x = z3.Real("x_sorted")
    f1 = _node_feature("n1")
    f2 = _node_feature("n0")
    constraints = (_fc("a", x >= 0.0, {f1, f2}),)
    result = attribute_core(constraints, ("a",))
    _, feats = result.clause_to_features[0]
    assert feats == tuple(sorted({f1, f2}))


def test_attribution_conflict_prone_is_sorted() -> None:
    x = z3.Real("x_sorted2")
    constraints = (
        _fc("a", x >= 10.0, {_node_feature("zzz")}),
        _fc("b", x <= 5.0, {_node_feature("aaa")}),
    )
    result = attribute_core(constraints, ("a", "b"))
    assert result.conflict_prone == tuple(sorted(result.conflict_prone))


# -- The gate: forced UNSAT identifies laser link --------------------------


def test_forced_unsat_identifies_laser_link_as_conflict_prone() -> None:
    """The roadmap gate: an architecture that is UNSAT solely because
    a Laser_Link's thermal constraint conflicts with a UAV node's
    power constraint must have the Laser_Link identified as
    conflict-prone."""
    x = z3.Real("x_gate")
    laser_type = _link_type_feature(Terminal.LASER_LINK)
    uav_type = GrammarFeature(FeatureKind.NODE_TYPE, Terminal.UAV_ENERGY.value)
    constraints = (
        _fc("laser_thermal_max", x >= 10.0, {laser_type}),
        _fc("uav_power_max", x <= 5.0, {uav_type}),
    )
    result = attribute_core(constraints, ("laser_thermal_max", "uav_power_max"))
    assert result.status == "unsat"
    assert laser_type in result.conflict_prone, (
        f"Laser_Link not identified as conflict-prone; got {result.conflict_prone}"
    )


# -- ConflictProneTable -----------------------------------------------------


def test_table_starts_empty() -> None:
    t = ConflictProneTable()
    assert len(t) == 0
    assert t.all_marked() == ()
    assert t.to_mapping() == {}


def test_table_marks_features() -> None:
    t = ConflictProneTable()
    f = _node_feature("n0")
    t.mark([f])
    assert t.is_conflict_prone(f)
    assert t.hit_count(f) == 1
    assert f in t


def test_table_hit_count_accumulates() -> None:
    t = ConflictProneTable()
    f = _node_feature("n0")
    t.mark([f])
    t.mark([f])
    t.mark([f])
    assert t.hit_count(f) == 3


def test_table_marks_multiple_features() -> None:
    t = ConflictProneTable()
    f1 = _node_feature("a")
    f2 = _node_feature("b")
    t.mark([f1, f2])
    assert t.hit_count(f1) == 1
    assert t.hit_count(f2) == 1


def test_table_all_marked_is_sorted() -> None:
    t = ConflictProneTable()
    for f in (
        _node_feature("zzz"),
        _node_feature("aaa"),
        _node_feature("mmm"),
    ):
        t.mark([f])
    marked = t.all_marked()
    assert marked == tuple(sorted(marked))


def test_table_to_mapping_is_sorted() -> None:
    t = ConflictProneTable()
    for f in (
        _node_feature("zzz"),
        _node_feature("aaa"),
    ):
        t.mark([f])
    mapping = t.to_mapping()
    keys = list(mapping.keys())
    assert keys == sorted(keys)


def test_table_clear() -> None:
    t = ConflictProneTable()
    t.mark([_node_feature("n0")])
    assert len(t) == 1
    t.clear()
    assert len(t) == 0


def test_table_unmarked_feature_returns_zero() -> None:
    t = ConflictProneTable()
    assert t.hit_count(_node_feature("never")) == 0
    assert not t.is_conflict_prone(_node_feature("never"))


# -- Full pipeline ----------------------------------------------------------


def test_full_pipeline_sat_does_not_touch_table() -> None:
    x = z3.Real("x_pipe_sat")
    constraints = (
        _fc("a", x >= 0.0, {_node_feature("n0")}),
        _fc("b", x <= 10.0, {_node_feature("n0")}),
    )
    t = ConflictProneTable()
    result = attribute_and_mark(constraints, t)
    assert result.status == "sat"
    assert len(t) == 0


def test_full_pipeline_unsat_marks_table() -> None:
    x = z3.Real("x_pipe_unsat")
    laser = _link_type_feature(Terminal.LASER_LINK)
    constraints = (
        _fc("hi", x >= 10.0, {laser}),
        _fc("lo", x <= 5.0, {laser}),
    )
    t = ConflictProneTable()
    result = attribute_and_mark(constraints, t)
    assert result.status == "unsat"
    assert t.is_conflict_prone(laser)
    # Both clauses implicate the same feature, but attribution.conflict_prone
    # is a deduplicated tuple, so a single call to attribute_and_mark
    # increments the hit count by 1. hit_count therefore counts the
    # number of distinct UNSAT cores a feature has appeared in, not the
    # number of clauses that mention it within one core. That is the
    # semantically useful metric for biasing the discovery loop.
    assert t.hit_count(laser) == 1


def test_full_pipeline_determinism_twice() -> None:
    """The s4-8 gate: same core -> same bias, twice."""
    x = z3.Real("x_det")
    laser = _link_type_feature(Terminal.LASER_LINK)
    uav = GrammarFeature(FeatureKind.NODE_TYPE, Terminal.UAV_ENERGY.value)
    constraints = (
        _fc("a", x >= 10.0, {laser}),
        _fc("b", x <= 5.0, {uav}),
    )

    t1 = ConflictProneTable()
    t2 = ConflictProneTable()
    r1 = attribute_and_mark(constraints, t1)
    r2 = attribute_and_mark(constraints, t2)

    assert r1 == r2
    assert t1.to_mapping() == t2.to_mapping()
    assert t1.all_marked() == t2.all_marked()


# -- Different conflicts produce different markings -------------------------


def test_attribution_distinguishes_different_conflicts() -> None:
    """Two architectures with different sources of infeasibility must
    produce different conflict-prone sets."""
    x = z3.Real("x_diff")

    laser = _link_type_feature(Terminal.LASER_LINK)
    microwave = _link_type_feature(Terminal.MICROWAVE_LINK)

    # Architecture 1: laser link is the problem.
    constraints_a = (
        _fc("a_hi", x >= 10.0, {laser}),
        _fc("a_lo", x <= 5.0, {laser}),
    )
    result_a = attribute_core(constraints_a, ("a_hi", "a_lo"))

    # Architecture 2: microwave link is the problem.
    constraints_b = (
        _fc("b_hi", x >= 10.0, {microwave}),
        _fc("b_lo", x <= 5.0, {microwave}),
    )
    result_b = attribute_core(constraints_b, ("b_hi", "b_lo"))

    assert laser in result_a.conflict_prone
    assert laser not in result_b.conflict_prone
    assert microwave in result_b.conflict_prone
    assert microwave not in result_a.conflict_prone


def test_fuzz_attribution_is_deterministic_under_shuffle() -> None:
    """Shuffling the constraint list must not change the attribution
    output, because attribution is a set-based operation after the
    core names are known."""
    rng = random.Random(20261009)
    for _ in range(20):
        x = z3.Real(f"x_fuzz_{_}")
        features_a = _node_feature("f_a")
        features_b = _link_feature("f_b")
        constraints = [
            _fc("a", x >= 10.0, {features_a}),
            _fc("b", x <= 5.0, {features_b}),
        ]
        rng.shuffle(constraints)
        tuple_constraints = tuple(constraints)

        result1 = attribute_core(tuple_constraints, ("a", "b"))
        result2 = attribute_core(tuple_constraints, ("a", "b"))
        assert result1 == result2

        # Also test that the core order does not matter.
        result3 = attribute_core(tuple_constraints, ("b", "a"))
        assert result1.conflict_prone == result3.conflict_prone
