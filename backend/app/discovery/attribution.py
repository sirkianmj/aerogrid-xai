"""UNSAT-core-to-grammar-feature attribution.

Roadmap task s4-4: UNSAT-core-to-grammar-feature attribution
(inventive core; defensively published per D1).
Gate: Forced UNSAT correctly identifies laser link as conflict-prone.

Reference:
    AeroGrid-XAI Final Comprehensive Specification (Rev. 6),
    Section 35.3 ("The Inventive Core") and Section 35.4
    (Discovery Loop).

What this module does
---------------------

Given a set of FeatureConstraint objects and the UNSAT core names
returned by the s4-3 extractor, this module maps each core clause to
the grammar features that generated it and produces a
conflict-prone table. The mutation operator (s4-5) reads that table
to bias the next generation of candidates away from the features
that caused infeasibility.

This is the mechanism the defensive publication is about. It is
prior art in the neural network verification domain (MUC-G4 reuses
UNSAT cores to prune search space); the novel element is that here
the core clauses are mapped back to grammar production rules and the
resulting feature set is used to bias mutation operators in a
grammar-based generator. See Section 40 for the patentability
analysis.

Scope boundary
--------------

This module does not mutate architectures. It produces markings.
The mutator that consumes them is s4-5. Keeping the boundary clean
lets this module be audited in isolation against the spec's
wording.

Determinism
-----------

The s4-8 gate requires "same UNSAT core -> same bias, twice".
Every output of this module is deterministic: conflict_prone and
clause_to_features are sorted tuples, ConflictProneTable returns
its contents in sorted order, and no operation depends on dict
iteration order.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

import z3

from app.discovery.grammar import (
    Architecture,
    LinkInstance,
    NodeInstance,
)
from app.discovery.unsat import NamedConstraint, UnsatCoreExtractor


class FeatureKind(StrEnum):
    """The four kinds of grammar feature that can be marked.

    INSTANCE features identify a specific node or link inside a
    single architecture. TYPE features identify a terminal symbol of
    the grammar (a node kind or a link kind), which is comparable
    across architectures. Both are produced for every node and link
    by features_of_node and features_of_link.
    """

    NODE_INSTANCE = "node_instance"
    LINK_INSTANCE = "link_instance"
    NODE_TYPE = "node_type"
    LINK_TYPE = "link_type"


@dataclass(frozen=True, order=True)
class GrammarFeature:
    """A single identifiable element of an architecture.

    Ordering is by (kind, identifier), so tuples of GrammarFeature
    sort deterministically. Two features are equal iff kind and
    identifier are both equal.
    """

    kind: FeatureKind
    identifier: str

    def __post_init__(self) -> None:
        if not self.identifier:
            raise ValueError("GrammarFeature identifier must be non-empty")


def features_of_node(node: NodeInstance) -> frozenset[GrammarFeature]:
    """Return both the instance-level and type-level features of a
    node. A constraint about a specific node is a constraint about
    both that node's identity and its kind; the mutator can choose
    which level to act on."""
    return frozenset(
        {
            GrammarFeature(FeatureKind.NODE_INSTANCE, node.node_id),
            GrammarFeature(FeatureKind.NODE_TYPE, node.kind.value),
        }
    )


def features_of_link(link: LinkInstance) -> frozenset[GrammarFeature]:
    """Return both the instance-level and type-level features of a
    link."""
    return frozenset(
        {
            GrammarFeature(FeatureKind.LINK_INSTANCE, link.link_id),
            GrammarFeature(FeatureKind.LINK_TYPE, link.kind.value),
        }
    )


def features_of_architecture(arch: Architecture) -> dict[str, frozenset[GrammarFeature]]:
    """Return a mapping from node_id or link_id to its features.

    Useful when constructing FeatureConstraints: for each node or
    link a constraint is about, look up its feature set here.
    """
    out: dict[str, frozenset[GrammarFeature]] = {}
    for node in arch.nodes:
        out[node.node_id] = features_of_node(node)
    for link in arch.links:
        out[link.link_id] = features_of_link(link)
    return out


@dataclass(frozen=True)
class FeatureConstraint:
    """A named constraint tagged with the grammar features it derives
    from.

    The features set is what the attribution mechanism uses to map a
    core clause back to a grammar element. It must be non-empty: a
    constraint with no declared feature cannot be attributed, and
    silently allowing it would make the conflict-prone table
    incomplete without any signal.
    """

    family_name: str
    expression: z3.BoolRef
    features: frozenset[GrammarFeature]

    def __post_init__(self) -> None:
        if not self.family_name:
            raise ValueError("family_name must be non-empty")
        if not self.features:
            raise ValueError(
                f"FeatureConstraint {self.family_name} has no features; "
                "every constraint must declare at least one feature so "
                "attribution can trace it"
            )
        if not z3.is_bool(self.expression):
            raise ValueError(
                f"expression for {self.family_name} must be Boolean; "
                f"got sort {self.expression.sort()}"
            )

    def to_named(self) -> NamedConstraint:
        """Return the plain NamedConstraint view for use with the
        s4-3 extractor."""
        return NamedConstraint(
            family_name=self.family_name,
            expression=self.expression,
        )


@dataclass(frozen=True)
class Attribution:
    """Result of mapping an UNSAT core to grammar features.

    Attributes:
        status: "sat" if the constraints were satisfiable (in which
            case conflict_prone and clause_to_features are empty);
            "unsat" otherwise.
        conflict_prone: Sorted tuple of every feature appearing in
            the core's clauses. This is what s4-5 consumes.
        clause_to_features: For each core clause, a sorted tuple of
            its features. Preserves the traceback so the explanation
            can name which clause contributed which feature.
    """

    status: str
    conflict_prone: tuple[GrammarFeature, ...]
    clause_to_features: tuple[tuple[str, tuple[GrammarFeature, ...]], ...]

    @property
    def conflict_count(self) -> int:
        return len(self.conflict_prone)

    @property
    def is_empty(self) -> bool:
        return len(self.conflict_prone) == 0


class ConflictProneTable:
    """Accumulates conflict-prone markings across attributions.

    The table stores a hit count per feature. A feature is marked if
    its hit count is greater than zero. The table is designed for use
    across multiple attributions in the discovery loop, where each
    UNSAT verdict increments the counts of the features it implicates.

    All retrieval methods return results in sorted order, so two
    tables with the same contents print identically and compare
    identically via to_mapping.
    """

    def __init__(self) -> None:
        self._counts: dict[GrammarFeature, int] = {}

    def mark(self, features: Iterable[GrammarFeature]) -> None:
        """Increment the hit count of every feature in the iterable.

        Duplicate features in the iterable each contribute one
        increment. An empty iterable is a no-op.
        """
        for f in features:
            self._counts[f] = self._counts.get(f, 0) + 1

    def hit_count(self, feature: GrammarFeature) -> int:
        return self._counts.get(feature, 0)

    def is_conflict_prone(self, feature: GrammarFeature) -> bool:
        return feature in self._counts

    def all_marked(self) -> tuple[GrammarFeature, ...]:
        return tuple(sorted(self._counts.keys()))

    def to_mapping(self) -> Mapping[GrammarFeature, int]:
        """Return a sorted snapshot of the table as a mapping."""
        return {f: self._counts[f] for f in sorted(self._counts)}

    def __len__(self) -> int:
        return len(self._counts)

    def __contains__(self, feature: object) -> bool:
        return feature in self._counts

    def clear(self) -> None:
        self._counts.clear()


def attribute_core(
    constraints: tuple[FeatureConstraint, ...],
    core_names: tuple[str, ...],
) -> Attribution:
    """Map an UNSAT core to the grammar features of its clauses.

    Deterministic. Same inputs always produce the same Attribution.

    Args:
        constraints: Every constraint that was submitted to the
            extractor, with its features.
        core_names: The family names of the core, as returned by
            UnsatCoreExtractor.check(). May be empty (SAT case).

    Raises:
        ValueError if any name in core_names is not present in
        constraints.
    """
    family_map = {c.family_name: c for c in constraints}
    missing = [n for n in core_names if n not in family_map]
    if missing:
        raise ValueError(f"Core contains names not present in constraints: {missing}")

    if not core_names:
        return Attribution(status="sat", conflict_prone=(), clause_to_features=())

    conflict_set: set[GrammarFeature] = set()
    clause_to_features: list[tuple[str, tuple[GrammarFeature, ...]]] = []

    for name in core_names:
        constraint = family_map[name]
        sorted_features = tuple(sorted(constraint.features))
        clause_to_features.append((name, sorted_features))
        conflict_set.update(constraint.features)

    return Attribution(
        status="unsat",
        conflict_prone=tuple(sorted(conflict_set)),
        clause_to_features=tuple(clause_to_features),
    )


def attribute_and_mark(
    constraints: tuple[FeatureConstraint, ...],
    table: ConflictProneTable,
) -> Attribution:
    """Run the full attribution pipeline and update the table.

    Steps:
      1. Submit every constraint to an UnsatCoreExtractor.
      2. If SAT, return an empty Attribution and do not touch the
         table.
      3. If UNSAT, extract the core, attribute it, mark the
         conflict-prone table, and return the Attribution.

    This is the API that s4-5 will use per architecture in the
    discovery loop.
    """
    extractor = UnsatCoreExtractor()
    for fc in constraints:
        extractor.add(fc.to_named())
    result = extractor.check()

    if result.status != "unsat":
        return Attribution(
            status=result.status,
            conflict_prone=(),
            clause_to_features=(),
        )

    attribution = attribute_core(constraints, result.core_names)
    table.mark(attribution.conflict_prone)
    return attribution
