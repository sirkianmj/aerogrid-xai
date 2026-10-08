"""Piecewise-linear over-approximation of physics constraint functions.

Roadmap task s3-1: PWL approximation builder.
Roadmap task s3-2: Error tracker (epsilon per constraint family).

Reference:
    AeroGrid-XAI Final Comprehensive Specification (Rev. 6),
    Section 34 (Stage B - PWL-SMT Constraint Encoding).

Direction of the approximation
------------------------------

Section 34.2 writes the approximation as f_hat(x) <= f(x) and calls it
a "sound over-approximation" of the feasible set { x : f(x) <= 0 }.
Those two statements are consistent with each other: from f_hat <= f
it follows that

    { x : f(x) <= 0 }  is contained in  { x : f_hat(x) <= 0 },

so the encoded feasible region is a superset of the true feasible
region. The consequences are:

  - UNSAT is definitive. An empty encoded region implies an empty
    true region.
  - SAT is necessary but not sufficient for true feasibility. It may
    be a false positive at points where f_hat <= 0 but f > 0.

Section 34.2 additionally claims that a SAT verdict "never falsely
declares an infeasible architecture feasible". Under the direction
f_hat <= f that claim does not hold, as shown above. This module
implements the direction the specification literally writes and
reports the numeric epsilon per constraint family so that the reader
can judge how large the false-positive region can be in practice.
The discrepancy is documented here rather than silently resolved.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

SAMPLES_PER_SEGMENT = 101
"""Dense sample count per segment used to build the constant lower
bound. With this density the sampled minimum is exact for monotonic f
and approximates the true minimum for smooth non-monotonic f."""


@dataclass(frozen=True)
class PWLSegment:
    """One constant-valued piece of a PWL over-approximation.

    Written as a general linear segment f_hat(x) = slope * x + intercept
    for encoding convenience. This builder always produces constant
    segments (slope = 0) whose value is the sampled minimum of the
    underlying function on [x_lo, x_hi].
    """

    x_lo: float
    x_hi: float
    slope: float
    intercept: float

    def evaluate(self, x: float) -> float:
        return self.slope * x + self.intercept


@dataclass(frozen=True)
class PWLApproximation:
    """A piecewise-constant over-approximation of a scalar function.

    The approximation satisfies f_hat(x) <= f(x) on the covered domain,
    which makes { x : f_hat(x) <= 0 } a superset of { x : f(x) <= 0 }
    (see the module docstring).

    Attributes:
        family_name: Human-readable constraint-family name, used for
            per-family epsilon reporting (Section 34.2).
        segments: The linear pieces in ascending x order.
        epsilon: max |f(x) - f_hat(x)| over the domain, by dense
            sampling.
        x_min, x_max: The covered domain.
    """

    family_name: str
    segments: tuple[PWLSegment, ...]
    epsilon: float
    x_min: float
    x_max: float

    def evaluate(self, x: float) -> float:
        if x != x:
            raise ValueError("x must be a real number; got NaN")
        if x < self.x_min or x > self.x_max:
            raise ValueError(f"x = {x} outside PWL domain [{self.x_min}, {self.x_max}]")
        for seg in self.segments:
            if seg.x_lo <= x <= seg.x_hi:
                return seg.evaluate(x)
        raise RuntimeError(f"No segment covers x = {x}; this is a bug in the PWL builder.")

    def is_lower_bound_at(self, x: float, f: Callable[[float], float]) -> bool:
        return self.evaluate(x) <= f(x) + 1e-12


def pwl_approximate(
    f: Callable[[float], float],
    x_range: tuple[float, float],
    n_segments: int,
    family_name: str,
    *,
    n_validation_samples: int = 2001,
) -> PWLApproximation:
    """Build a sound piecewise-constant over-approximation of f.

    Each segment [x_i, x_{i+1}] is replaced by the constant value
    min over the sampled points, which is <= f on the segment (exact
    for monotonic f, approximate otherwise). The resulting feasible
    set { x : f_hat(x) <= 0 } is a superset of { x : f(x) <= 0 }.

    Args:
        f: Scalar function of one real variable.
        x_range: (x_min, x_max) with x_min < x_max.
        n_segments: Number of equal-width segments. Must be >= 1.
        family_name: Constraint-family name, used for the epsilon
            report required by Section 34.2.
        n_validation_samples: Dense sample count used to compute the
            reported epsilon.
    """
    x_min, x_max = x_range
    if not x_min < x_max:
        raise ValueError(f"x_range must be strictly increasing; got {x_range}")
    if n_segments < 1:
        raise ValueError(f"n_segments must be >= 1; got {n_segments}")
    if n_validation_samples < 2:
        raise ValueError(f"n_validation_samples must be >= 2; got {n_validation_samples}")

    edges = np.linspace(x_min, x_max, n_segments + 1)
    segments: list[PWLSegment] = []

    for i in range(n_segments):
        x_lo = float(edges[i])
        x_hi = float(edges[i + 1])
        samples = np.linspace(x_lo, x_hi, SAMPLES_PER_SEGMENT)
        f_min = min(f(float(s)) for s in samples)
        segments.append(PWLSegment(x_lo=x_lo, x_hi=x_hi, slope=0.0, intercept=f_min))

    provisional = PWLApproximation(
        family_name=family_name,
        segments=tuple(segments),
        epsilon=0.0,
        x_min=x_min,
        x_max=x_max,
    )

    dense_x = np.linspace(x_min, x_max, n_validation_samples)
    epsilon = 0.0
    for x in dense_x:
        err = abs(f(float(x)) - provisional.evaluate(float(x)))
        if err > epsilon:
            epsilon = err

    return PWLApproximation(
        family_name=family_name,
        segments=tuple(segments),
        epsilon=epsilon,
        x_min=x_min,
        x_max=x_max,
    )


def verify_lower_bound(
    approx: PWLApproximation,
    f: Callable[[float], float],
    n_samples: int = 2001,
    *,
    tolerance: float = 1e-9,
) -> None:
    """Assert that approx.evaluate(x) <= f(x) + tolerance on a dense grid.

    Raises AssertionError if the lower-bound property is violated.
    """
    xs = np.linspace(approx.x_min, approx.x_max, n_samples)
    for x in xs:
        gap = approx.evaluate(float(x)) - f(float(x))
        if gap > tolerance:
            raise AssertionError(
                f"PWL soundness violation at x = {x}: "
                f"f_hat = {approx.evaluate(float(x))}, "
                f"f = {f(float(x))}, gap = {gap}"
            )


@dataclass(frozen=True)
class ErrorReport:
    """Per-family epsilon report required by Section 34.2."""

    family_name: str
    epsilon: float

    def __str__(self) -> str:
        return f"{self.family_name}: epsilon = {self.epsilon:.6g}"


class ErrorTracker:
    """Accumulates per-family epsilon values for a SAT/UNSAT result.

    Section 34.2 requires every constraint family to carry its own
    epsilon, and every verification result to report all of them.
    This class is the collection point.
    """

    def __init__(self) -> None:
        self._reports: dict[str, ErrorReport] = {}

    def add(self, approx: PWLApproximation) -> None:
        if approx.family_name in self._reports:
            raise ValueError(
                f"Family '{approx.family_name}' is already tracked; each "
                "constraint family must carry exactly one epsilon."
            )
        self._reports[approx.family_name] = ErrorReport(
            family_name=approx.family_name,
            epsilon=approx.epsilon,
        )

    def reports(self) -> tuple[ErrorReport, ...]:
        return tuple(self._reports.values())

    def max_epsilon(self) -> float:
        if not self._reports:
            return 0.0
        return max(r.epsilon for r in self._reports.values())

    def summary(self) -> str:
        if not self._reports:
            return "(no constraint families tracked)"
        lines = [str(r) for r in self._reports.values()]
        lines.append(f"max epsilon = {self.max_epsilon():.6g}")
        return chr(10).join(lines)
