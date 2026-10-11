"""CLEAR-D closed-loop discovery composition (Stage C execution).

This module composes the individual CLEAR-D stages into an executable
loop, matching the discovery loop described in AeroGrid-XAI Rev. 6
Section 35.4 and scheduled by the roadmap for
``notebooks/10_clear_d_end_to_end.ipynb`` (Sprint 9).

Loop, per generation:

1. Classify every individual in the population by encoding (Stage B)
   and checking satisfiability, attributing UNSAT cores to grammar
   features via ``attribute_and_mark`` (Stage C).
2. Generate offspring: feasible individuals receive random mutation;
   infeasible individuals receive conflict-directed mutation weighted
   by the ConflictProneTable accumulated across generations.
3. Select the next generation by NSGA-II over the union of parents
   and offspring.
4. Record per-generation statistics and hypervolume.

The loop never mutates a feasible individual with conflict-directed
operators (there is no conflict to direct against), and never mutates
an infeasible individual with purely random operators unless the
ConflictProneTable is empty. This is the composition the spec
describes. It does not modify ``nsga2.py``; the NSGA-II primitives
are used as-is.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass, field

from app.discovery.attribution import (
    ConflictProneTable,
    FeatureConstraint,
    attribute_and_mark,
)
from app.discovery.grammar import Architecture
from app.discovery.mutation import (
    MutationConfig,
    mutate_conflict_directed,
    mutate_random,
)
from app.discovery.nsga2 import (
    Individual,
    NSGA2Config,
    ObjectiveEvaluator,
    ObjectiveVector,
    _default_reference_point,
    monte_carlo_hypervolume,
    nsga2_select,
)

EncoderFn = Callable[[Architecture], tuple[FeatureConstraint, ...]]


@dataclass(frozen=True)
class ClearDLoopConfig:
    """Configuration for one CLEAR-D loop run."""

    population_size: int = 20
    n_generations: int = 20
    mutation_config: MutationConfig = field(default_factory=MutationConfig)
    nsga2_config: NSGA2Config = field(default_factory=NSGA2Config)

    def __post_init__(self) -> None:
        if self.population_size < 2:
            raise ValueError(f"population_size must be >= 2; got {self.population_size}")
        if self.n_generations < 1:
            raise ValueError(f"n_generations must be >= 1; got {self.n_generations}")


@dataclass(frozen=True)
class GenerationStats:
    """Per-generation summary of the discovery loop."""

    generation: int
    n_feasible: int
    n_infeasible: int
    n_conflict_prone_features: int
    mean_feasible_birth_generation: float


@dataclass(frozen=True)
class ClearDLoopResult:
    """Result of a CLEAR-D loop run."""

    final_population: tuple[Individual, ...]
    feasible_architectures: tuple[Architecture, ...]
    infeasible_architectures: tuple[Architecture, ...]
    conflict_prone_table: ConflictProneTable
    generation_stats: tuple[GenerationStats, ...]
    hypervolume_history: tuple[float, ...]


def _classify(
    population: list[Individual],
    encoder: EncoderFn,
    table: ConflictProneTable,
) -> tuple[list[Individual], list[Individual]]:
    """Encode, check, and attribute every individual.

    Returns (feasible, infeasible). The table is updated in place for
    every UNSAT result.
    """
    feasible: list[Individual] = []
    infeasible: list[Individual] = []
    for ind in population:
        constraints = encoder(ind.architecture)
        attribution = attribute_and_mark(constraints, table)
        if attribution.status == "sat":
            feasible.append(ind)
        else:
            infeasible.append(ind)
    return feasible, infeasible


def run_clear_d_loop(
    initial_population: list[Architecture],
    encoder: EncoderFn,
    evaluator: ObjectiveEvaluator,
    config: ClearDLoopConfig | None = None,
    rng: random.Random | None = None,
    *,
    reference_point: ObjectiveVector | None = None,
    hypervolume_samples: int = 2048,
) -> ClearDLoopResult:
    """Run the CLEAR-D closed loop.

    Args:
        initial_population: Seed architectures from the generator.
        encoder: Stage B encoder callable. See
            ``app.verification.architecture_encoder.encode_architecture``.
        evaluator: Objective function for NSGA-II.
        config: Loop hyperparameters.
        rng: Deterministic RNG. Defaults to seed 0.
        reference_point: NSGA-II hypervolume reference point. If None,
            derived from the first generation's population.
        hypervolume_samples: Monte Carlo samples per generation.

    Returns:
        ClearDLoopResult.
    """
    cfg = config or ClearDLoopConfig()
    if rng is None:
        rng = random.Random(0)
    if not initial_population:
        raise ValueError("initial_population must be non-empty")

    population: list[Individual] = []
    for i in range(cfg.population_size):
        base = initial_population[i % len(initial_population)]
        arch = (
            base if i < len(initial_population) else mutate_random(base, rng, cfg.mutation_config)
        )
        population.append(Individual(architecture=arch, objectives=evaluator(arch), generation=0))

    table = ConflictProneTable()
    stats: list[GenerationStats] = []
    hypervolume_history: list[float] = []
    ref = reference_point

    for gen in range(cfg.n_generations):
        feasible, infeasible = _classify(population, encoder, table)

        birth_gens = [ind.generation for ind in feasible]
        mean_birth = sum(birth_gens) / len(birth_gens) if birth_gens else float("nan")
        stats.append(
            GenerationStats(
                generation=gen,
                n_feasible=len(feasible),
                n_infeasible=len(infeasible),
                n_conflict_prone_features=len(table),
                mean_feasible_birth_generation=mean_birth,
            )
        )

        if feasible:
            if ref is None:
                ref = _default_reference_point(population)
            hypervolume_history.append(
                monte_carlo_hypervolume(
                    feasible,
                    ref,
                    n_samples=hypervolume_samples,
                    seed=20261009 + gen,
                )
            )
        else:
            hypervolume_history.append(0.0)

        offspring: list[Individual] = []
        for ind in feasible:
            child_arch = mutate_random(ind.architecture, rng, cfg.mutation_config)
            offspring.append(
                Individual(
                    architecture=child_arch,
                    objectives=evaluator(child_arch),
                    generation=gen + 1,
                )
            )
        for ind in infeasible:
            child_arch = mutate_conflict_directed(ind.architecture, table, rng, cfg.mutation_config)
            offspring.append(
                Individual(
                    architecture=child_arch,
                    objectives=evaluator(child_arch),
                    generation=gen + 1,
                )
            )

        combined = population + offspring
        population = nsga2_select(combined, cfg.population_size)

    final_feasible, final_infeasible = _classify(population, encoder, table)

    return ClearDLoopResult(
        final_population=tuple(population),
        feasible_architectures=tuple(ind.architecture for ind in final_feasible),
        infeasible_architectures=tuple(ind.architecture for ind in final_infeasible),
        conflict_prone_table=table,
        generation_stats=tuple(stats),
        hypervolume_history=tuple(hypervolume_history),
    )
