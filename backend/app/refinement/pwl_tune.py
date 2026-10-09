"""Adaptive PWL refinement from operational observations.

Roadmap task s6-2: PWL tightening/relaxing based on SAT/UNSAT vs
observed.
Gate: epsilon reduces by >=50% over 100 cycles (H12).

Reference:
    AeroGrid-XAI Final Comprehensive Specification (Rev. 6),
    Section 37.2 (Encoding Tightening). If operational data shows
    that the PWL over-approximation was too conservative, the
    breakpoints are refined to reduce epsilon.

Mechanism
---------

The refiner holds a piecewise-constant over-approximation f_hat of a
scalar function f on [x_min, x_max]. As observations (x_i, y_i)
arrive, it splits the segment with the largest observed residual at
the midpoint. Because splitting a segment raises the new subsegments'
minima at least to the old segment's minimum, f_hat(x) is monotonic
non-decreasing at every refinement step, hence epsilon = max(f - f_hat)
is monotonic non-increasing.

A maximum segment count bounds the refinement. Once reached, the
refiner stops splitting but continues to accept observations and
records the same epsilon in subsequent cycles.

Direction
---------

Only tightening is implemented. In the current encoding direction
(Section 34.2, f_hat <= f), f_hat is always below f, so the only
meaningful operation is to raise f_hat. Relaxing would be needed only
if the encoding direction were flipped to f_hat >= f, which the spec
does not require.
"""

from __future__ import annotations

import bisect
import math
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

import numpy as np

from app.verification.pwl import PWLApproximation, PWLSegment

DEFAULT_SAMPLES_PER_SEGMENT = 101


@dataclass(frozen=True)
class PWLCycleRecord:
    """Summary of one refinement cycle.

    Attributes:
        cycle: Zero-based cycle index.
        n_segments: Number of PWL segments after the cycle.
        epsilon: Maximum approximation error over the fitting grid
            after the cycle.
        n_observations: Cumulative observations received up to and
            including this cycle.
    """

    cycle: int
    n_segments: int
    epsilon: float
    n_observations: int


def _fit_pwl_at_breakpoints(
    f: Callable[[float], float],
    breakpoints: Sequence[float],
    family_name: str,
    samples_per_segment: int,
) -> PWLApproximation:
    """Fit a piecewise-constant over-approximation at given breakpoints.

    Each segment is assigned the minimum sampled value of f over that
    segment, so f_hat(x) <= f(x) everywhere on [breakpoints[0],
    breakpoints[-1]].
    """
    segments: list[PWLSegment] = []
    epsilon = 0.0
    for i in range(len(breakpoints) - 1):
        a = float(breakpoints[i])
        b = float(breakpoints[i + 1])
        xs = np.linspace(a, b, samples_per_segment)
        ys = np.array([f(float(x)) for x in xs], dtype=float)
        v = float(np.min(ys))
        segments.append(PWLSegment(x_lo=a, x_hi=b, slope=0.0, intercept=v))
        gap = float(np.max(ys) - v)
        if gap > epsilon:
            epsilon = gap
    return PWLApproximation(
        family_name=family_name,
        segments=tuple(segments),
        epsilon=epsilon,
        x_min=float(breakpoints[0]),
        x_max=float(breakpoints[-1]),
    )


class AdaptivePWLRefiner:
    """Maintain and refine a PWL over-approximation from observations."""

    def __init__(
        self,
        f: Callable[[float], float],
        x_range: tuple[float, float],
        *,
        initial_n_segments: int = 8,
        max_segments: int = 64,
        samples_per_segment: int = DEFAULT_SAMPLES_PER_SEGMENT,
    ) -> None:
        if not callable(f):
            raise ValueError("f must be callable")
        x_min = float(x_range[0])
        x_max = float(x_range[1])
        if not (math.isfinite(x_min) and math.isfinite(x_max)):
            raise ValueError("x_range endpoints must be finite")
        if x_min >= x_max:
            raise ValueError(f"x_range must be increasing; got {x_range}")
        if initial_n_segments < 1:
            raise ValueError(f"initial_n_segments must be >= 1; got {initial_n_segments}")
        if max_segments < initial_n_segments:
            raise ValueError(
                f"max_segments ({max_segments}) must be >= "
                f"initial_n_segments ({initial_n_segments})"
            )
        if samples_per_segment < 2:
            raise ValueError(f"samples_per_segment must be >= 2; got {samples_per_segment}")

        self._f = f
        self._x_min = x_min
        self._x_max = x_max
        self._max_segments = max_segments
        self._samples_per_segment = samples_per_segment

        self._breakpoints: list[float] = list(np.linspace(x_min, x_max, initial_n_segments + 1))
        self._observations: list[tuple[float, float]] = []
        self._current = _fit_pwl_at_breakpoints(
            f, self._breakpoints, "adaptive", samples_per_segment
        )
        self._history: list[PWLCycleRecord] = []

    @property
    def n_segments(self) -> int:
        return len(self._breakpoints) - 1

    @property
    def breakpoints(self) -> tuple[float, ...]:
        return tuple(self._breakpoints)

    def current_approximation(self) -> PWLApproximation:
        return self._current

    def current_epsilon(self) -> float:
        return self._current.epsilon

    def cycle_history(self) -> tuple[PWLCycleRecord, ...]:
        return tuple(self._history)

    def observe(self, x: float, y: float) -> None:
        """Record one operational observation.

        Points outside [x_min, x_max] are ignored; the PWL is only
        defined on the operating range.
        """
        if not (math.isfinite(x) and math.isfinite(y)):
            return
        if x < self._x_min or x > self._x_max:
            return
        self._observations.append((float(x), float(y)))

    def observe_batch(self, observations: Iterable[tuple[float, float]]) -> None:
        for x, y in observations:
            self.observe(x, y)

    def _segment_index_for_x(self, x: float) -> int | None:
        idx = bisect.bisect_right(self._breakpoints, x) - 1
        if idx < 0 or idx >= self.n_segments:
            return None
        return idx

    def refine_once(self) -> PWLCycleRecord:
        """Split the highest-residual segment and re-fit.

        If the segment count is already at max_segments, no split is
        performed and the record reflects the unchanged state.
        """
        if self.n_segments < self._max_segments:
            seg_errors = [0.0] * self.n_segments
            for x, y in self._observations:
                idx = self._segment_index_for_x(x)
                if idx is None:
                    continue
                f_hat = self._current.evaluate(x)
                resid = abs(y - f_hat)
                if resid > seg_errors[idx]:
                    seg_errors[idx] = resid

            worst = max(range(self.n_segments), key=lambda i: seg_errors[i])
            a = self._breakpoints[worst]
            b = self._breakpoints[worst + 1]
            mid = 0.5 * (a + b)
            self._breakpoints.insert(worst + 1, mid)
            self._current = _fit_pwl_at_breakpoints(
                self._f,
                self._breakpoints,
                "adaptive",
                self._samples_per_segment,
            )

        record = PWLCycleRecord(
            cycle=len(self._history),
            n_segments=self.n_segments,
            epsilon=self._current.epsilon,
            n_observations=len(self._observations),
        )
        self._history.append(record)
        return record

    def run_cycles(
        self,
        observation_source: Callable[[int], Iterable[tuple[float, float]]],
        n_cycles: int,
    ) -> tuple[PWLCycleRecord, ...]:
        """Run n_cycles of: receive observations, refine once, record.

        Args:
            observation_source: Called with the cycle index (0-based),
                returns an iterable of (x, y) observations.
            n_cycles: Number of cycles to run. Must be >= 1.

        Returns:
            Tuple of PWLCycleRecord, one per cycle.
        """
        if n_cycles < 1:
            raise ValueError(f"n_cycles must be >= 1; got {n_cycles}")
        start_len = len(self._history)
        for k in range(n_cycles):
            cycle_index = start_len + k
            self.observe_batch(observation_source(cycle_index))
            self.refine_once()
        return tuple(self._history[start_len:])
