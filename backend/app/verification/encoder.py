"""Encoding of PWL approximations as Z3 assertions.

Roadmap task s3-3: Incremental Linearization encoding to SMT-LIB.
Gate: Z3 returns SAT/UNSAT correctly for known cases.

Reference:
    AeroGrid-XAI Final Comprehensive Specification (Rev. 6),
    Section 34 (Stage B - PWL-SMT Constraint Encoding).

Prior art acknowledgement
-------------------------

The PWL-to-SMT encoding technique used here is an application of
Incremental Linearization (Cimatti et al., ACM TOCL 2018; formalized
in CPP 2026, implemented in MathSAT and cvc5). Incremental
Linearization is a general, published method for SMT over nonlinear
real arithmetic and transcendental functions. Nothing in this module
is novel. The CLEAR-D inventive core is the unsat-core-to-grammar-
feature attribution mechanism in backend/app/discovery/ (Sprint 4),
not the encoding.

Direction of the over-approximation
-----------------------------------

Consistent with backend/app/verification/pwl.py, this module encodes
the lower-bound approximation f_hat <= f. Consequences:

  - For constraints of the form f(x) <= 0, the encoded region
    { x : f_hat(x) <= 0 } is a superset of the true safe set
    { x : f(x) <= 0 }. UNSAT is definitive. SAT may be a false
    positive at x where f_hat(x) <= 0 but f(x) > 0.
  - For constraints of the form f(x) >= 0, the encoded region
    { x : f_hat(x) >= 0 } is a subset of the true region
    { x : f(x) >= 0 }. SAT is definitive. UNSAT may be a false
    negative.

Section 34.2 of the specification claims that a SAT verdict "never
falsely declares an infeasible architecture feasible". That claim
does not follow from f_hat <= f for f(x) <= 0 constraints; see the
pwl.py docstring for the derivation. This module implements the
direction the specification literally writes, reports epsilon per
family so the size of the false-positive region can be bounded, and
records the discrepancy here rather than silently resolving it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

import z3

from app.verification.pwl import (
    ErrorReport,
    ErrorTracker,
    PWLApproximation,
    pwl_approximate,
)

Sense = Literal["le", "ge"]
"""Constraint sense. "le" encodes f_hat(x) <= 0; "ge" encodes f_hat(x) >= 0."""


def _z3_real(value: float) -> z3.ArithRef:
    """Return a Z3 real literal for a Python float.

    Uses repr() so that the exact Python float value is captured; Z3
    parses the decimal string back to a rational that equals the
    original float to machine precision.
    """
    return z3.RealVal(repr(float(value)))


@dataclass(frozen=True)
class ConstraintSpec:
    """A single constraint to encode in a Z3 session.

    Attributes:
        family_name: Constraint-family name; must be unique within a
            session. Used as the tracking variable name in the unsat
            core (Section 34.2 requires per-family epsilon, which
            implies per-family identity in the core).
        approx: The PWL over-approximation of the constraint function.
        sense: "le" encodes approx(x) <= 0; "ge" encodes approx(x) >= 0.
    """

    family_name: str
    approx: PWLApproximation
    sense: Sense = "le"


@dataclass(frozen=True)
class SolverResult:
    """Outcome of a Z3 check.

    Attributes:
        status: "sat", "unsat", or "unknown".
        x_value: The satisfying value of x if SAT, else None.
        epsilon_reports: Per-family epsilon values, required by
            Section 34.2 to accompany every verification result.
        max_epsilon: Largest epsilon across all families; a single
            scope tag on the verdict.
        unsat_core: Family names appearing in the unsat core when
            UNSAT; empty otherwise. Each name is either a user-supplied
            family_name or "domain_<family_name>" when the PWL domain
            bound is the source of infeasibility.
    """

    status: str
    x_value: float | None
    epsilon_reports: tuple[ErrorReport, ...] = field(default_factory=tuple)
    max_epsilon: float = 0.0
    unsat_core: tuple[str, ...] = field(default_factory=tuple)


def pwl_to_z3_expr(x: z3.ArithRef, approx: PWLApproximation) -> z3.ArithRef:
    """Return a Z3 real expression equal to the PWL value of x.

    Uses nested ite over the segments. The Z3 encoding is a direct
    translation of the piecewise-constant function; no linear-
    arithmetic relaxation is applied because Z3 handles nested ites
    on real arithmetic natively. At segment boundaries the lower-index
    segment is selected; this is harmless because both adjacent
    segments are lower bounds at the shared boundary.
    """
    if not approx.segments:
        raise ValueError("Cannot encode a PWL approximation with no segments")

    result: z3.ArithRef = _z3_real(approx.segments[-1].intercept)
    for seg in reversed(approx.segments[:-1]):
        cond = z3.And(x >= _z3_real(seg.x_lo), x <= _z3_real(seg.x_hi))
        result = z3.If(cond, _z3_real(seg.intercept), result)
    return result


class ConstraintSession:
    """A single-variable Z3 session accumulating PWL constraints.

    Exactly one real variable, named "x". Multi-variable support for
    hierarchical decomposition (s3-4) is not yet implemented; each
    session is a scalar subproblem, matching Section 34.3's
    intra-cluster decomposition.

    Usage:

        session = ConstraintSession()
        session.add_constraint(ConstraintSpec("thermal", pwl_thermal, "le"))
        session.add_constraint(ConstraintSpec("efficiency", pwl_eff, "ge"))
        result = session.check()
        # result.status in {"sat", "unsat", "unknown"}
        # result.epsilon_reports carries per-family epsilon (Section 34.2)
    """

    _VAR_NAME = "x"

    def __init__(self) -> None:
        self._solver = z3.Solver()
        self._solver.set(unsat_core=True)
        self._tracker = ErrorTracker()
        self._var: z3.ArithRef = z3.Real(self._VAR_NAME)
        self._added_families: set[str] = set()

    @property
    def variable(self) -> z3.ArithRef:
        return self._var

    @property
    def family_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._added_families))

    def add_constraint(self, spec: ConstraintSpec) -> None:
        """Encode and assert a PWL constraint on the session variable."""
        if spec.family_name in self._added_families:
            raise ValueError(
                f"Family '{spec.family_name}' already added to this session; "
                "each family must carry exactly one epsilon (Section 34.2)."
            )

        x = self._var
        a = spec.approx

        # Domain restriction. The PWL is only valid on [x_min, x_max].
        # Encoded as a tracked assertion so the unsat core names the
        # family if the domain bound is the source of infeasibility.
        domain_name = f"domain_{spec.family_name}"
        domain_var = z3.Bool(domain_name)
        self._solver.assert_and_track(
            z3.And(x >= _z3_real(a.x_min), x <= _z3_real(a.x_max)),
            domain_var,
        )

        # The PWL constraint itself.
        expr = pwl_to_z3_expr(x, a)
        assertion = expr <= _z3_real(0.0) if spec.sense == "le" else expr >= _z3_real(0.0)
        constraint_var = z3.Bool(spec.family_name)
        self._solver.assert_and_track(assertion, constraint_var)

        self._tracker.add(a)
        self._added_families.add(spec.family_name)

    def check(self) -> SolverResult:
        """Run the solver and return a structured result."""
        status = self._solver.check()
        reports = self._tracker.reports()
        max_eps = self._tracker.max_epsilon()

        if status == z3.sat:
            model = self._solver.model()
            x_val = model.eval(self._var, model_completion=True)
            x_float = float(x_val.as_fraction())
            return SolverResult(
                status="sat",
                x_value=x_float,
                epsilon_reports=reports,
                max_epsilon=max_eps,
                unsat_core=(),
            )

        if status == z3.unsat:
            core = self._solver.unsat_core()
            core_names = tuple(sorted(str(c) for c in core))
            return SolverResult(
                status="unsat",
                x_value=None,
                epsilon_reports=reports,
                max_epsilon=max_eps,
                unsat_core=core_names,
            )

        return SolverResult(
            status="unknown",
            x_value=None,
            epsilon_reports=reports,
            max_epsilon=max_eps,
            unsat_core=(),
        )


def build_constraint_spec(
    family_name: str,
    f: Callable[[float], float],
    x_range: tuple[float, float],
    n_segments: int,
    *,
    sense: Sense = "le",
    epsilon_target: float | None = None,
    max_segment_doublings: int = 10,
) -> ConstraintSpec:
    """Build a ConstraintSpec by PWL-approximating a physics function.

    If epsilon_target is given and the initial approximation exceeds
    it, the segment count is doubled until the target is met or the
    doubling budget is exhausted. Raises RuntimeError if the target
    cannot be met.
    """
    n = n_segments
    approx = pwl_approximate(f, x_range, n, family_name)
    if epsilon_target is None:
        return ConstraintSpec(family_name=family_name, approx=approx, sense=sense)

    for _ in range(max_segment_doublings):
        if approx.epsilon <= epsilon_target:
            return ConstraintSpec(family_name=family_name, approx=approx, sense=sense)
        n *= 2
        approx = pwl_approximate(f, x_range, n, family_name)

    if approx.epsilon <= epsilon_target:
        return ConstraintSpec(family_name=family_name, approx=approx, sense=sense)

    raise RuntimeError(
        f"Could not achieve epsilon <= {epsilon_target} for family "
        f"'{family_name}' after {max_segment_doublings} doublings "
        f"(final n = {n}, final epsilon = {approx.epsilon})"
    )
