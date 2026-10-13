"""Sprint 9 s9-3 - Z3 verification end-to-end.

Roadmap gate:

    Generate -> encode -> verify -> extract core -> mutate;
    loop completes 100 generations without error.

The headline test runs ``run_clear_d_loop`` against the real Stage B
encoder (``app.verification.architecture_encoder.encode_architecture``)
for 100 generations. The encoder delegates to Z3. The gate is about
completion and pipeline coverage, not about feasibility rates, which
the s4-4, s4-7, and H9 tests already validate on their own axes.

This module verifies:

  * 100 generations complete (the loop returns; no exception).
  * The encoder is invoked at least once per individual per generation
    (proving the pipeline reaches Stage B rather than short-circuiting).
  * Per-generation counts sum to ``population_size`` (nothing dropped).
  * Both SAT and UNSAT branches are exercised across the run, so the
    "extract unsat core -> conflict-directed mutation" path runs at
    least once (otherwise the gate is trivially satisfied).
  * ``generation_stats`` and ``hypervolume_history`` each contain
    exactly ``n_generations`` entries.
  * Determinism: identical seeds produce identical histories.
  * The config rejects invalid ``n_generations``; the loop rejects an
    empty initial population.

Population size is deliberately kept small (4) for the 100-generation
runs. The gate is on generation count, not population size; 4 keeps
the wall clock within a few seconds per test while still exercising
the full pipeline. Population 10 at 100 generations would take ~20 s
under the current Z3 solve latency, which is too much for a single
test in the backend CI job.
"""

from __future__ import annotations

import random

import pytest

from app.discovery.generator import GeneratorConfig, generate_architecture
from app.discovery.grammar import (
    Architecture,
    Terminal,
)
from app.discovery.loop import ClearDLoopConfig, run_clear_d_loop
from app.discovery.nsga2 import synthetic_evaluator
from app.verification.architecture_encoder import encode_architecture

N_GENERATIONS = 100
POPULATION_SIZE = 4
HYPERVOLUME_SAMPLES = 16


def _seeds(n: int, seed: int) -> list[Architecture]:
    return [
        generate_architecture(GeneratorConfig(min_nodes=3, max_nodes=6, max_links=4, seed=seed + i))
        for i in range(n)
    ]


class _CountingEncoder:
    """Wraps ``encode_architecture`` to count invocations.

    Every call delegates to the real encoder, so Z3 is genuinely
    invoked. The counter is an instance attribute; tests read
    ``counter.calls`` after the loop returns.
    """

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, arch: Architecture):  # type: ignore[no-untyped-def]
        self.calls += 1
        return encode_architecture(arch)


# --- headline gate ---------------------------------------------------------


def test_100_generations_completes_without_error() -> None:
    """The s9-3 gate: the loop runs 100 generations over the real
    encoder without raising."""
    seeds = _seeds(POPULATION_SIZE, seed=9000)
    cfg = ClearDLoopConfig(
        population_size=POPULATION_SIZE,
        n_generations=N_GENERATIONS,
    )
    result = run_clear_d_loop(
        seeds,
        encode_architecture,
        synthetic_evaluator(),
        cfg,
        random.Random(20261013),
        hypervolume_samples=HYPERVOLUME_SAMPLES,
    )
    assert len(result.generation_stats) == N_GENERATIONS
    assert len(result.hypervolume_history) == N_GENERATIONS
    assert len(result.final_population) == POPULATION_SIZE


def test_100_generations_is_deterministic_under_fixed_seed() -> None:
    """Same seed, same 100-generation run, same histories. If this
    fails, the loop is not reproducible and the previous test's
    "completes without error" is meaningless as a scientific claim."""
    seeds = _seeds(POPULATION_SIZE, seed=9100)
    cfg = ClearDLoopConfig(
        population_size=POPULATION_SIZE,
        n_generations=N_GENERATIONS,
    )
    r1 = run_clear_d_loop(
        seeds,
        encode_architecture,
        synthetic_evaluator(),
        cfg,
        random.Random(20261013),
        hypervolume_samples=HYPERVOLUME_SAMPLES,
    )
    r2 = run_clear_d_loop(
        seeds,
        encode_architecture,
        synthetic_evaluator(),
        cfg,
        random.Random(20261013),
        hypervolume_samples=HYPERVOLUME_SAMPLES,
    )
    assert r1.hypervolume_history == r2.hypervolume_history
    assert len(r1.feasible_architectures) == len(r2.feasible_architectures)
    for a, b in zip(r1.generation_stats, r2.generation_stats, strict=True):
        assert a == b


# --- pipeline coverage -----------------------------------------------------


def test_encoder_invoked_at_least_once_per_individual_per_generation() -> None:
    """The loop must call the Stage B encoder at least once for every
    individual in the initial population and once for every offspring.
    With population ``P`` and ``G`` generations, that is at least
    ``P * (1 + G)`` invocations."""
    n_gen = 20
    seeds = _seeds(POPULATION_SIZE, seed=9200)
    cfg = ClearDLoopConfig(
        population_size=POPULATION_SIZE,
        n_generations=n_gen,
    )
    counter = _CountingEncoder()
    run_clear_d_loop(
        seeds,
        counter,
        synthetic_evaluator(),
        cfg,
        random.Random(11),
        hypervolume_samples=HYPERVOLUME_SAMPLES,
    )
    minimum = POPULATION_SIZE * (1 + n_gen)
    assert counter.calls >= minimum, (
        f"encoder invoked {counter.calls} times; expected at least {minimum} "
        f"({POPULATION_SIZE} initial + {POPULATION_SIZE} offspring x {n_gen} generations)"
    )


def test_per_generation_counts_sum_to_population_size() -> None:
    """No individual is dropped between classification and recording."""
    n_gen = 20
    seeds = _seeds(POPULATION_SIZE, seed=9300)
    cfg = ClearDLoopConfig(
        population_size=POPULATION_SIZE,
        n_generations=n_gen,
    )
    result = run_clear_d_loop(
        seeds,
        encode_architecture,
        synthetic_evaluator(),
        cfg,
        random.Random(5),
        hypervolume_samples=HYPERVOLUME_SAMPLES,
    )
    for gs in result.generation_stats:
        assert gs.n_feasible + gs.n_infeasible == POPULATION_SIZE, (
            f"generation {gs.generation}: feasible={gs.n_feasible} "
            f"infeasible={gs.n_infeasible} != {POPULATION_SIZE}"
        )


def _unsat_seed_from_generator(seed: int) -> Architecture:
    """Return a generator-produced architecture rendered UNSAT by
    removing the incoming link from one UAV.

    The stripped UAV then triggers ``demand_unmet`` in the encoder,
    which is an unconditional FALSE constraint. The remaining links
    stay in the graph, so the mutator has link targets to choose from;
    a hand-built linkless architecture would raise IndexError inside
    ``mutate_random`` (see mutation.py ``_pick_random_operator_and_target``).

    Deterministic for a given seed. Raises AssertionError if the seed
    happens to produce an architecture from which no such surgery is
    possible -- in that case, the caller should try another seed.
    """
    base = generate_architecture(GeneratorConfig(min_nodes=4, max_nodes=6, max_links=4, seed=seed))
    uav_kinds = (Terminal.UAV_ENERGY, Terminal.UAV_COMPUTE)
    candidates = [
        n
        for n in base.nodes
        if n.kind in uav_kinds and any(ln.target_id == n.node_id for ln in base.links)
    ]
    for uav in candidates:
        remaining = tuple(ln for ln in base.links if ln.target_id != uav.node_id)
        if len(remaining) >= 1:
            return Architecture(nodes=base.nodes, links=remaining)
    raise AssertionError(
        f"seed {seed}: removing the incoming link from any UAV would leave "
        "zero links; cannot construct an UNSAT architecture that still has "
        "link targets for the mutator"
    )


def _mixed_seed_population() -> list[Architecture]:
    """Four seed architectures: two deterministic UNSAT variants
    (generator outputs rendered UNSAT by stripping one incoming link
    from a UAV) and two intact generator outputs.

    The UNSAT variants exercise the extract-core -> conflict-directed
    mutation path on every run, not just when the RNG lands on a
    naturally infeasible seed. The two intact outputs give the loop
    real SAT workload to select against.
    """
    return [
        _unsat_seed_from_generator(seed=0),
        _unsat_seed_from_generator(seed=1),
        generate_architecture(GeneratorConfig(min_nodes=4, max_nodes=6, max_links=4, seed=2)),
        generate_architecture(GeneratorConfig(min_nodes=4, max_nodes=6, max_links=4, seed=3)),
    ]


def test_both_sat_and_unsat_branches_exercised() -> None:
    """The gate requires "extract unsat core -> conflict-directed
    mutation". That branch only runs on UNSAT individuals. Seeding the
    loop with hand-crafted UNSAT architectures guarantees the branch
    is exercised every run; the two generator outputs ensure both
    feasibility branches are present in the same population.

    This test also asserts the attribution table is populated, which
    is the observable signal that ``attribute_and_mark`` ran on the
    UNSAT individuals and the conflict-directed mutation has
    something to target."""
    seeds = _mixed_seed_population()
    cfg = ClearDLoopConfig(population_size=len(seeds), n_generations=10)
    result = run_clear_d_loop(
        seeds,
        encode_architecture,
        synthetic_evaluator(),
        cfg,
        random.Random(3),
        hypervolume_samples=HYPERVOLUME_SAMPLES,
    )
    total_infeasible = sum(gs.n_infeasible for gs in result.generation_stats)
    assert total_infeasible > 0, (
        f"hand-crafted UNSAT architectures were seeded but the loop "
        f"recorded zero infeasible individuals across "
        f"{cfg.n_generations} generations"
    )
    assert len(result.conflict_prone_table) > 0, (
        "infeasible individuals observed but the conflict-prone table "
        "is empty; attribution did not run"
    )


def test_config_rejects_zero_generations() -> None:
    with pytest.raises(ValueError, match="n_generations"):
        ClearDLoopConfig(population_size=4, n_generations=0)


def test_config_rejects_singleton_population() -> None:
    with pytest.raises(ValueError, match="population_size"):
        ClearDLoopConfig(population_size=1, n_generations=1)


def test_loop_rejects_empty_initial_population() -> None:
    cfg = ClearDLoopConfig(population_size=4, n_generations=1)
    with pytest.raises(ValueError, match="non-empty"):
        run_clear_d_loop(
            [],
            encode_architecture,
            synthetic_evaluator(),
            cfg,
            random.Random(1),
        )
