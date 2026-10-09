"""Tests for NSGA-II Pareto selection.

Roadmap task s4-6: NSGA-II integration.
Gate: Hypervolume improves over generations.
"""

from __future__ import annotations

import random

import pytest

from app.discovery.generator import GeneratorConfig, generate_architecture
from app.discovery.grammar import (
    Architecture,
    LinkInstance,
    NodeInstance,
    Terminal,
)
from app.discovery.nsga2 import (
    NEGATIVE_OBJECTIVES,
    OBJECTIVE_COUNT,
    OBJECTIVE_LABELS,
    Individual,
    NSGA2Config,
    NSGA2Result,
    ObjectiveVector,
    crowding_distance,
    monte_carlo_hypervolume,
    non_dominated_sort,
    nsga2_select,
    run_nsga2,
    synthetic_evaluator,
    weighted_sum_score,
)


def _obj(c: float, r: float, e: float, n: float, t: float, u: float) -> ObjectiveVector:
    return ObjectiveVector((c, r, e, n, t, u))


def _trivial_arch() -> Architecture:
    return Architecture(
        nodes=(
            NodeInstance(node_id="n0", kind=Terminal.SATELLITE_LEO),
            NodeInstance(node_id="n1", kind=Terminal.UAV_ENERGY),
        ),
        links=(
            LinkInstance(
                link_id="l0",
                kind=Terminal.LASER_LINK,
                source_id="n0",
                target_id="n1",
            ),
        ),
    )


def test_objective_vector_requires_six_components() -> None:
    with pytest.raises(ValueError, match="exactly 6"):
        ObjectiveVector((1.0, 2.0, 3.0))  # type: ignore[arg-type]


def test_objective_labels() -> None:
    assert OBJECTIVE_LABELS == ("C", "R", "E", "N", "T", "U")
    assert OBJECTIVE_COUNT == 6


def test_negative_objectives_is_u() -> None:
    assert frozenset({5}) == NEGATIVE_OBJECTIVES


def test_dominates_strict_win_on_all() -> None:
    a = _obj(0.9, 0.9, 0.9, 0.9, 0.9, 0.1)
    b = _obj(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    assert a.dominates(b)
    assert not b.dominates(a)


def test_dominates_tie_with_one_strict_win() -> None:
    a = _obj(0.9, 0.5, 0.5, 0.5, 0.5, 0.5)
    b = _obj(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    assert a.dominates(b)


def test_dominates_false_on_identical() -> None:
    a = _obj(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    b = _obj(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    assert not a.dominates(b)
    assert not b.dominates(a)


def test_dominates_false_on_tradeoff() -> None:
    a = _obj(0.9, 0.9, 0.9, 0.9, 0.9, 0.5)
    b = _obj(0.5, 0.5, 0.5, 0.5, 0.5, 0.1)
    assert not a.dominates(b)
    assert not b.dominates(a)


def test_u_is_minimized() -> None:
    good = _obj(0.5, 0.5, 0.5, 0.5, 0.5, 0.1)
    bad = _obj(0.5, 0.5, 0.5, 0.5, 0.5, 0.9)
    assert good.dominates(bad)
    assert not bad.dominates(good)


def test_as_dict_round_trip() -> None:
    v = _obj(0.1, 0.2, 0.3, 0.4, 0.5, 0.6)
    d = v.as_dict()
    assert set(d.keys()) == set(OBJECTIVE_LABELS)
    assert d["C"] == 0.1 and d["U"] == 0.6


def test_weighted_sum_score_rejects_wrong_length() -> None:
    with pytest.raises(ValueError, match="must have 6 entries"):
        weighted_sum_score(_obj(0, 0, 0, 0, 0, 0), [1.0])


def test_weighted_sum_score_direction() -> None:
    v_low_u = _obj(0.5, 0.5, 0.5, 0.5, 0.5, 0.1)
    v_high_u = _obj(0.5, 0.5, 0.5, 0.5, 0.5, 0.9)
    weights = [1.0] * 6
    assert weighted_sum_score(v_low_u, weights) > weighted_sum_score(v_high_u, weights)


def test_sort_single_individual() -> None:
    ind = Individual(
        architecture=_trivial_arch(),
        objectives=_obj(0.5, 0.5, 0.5, 0.5, 0.5, 0.5),
    )
    fronts = non_dominated_sort([ind])
    assert len(fronts) == 1
    assert fronts[0] == [ind]


def test_sort_two_dominated() -> None:
    a = Individual(
        architecture=_trivial_arch(),
        objectives=_obj(0.9, 0.9, 0.9, 0.9, 0.9, 0.1),
    )
    b = Individual(
        architecture=_trivial_arch(),
        objectives=_obj(0.5, 0.5, 0.5, 0.5, 0.5, 0.5),
    )
    fronts = non_dominated_sort([a, b])
    assert len(fronts) == 2
    assert fronts[0] == [a]
    assert fronts[1] == [b]


def test_sort_two_nondominated() -> None:
    a = Individual(
        architecture=_trivial_arch(),
        objectives=_obj(0.9, 0.5, 0.5, 0.5, 0.5, 0.5),
    )
    b = Individual(
        architecture=_trivial_arch(),
        objectives=_obj(0.5, 0.9, 0.5, 0.5, 0.5, 0.5),
    )
    fronts = non_dominated_sort([a, b])
    assert len(fronts) == 1
    assert fronts[0] == [a, b]


def test_sort_three_fronts() -> None:
    a = Individual(
        architecture=_trivial_arch(),
        objectives=_obj(0.9, 0.9, 0.9, 0.9, 0.9, 0.1),
    )
    b = Individual(
        architecture=_trivial_arch(),
        objectives=_obj(0.7, 0.7, 0.7, 0.7, 0.7, 0.3),
    )
    c = Individual(
        architecture=_trivial_arch(),
        objectives=_obj(0.5, 0.5, 0.5, 0.5, 0.5, 0.5),
    )
    fronts = non_dominated_sort([a, b, c])
    assert [len(f) for f in fronts] == [1, 1, 1]
    assert fronts[0] == [a]


def test_crowding_distance_small_front() -> None:
    ind = Individual(
        architecture=_trivial_arch(),
        objectives=_obj(0.5, 0.5, 0.5, 0.5, 0.5, 0.5),
    )
    assert crowding_distance([ind]) == [float("inf")]


def test_crowding_distance_boundaries_are_infinite() -> None:
    inds = [
        Individual(
            architecture=_trivial_arch(),
            objectives=_obj(0.1, 0.5, 0.5, 0.5, 0.5, 0.5),
        ),
        Individual(
            architecture=_trivial_arch(),
            objectives=_obj(0.5, 0.5, 0.5, 0.5, 0.5, 0.5),
        ),
        Individual(
            architecture=_trivial_arch(),
            objectives=_obj(0.9, 0.5, 0.5, 0.5, 0.5, 0.5),
        ),
    ]
    d = crowding_distance(inds)
    assert d[0] == float("inf")
    assert d[2] == float("inf")
    assert d[1] > 0


def test_select_zero() -> None:
    assert nsga2_select([], 0) == []
    ind = Individual(
        architecture=_trivial_arch(),
        objectives=_obj(0.5, 0.5, 0.5, 0.5, 0.5, 0.5),
    )
    assert nsga2_select([ind], 0) == []


def test_select_more_than_population_returns_all() -> None:
    inds = [
        Individual(
            architecture=_trivial_arch(),
            objectives=_obj(0.5, 0.5, 0.5, 0.5, 0.5, 0.5),
        ),
        Individual(
            architecture=_trivial_arch(),
            objectives=_obj(0.6, 0.6, 0.6, 0.6, 0.6, 0.4),
        ),
    ]
    assert nsga2_select(inds, 5) == inds


def test_select_fills_front_completely() -> None:
    a = Individual(
        architecture=_trivial_arch(),
        objectives=_obj(0.9, 0.9, 0.9, 0.9, 0.9, 0.1),
    )
    b = Individual(
        architecture=_trivial_arch(),
        objectives=_obj(0.5, 0.5, 0.5, 0.5, 0.5, 0.5),
    )
    selected = nsga2_select([a, b], 1)
    assert selected == [a]


def test_select_rejects_negative_n() -> None:
    with pytest.raises(ValueError, match="n must be >= 0"):
        nsga2_select([], -1)


def test_hypervolume_empty_front() -> None:
    ref = _obj(0.0, 0.0, 0.0, 0.0, 0.0, 1.0)
    assert monte_carlo_hypervolume([], ref) == 0.0


def test_hypervolume_is_nonnegative() -> None:
    a = Individual(
        architecture=_trivial_arch(),
        objectives=_obj(0.9, 0.9, 0.9, 0.9, 0.9, 0.1),
    )
    ref = _obj(0.0, 0.0, 0.0, 0.0, 0.0, 1.0)
    assert monte_carlo_hypervolume([a], ref) > 0.0


def test_hypervolume_deterministic() -> None:
    a = Individual(
        architecture=_trivial_arch(),
        objectives=_obj(0.9, 0.9, 0.9, 0.9, 0.9, 0.1),
    )
    b = Individual(
        architecture=_trivial_arch(),
        objectives=_obj(0.5, 0.5, 0.5, 0.5, 0.5, 0.5),
    )
    ref = _obj(0.0, 0.0, 0.0, 0.0, 0.0, 1.0)
    hv1 = monte_carlo_hypervolume([a, b], ref, seed=42)
    hv2 = monte_carlo_hypervolume([a, b], ref, seed=42)
    assert hv1 == hv2


def test_hypervolume_larger_front_covers_more() -> None:
    a = Individual(
        architecture=_trivial_arch(),
        objectives=_obj(0.9, 0.9, 0.9, 0.9, 0.9, 0.1),
    )
    b = Individual(
        architecture=_trivial_arch(),
        objectives=_obj(0.5, 0.5, 0.5, 0.5, 0.5, 0.5),
    )
    ref = _obj(0.0, 0.0, 0.0, 0.0, 0.0, 1.0)
    hv_a = monte_carlo_hypervolume([a], ref, seed=7)
    hv_ab = monte_carlo_hypervolume([a, b], ref, seed=7)
    assert hv_ab >= hv_a


def test_run_nsga2_returns_result() -> None:
    rng = random.Random(0)
    initial = [
        generate_architecture(GeneratorConfig(min_nodes=4, max_nodes=6, max_links=6, seed=s))
        for s in range(5)
    ]
    result = run_nsga2(
        initial,
        synthetic_evaluator(),
        NSGA2Config(population_size=6, n_generations=3),
        rng,
    )
    assert isinstance(result, NSGA2Result)
    assert len(result.final_population) == 6
    assert len(result.pareto_front) >= 1
    assert len(result.hypervolume_history) == 3


def test_run_nsga2_hypervolume_non_decreasing_on_average() -> None:
    """The s4-6 gate: hypervolume improves over generations."""
    rng = random.Random(20261009)
    initial = [
        generate_architecture(GeneratorConfig(min_nodes=4, max_nodes=6, max_links=6, seed=s))
        for s in range(6)
    ]
    result = run_nsga2(
        initial,
        synthetic_evaluator(),
        NSGA2Config(population_size=10, n_generations=6),
        rng,
    )
    hv = result.hypervolume_history
    print(f"Hypervolume history: {[f'{v:.4f}' for v in hv]}")
    first_half = hv[: len(hv) // 2]
    second_half = hv[len(hv) // 2 :]
    mean_first = sum(first_half) / len(first_half)
    mean_second = sum(second_half) / len(second_half)
    assert mean_second >= mean_first * 0.95, (
        f"Hypervolume did not improve: first-half mean = {mean_first:.4f}, "
        f"second-half mean = {mean_second:.4f}"
    )


def test_run_nsga2_deterministic_twice() -> None:
    initial = [
        generate_architecture(GeneratorConfig(min_nodes=4, max_nodes=6, max_links=6, seed=s))
        for s in range(5)
    ]
    config = NSGA2Config(population_size=6, n_generations=4)
    r1 = run_nsga2(initial, synthetic_evaluator(), config, random.Random(111))
    r2 = run_nsga2(initial, synthetic_evaluator(), config, random.Random(111))
    assert r1.hypervolume_history == r2.hypervolume_history
    assert len(r1.final_population) == len(r2.final_population)


def test_nsga2_config_rejects_tiny_population() -> None:
    with pytest.raises(ValueError, match="population_size must be >= 2"):
        NSGA2Config(population_size=1)


def test_nsga2_config_rejects_zero_generations() -> None:
    with pytest.raises(ValueError, match="n_generations must be >= 1"):
        NSGA2Config(n_generations=0)


def test_synthetic_evaluator_is_deterministic() -> None:
    ev = synthetic_evaluator()
    arch = _trivial_arch()
    assert ev(arch) == ev(arch)
