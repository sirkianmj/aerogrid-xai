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
    """Configuration for one CLEAR-D loop run.

    Attributes:
        use_conflict_directed: If True (the default), infeasible
            individuals are mutated with conflict-directed mutation
            weighted by the accumulated ConflictProneTable. If False,
            they are mutated with uniform random mutation, giving a
            proper control arm for the H9 hypothesis (closed-loop
            CLEAR-D discovers feasible architectures at a higher rate
            than random search at equal budget).
    """

    population_size: int = 20
    n_generations: int = 20
    mutation_config: MutationConfig = field(default_factory=MutationConfig)
    nsga2_config: NSGA2Config = field(default_factory=NSGA2Config)
    use_conflict_directed: bool = True

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
) -> tuple[list[Individual], list[Individual], set[int]]:
    """Encode, check, and attribute every individual.

    Returns (feasible, infeasible, feasible_ids). The table is updated
    in place for every UNSAT result. ``feasible_ids`` contains the
    ``id()`` of every individual in ``feasible`` so that a caller can
    test membership without object equality on Architecture.
    """
    feasible: list[Individual] = []
    infeasible: list[Individual] = []
    feasible_ids: set[int] = set()
    for ind in population:
        constraints = encoder(ind.architecture)
        attribution = attribute_and_mark(constraints, table)
        if attribution.status == "sat":
            feasible.append(ind)
            feasible_ids.add(id(ind))
        else:
            infeasible.append(ind)
    return feasible, infeasible, feasible_ids


def _constrained_select(
    population: list[Individual],
    feasible_ids: set[int],
    n: int,
) -> list[Individual]:
    """NSGA-II selection with the constrained-domination principle.

    Feasible individuals always dominate infeasible ones, regardless
    of objective values. This prevents the selection step from
    discarding a feasible architecture in favour of an infeasible
    architecture with a more attractive objective vector.

    Within the feasible subset, ordinary Pareto dominance (via
    nsga2_select) orders the individuals. Within the infeasible
    subset, the same ordering is applied; infeasible individuals are
    used only to fill slots the feasible subset does not occupy.

    Args:
        population: Every candidate individual.
        feasible_ids: ``id()`` values of the individuals classified
            as feasible. ``id`` is used rather than the Individual
            object itself because Individual is a frozen dataclass
            with a heavy equality check on Architecture.
        n: Number of individuals to return.

    Returns:
        A list of at most n individuals, feasible ones first.
    """
    feasible = [ind for ind in population if id(ind) in feasible_ids]
    infeasible = [ind for ind in population if id(ind) not in feasible_ids]

    if len(feasible) >= n:
        return nsga2_select(feasible, n)

    selected = list(feasible)
    remaining = n - len(selected)
    if remaining > 0 and infeasible:
        selected.extend(nsga2_select(infeasible, remaining))
    return selected


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

    Classification discipline: every individual is classified exactly
    once, either as part of the initial population, or when generated
    as offspring. Feasibility of the surviving population is derived
    from the feasibility of the combined parent-and-offspring pool,
    which is already known from those two classification passes. The
    loop does not re-classify individuals that survive selection.

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

    # Initial classification of the seed population. This is the only
    # classification of these individuals; later classifications are
    # reserved for offspring.
    feasible, infeasible, feasible_ids = _classify(population, encoder, table)

    for gen in range(cfg.n_generations):
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
            if cfg.use_conflict_directed:
                child_arch = mutate_conflict_directed(
                    ind.architecture, table, rng, cfg.mutation_config
                )
            else:
                child_arch = mutate_random(ind.architecture, rng, cfg.mutation_config)
            offspring.append(
                Individual(
                    architecture=child_arch,
                    objectives=evaluator(child_arch),
                    generation=gen + 1,
                )
            )

        # Classify offspring exactly once. This is the only pass that
        # updates the ConflictProneTable for offspring contributions.
        _, _, offspring_feasible_ids = _classify(offspring, encoder, table)

        # Constrained selection over parents plus offspring. Feasibility
        # for the combined pool is the union of the two known sets, so
        # no re-classification is needed.
        combined = population + offspring
        combined_feasible_ids = feasible_ids | offspring_feasible_ids
        selected = _constrained_select(combined, combined_feasible_ids, cfg.population_size)

        # Derive the surviving population's feasibility from the known
        # combined set, not from a fresh classification.
        feasible = [ind for ind in selected if id(ind) in combined_feasible_ids]
        infeasible = [ind for ind in selected if id(ind) not in combined_feasible_ids]
        feasible_ids = {id(ind) for ind in feasible}
        population = selected

    return ClearDLoopResult(
        final_population=tuple(population),
        feasible_architectures=tuple(ind.architecture for ind in feasible),
        infeasible_architectures=tuple(ind.architecture for ind in infeasible),
        conflict_prone_table=table,
        generation_stats=tuple(stats),
        hypervolume_history=tuple(hypervolume_history),
    )
