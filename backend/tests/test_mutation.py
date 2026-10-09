"""Tests for the mutation operators and mutators.

Roadmap task s4-5: Conflict-directed mutation.
Gate is exercised separately in test_h9_convergence.py.
"""

from __future__ import annotations

import random

import pytest

from app.discovery.attribution import (
    ConflictProneTable,
    FeatureKind,
    GrammarFeature,
)
from app.discovery.generator import GeneratorConfig, generate_architecture
from app.discovery.grammar import (
    LINK_TERMINALS,
    NODE_TERMINALS,
    Architecture,
)
from app.discovery.mutation import (
    MutationConfig,
    MutationOperator,
    mutate_conflict_directed,
    mutate_random,
)


def _sample_architecture(seed: int = 0) -> Architecture:
    config = GeneratorConfig(min_nodes=4, max_nodes=6, max_links=8, seed=seed)
    return generate_architecture(config)


# -- MutationConfig validation ---------------------------------------------


def test_config_rejects_min_nodes_below_2() -> None:
    with pytest.raises(ValueError, match="min_nodes must be >= 2"):
        MutationConfig(min_nodes=1)


def test_config_rejects_inverted_node_bounds() -> None:
    with pytest.raises(ValueError, match=r"max_nodes .* must be >= min_nodes"):
        MutationConfig(min_nodes=5, max_nodes=3)


def test_config_rejects_min_links_below_1() -> None:
    with pytest.raises(ValueError, match="min_links must be >= 1"):
        MutationConfig(min_links=0)


def test_config_rejects_non_positive_jitter_scale() -> None:
    with pytest.raises(ValueError, match="param_jitter_scale must be > 0"):
        MutationConfig(param_jitter_scale=0.0)


def test_config_rejects_out_of_range_conflict_probability() -> None:
    with pytest.raises(ValueError, match="conflict_probability must be in"):
        MutationConfig(conflict_probability=1.5)
    with pytest.raises(ValueError, match="conflict_probability must be in"):
        MutationConfig(conflict_probability=-0.1)


# -- Invariant preservation --------------------------------------------------


def _assert_invariants(arch: Architecture) -> None:
    """Every operator must produce an Architecture that satisfies the
    same invariants the constructor enforces. This is a redundant check
    but guards against future edits to the operator implementations."""
    node_ids = [n.node_id for n in arch.nodes]
    assert len(set(node_ids)) == len(node_ids)
    link_ids = [ln.link_id for ln in arch.links]
    assert len(set(link_ids)) == len(link_ids)
    node_id_set = set(node_ids)
    for ln in arch.links:
        assert ln.source_id in node_id_set
        assert ln.target_id in node_id_set


def test_random_mutation_preserves_invariants() -> None:
    arch = _sample_architecture(seed=1)
    config = MutationConfig()
    for seed in range(30):
        rng = random.Random(seed)
        mutated = mutate_random(arch, rng, config)
        _assert_invariants(mutated)


def test_conflict_directed_mutation_preserves_invariants() -> None:
    arch = _sample_architecture(seed=2)
    config = MutationConfig()
    table = ConflictProneTable()
    table.mark(
        [
            GrammarFeature(FeatureKind.LINK_INSTANCE, arch.links[0].link_id),
        ]
    )
    for seed in range(30):
        rng = random.Random(seed)
        mutated = mutate_conflict_directed(arch, table, rng, config)
        _assert_invariants(mutated)


# -- Determinism -------------------------------------------------------------


def test_random_mutation_is_deterministic_given_rng_seed() -> None:
    arch = _sample_architecture(seed=3)
    config = MutationConfig()
    rng1 = random.Random(42)
    rng2 = random.Random(42)
    assert mutate_random(arch, rng1, config) == mutate_random(arch, rng2, config)


def test_conflict_directed_mutation_is_deterministic_given_rng_seed() -> None:
    arch = _sample_architecture(seed=4)
    config = MutationConfig()
    table = ConflictProneTable()
    table.mark(
        [
            GrammarFeature(FeatureKind.LINK_INSTANCE, arch.links[0].link_id),
            GrammarFeature(FeatureKind.LINK_TYPE, arch.links[0].kind.value),
        ]
    )
    rng1 = random.Random(7)
    rng2 = random.Random(7)
    assert mutate_conflict_directed(arch, table, rng1, config) == mutate_conflict_directed(
        arch, table, rng2, config
    )


# -- Operators affect correct kinds ------------------------------------------


def test_random_mutation_changes_something() -> None:
    arch = _sample_architecture(seed=5)
    config = MutationConfig()
    for seed in range(30):
        rng = random.Random(seed)
        mutated = mutate_random(arch, rng, config)
        assert mutated != arch, f"seed={seed} produced no change"


def test_conflict_directed_targets_marked_link() -> None:
    """With a table marking a specific link, and high conflict
    probability, the mutator should hit that link in the vast majority
    of runs."""
    arch = _sample_architecture(seed=6)
    config = MutationConfig(conflict_probability=1.0)
    target_link = arch.links[0]
    table = ConflictProneTable()
    table.mark(
        [
            GrammarFeature(FeatureKind.LINK_INSTANCE, target_link.link_id),
        ]
    )

    hits = 0
    trials = 40
    for seed in range(trials):
        rng = random.Random(seed)
        mutated = mutate_conflict_directed(arch, table, rng, config)
        # Determine whether the mutation touched the marked link:
        # either its kind changed, its params changed, or it was removed.
        original = next(ln for ln in arch.links if ln.link_id == target_link.link_id)
        after = next(
            (ln for ln in mutated.links if ln.link_id == target_link.link_id),
            None,
        )
        if (
            after is None
            or after.kind != original.kind
            or dict(after.params) != dict(original.params)
        ):
            hits += 1

    assert hits >= 30, f"Conflict-directed mutator only hit the marked link {hits}/{trials} times"


def test_conflict_directed_with_empty_table_falls_back() -> None:
    """With an empty table, the conflict-directed mutator is equivalent
    to random (same rng seed -> same result)."""
    arch = _sample_architecture(seed=7)
    config = MutationConfig(conflict_probability=0.85)
    empty = ConflictProneTable()

    rng_a = random.Random(11)
    rng_b = random.Random(11)
    result_random = mutate_random(arch, rng_a, config)
    result_conflict_empty = mutate_conflict_directed(arch, empty, rng_b, config)
    # The fallback path invokes mutate_random with the same rng state,
    # so the two must be identical.
    assert result_random == result_conflict_empty


def test_conflict_directed_targets_node_kind_change() -> None:
    """A NODE_TYPE feature should also bias the mutation."""
    arch = _sample_architecture(seed=8)
    config = MutationConfig(conflict_probability=1.0)
    # Mark the type of the first node.
    target_node = arch.nodes[0]
    table = ConflictProneTable()
    table.mark(
        [
            GrammarFeature(FeatureKind.NODE_TYPE, target_node.kind.value),
        ]
    )
    # Just verify it runs without error and produces a valid architecture.
    for seed in range(20):
        rng = random.Random(seed)
        mutated = mutate_conflict_directed(arch, table, rng, config)
        _assert_invariants(mutated)


def test_config_bounds_are_respected() -> None:
    """If the initial architecture is within the mutation config's
    bounds, the mutator never exceeds them.

    The initial architecture is generated with a GeneratorConfig
    matching the MutationConfig bounds. This isolates the property
    under test (mutation does not add beyond the bounds) from the
    orthogonal property (mutation does not remove pre-existing
    violations in an over-sized input, which it does not claim to
    do)."""
    config = MutationConfig(max_nodes=5, max_links=6)
    gen_config = GeneratorConfig(
        min_nodes=4,
        max_nodes=5,
        max_links=6,
        seed=9,
    )
    arch = generate_architecture(gen_config)
    assert len(arch.nodes) <= config.max_nodes
    assert len(arch.links) <= config.max_links
    for seed in range(50):
        rng = random.Random(seed)
        mutated = mutate_random(arch, rng, config)
        assert len(mutated.nodes) <= config.max_nodes
        assert len(mutated.links) <= config.max_links


def test_mutation_operator_enum_values() -> None:
    expected = {
        "node_kind_change",
        "node_param_jitter",
        "node_remove",
        "node_add",
        "link_kind_change",
        "link_param_jitter",
        "link_remove",
        "link_add",
    }
    assert {op.value for op in MutationOperator} == expected


def test_mutation_introduces_new_link_terminals_only() -> None:
    """Any link added or changed by mutation uses a spec terminal."""
    arch = _sample_architecture(seed=10)
    config = MutationConfig()
    for seed in range(40):
        rng = random.Random(seed)
        mutated = mutate_random(arch, rng, config)
        for ln in mutated.links:
            assert ln.kind in LINK_TERMINALS
        for n in mutated.nodes:
            assert n.kind in NODE_TERMINALS
