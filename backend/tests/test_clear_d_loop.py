"""Tests for the CLEAR-D closed-loop composition."""

from __future__ import annotations

import random

from app.discovery.generator import GeneratorConfig, generate_architecture
from app.discovery.grammar import Architecture
from app.discovery.loop import (
    ClearDLoopConfig,
    run_clear_d_loop,
)
from app.discovery.nsga2 import synthetic_evaluator
from app.verification.architecture_encoder import encode_architecture


def _seed_population(n: int, seed: int) -> list[Architecture]:
    out: list[Architecture] = []
    for i in range(n):
        arch = generate_architecture(
            GeneratorConfig(min_nodes=3, max_nodes=6, max_links=4, seed=seed + i)
        )
        out.append(arch)
    return out


def test_loop_runs_and_returns_result() -> None:
    seeds = _seed_population(4, seed=1000)
    cfg = ClearDLoopConfig(population_size=6, n_generations=3)
    result = run_clear_d_loop(
        seeds,
        encode_architecture,
        synthetic_evaluator(),
        cfg,
        random.Random(42),
        hypervolume_samples=256,
    )
    assert len(result.generation_stats) == 3
    assert len(result.hypervolume_history) == 3
    assert len(result.final_population) == 6


def test_loop_is_deterministic_given_seed() -> None:
    seeds = _seed_population(4, seed=2000)
    cfg = ClearDLoopConfig(population_size=6, n_generations=3)
    r1 = run_clear_d_loop(
        seeds,
        encode_architecture,
        synthetic_evaluator(),
        cfg,
        random.Random(7),
        hypervolume_samples=256,
    )
    r2 = run_clear_d_loop(
        seeds,
        encode_architecture,
        synthetic_evaluator(),
        cfg,
        random.Random(7),
        hypervolume_samples=256,
    )
    assert len(r1.feasible_architectures) == len(r2.feasible_architectures)
    assert r1.hypervolume_history == r2.hypervolume_history, (
        f"hypervolume mismatch: {r1.hypervolume_history} vs {r2.hypervolume_history}"
    )


def test_loop_feasible_fraction_does_not_decrease_monotonically_but_trends_up() -> None:
    """Over enough generations starting from random seeds the conflict-
    directed arm should produce at least as many feasible architectures
    at the end as at the start."""
    seeds = _seed_population(4, seed=3000)
    cfg = ClearDLoopConfig(population_size=10, n_generations=8)
    result = run_clear_d_loop(
        seeds,
        encode_architecture,
        synthetic_evaluator(),
        cfg,
        random.Random(11),
        hypervolume_samples=512,
    )
    first = result.generation_stats[0].n_feasible
    last = result.generation_stats[-1].n_feasible
    assert last >= first, (
        f"feasible count dropped from {first} at gen 0 to {last} at gen "
        f"{len(result.generation_stats) - 1}; loop is not making progress"
    )


def test_loop_conflict_table_is_populated_when_unsat_occurs() -> None:
    seeds = _seed_population(4, seed=4000)
    cfg = ClearDLoopConfig(population_size=8, n_generations=4)
    result = run_clear_d_loop(
        seeds,
        encode_architecture,
        synthetic_evaluator(),
        cfg,
        random.Random(99),
        hypervolume_samples=256,
    )
    total_infeasible = sum(s.n_infeasible for s in result.generation_stats)
    if total_infeasible > 0:
        assert len(result.conflict_prone_table) > 0, (
            "infeasible architectures were encountered but the conflict-prone table is empty"
        )
