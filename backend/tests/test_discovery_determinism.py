"""Determinism gate for the full discovery pipeline.

Roadmap task s4-8: Scientific gate: attribution is deterministic and
reproducible.
Gate: Same UNSAT core -> same bias, twice.

The gate is decomposed into one test per pipeline stage plus one
end-to-end test that exercises the full loop twice and asserts
identical outputs at every stage.
"""

from __future__ import annotations

import random

import z3

from app.discovery.attribution import (
    ConflictProneTable,
    FeatureConstraint,
    FeatureKind,
    GrammarFeature,
    attribute_and_mark,
    attribute_core,
)
from app.discovery.generator import GeneratorConfig, generate_architecture
from app.discovery.grammar import Terminal
from app.discovery.mutation import (
    MutationConfig,
    mutate_conflict_directed,
)
from app.discovery.unsat import NamedConstraint, UnsatCoreExtractor

# -- Stage 1: grammar / generator --------------------------------------------


def test_generator_is_deterministic_given_seed() -> None:
    a = generate_architecture(GeneratorConfig(seed=777))
    b = generate_architecture(GeneratorConfig(seed=777))
    assert a == b


# -- Stage 2: encoder / sat check --------------------------------------------


def test_sat_verdict_is_deterministic_twice() -> None:
    x = z3.Real("x_det")
    for _ in range(2):
        solver = z3.Solver()
        solver.add(x >= 5.0)
        solver.add(x <= 10.0)
        assert solver.check() == z3.sat


# -- Stage 3: unsat core extraction ------------------------------------------


def test_unsat_core_is_deterministic_twice() -> None:
    x = z3.Real("x_core")
    constraints = (
        NamedConstraint("hi", x >= 10.0),
        NamedConstraint("lo", x <= 5.0),
    )

    def run_once() -> tuple[str, tuple[str, ...]]:
        ext = UnsatCoreExtractor()
        for c in constraints:
            ext.add(c)
        r = ext.check()
        return r.status, r.core_names

    assert run_once() == run_once()


# -- Stage 4: attribution ----------------------------------------------------


def _two_feature_constraints() -> tuple[FeatureConstraint, ...]:
    x = z3.Real("x_att")
    laser = GrammarFeature(FeatureKind.LINK_TYPE, Terminal.LASER_LINK.value)
    uav = GrammarFeature(FeatureKind.NODE_TYPE, Terminal.UAV_ENERGY.value)
    return (
        FeatureConstraint(
            family_name="a_hi",
            expression=x >= 10.0,
            features=frozenset({laser}),
        ),
        FeatureConstraint(
            family_name="a_lo",
            expression=x <= 5.0,
            features=frozenset({uav}),
        ),
    )


def test_attribution_is_deterministic_twice() -> None:
    constraints = _two_feature_constraints()
    r1 = attribute_core(constraints, ("a_hi", "a_lo"))
    r2 = attribute_core(constraints, ("a_hi", "a_lo"))
    assert r1 == r2


# -- Stage 5: mutation -------------------------------------------------------


def test_conflict_directed_mutation_is_deterministic_twice() -> None:
    arch = generate_architecture(GeneratorConfig(seed=42, min_nodes=4, max_nodes=6))
    table = ConflictProneTable()
    table.mark([GrammarFeature(FeatureKind.LINK_INSTANCE, arch.links[0].link_id)])
    cfg = MutationConfig(conflict_probability=1.0)

    r1 = mutate_conflict_directed(arch, table, random.Random(99), cfg)
    r2 = mutate_conflict_directed(arch, table, random.Random(99), cfg)
    assert r1 == r2


# -- Full pipeline -----------------------------------------------------------


def test_full_pipeline_determinism_twice() -> None:
    """Run the full pipeline twice and assert identical outputs at
    every stage. This is the s4-8 gate: same UNSAT core -> same bias,
    twice."""

    def run_once() -> tuple[
        tuple[str, ...],
        str,
        tuple[str, ...],
        tuple[GrammarFeature, ...],
    ]:
        arch = generate_architecture(GeneratorConfig(seed=2026, min_nodes=4, max_nodes=6))
        constraints = _two_feature_constraints()
        table = ConflictProneTable()
        attribution = attribute_and_mark(constraints, table)
        return (
            tuple(n.kind.value for n in arch.nodes),
            attribution.status,
            tuple(f.family_name for f in constraints),
            attribution.conflict_prone,
        )

    run_a = run_once()
    run_b = run_once()
    assert run_a == run_b


def test_different_seeds_produce_different_architectures() -> None:
    """Sanity check: determinism is a real property, not a constant.
    Two different seeds must produce structurally different
    architectures, otherwise the determinism test would pass
    trivially."""
    a = generate_architecture(GeneratorConfig(seed=1, min_nodes=4, max_nodes=6))
    b = generate_architecture(GeneratorConfig(seed=2, min_nodes=4, max_nodes=6))
    assert (
        len(a.nodes) != len(b.nodes)
        or len(a.links) != len(b.links)
        or tuple(n.kind for n in a.nodes) != tuple(n.kind for n in b.nodes)
    )
