"""Conflict-directed mutation operators for the discovery loop.

Roadmap task s4-5: Conflict-directed mutation.
Gate: Bias toward changing conflict-prone features; convergence rate
> random mutation (H9 test).

Reference:
    AeroGrid-XAI Final Comprehensive Specification (Rev. 6),
    Section 35.3 ("if the unsat core involves a laser link's thermal
    constraint, the mutator is more likely to switch that link to
    microwave (lower peak intensity, different thermal profile) or to
    add a cooling UAV node") and Section 35.4 (Discovery Loop).

Operators
---------

Eight operators act on Architecture objects:

    NODE_KIND_CHANGE   replace a node's kind with a different one
    NODE_PARAM_JITTER  perturb a node's numeric parameters
    NODE_REMOVE        remove a node and its incident links
    NODE_ADD           add a node connected by a new link
    LINK_KIND_CHANGE   replace a link's kind with a different one
    LINK_PARAM_JITTER  perturb a link's numeric parameters
    LINK_REMOVE        remove a link
    LINK_ADD           add a link between two existing nodes

All operators preserve the Architecture invariants: unique IDs, no
dangling references, at least min_nodes nodes, at least min_links
links. An operator that would violate an invariant returns None and
the mutator falls back.

Mutators
--------

mutate_random picks operator and target uniformly from the applicable
set. mutate_conflict_directed reads a ConflictProneTable and, with
probability config.conflict_probability, samples a conflict-prone
feature weighted by its hit count and applies an operator that acts
on that feature. Otherwise it falls back to random.

This is the mechanism Section 35.3 describes: the solver's UNSAT
proof is used as a gradient signal to guide the grammar-based
generator away from infeasible regions.

ID assignment
-------------

New IDs use the smallest unused integer for the prefix. Given the
same input architecture and the same rng state, the mutator's output
is identical. The s4-8 gate ("same UNSAT core -> same bias, twice")
relies on this.

Scope boundary
--------------

This module does not solve constraints, extract cores, or attribute
features. It consumes a ConflictProneTable produced by s4-4 and
produces a mutated Architecture. Composing attribution and mutation
into a discovery loop is the job of s4-6 (NSGA-II integration).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import StrEnum

from app.discovery.attribution import (
    ConflictProneTable,
    FeatureKind,
    GrammarFeature,
)
from app.discovery.generator import (
    LINK_PARAM_RANGES,
    NODE_PARAM_RANGES,
)
from app.discovery.grammar import (
    LINK_TERMINALS,
    NODE_TERMINALS,
    Architecture,
    LinkInstance,
    NodeInstance,
    Terminal,
)


class MutationOperator(StrEnum):
    """The eight mutation operators available to the mutators."""

    NODE_KIND_CHANGE = "node_kind_change"
    NODE_PARAM_JITTER = "node_param_jitter"
    NODE_REMOVE = "node_remove"
    NODE_ADD = "node_add"
    LINK_KIND_CHANGE = "link_kind_change"
    LINK_PARAM_JITTER = "link_param_jitter"
    LINK_REMOVE = "link_remove"
    LINK_ADD = "link_add"


@dataclass(frozen=True)
class MutationConfig:
    """Configuration for the mutators."""

    min_nodes: int = 2
    max_nodes: int = 12
    min_links: int = 1
    max_links: int = 20
    param_jitter_scale: float = 0.10
    conflict_probability: float = 0.85

    def __post_init__(self) -> None:
        if self.min_nodes < 2:
            raise ValueError(f"min_nodes must be >= 2; got {self.min_nodes}")
        if self.max_nodes < self.min_nodes:
            raise ValueError(
                f"max_nodes ({self.max_nodes}) must be >= min_nodes ({self.min_nodes})"
            )
        if self.min_links < 1:
            raise ValueError(f"min_links must be >= 1; got {self.min_links}")
        if self.max_links < self.min_links:
            raise ValueError(
                f"max_links ({self.max_links}) must be >= min_links ({self.min_links})"
            )
        if self.param_jitter_scale <= 0.0:
            raise ValueError(f"param_jitter_scale must be > 0; got {self.param_jitter_scale}")
        if not 0.0 <= self.conflict_probability <= 1.0:
            raise ValueError(
                f"conflict_probability must be in [0, 1]; got {self.conflict_probability}"
            )


# --- Helpers ---------------------------------------------------------------


def _fresh_node_id(arch: Architecture) -> str:
    existing = {n.node_id for n in arch.nodes}
    i = 0
    while f"n{i}" in existing:
        i += 1
    return f"n{i}"


def _fresh_link_id(arch: Architecture) -> str:
    existing = {ln.link_id for ln in arch.links}
    i = 0
    while f"l{i}" in existing:
        i += 1
    return f"l{i}"


def _sample_node_params(rng: random.Random, kind: Terminal) -> dict[str, float]:
    ranges = NODE_PARAM_RANGES[kind]
    params = {name: rng.uniform(lo, hi) for name, (lo, hi) in ranges.items()}
    if "role" in params:
        params["role"] = float(round(params["role"]))
    return params


def _sample_link_params(rng: random.Random, kind: Terminal) -> dict[str, float]:
    ranges = LINK_PARAM_RANGES[kind]
    return {name: rng.uniform(lo, hi) for name, (lo, hi) in ranges.items()}


def _other_kind(
    current: Terminal,
    choices: frozenset[Terminal],
    rng: random.Random,
) -> Terminal:
    others = sorted(t for t in choices if t != current)
    return rng.choice(others)


def _jitter_dict(
    params: dict[str, float],
    ranges: dict[str, tuple[float, float]],
    scale: float,
    rng: random.Random,
) -> dict[str, float]:
    out: dict[str, float] = {}
    for name, (lo, hi) in ranges.items():
        current = params.get(name, (lo + hi) / 2.0)
        span = hi - lo
        delta = rng.gauss(0.0, scale * span)
        out[name] = max(lo, min(hi, current + delta))
    if "role" in out:
        out["role"] = float(round(out["role"]))
    return out


# --- Individual operators --------------------------------------------------


def _op_node_kind_change(
    arch: Architecture,
    target: str | None,
    rng: random.Random,
    config: MutationConfig,
) -> Architecture | None:
    if target is None:
        return None
    node = next((n for n in arch.nodes if n.node_id == target), None)
    if node is None:
        return None
    new_kind = _other_kind(node.kind, NODE_TERMINALS, rng)
    new_params = _sample_node_params(rng, new_kind)
    new_node = NodeInstance(node_id=node.node_id, kind=new_kind, params=new_params)
    new_nodes = tuple(new_node if n.node_id == target else n for n in arch.nodes)
    return Architecture(nodes=new_nodes, links=arch.links)


def _op_node_param_jitter(
    arch: Architecture,
    target: str | None,
    rng: random.Random,
    config: MutationConfig,
) -> Architecture | None:
    if target is None:
        return None
    node = next((n for n in arch.nodes if n.node_id == target), None)
    if node is None:
        return None
    new_params = _jitter_dict(
        dict(node.params),
        NODE_PARAM_RANGES[node.kind],
        config.param_jitter_scale,
        rng,
    )
    new_node = NodeInstance(
        node_id=node.node_id,
        kind=node.kind,
        params=new_params,
    )
    new_nodes = tuple(new_node if n.node_id == target else n for n in arch.nodes)
    return Architecture(nodes=new_nodes, links=arch.links)


def _op_node_remove(
    arch: Architecture,
    target: str | None,
    rng: random.Random,
    config: MutationConfig,
) -> Architecture | None:
    if target is None:
        return None
    if len(arch.nodes) <= config.min_nodes:
        return None
    new_nodes = tuple(n for n in arch.nodes if n.node_id != target)
    new_links = tuple(ln for ln in arch.links if ln.source_id != target and ln.target_id != target)
    if len(new_links) < config.min_links:
        return None
    return Architecture(nodes=new_nodes, links=new_links)


def _op_node_add(
    arch: Architecture,
    target: str | None,
    rng: random.Random,
    config: MutationConfig,
) -> Architecture | None:
    if len(arch.nodes) >= config.max_nodes:
        return None
    if len(arch.links) >= config.max_links:
        return None
    new_kind = rng.choice(sorted(NODE_TERMINALS))
    new_node_id = _fresh_node_id(arch)
    new_node = NodeInstance(
        node_id=new_node_id,
        kind=new_kind,
        params=_sample_node_params(rng, new_kind),
    )
    anchor = rng.choice(arch.nodes)
    new_link_kind = rng.choice(sorted(LINK_TERMINALS))
    new_link = LinkInstance(
        link_id=_fresh_link_id(arch),
        kind=new_link_kind,
        source_id=new_node_id,
        target_id=anchor.node_id,
        params=_sample_link_params(rng, new_link_kind),
    )
    return Architecture(
        nodes=(*arch.nodes, new_node),
        links=(*arch.links, new_link),
    )


def _op_link_kind_change(
    arch: Architecture,
    target: str | None,
    rng: random.Random,
    config: MutationConfig,
) -> Architecture | None:
    if target is None:
        return None
    link = next((ln for ln in arch.links if ln.link_id == target), None)
    if link is None:
        return None
    new_kind = _other_kind(link.kind, LINK_TERMINALS, rng)
    new_link = LinkInstance(
        link_id=link.link_id,
        kind=new_kind,
        source_id=link.source_id,
        target_id=link.target_id,
        params=_sample_link_params(rng, new_kind),
    )
    new_links = tuple(new_link if ln.link_id == target else ln for ln in arch.links)
    return Architecture(nodes=arch.nodes, links=new_links)


def _op_link_param_jitter(
    arch: Architecture,
    target: str | None,
    rng: random.Random,
    config: MutationConfig,
) -> Architecture | None:
    if target is None:
        return None
    link = next((ln for ln in arch.links if ln.link_id == target), None)
    if link is None:
        return None
    new_params = _jitter_dict(
        dict(link.params),
        LINK_PARAM_RANGES[link.kind],
        config.param_jitter_scale,
        rng,
    )
    new_link = LinkInstance(
        link_id=link.link_id,
        kind=link.kind,
        source_id=link.source_id,
        target_id=link.target_id,
        params=new_params,
    )
    new_links = tuple(new_link if ln.link_id == target else ln for ln in arch.links)
    return Architecture(nodes=arch.nodes, links=new_links)


def _op_link_remove(
    arch: Architecture,
    target: str | None,
    rng: random.Random,
    config: MutationConfig,
) -> Architecture | None:
    if target is None:
        return None
    if len(arch.links) <= config.min_links:
        return None
    new_links = tuple(ln for ln in arch.links if ln.link_id != target)
    return Architecture(nodes=arch.nodes, links=new_links)


def _op_link_add(
    arch: Architecture,
    target: str | None,
    rng: random.Random,
    config: MutationConfig,
) -> Architecture | None:
    if len(arch.links) >= config.max_links:
        return None
    if len(arch.nodes) < 2:
        return None
    src, tgt = rng.sample(list(arch.nodes), 2)
    link_kind = rng.choice(sorted(LINK_TERMINALS))
    new_link = LinkInstance(
        link_id=_fresh_link_id(arch),
        kind=link_kind,
        source_id=src.node_id,
        target_id=tgt.node_id,
        params=_sample_link_params(rng, link_kind),
    )
    return Architecture(nodes=arch.nodes, links=(*arch.links, new_link))


_DISPATCH = {
    MutationOperator.NODE_KIND_CHANGE: _op_node_kind_change,
    MutationOperator.NODE_PARAM_JITTER: _op_node_param_jitter,
    MutationOperator.NODE_REMOVE: _op_node_remove,
    MutationOperator.NODE_ADD: _op_node_add,
    MutationOperator.LINK_KIND_CHANGE: _op_link_kind_change,
    MutationOperator.LINK_PARAM_JITTER: _op_link_param_jitter,
    MutationOperator.LINK_REMOVE: _op_link_remove,
    MutationOperator.LINK_ADD: _op_link_add,
}


def _apply_operator(
    arch: Architecture,
    op: MutationOperator,
    target: str | None,
    rng: random.Random,
    config: MutationConfig,
) -> Architecture | None:
    return _DISPATCH[op](arch, target, rng, config)


# --- Mutators --------------------------------------------------------------


def _applicable_operators(arch: Architecture, config: MutationConfig) -> list[MutationOperator]:
    out: list[MutationOperator] = []
    for op in MutationOperator:
        if op == MutationOperator.NODE_REMOVE and len(arch.nodes) <= config.min_nodes:
            continue
        if op == MutationOperator.NODE_ADD and len(arch.nodes) >= config.max_nodes:
            continue
        if op == MutationOperator.LINK_REMOVE and len(arch.links) <= config.min_links:
            continue
        if op == MutationOperator.LINK_ADD:
            if len(arch.links) >= config.max_links:
                continue
            if len(arch.nodes) < 2:
                continue
        out.append(op)
    return out


def _pick_random_operator_and_target(
    arch: Architecture,
    config: MutationConfig,
    rng: random.Random,
) -> tuple[MutationOperator, str | None]:
    applicable = _applicable_operators(arch, config)
    if not applicable:
        return (MutationOperator.NODE_PARAM_JITTER, arch.nodes[0].node_id)
    op = rng.choice(applicable)
    target: str | None = None
    if op in (
        MutationOperator.NODE_KIND_CHANGE,
        MutationOperator.NODE_PARAM_JITTER,
        MutationOperator.NODE_REMOVE,
    ):
        target = rng.choice(sorted(n.node_id for n in arch.nodes))
    elif op in (
        MutationOperator.LINK_KIND_CHANGE,
        MutationOperator.LINK_PARAM_JITTER,
        MutationOperator.LINK_REMOVE,
    ):
        target = rng.choice(sorted(ln.link_id for ln in arch.links))
    return (op, target)


def mutate_random(
    arch: Architecture,
    rng: random.Random,
    config: MutationConfig | None = None,
) -> Architecture:
    """Apply a uniformly random mutation operator and target."""
    cfg = config or MutationConfig()
    op, target = _pick_random_operator_and_target(arch, cfg, rng)
    result = _apply_operator(arch, op, target, rng, cfg)
    return result if result is not None else arch


def _operators_for_feature(
    feature: GrammarFeature,
    arch: Architecture,
    config: MutationConfig,
) -> list[tuple[MutationOperator, str]]:
    """Return (operator, target_id) pairs that act on this feature.

    Operators that would violate a min/max invariant are excluded, so
    the returned list is guaranteed to contain at least one feasible
    action when non-empty.
    """
    ops: list[tuple[MutationOperator, str]] = []
    if feature.kind == FeatureKind.NODE_INSTANCE:
        node = next(
            (n for n in arch.nodes if n.node_id == feature.identifier),
            None,
        )
        if node is not None:
            ops.append((MutationOperator.NODE_KIND_CHANGE, node.node_id))
            ops.append((MutationOperator.NODE_PARAM_JITTER, node.node_id))
            if len(arch.nodes) > config.min_nodes:
                ops.append((MutationOperator.NODE_REMOVE, node.node_id))
    elif feature.kind == FeatureKind.LINK_INSTANCE:
        link = next(
            (ln for ln in arch.links if ln.link_id == feature.identifier),
            None,
        )
        if link is not None:
            ops.append((MutationOperator.LINK_KIND_CHANGE, link.link_id))
            ops.append((MutationOperator.LINK_PARAM_JITTER, link.link_id))
            if len(arch.links) > config.min_links:
                ops.append((MutationOperator.LINK_REMOVE, link.link_id))
    elif feature.kind == FeatureKind.NODE_TYPE:
        for node in arch.nodes:
            if node.kind.value == feature.identifier:
                ops.append((MutationOperator.NODE_KIND_CHANGE, node.node_id))
                if len(arch.nodes) > config.min_nodes:
                    ops.append((MutationOperator.NODE_REMOVE, node.node_id))
    elif feature.kind == FeatureKind.LINK_TYPE:
        for link in arch.links:
            if link.kind.value == feature.identifier:
                ops.append((MutationOperator.LINK_KIND_CHANGE, link.link_id))
                if len(arch.links) > config.min_links:
                    ops.append((MutationOperator.LINK_REMOVE, link.link_id))
    return ops


def mutate_conflict_directed(
    arch: Architecture,
    table: ConflictProneTable,
    rng: random.Random,
    config: MutationConfig | None = None,
) -> Architecture:
    """Apply a mutation biased toward conflict-prone features.

    With probability config.conflict_probability, samples a feature
    from the table weighted by its hit count and applies an operator
    that acts on that feature. Otherwise, or if no feature is
    actionable on the current architecture, falls back to random.
    """
    cfg = config or MutationConfig()

    if len(table) == 0 or rng.random() >= cfg.conflict_probability:
        return mutate_random(arch, rng, cfg)

    mapping = table.to_mapping()
    actionable: list[tuple[GrammarFeature, int, list[tuple[MutationOperator, str]]]] = []
    for feature, weight in mapping.items():
        ops = _operators_for_feature(feature, arch, cfg)
        if ops:
            actionable.append((feature, weight, ops))

    if not actionable:
        return mutate_random(arch, rng, cfg)

    total_weight = sum(w for _, w, _ in actionable)
    r = rng.uniform(0.0, total_weight)
    acc = 0.0
    chosen_ops = actionable[-1][2]
    for _, weight, ops in actionable:
        acc += weight
        if r <= acc:
            chosen_ops = ops
            break

    op, target = rng.choice(sorted(chosen_ops))
    result = _apply_operator(arch, op, target, rng, cfg)
    return result if result is not None else mutate_random(arch, rng, cfg)
