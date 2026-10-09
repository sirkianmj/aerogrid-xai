"""UNSAT-core extraction and minimality verification.

Roadmap task s4-3: UNSAT-core extraction (z3.get_unsat_core()).
Gate: Core is minimal - all proper subsets are SAT.

Reference:
    AeroGrid-XAI Final Comprehensive Specification (Rev. 6),
    Section 35.3 ("The unsat core is a minimal set of constraints
    that are jointly infeasible") and Section 35.4 (Discovery Loop,
    "core = Z3.get_unsat_core()").

What this module provides
-------------------------

A named-constraint wrapper around z3.Solver that:

  1. Accepts Boolean Z3 expressions, each carrying a family name.
  2. Solves the conjunction of the tracked constraints.
  3. On UNSAT, extracts the Z3 unsat core (the subset of the
     tracked names that Z3 identifies as sufficient for
     unsatisfiability).
  4. Provides two independent minimality verifications:
     - verify_core_minimality_removal: the operational definition.
       Remove each single clause from the core and check that the
       remainder is SAT. Equivalent to "no proper subset is UNSAT".
     - verify_core_minimality_exhaustive: for small cores, enumerate
       every proper subset and check that every one is SAT. Directly
       verifies the roadmap's literal wording. Capped at 2^8 = 256
       subsets by default.

Why two checks
--------------

The operational definition of minimality is "no proper subset is
UNSAT". The two verifications are equivalent in exact arithmetic:
if any proper subset were UNSAT, repeatedly removing clauses would
eventually yield a singleton removal that kept the remainder UNSAT.
So the singleton check is sufficient and necessary.

The exhaustive check is offered because it directly verifies the
roadmap's wording for small cores and serves as a cross-check on
the singleton implementation.

Scope
-----

This module operates on arbitrary Boolean Z3 expressions. It does
not know about architectures, grammars, or Stage B constraints.
Bridging an architecture to a set of named constraints is the job
of s4-4 (unsat-core-to-grammar-feature attribution).

Determinism
-----------

The core is returned as a sorted tuple of family names. Z3's
unsat_core is itself a set, so without sorting, order would be
implementation-defined. Sorting makes the result reproducible
across runs, which the s4-8 gate ("same UNSAT core -> same bias,
twice") depends on.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import z3

MAX_EXHAUSTIVE_CORE_SIZE = 8
"""Exhaustive verification enumerates 2^n - 1 subsets. At n = 8 that is
255 SMT calls, which is tractable. Above n = 8 the caller should use
the singleton-removal check instead."""


@dataclass(frozen=True)
class NamedConstraint:
    """A Boolean Z3 expression with a family name.

    Attributes:
        family_name: Unique identifier for this constraint, used as
            the tracking literal in the Z3 unsat core and as the key
            that s4-4 will map back to a grammar feature.
        expression: A Z3 Boolean expression.
    """

    family_name: str
    expression: z3.BoolRef

    def __post_init__(self) -> None:
        if not self.family_name:
            raise ValueError("family_name must be non-empty")
        if not z3.is_bool(self.expression):
            raise ValueError(
                f"expression for {self.family_name} must be Boolean; "
                f"got sort {self.expression.sort()}"
            )


@dataclass(frozen=True)
class CoreResult:
    """Result of an unsat-core extraction.

    Attributes:
        status: "sat", "unsat", or "unknown".
        core_names: Sorted tuple of family names in the unsat core.
            Empty if status is not "unsat".
        all_family_names: Sorted tuple of every constraint added to
            the extractor, in the order they appear in the solver.
            Useful for callers that want to check the core is a
            strict subset of the full system.
    """

    status: str
    core_names: tuple[str, ...] = field(default_factory=tuple)
    all_family_names: tuple[str, ...] = field(default_factory=tuple)

    @property
    def core_size(self) -> int:
        return len(self.core_names)


class UnsatCoreExtractor:
    """Named-constraint Z3 solver with unsat-core extraction.

    Usage:

        ext = UnsatCoreExtractor()
        ext.add(NamedConstraint("a", x >= 10))
        ext.add(NamedConstraint("b", x <= 5))
        result = ext.check()
        # result.status == "unsat"
        # result.core_names == ("a", "b")

    Raises on duplicate family names. Every constraint is asserted
    with its family name as a tracking literal, so Z3's unsat_core
    returns names rather than indices.
    """

    def __init__(self) -> None:
        self._solver = z3.Solver()
        self._solver.set(unsat_core=True)
        self._constraints: list[NamedConstraint] = []
        self._seen: set[str] = set()

    @property
    def constraints(self) -> tuple[NamedConstraint, ...]:
        return tuple(self._constraints)

    @property
    def family_names(self) -> tuple[str, ...]:
        return tuple(c.family_name for c in self._constraints)

    def add(self, constraint: NamedConstraint) -> None:
        """Add a named constraint and track it for core extraction."""
        if constraint.family_name in self._seen:
            raise ValueError(
                f"Constraint family '{constraint.family_name}' already "
                "added; each family must be unique within an extractor"
            )
        self._solver.assert_and_track(constraint.expression, z3.Bool(constraint.family_name))
        self._constraints.append(constraint)
        self._seen.add(constraint.family_name)

    def check(self) -> CoreResult:
        """Solve the conjunction and return the status and (if UNSAT)
        the core as a sorted tuple of family names."""
        status = self._solver.check()
        if status == z3.sat:
            return CoreResult(
                status="sat",
                core_names=(),
                all_family_names=tuple(sorted(self._seen)),
            )
        if status == z3.unsat:
            core = self._solver.unsat_core()
            names = tuple(sorted(str(c) for c in core))
            return CoreResult(
                status="unsat",
                core_names=names,
                all_family_names=tuple(sorted(self._seen)),
            )
        return CoreResult(
            status="unknown",
            core_names=(),
            all_family_names=tuple(sorted(self._seen)),
        )


def verify_core_minimality_removal(
    constraints: tuple[NamedConstraint, ...],
    core_names: tuple[str, ...],
) -> bool:
    """Verify the operational definition of core minimality.

    A core is minimal iff, for every constraint c in the core,
    removing c from the core leaves a satisfiable system. This is
    equivalent to "no proper subset of the core is UNSAT".

    Args:
        constraints: The full constraint set (superset of the core).
        core_names: The family names of the core to verify.

    Returns:
        True if the core is minimal.

    Raises:
        ValueError if core_names contains a name that is not in
        constraints, or if the core itself is not UNSAT.
    """
    family_map = {c.family_name: c for c in constraints}
    missing = [n for n in core_names if n not in family_map]
    if missing:
        raise ValueError(f"Core contains names not present in constraints: {missing}")
    core_constraints = tuple(family_map[n] for n in core_names)

    # Sanity check: the full core must be UNSAT.
    solver = z3.Solver()
    for c in core_constraints:
        solver.add(c.expression)
    if solver.check() != z3.unsat:
        raise ValueError(
            "verify_core_minimality_removal called on a core that is "
            "not UNSAT; the check would be meaningless"
        )

    # For each constraint, removing it must yield SAT.
    for removed in core_constraints:
        reduced = z3.Solver()
        for c in core_constraints:
            if c.family_name == removed.family_name:
                continue
            reduced.add(c.expression)
        if reduced.check() != z3.sat:
            return False
    return True


def verify_core_minimality_exhaustive(
    constraints: tuple[NamedConstraint, ...],
    core_names: tuple[str, ...],
    *,
    max_core_size: int = MAX_EXHAUSTIVE_CORE_SIZE,
) -> bool:
    """Verify the roadmap's literal wording for small cores.

    Enumerate every proper non-empty subset of the core and check
    that each is satisfiable. This directly verifies "all proper
    subsets are SAT".

    Args:
        constraints: The full constraint set (superset of the core).
        core_names: The family names of the core to verify.
        max_core_size: Cap on the core size for which exhaustive
            enumeration is run. Default 8 (2^8 - 1 = 255 subsets).

    Returns:
        True if every proper non-empty subset of the core is SAT.

    Raises:
        ValueError if the core is larger than max_core_size, if any
        core name is missing from constraints, or if the core itself
        is not UNSAT.
    """
    if len(core_names) > max_core_size:
        raise ValueError(
            f"Core size {len(core_names)} exceeds max_core_size "
            f"{max_core_size}; use verify_core_minimality_removal instead"
        )
    family_map = {c.family_name: c for c in constraints}
    missing = [n for n in core_names if n not in family_map]
    if missing:
        raise ValueError(f"Core contains names not present in constraints: {missing}")
    core_constraints = tuple(family_map[n] for n in core_names)

    # The full core must be UNSAT.
    full_solver = z3.Solver()
    for c in core_constraints:
        full_solver.add(c.expression)
    if full_solver.check() != z3.unsat:
        raise ValueError(
            "verify_core_minimality_exhaustive called on a core that "
            "is not UNSAT; the check would be meaningless"
        )

    n = len(core_constraints)
    for k in range(1, n):
        for subset in itertools.combinations(core_constraints, k):
            subset_solver = z3.Solver()
            for c in subset:
                subset_solver.add(c.expression)
            if subset_solver.check() != z3.sat:
                return False
    return True
