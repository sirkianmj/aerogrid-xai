"""Tests for the architecture grammar.

Roadmap task s4-1: Architecture grammar (context-free).
Gate: Parse tree -> architecture object round-trip correct.

The round trip exercised here is:

    Architecture  --architecture_to_derivation-->  DerivationStep tuple
    DerivationStep tuple  --derivation_to_architecture-->  Architecture

and the test asserts the two endpoints are equal as frozen
dataclasses. Because Architecture equality is structural and IDs are
assigned deterministically from position, this is a strict check.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from app.discovery.grammar import (
    LINK_TERMINALS,
    NODE_TERMINALS,
    PRODUCTION_RULES,
    Architecture,
    DerivationStep,
    LinkInstance,
    NodeInstance,
    NonTerminal,
    ProductionRule,
    Terminal,
    architecture_to_derivation,
    derivation_to_architecture,
    rules_for,
)

# -- Static grammar structure ------------------------------------------------


def test_node_terminals_are_exactly_the_spec_set() -> None:
    """Section 35.1 lists exactly these five node terminals. Changing
    this set without a corresponding Stage B constraint family would
    break encoding soundness."""
    expected = {
        Terminal.SATELLITE_GEO,
        Terminal.SATELLITE_LEO,
        Terminal.UAV_ENERGY,
        Terminal.UAV_COMPUTE,
        Terminal.GROUND_STATION,
    }
    assert expected == NODE_TERMINALS


def test_link_terminals_are_exactly_the_spec_set() -> None:
    expected = {
        Terminal.LASER_LINK,
        Terminal.MICROWAVE_LINK,
        Terminal.HYBRID_LINK,
    }
    assert expected == LINK_TERMINALS


def test_node_and_link_terminals_are_disjoint() -> None:
    assert NODE_TERMINALS.isdisjoint(LINK_TERMINALS)


def test_production_rules_cover_every_non_terminal() -> None:
    """Every non-terminal except the start symbol must appear on the
    left-hand side of at least one production rule."""
    lhs_set = {r.lhs for r in PRODUCTION_RULES}
    for nt in NonTerminal:
        assert nt in lhs_set, f"Non-terminal {nt} has no production rule"


def test_start_symbol_is_architecture() -> None:
    assert NonTerminal.ARCHITECTURE in {r.lhs for r in PRODUCTION_RULES}


def test_rules_for_returns_matching_rules() -> None:
    node_rules = rules_for(NonTerminal.NODE)
    assert len(node_rules) == len(NODE_TERMINALS)
    for rule in node_rules:
        assert rule.lhs == NonTerminal.NODE
        assert len(rule.rhs) == 1
        assert isinstance(rule.rhs[0], Terminal)
        assert rule.rhs[0] in NODE_TERMINALS


def test_modality_rules_cover_every_link_terminal() -> None:
    modality_rules = rules_for(NonTerminal.MODALITY)
    assert len(modality_rules) == len(LINK_TERMINALS)
    produced = {rule.rhs[0] for rule in modality_rules}
    assert produced == LINK_TERMINALS


# -- Node and link validation ------------------------------------------------


def test_node_instance_rejects_link_terminal() -> None:
    with pytest.raises(ValueError, match="Node kind must be a node terminal"):
        NodeInstance(node_id="n0", kind=Terminal.LASER_LINK)


def test_link_instance_rejects_node_terminal() -> None:
    with pytest.raises(ValueError, match="Link kind must be a link terminal"):
        LinkInstance(
            link_id="l0",
            kind=Terminal.UAV_ENERGY,
            source_id="n0",
            target_id="n1",
        )


def test_node_instance_rejects_empty_id() -> None:
    with pytest.raises(ValueError, match="node_id must be non-empty"):
        NodeInstance(node_id="", kind=Terminal.UAV_ENERGY)


def test_node_instance_freezes_params() -> None:
    mutable = {"role": 1.0, "power_w": 100.0}
    n = NodeInstance(node_id="n0", kind=Terminal.UAV_ENERGY, params=mutable)
    # The instance holds an immutable proxy.
    with pytest.raises(TypeError):
        n.params["new_key"] = 5.0  # type: ignore[index]


def test_node_instance_params_are_sorted() -> None:
    n = NodeInstance(
        node_id="n0",
        kind=Terminal.UAV_ENERGY,
        params={"z_key": 1.0, "a_key": 2.0},
    )
    assert list(n.params.keys()) == ["a_key", "z_key"]


# -- Architecture invariants -------------------------------------------------


def test_architecture_rejects_duplicate_node_ids() -> None:
    n1 = NodeInstance(node_id="dup", kind=Terminal.UAV_ENERGY)
    n2 = NodeInstance(node_id="dup", kind=Terminal.UAV_COMPUTE)
    with pytest.raises(ValueError, match="Duplicate node_ids"):
        Architecture(nodes=(n1, n2), links=())


def test_architecture_rejects_duplicate_link_ids() -> None:
    n1 = NodeInstance(node_id="n0", kind=Terminal.UAV_ENERGY)
    n2 = NodeInstance(node_id="n1", kind=Terminal.GROUND_STATION)
    link_a = LinkInstance(
        link_id="dup",
        kind=Terminal.LASER_LINK,
        source_id="n0",
        target_id="n1",
    )
    link_b = LinkInstance(
        link_id="dup",
        kind=Terminal.MICROWAVE_LINK,
        source_id="n0",
        target_id="n1",
    )
    with pytest.raises(ValueError, match="Duplicate link_ids"):
        Architecture(nodes=(n1, n2), links=(link_a, link_b))


def test_architecture_rejects_link_to_unknown_node() -> None:
    n1 = NodeInstance(node_id="n0", kind=Terminal.UAV_ENERGY)
    bad_link = LinkInstance(
        link_id="l0",
        kind=Terminal.LASER_LINK,
        source_id="n0",
        target_id="ghost",
    )
    with pytest.raises(ValueError, match="unknown target node ghost"):
        Architecture(nodes=(n1,), links=(bad_link,))


# -- Round trip --------------------------------------------------------------


def _make_two_node_one_link_arch() -> Architecture:
    return Architecture(
        nodes=(
            NodeInstance(
                node_id="n0",
                kind=Terminal.SATELLITE_LEO,
                params={"altitude_km": 550.0},
            ),
            NodeInstance(
                node_id="n1",
                kind=Terminal.UAV_ENERGY,
                params={"role": 0.0},
            ),
        ),
        links=(
            LinkInstance(
                link_id="l0",
                kind=Terminal.LASER_LINK,
                source_id="n0",
                target_id="n1",
                params={"wavelength_nm": 1064.0},
            ),
        ),
    )


def test_round_trip_single_architecture() -> None:
    original = _make_two_node_one_link_arch()
    steps = architecture_to_derivation(original)
    rebuilt = derivation_to_architecture(
        steps=steps,
        node_params=tuple(n.params for n in original.nodes),
        link_params=tuple(ln.params for ln in original.links),
        link_endpoints=tuple((ln.source_id, ln.target_id) for ln in original.links),
    )
    assert rebuilt == original


def test_round_trip_preserves_node_kinds_in_order() -> None:
    original = Architecture(
        nodes=(
            NodeInstance(node_id="n0", kind=Terminal.SATELLITE_GEO),
            NodeInstance(node_id="n1", kind=Terminal.GROUND_STATION),
            NodeInstance(node_id="n2", kind=Terminal.UAV_COMPUTE),
        ),
        links=(
            LinkInstance(
                link_id="l0",
                kind=Terminal.MICROWAVE_LINK,
                source_id="n0",
                target_id="n1",
            ),
        ),
    )
    steps = architecture_to_derivation(original)
    rebuilt = derivation_to_architecture(
        steps=steps,
        node_params=tuple(n.params for n in original.nodes),
        link_params=tuple(ln.params for ln in original.links),
        link_endpoints=tuple((ln.source_id, ln.target_id) for ln in original.links),
    )
    assert [n.kind for n in rebuilt.nodes] == [
        Terminal.SATELLITE_GEO,
        Terminal.GROUND_STATION,
        Terminal.UAV_COMPUTE,
    ]


def test_round_trip_preserves_link_kinds_in_order() -> None:
    original = Architecture(
        nodes=(
            NodeInstance(node_id="n0", kind=Terminal.GROUND_STATION),
            NodeInstance(node_id="n1", kind=Terminal.UAV_ENERGY),
            NodeInstance(node_id="n2", kind=Terminal.UAV_COMPUTE),
        ),
        links=(
            LinkInstance(
                link_id="l0",
                kind=Terminal.LASER_LINK,
                source_id="n0",
                target_id="n1",
            ),
            LinkInstance(
                link_id="l1",
                kind=Terminal.HYBRID_LINK,
                source_id="n1",
                target_id="n2",
            ),
        ),
    )
    steps = architecture_to_derivation(original)
    rebuilt = derivation_to_architecture(
        steps=steps,
        node_params=tuple(n.params for n in original.nodes),
        link_params=tuple(ln.params for ln in original.links),
        link_endpoints=tuple((ln.source_id, ln.target_id) for ln in original.links),
    )
    assert [ln.kind for ln in rebuilt.links] == [
        Terminal.LASER_LINK,
        Terminal.HYBRID_LINK,
    ]


def test_round_trip_preserves_params() -> None:
    original = Architecture(
        nodes=(
            NodeInstance(
                node_id="n0",
                kind=Terminal.UAV_ENERGY,
                params={"role": 0.0, "max_power_w": 500.0},
            ),
            NodeInstance(
                node_id="n1",
                kind=Terminal.GROUND_STATION,
                params={"lat_deg": 38.99, "lon_deg": -76.84},
            ),
        ),
        links=(
            LinkInstance(
                link_id="l0",
                kind=Terminal.LASER_LINK,
                source_id="n1",
                target_id="n0",
                params={"wavelength_nm": 1064.0, "aperture_m": 0.15},
            ),
        ),
    )
    steps = architecture_to_derivation(original)
    rebuilt = derivation_to_architecture(
        steps=steps,
        node_params=tuple(n.params for n in original.nodes),
        link_params=tuple(ln.params for ln in original.links),
        link_endpoints=tuple((ln.source_id, ln.target_id) for ln in original.links),
    )
    assert rebuilt == original
    # Specifically check the params survived.
    assert dict(rebuilt.nodes[0].params) == {"max_power_w": 500.0, "role": 0.0}
    assert dict(rebuilt.links[0].params) == {"aperture_m": 0.15, "wavelength_nm": 1064.0}


# -- Derivation validation ---------------------------------------------------


def test_derivation_to_architecture_rejects_short_derivation() -> None:
    with pytest.raises(ValueError, match="at least 3 steps"):
        derivation_to_architecture(
            steps=(),
            node_params=(),
            link_params=(),
            link_endpoints=(),
        )


def test_derivation_to_architecture_rejects_bad_first_step() -> None:
    # Three steps so the length check passes; the first step is wrong.
    bad = (
        DerivationStep(NonTerminal.NODE, 0),
        DerivationStep(NonTerminal.NODE_CLUSTER, 0),
        DerivationStep(NonTerminal.LINK, 0),
    )
    with pytest.raises(ValueError, match="First step must be"):
        derivation_to_architecture(
            steps=bad,
            node_params=(),
            link_params=(),
            link_endpoints=(),
        )


def test_derivation_to_architecture_rejects_length_mismatch() -> None:
    original = _make_two_node_one_link_arch()
    steps = architecture_to_derivation(original)
    with pytest.raises(ValueError, match="node_params length"):
        derivation_to_architecture(
            steps=steps,
            node_params=(MappingProxyType({}),),  # only one, need two
            link_params=tuple(ln.params for ln in original.links),
            link_endpoints=tuple((ln.source_id, ln.target_id) for ln in original.links),
        )


# -- Enums ------------------------------------------------------------------


def test_non_terminal_values_are_the_spec_names() -> None:
    assert {nt.value for nt in NonTerminal} == {
        "Architecture",
        "NodeCluster",
        "Node",
        "Link",
        "Modality",
    }


def test_terminal_values_are_the_spec_names() -> None:
    expected = {
        "Satellite_GEO",
        "Satellite_LEO",
        "UAV_Energy",
        "UAV_Compute",
        "Ground_Station",
        "Laser_Link",
        "Microwave_Link",
        "Hybrid_Link",
    }
    assert {t.value for t in Terminal} == expected


def test_production_rule_is_frozen() -> None:
    rule = ProductionRule(NonTerminal.NODE, (Terminal.UAV_ENERGY,))
    with pytest.raises(FrozenInstanceError):
        rule.lhs = NonTerminal.LINK  # type: ignore[misc]
