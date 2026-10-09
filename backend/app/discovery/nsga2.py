"""NSGA-II Pareto-based multi-objective selection.

Roadmap task s4-6: NSGA-II integration (Pareto over C, R, E, N, T, U).
Gate: Hypervolume improves over generations.

Reference:
    AeroGrid-XAI Final Comprehensive Specification (Rev. 6),
    Section 14 and Section 35.4.

Objective vector
----------------

Section 14 defines a six-component vector (C, R, E, N, T, U):
coverage, resilience, energy efficiency, mission continuity, thermal
safety margin, uncertainty/risk. U is minimized; the rest are
maximized. Scalarization by weights is retained only as a post-hoc
reporting metric; it must not be the optimization target.

Determinism
-----------

Every random-consuming function takes a random.Random. Given the
same seed and inputs, output is identical.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from app.discovery.grammar import Architecture
from app.discovery.mutation import MutationConfig, mutate_random

OBJECTIVE_COUNT = 6
OBJECTIVE_LABELS: tuple[str, ...] = ("C", "R", "E", "N", "T", "U")
NEGATIVE_OBJECTIVES: frozenset[int] = frozenset({5})


@dataclass(frozen=True)
class ObjectiveVector:
    """A six-component objective vector in order (C, R, E, N, T, U)."""

    values: tuple[float, float, float, float, float, float]

    def __post_init__(self) -> None:
        if len(self.values) != OBJECTIVE_COUNT:
            raise ValueError(
                f"ObjectiveVector requires exactly {OBJECTIVE_COUNT} "
                f"components; got {len(self.values)}"
            )

    def _sign(self, i: int) -> float:
        return -1.0 if i in NEGATIVE_OBJECTIVES else 1.0

    def dominates(self, other: ObjectiveVector, *, atol: float = 1e-12) -> bool:
        """Return True if self Pareto-dominates other."""
        strictly_better = False
        for i in range(OBJECTIVE_COUNT):
            s = self._sign(i)
            a = s * self.values[i]
            b = s * other.values[i]
            if a < b - atol:
                return False
            if a > b + atol:
                strictly_better = True
        return strictly_better

    def as_dict(self) -> dict[str, float]:
        return dict(zip(OBJECTIVE_LABELS, self.values, strict=True))


ObjectiveEvaluator = Callable[[Architecture], ObjectiveVector]


@dataclass(frozen=True)
class Individual:
    """An architecture together with its evaluated objectives."""

    architecture: Architecture
    objectives: ObjectiveVector
    generation: int = 0


def weighted_sum_score(
    objectives: ObjectiveVector,
    weights: Sequence[float],
) -> float:
    """Post-hoc weighted-sum score for reporting.

    Section 14 permits the weighted sum only as a reporting metric
    applied after the Pareto front is computed. It must not be used
    as the optimization target.
    """
    if len(weights) != OBJECTIVE_COUNT:
        raise ValueError(f"weights must have {OBJECTIVE_COUNT} entries; got {len(weights)}")
    score = 0.0
    for i, w in enumerate(weights):
        s = -1.0 if i in NEGATIVE_OBJECTIVES else 1.0
        score += w * s * objectives.values[i]
    return score


def non_dominated_sort(
    population: Sequence[Individual],
) -> list[list[Individual]]:
    """Return Pareto fronts ordered best-first.

    Front 0 is the set of individuals not dominated by any other.
    Front k is the set dominated only by fronts 0..k-1.
    """
    n = len(population)
    dominated_by: list[list[int]] = [[] for _ in range(n)]
    dominates_count: list[int] = [0] * n

    for i in range(n):
        for j in range(i + 1, n):
            if population[i].objectives.dominates(population[j].objectives):
                dominated_by[i].append(j)
                dominates_count[j] += 1
            elif population[j].objectives.dominates(population[i].objectives):
                dominated_by[j].append(i)
                dominates_count[i] += 1

    fronts: list[list[Individual]] = []
    current = [i for i in range(n) if dominates_count[i] == 0]

    while current:
        fronts.append([population[i] for i in current])
        nxt: list[int] = []
        for i in current:
            for j in dominated_by[i]:
                dominates_count[j] -= 1
                if dominates_count[j] == 0:
                    nxt.append(j)
        current = nxt

    return fronts


def crowding_distance(front: Sequence[Individual]) -> list[float]:
    """Return crowding distance for each member of a front."""
    n = len(front)
    if n <= 2:
        return [float("inf")] * n

    distances = [0.0] * n
    for dim in range(OBJECTIVE_COUNT):
        order = sorted(range(n), key=lambda k: front[k].objectives.values[dim])
        values = [front[k].objectives.values[dim] for k in order]
        span = max(values) - min(values)
        distances[order[0]] = float("inf")
        distances[order[-1]] = float("inf")
        if span <= 0.0:
            continue
        for k in range(1, n - 1):
            distances[order[k]] += (values[k + 1] - values[k - 1]) / span
    return distances


def nsga2_select(
    population: Sequence[Individual],
    n: int,
) -> list[Individual]:
    """Select n individuals by NSGA-II rules."""
    if n < 0:
        raise ValueError(f"n must be >= 0; got {n}")
    if n == 0:
        return []
    if n >= len(population):
        return list(population)

    fronts = non_dominated_sort(population)
    selected: list[Individual] = []

    for front in fronts:
        if len(selected) + len(front) <= n:
            selected.extend(front)
        else:
            remaining = n - len(selected)
            distances = crowding_distance(front)
            indexed = list(enumerate(front))
            indexed.sort(key=lambda pair: (-distances[pair[0]], pair[0]))
            selected.extend(ind for _, ind in indexed[:remaining])
            break

    return selected


def monte_carlo_hypervolume(
    front: Sequence[Individual],
    reference_point: ObjectiveVector,
    *,
    n_samples: int = 4096,
    seed: int = 20261009,
) -> float:
    """Estimate hypervolume dominated by front up to a reference point.

    Monte Carlo estimator, deterministic given seed. Not exact.

    Sign convention: score_i = s_i * value_i with s_i = -1 for U and
    +1 otherwise, so higher score is always better. A point x in
    score space is dominated by front member a iff
    x[i] <= score(a, i) for every i.

    The box extends from ref_scores[i] up to
    max-over-front score[i]. If the reference is not strictly worse
    than every front member along any dimension, the box has
    non-positive extent there and the function returns zero.
    """
    if not front:
        return 0.0
    if n_samples < 1:
        raise ValueError(f"n_samples must be >= 1; got {n_samples}")

    def score(v: ObjectiveVector, i: int) -> float:
        s = -1.0 if i in NEGATIVE_OBJECTIVES else 1.0
        return s * v.values[i]

    ref_scores = [score(reference_point, i) for i in range(OBJECTIVE_COUNT)]
    best_scores = [-math.inf] * OBJECTIVE_COUNT
    for ind in front:
        for i in range(OBJECTIVE_COUNT):
            best_scores[i] = max(best_scores[i], score(ind.objectives, i))

    side: list[float] = []
    for i in range(OBJECTIVE_COUNT):
        extent = best_scores[i] - ref_scores[i]
        if extent <= 0.0:
            return 0.0
        side.append(extent)

    box_volume = 1.0
    for s in side:
        box_volume *= s

    rng = random.Random(seed)
    dominated = 0
    for _ in range(n_samples):
        sample = [rng.uniform(ref_scores[i], best_scores[i]) for i in range(OBJECTIVE_COUNT)]
        for ind in front:
            if all(sample[i] <= score(ind.objectives, i) + 1e-12 for i in range(OBJECTIVE_COUNT)):
                dominated += 1
                break

    return box_volume * dominated / n_samples


@dataclass(frozen=True)
class NSGA2Config:
    population_size: int = 20
    n_generations: int = 10
    mutation_config: MutationConfig = field(default_factory=MutationConfig)

    def __post_init__(self) -> None:
        if self.population_size < 2:
            raise ValueError(f"population_size must be >= 2; got {self.population_size}")
        if self.n_generations < 1:
            raise ValueError(f"n_generations must be >= 1; got {self.n_generations}")


@dataclass(frozen=True)
class NSGA2Result:
    """Result of an NSGA-II run."""

    final_population: tuple[Individual, ...]
    pareto_front: tuple[Individual, ...]
    hypervolume_history: tuple[float, ...]


def run_nsga2(
    initial_population: Sequence[Architecture],
    evaluator: ObjectiveEvaluator,
    config: NSGA2Config | None = None,
    rng: random.Random | None = None,
    *,
    reference_point: ObjectiveVector | None = None,
    hypervolume_samples: int = 2048,
) -> NSGA2Result:
    """Run NSGA-II for the configured number of generations."""
    cfg = config or NSGA2Config()
    if rng is None:
        rng = random.Random(0)
    if len(initial_population) == 0:
        raise ValueError("initial_population must be non-empty")

    population: list[Individual] = []
    for i in range(cfg.population_size):
        base = initial_population[i % len(initial_population)]
        arch = (
            base if i < len(initial_population) else mutate_random(base, rng, cfg.mutation_config)
        )
        population.append(
            Individual(
                architecture=arch,
                objectives=evaluator(arch),
                generation=0,
            )
        )

    ref = reference_point
    hypervolume_history: list[float] = []

    for gen in range(cfg.n_generations):
        survivors = nsga2_select(population, cfg.population_size)

        offspring: list[Individual] = []
        for ind in survivors:
            child_arch = mutate_random(ind.architecture, rng, cfg.mutation_config)
            offspring.append(
                Individual(
                    architecture=child_arch,
                    objectives=evaluator(child_arch),
                    generation=gen + 1,
                )
            )

        combined = survivors + offspring
        population = nsga2_select(combined, cfg.population_size)

        if ref is None:
            ref = _default_reference_point(population)
        hypervolume_history.append(
            monte_carlo_hypervolume(
                population,
                ref,
                n_samples=hypervolume_samples,
                seed=20261009 + gen,
            )
        )

    final_population = tuple(population)
    fronts = non_dominated_sort(population)
    pareto_front = tuple(fronts[0]) if fronts else ()

    return NSGA2Result(
        final_population=final_population,
        pareto_front=pareto_front,
        hypervolume_history=tuple(hypervolume_history),
    )


def _default_reference_point(
    population: Sequence[Individual],
) -> ObjectiveVector:
    """Return a reference point strictly worse than every individual.

    For each dimension, take the worst observed score (minimum in
    sign-adjusted score space), then subtract 1.0 to make it
    strictly worse. Reapply the sign to convert back to value space.
    """
    w0 = 0.0
    w1 = 0.0
    w2 = 0.0
    w3 = 0.0
    w4 = 0.0
    w5 = 0.0
    scores: list[float] = [0.0] * OBJECTIVE_COUNT
    for i in range(OBJECTIVE_COUNT):
        s = -1.0 if i in NEGATIVE_OBJECTIVES else 1.0
        vals = [s * ind.objectives.values[i] for ind in population]
        worst_score = min(vals) - 1.0
        scores[i] = s * worst_score

    w0, w1, w2, w3, w4, w5 = scores
    return ObjectiveVector((w0, w1, w2, w3, w4, w5))


def synthetic_evaluator(seed: int = 20261009) -> ObjectiveEvaluator:
    """Return a deterministic evaluator for testing NSGA-II.

    Test instrument, not a physical model. Computes each objective as
    a bounded function of node count, link count, and link-kind
    diversity, so the resulting Pareto front has genuine trade-offs
    and the run is reproducible.
    """
    _ = seed

    def evaluate(arch: Architecture) -> ObjectiveVector:
        n_nodes = len(arch.nodes)
        n_links = len(arch.links)
        n_link_kinds = len({ln.kind for ln in arch.links})

        c = min(1.0, n_nodes / 8.0)
        r = min(1.0, n_links / 12.0)
        e = 1.0 / (1.0 + n_links)
        n_mission = min(1.0, n_link_kinds / 3.0)
        t = max(0.0, 1.0 - n_nodes / 16.0)
        u = min(1.0, n_links / 20.0)
        return ObjectiveVector((c, r, e, n_mission, t, u))

    return evaluate
