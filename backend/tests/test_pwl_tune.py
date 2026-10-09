"""Tests for adaptive PWL refinement.

Roadmap task s6-2: PWL tightening/relaxing based on SAT/UNSAT vs observed.
Gate: epsilon reduces by >=50% over 100 cycles (H12).
"""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np
import pytest

from app.refinement.pwl_tune import (
    AdaptivePWLRefiner,
    PWLCycleRecord,
    _fit_pwl_at_breakpoints,
)


def _exp_decay(x: float) -> float:
    return math.exp(-x)


def _linear(x: float) -> float:
    return 0.3 * x


def test_fit_pwl_returns_lower_bound() -> None:
    bps = [0.0, 0.5, 1.0, 1.5, 2.0]
    approx = _fit_pwl_at_breakpoints(_exp_decay, bps, "test", 101)
    rng = np.random.default_rng(0)
    for _ in range(200):
        x = float(rng.uniform(0.0, 2.0))
        assert approx.evaluate(x) <= _exp_decay(x) + 1e-12


def test_fit_pwl_epsilon_is_max_gap() -> None:
    bps = [0.0, 1.0, 2.0]
    approx = _fit_pwl_at_breakpoints(_exp_decay, bps, "test", 201)
    assert approx.epsilon == pytest.approx(1.0 - math.exp(-1.0), rel=1e-6)


def test_refiner_rejects_non_callable() -> None:
    with pytest.raises(ValueError, match="f must be callable"):
        AdaptivePWLRefiner(42, (0.0, 1.0))  # type: ignore[arg-type]


def test_refiner_rejects_inverted_range() -> None:
    with pytest.raises(ValueError, match="x_range must be increasing"):
        AdaptivePWLRefiner(_exp_decay, (5.0, 0.0))


def test_refiner_rejects_zero_initial_segments() -> None:
    with pytest.raises(ValueError, match="initial_n_segments must be >= 1"):
        AdaptivePWLRefiner(_exp_decay, (0.0, 1.0), initial_n_segments=0)


def test_refiner_rejects_max_below_initial() -> None:
    with pytest.raises(ValueError, match="max_segments"):
        AdaptivePWLRefiner(_exp_decay, (0.0, 1.0), initial_n_segments=16, max_segments=8)


def test_refiner_rejects_bad_samples_per_segment() -> None:
    with pytest.raises(ValueError, match="samples_per_segment must be >= 2"):
        AdaptivePWLRefiner(_exp_decay, (0.0, 1.0), samples_per_segment=1)


def test_run_cycles_rejects_zero() -> None:
    r = AdaptivePWLRefiner(_exp_decay, (0.0, 1.0))
    with pytest.raises(ValueError, match="n_cycles must be >= 1"):
        r.run_cycles(lambda k: [], 0)


def test_observe_ignores_out_of_range() -> None:
    r = AdaptivePWLRefiner(_exp_decay, (0.0, 1.0))
    r.observe(-1.0, 1.0)
    r.observe(2.0, 1.0)
    assert len(r.cycle_history()) == 0
    r.observe(0.5, 0.5)
    rec = r.refine_once()
    assert rec.n_observations == 1


def test_observe_ignores_non_finite() -> None:
    r = AdaptivePWLRefiner(_exp_decay, (0.0, 1.0))
    r.observe(float("nan"), 1.0)
    r.observe(0.5, float("inf"))
    rec = r.refine_once()
    assert rec.n_observations == 0


def test_refine_increases_segment_count() -> None:
    r = AdaptivePWLRefiner(_exp_decay, (0.0, 5.0), initial_n_segments=8)
    assert r.n_segments == 8
    for i in range(1, 6):
        rec = r.refine_once()
        assert rec.n_segments == 8 + i


def test_refine_stops_at_max() -> None:
    r = AdaptivePWLRefiner(_exp_decay, (0.0, 5.0), initial_n_segments=4, max_segments=6)
    r.refine_once()
    r.refine_once()
    assert r.n_segments == 6
    rec = r.refine_once()
    assert rec.n_segments == 6


def test_epsilon_monotonic_nonincreasing() -> None:
    """Splitting raises f_hat everywhere, so epsilon cannot increase."""
    r = AdaptivePWLRefiner(_exp_decay, (0.0, 5.0), initial_n_segments=8, max_segments=32)
    rng = np.random.default_rng(0)

    def source(_: int) -> list[tuple[float, float]]:
        xs = rng.uniform(0.0, 5.0, size=30)
        return [(float(x), _exp_decay(float(x))) for x in xs]

    records = r.run_cycles(source, 40)
    epsilons = [rec.epsilon for rec in records]
    for i in range(1, len(epsilons)):
        assert epsilons[i] <= epsilons[i - 1] + 1e-12, (
            f"epsilon increased at cycle {i}: {epsilons[i - 1]} -> {epsilons[i]}"
        )


def test_approximation_remains_lower_bound_after_refinement() -> None:
    r = AdaptivePWLRefiner(_exp_decay, (0.0, 5.0), initial_n_segments=8, max_segments=32)
    rng = np.random.default_rng(1)

    def source(_: int) -> list[tuple[float, float]]:
        xs = rng.uniform(0.0, 5.0, size=20)
        return [(float(x), _exp_decay(float(x))) for x in xs]

    r.run_cycles(source, 20)
    approx = r.current_approximation()
    for _ in range(300):
        x = rng.uniform(0.0, 5.0)
        assert approx.evaluate(float(x)) <= _exp_decay(float(x)) + 1e-9


def test_h12_epsilon_reduces_by_half_over_100_cycles() -> None:
    """The s6-2 gate, exercised on exp(-x) over [0, 5]."""
    r = AdaptivePWLRefiner(_exp_decay, (0.0, 5.0), initial_n_segments=8, max_segments=64)
    epsilon_0 = r.current_epsilon()
    assert epsilon_0 > 0.0

    rng = np.random.default_rng(20261009)

    def source(_: int) -> list[tuple[float, float]]:
        xs = rng.uniform(0.0, 5.0, size=50)
        return [(float(x), _exp_decay(float(x))) for x in xs]

    records = r.run_cycles(source, 100)
    epsilon_final = records[-1].epsilon
    ratio = epsilon_final / epsilon_0

    print(f"epsilon_0     = {epsilon_0:.6f}")
    print(f"epsilon_final = {epsilon_final:.6f}")
    print(f"ratio         = {ratio:.4f}")
    print(f"n_segments    = {records[-1].n_segments}")
    print("Cycle history (every 25 cycles):")
    for i in range(0, 100, 25):
        rec = records[i]
        print(
            f"  cycle {rec.cycle:3d}: n_seg={rec.n_segments:3d} "
            f"eps={rec.epsilon:.6f} n_obs={rec.n_observations}"
        )

    assert ratio <= 0.5, f"epsilon only reduced to {ratio:.3f} of initial; H12 requires <= 0.5"


def test_h12_linear_function_also_reduces() -> None:
    r = AdaptivePWLRefiner(_linear, (0.0, 5.0), initial_n_segments=8, max_segments=64)
    epsilon_0 = r.current_epsilon()
    rng = np.random.default_rng(42)

    def source(_: int) -> list[tuple[float, float]]:
        xs = rng.uniform(0.0, 5.0, size=50)
        return [(float(x), _linear(float(x))) for x in xs]

    records = r.run_cycles(source, 100)
    epsilon_final = records[-1].epsilon
    assert epsilon_final <= 0.5 * epsilon_0


def test_run_cycles_deterministic_with_seeded_rng() -> None:
    r1 = AdaptivePWLRefiner(_exp_decay, (0.0, 5.0), initial_n_segments=8, max_segments=32)
    r2 = AdaptivePWLRefiner(_exp_decay, (0.0, 5.0), initial_n_segments=8, max_segments=32)

    def make_source(
        seed: int,
    ) -> Callable[[int], list[tuple[float, float]]]:
        rng = np.random.default_rng(seed)

        def source(_: int) -> list[tuple[float, float]]:
            xs = rng.uniform(0.0, 5.0, size=30)
            return [(float(x), _exp_decay(float(x))) for x in xs]

        return source

    recs1 = r1.run_cycles(make_source(7), 30)
    recs2 = r2.run_cycles(make_source(7), 30)
    assert recs1 == recs2


def test_cycle_history_grows_by_n_cycles() -> None:
    r = AdaptivePWLRefiner(_exp_decay, (0.0, 1.0), initial_n_segments=4)
    assert len(r.cycle_history()) == 0
    r.run_cycles(lambda k: [], 3)
    assert len(r.cycle_history()) == 3
    r.run_cycles(lambda k: [], 5)
    assert len(r.cycle_history()) == 8


def test_cycle_record_is_frozen() -> None:
    from dataclasses import FrozenInstanceError

    rec = PWLCycleRecord(cycle=0, n_segments=8, epsilon=0.1, n_observations=0)
    with pytest.raises(FrozenInstanceError):
        rec.epsilon = 0.2  # type: ignore[misc]
