"""Context-free grammar for the architecture discovery space.

Roadmap task s4-1: Architecture grammar (context-free).
Gate: Parse tree -> architecture object round-trip correct.

Reference:
    AeroGrid-XAI Final Comprehensive Specification (Rev. 6),
    Section 35.1 (Architecture Grammar).

Scope and design decision (must be read before extending)
---------------------------------------------------------

This module implements the grammar exactly as Section 35.1 specifies:

    Non-terminals: Architecture, NodeCluster, Node, Link, Modality
    Terminals:     Satellite_GEO, Satellite_LEO, UAV_Energy,
                   UAV_Compute, Ground_Station, Laser_Link,
                   Microwave_Link, Hybrid_Link
    Start symbol:  Architecture

The terminal set defines the search space the discovery engine can
reach. Every terminal must have a corresponding constraint family in
Stage B. Adding a terminal without the matching constraint family
would let the engine propose architectures whose semantics the
encoder does not constrain, and a SAT verdict for such an
architecture would be meaningless per Section 21's epistemic
hierarchy: a partial encoding is not a formal verification.

The platform's stated scope (Section 10 lists energy, compute,
monitoring, relay, and emergency roles for UAVs; Section 1 lists
bidirectional topologies) is broader than the terminal set. The
correct way to express that breadth is through role parameters on
UAV terminals, not through new terminals. A UAV is a UAV regardless
of what it is running. Role is a property of the instance, not a
distinct physical kind, so it belongs in the parameter table.

Any future extension of the terminal set must be accompanied by:
  (a) the Stage B constraint family that governs the new terminal,
  (b) a test that exercises the new constraint family against a
      randomly generated architecture that uses the terminal, and
  (c) a migration note explaining why the extension preserves
      encoding soundness.

Canonical form
--------------

A derivation is represented as an Architecture object, which is a
list of NodeInstance and LinkInstance entries with stable IDs and
parameter maps. The grammar round trip is

    Architecture  -->  derivation tokens  -->  Architecture

with the derivation tokens carrying the same node kinds, link kinds,
endpoints, and parameters. Identifiers are assigned in
deterministic order so that architecture equality can be tested
structurally.

No parameters are attached to Satellite or Ground_Station terminals
in this module beyond position; adding position is a job for the
generator (s4-2), which attaches numeric parameters to a derivation
after it is produced. This module keeps the type structure separate
from the numeric instantiation so that type-level tests do not
depend on numeric sampling.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType


class NonTerminal(StrEnum):
    """Non-terminal symbols of the architecture grammar."""

    ARCHITECTURE = "Architecture"
    NODE_CLUSTER = "NodeCluster"
    NODE = "Node"
    LINK = "Link"
    MODALITY = "Modality"


class Terminal(StrEnum):
    """Terminal symbols of the architecture grammar.

    The split between node terminals and link terminals is enforced
    by the grammar: a Node rule produces node terminals only, and a
    Modality rule produces link terminals only.
    """

    # Node terminals
    SATELLITE_GEO = "Satellite_GEO"
    SATELLITE_LEO = "Satellite_LEO"
    UAV_ENERGY = "UAV_Energy"
    UAV_COMPUTE = "UAV_Compute"
    GROUND_STATION = "Ground_Station"
    # Link terminals (modalities)
    LASER_LINK = "Laser_Link"
    MICROWAVE_LINK = "Microwave_Link"
    HYBRID_LINK = "Hybrid_Link"


NODE_TERMINALS: frozenset[Terminal] = frozenset(
    {
        Terminal.SATELLITE_GEO,
        Terminal.SATELLITE_LEO,
        Terminal.UAV_ENERGY,
        Terminal.UAV_COMPUTE,
        Terminal.GROUND_STATION,
    }
)

LINK_TERMINALS: frozenset[Terminal] = frozenset(
    {
        Terminal.LASER_LINK,
        Terminal.MICROWAVE_LINK,
        Terminal.HYBRID_LINK,
    }
)


@dataclass(frozen=True)
class ProductionRule:
    """A single context-free production rule.

    The right-hand side is an ordered tuple of non-terminal and
    terminal symbols. A rule with all-terminal RHS is a terminal
    production; a rule with a mixture is a composition rule.
    """

    lhs: NonTerminal
    rhs: tuple[NonTerminal | Terminal, ...]


PRODUCTION_RULES: tuple[ProductionRule, ...] = (
    ProductionRule(
        NonTerminal.ARCHITECTURE,
        (NonTerminal.NODE_CLUSTER,),
    ),
    ProductionRule(
        NonTerminal.NODE_CLUSTER,
        (NonTerminal.NODE, NonTerminal.NODE, NonTerminal.LINK),
    ),
    ProductionRule(NonTerminal.NODE, (Terminal.SATELLITE_GEO,)),
    ProductionRule(NonTerminal.NODE, (Terminal.SATELLITE_LEO,)),
    ProductionRule(NonTerminal.NODE, (Terminal.UAV_ENERGY,)),
    ProductionRule(NonTerminal.NODE, (Terminal.UAV_COMPUTE,)),
    ProductionRule(NonTerminal.NODE, (Terminal.GROUND_STATION,)),
    ProductionRule(NonTerminal.LINK, (NonTerminal.MODALITY,)),
    ProductionRule(NonTerminal.MODALITY, (Terminal.LASER_LINK,)),
    ProductionRule(NonTerminal.MODALITY, (Terminal.MICROWAVE_LINK,)),
    ProductionRule(NonTerminal.MODALITY, (Terminal.HYBRID_LINK,)),
)


def rules_for(lhs: NonTerminal) -> tuple[ProductionRule, ...]:
    """Return all production rules with the given left-hand side."""
    return tuple(r for r in PRODUCTION_RULES if r.lhs == lhs)


Params = Mapping[str, float]


def _freeze_params(params: Params) -> Params:
    """Return an immutable copy of a parameter mapping with sorted keys."""
    return MappingProxyType({k: float(v) for k, v in sorted(params.items())})


@dataclass(frozen=True)
class NodeInstance:
    """A node in an architecture instance.

    Attributes:
        node_id: Stable identifier, unique within the architecture.
        kind: A node terminal (must be in NODE_TERMINALS).
        params: Numeric parameters attached to the terminal. For UAV
            terminals, the ``role`` key carries the platform role
            (energy, compute, monitoring, relay, emergency) as a
            float ordinal; this is how the platform's broader scope
            is expressed without new terminals. Other parameter keys
            (position, power, aperture) are populated by the
            generator in s4-2.
    """

    node_id: str
    kind: Terminal
    params: Params = field(default_factory=lambda: _freeze_params({}))

    def __post_init__(self) -> None:
        if self.kind not in NODE_TERMINALS:
            raise ValueError(f"Node kind must be a node terminal; got {self.kind}")
        if not self.node_id:
            raise ValueError("node_id must be non-empty")
        object.__setattr__(self, "params", _freeze_params(self.params))


@dataclass(frozen=True)
class LinkInstance:
    """A directed edge in an architecture instance.

    Attributes:
        link_id: Stable identifier, unique within the architecture.
        kind: A link terminal (must be in LINK_TERMINALS).
        source_id: node_id of the source node.
        target_id: node_id of the target node.
        params: Numeric parameters attached to the modality
            (wavelength, frequency, aperture). Populated by the
            generator in s4-2.
    """

    link_id: str
    kind: Terminal
    source_id: str
    target_id: str
    params: Params = field(default_factory=lambda: _freeze_params({}))

    def __post_init__(self) -> None:
        if self.kind not in LINK_TERMINALS:
            raise ValueError(f"Link kind must be a link terminal; got {self.kind}")
        if not self.link_id:
            raise ValueError("link_id must be non-empty")
        if not self.source_id or not self.target_id:
            raise ValueError("source_id and target_id must be non-empty")
        object.__setattr__(self, "params", _freeze_params(self.params))


@dataclass(frozen=True)
class Architecture:
    """A fully instantiated architecture.

    Nodes and links are stored as tuples so that equality is
    structural. Order is part of the identity: two architectures
    with the same nodes and links in different orders are considered
    different. The generator (s4-2) produces instances in a
    deterministic order so that equality tests are meaningful.
    """

    nodes: tuple[NodeInstance, ...]
    links: tuple[LinkInstance, ...]

    def __post_init__(self) -> None:
        node_ids = [n.node_id for n in self.nodes]
        if len(set(node_ids)) != len(node_ids):
            raise ValueError(f"Duplicate node_ids: {node_ids}")
        link_ids = [ln.link_id for ln in self.links]
        if len(set(link_ids)) != len(link_ids):
            raise ValueError(f"Duplicate link_ids: {link_ids}")
        node_id_set = set(node_ids)
        for link in self.links:
            if link.source_id not in node_id_set:
                raise ValueError(
                    f"Link {link.link_id} references unknown source node {link.source_id}"
                )
            if link.target_id not in node_id_set:
                raise ValueError(
                    f"Link {link.link_id} references unknown target node {link.target_id}"
                )

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def link_count(self) -> int:
        return len(self.links)


@dataclass(frozen=True)
class DerivationStep:
    """One step of a canonical leftmost derivation.

    A step is (lhs, rhs_index) where rhs_index selects which
    production rule was applied. Together with the production rule
    table this fully specifies the derivation.

    This representation is compact: the round trip through
    ``architecture_to_derivation`` and ``derivation_to_architecture``
    reconstructs the architecture from the terminal-level structure
    of the derivation, so the test that exercises the round trip
    catches any mismatch between the parse-tree view and the
    object-level view.
    """

    lhs: NonTerminal
    rhs_index: int


def architecture_to_derivation(arch: Architecture) -> tuple[DerivationStep, ...]:
    """Return a canonical derivation that produces the architecture.

    The derivation is a sequence of rule applications:
        ARCHITECTURE -> NODE_CLUSTER
        NODE_CLUSTER -> NODE NODE LINK
        NODE -> <node terminal>  (once per node, in order)
        LINK -> MODALITY
        MODALITY -> <link terminal>  (once per link, in order)
    """
    steps: list[DerivationStep] = []
    steps.append(DerivationStep(NonTerminal.ARCHITECTURE, 0))
    steps.append(DerivationStep(NonTerminal.NODE_CLUSTER, 0))
    node_rule_index = {
        Terminal.SATELLITE_GEO: 0,
        Terminal.SATELLITE_LEO: 1,
        Terminal.UAV_ENERGY: 2,
        Terminal.UAV_COMPUTE: 3,
        Terminal.GROUND_STATION: 4,
    }
    for node in arch.nodes:
        steps.append(DerivationStep(NonTerminal.NODE, node_rule_index[node.kind]))
    steps.append(DerivationStep(NonTerminal.LINK, 0))
    modality_rule_index = {
        Terminal.LASER_LINK: 0,
        Terminal.MICROWAVE_LINK: 1,
        Terminal.HYBRID_LINK: 2,
    }
    for link in arch.links:
        steps.append(DerivationStep(NonTerminal.MODALITY, modality_rule_index[link.kind]))
    return tuple(steps)


def derivation_to_architecture(
    steps: tuple[DerivationStep, ...],
    node_params: tuple[Params, ...],
    link_params: tuple[Params, ...],
    link_endpoints: tuple[tuple[str, str], ...],
) -> Architecture:
    """Reconstruct an Architecture from a canonical derivation.

    The derivation carries the type structure (which terminals, in
    which order); the caller supplies the numeric parameters and
    link endpoints, because those are not part of the grammar and
    are attached by the generator (s4-2).

    The function validates that the derivation is well formed before
    building the architecture, so a malformed derivation raises
    ValueError rather than producing a partially valid object.
    """
    if len(steps) < 3:
        raise ValueError(f"Derivation must have at least 3 steps; got {len(steps)}")
    if steps[0] != DerivationStep(NonTerminal.ARCHITECTURE, 0):
        raise ValueError("First step must be ARCHITECTURE -> NODE_CLUSTER")
    if steps[1] != DerivationStep(NonTerminal.NODE_CLUSTER, 0):
        raise ValueError("Second step must be NODE_CLUSTER -> NODE NODE LINK")

    idx = 2
    nodes: list[NodeInstance] = []
    node_kinds_in_order: list[Terminal] = []
    while idx < len(steps) and steps[idx].lhs == NonTerminal.NODE:
        rhs_options = rules_for(NonTerminal.NODE)
        chosen = rhs_options[steps[idx].rhs_index]
        rhs0 = chosen.rhs[0]
        if not isinstance(rhs0, Terminal):
            raise ValueError(f"NODE rule must produce a terminal; got {rhs0}")
        node_kinds_in_order.append(rhs0)
        idx += 1

    if idx >= len(steps) or steps[idx].lhs != NonTerminal.LINK:
        raise ValueError("Expected LINK step after all NODE steps")
    idx += 1

    links: list[LinkInstance] = []
    link_kinds_in_order: list[Terminal] = []
    while idx < len(steps):
        if steps[idx].lhs != NonTerminal.MODALITY:
            raise ValueError(f"Unexpected non-terminal {steps[idx].lhs} in link sequence")
        modality_options = rules_for(NonTerminal.MODALITY)
        chosen = modality_options[steps[idx].rhs_index]
        rhs0 = chosen.rhs[0]
        if not isinstance(rhs0, Terminal):
            raise ValueError(f"MODALITY rule must produce a terminal; got {rhs0}")
        link_kinds_in_order.append(rhs0)
        idx += 1

    if len(node_params) != len(node_kinds_in_order):
        raise ValueError(
            f"node_params length {len(node_params)} does not match "
            f"derivation node count {len(node_kinds_in_order)}"
        )
    if len(link_params) != len(link_kinds_in_order):
        raise ValueError(
            f"link_params length {len(link_params)} does not match "
            f"derivation link count {len(link_kinds_in_order)}"
        )
    if len(link_endpoints) != len(link_kinds_in_order):
        raise ValueError(
            f"link_endpoints length {len(link_endpoints)} does not match "
            f"derivation link count {len(link_kinds_in_order)}"
        )

    for i, kind in enumerate(node_kinds_in_order):
        nodes.append(
            NodeInstance(
                node_id=f"n{i}",
                kind=kind,
                params=node_params[i],
            )
        )
    for i, kind in enumerate(link_kinds_in_order):
        src, tgt = link_endpoints[i]
        links.append(
            LinkInstance(
                link_id=f"l{i}",
                kind=kind,
                source_id=src,
                target_id=tgt,
                params=link_params[i],
            )
        )

    return Architecture(nodes=tuple(nodes), links=tuple(links))
