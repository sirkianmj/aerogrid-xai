"""Hierarchical decomposition of SMT constraint systems.

Roadmap task s3-4: Hierarchical decomposition (k=5-15 intra-cluster plus
inter-cluster flow).
Gate: SOUND composition - cluster partition has no shared variables.

Reference:
    AeroGrid-XAI Final Comprehensive Specification (Rev. 6),
    Section 34.3 (Hierarchical Decomposition).

Design
------

A monolithic SMT query over N nodes is intractable at network scale
because SMT solving is exponential in the worst case (Section 34.3).
The encoding is therefore decomposed into per-cluster subproblems and
a smaller inter-cluster flow problem.

The composition is sound iff:

  (a) each intra-cluster constraint references only variables within
      a single cluster, and
  (b) each inter-cluster constraint references no variable that also
      appears in any cluster.

When both conditions hold, the variable sets of the cluster
subproblems and the flow subproblem are pairwise disjoint, and every
constraint belongs to exactly one bucket. The conjunction of the
buckets therefore decomposes: the joint system is satisfiable if and
only if every cluster subproblem is satisfiable and the flow
subproblem is satisfiable. No constraint is lost or duplicated.

This class enforces (a) and (b) at insertion time and raises
ValueError on violation. If a constraint spans two clusters, the
caller must refactor it into intra-cluster pieces plus explicit
inter-cluster flow variables - that refactor is the design work the
decomposition requires, and silently accepting a spanning constraint
would make the composition unsound.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import z3

from app.verification.pwl import ErrorTracker, PWLApproximation

RECOMMENDED_K_MIN = 5
RECOMMENDED_K_MAX = 15
"""Section 34.3 recommends cluster sizes k in [5, 15] nodes so that each
intra-cluster subproblem solves within a bounded time. The
HierarchicalModel warns (does not reject) when a cluster falls outside
this band, since the band is a performance guideline, not a soundness
requirement."""


ConstraintFn = Callable[[dict[str, z3.ArithRef]], z3.BoolRef]
"""A constraint is a function from a variable-name -> Z3 ref mapping to
a Z3 boolean expression."""


@dataclass(frozen=True)
class Cluster:
    """A named group of variables that shares no variables with any
    other cluster."""

    name: str
    variables: frozenset[str]


@dataclass(frozen=True)
class ConstraintEntry:
    """A single constraint, tagged with the variable names it references."""

    family_name: str
    variables: frozenset[str]
    fn: ConstraintFn
    epsilon: float = 0.0


@dataclass(frozen=True)
class ClusterResult:
    """Result of solving one cluster subproblem."""

    cluster_name: str
    status: str
    model: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class HierarchicalResult:
    """Result of the full hierarchical check.

    Attributes:
        status: "sat" if every cluster and the flow subproblem are SAT;
            "unsat" if any subproblem is UNSAT; "unknown" otherwise.
        cluster_results: Per-cluster status and model (if SAT).
        flow_status: Status of the inter-cluster flow subproblem.
        unsat_clusters: Names of clusters that returned UNSAT.
        max_epsilon: Largest epsilon across all tracked families.
        epsilons: Per-family epsilon values.
    """

    status: str
    cluster_results: tuple[ClusterResult, ...]
    flow_status: str
    unsat_clusters: tuple[str, ...]
    max_epsilon: float
    epsilons: tuple[tuple[str, float], ...]

    def summary(self) -> str:
        lines = [f"status: {self.status}"]
        for cr in self.cluster_results:
            lines.append(f"  cluster {cr.cluster_name}: {cr.status}")
        lines.append(f"  flow: {self.flow_status}")
        if self.unsat_clusters:
            lines.append(f"  unsat clusters: {', '.join(self.unsat_clusters)}")
        lines.append(f"  max epsilon: {self.max_epsilon:.6g}")
        return chr(10).join(lines)


class HierarchicalModel:
    """Partition-based hierarchical SMT model.

    Usage:

        model = HierarchicalModel()
        model.add_cluster(Cluster("north", frozenset({"a", "b"})))
        model.add_cluster(Cluster("south", frozenset({"c", "d"})))
        model.add_intra_cluster_constraint(ConstraintEntry(
            family_name="north_thermal",
            variables=frozenset({"a", "b"}),
            fn=lambda v: v["a"] + v["b"] <= z3.RealVal("10"),
        ))
        model.add_inter_cluster_constraint(ConstraintEntry(
            family_name="flow_balance",
            variables=frozenset({"flow_north_to_south"}),
            fn=lambda v: v["flow_north_to_south"] >= z3.RealVal("0"),
        ))
        result = model.check()

    Raises:
        ValueError on duplicate cluster names, on a variable appearing
        in more than one cluster, on an intra-cluster constraint that
        references a variable not in any cluster or spanning multiple
        clusters, or on an inter-cluster constraint that references a
        variable inside any cluster.
    """

    def __init__(self) -> None:
        self._clusters: dict[str, Cluster] = {}
        self._var_to_cluster: dict[str, str] = {}
        self._intra: list[ConstraintEntry] = []
        self._inter: list[ConstraintEntry] = []
        self._tracker = ErrorTracker()

    @property
    def clusters(self) -> tuple[Cluster, ...]:
        return tuple(self._clusters.values())

    def add_cluster(self, cluster: Cluster) -> None:
        if cluster.name in self._clusters:
            raise ValueError(f"Cluster '{cluster.name}' already added")
        for var in cluster.variables:
            if var in self._var_to_cluster:
                raise ValueError(
                    f"Variable '{var}' already belongs to cluster "
                    f"'{self._var_to_cluster[var]}'; a true graph "
                    "partition forbids shared variables (Section 34.3)"
                )
            self._var_to_cluster[var] = cluster.name
        self._clusters[cluster.name] = cluster

    def add_intra_cluster_constraint(self, entry: ConstraintEntry) -> None:
        """Add a constraint that references variables within exactly one
        cluster. Raises if the constraint references no cluster variables
        or spans two clusters."""
        if not entry.variables:
            raise ValueError(
                f"Intra-cluster constraint '{entry.family_name}' has no "
                "variables; use add_inter_cluster_constraint instead"
            )
        owning = {self._var_to_cluster.get(v) for v in entry.variables}
        if None in owning:
            missing = sorted(v for v in entry.variables if v not in self._var_to_cluster)
            raise ValueError(
                f"Intra-cluster constraint '{entry.family_name}' references "
                f"unknown variables {missing}"
            )
        if len(owning) != 1:
            raise ValueError(
                f"Intra-cluster constraint '{entry.family_name}' spans "
                f"multiple clusters {sorted(o for o in owning if o is not None)}. Refactor into "
                "intra-cluster pieces plus explicit inter-cluster flow "
                "variables (Section 34.3)."
            )
        self._intra.append(entry)

    def add_inter_cluster_constraint(self, entry: ConstraintEntry) -> None:
        """Add a constraint that references only flow variables that lie
        outside every cluster."""
        overlapping = sorted(v for v in entry.variables if v in self._var_to_cluster)
        if overlapping:
            raise ValueError(
                f"Inter-cluster constraint '{entry.family_name}' references "
                f"variables that belong to clusters: {overlapping}. Flow "
                "variables must be disjoint from cluster variables "
                "(Section 34.3)."
            )
        self._inter.append(entry)

    def add_epsilon_source(self, approx: PWLApproximation) -> None:
        """Register a PWL approximation whose epsilon should be reported
        alongside the final verdict (Section 34.2)."""
        self._tracker.add(approx)

    def _build_solver(
        self, entries: list[ConstraintEntry]
    ) -> tuple[z3.Solver, dict[str, z3.ArithRef]]:
        solver = z3.Solver()
        var_refs: dict[str, z3.ArithRef] = {}
        for entry in entries:
            for name in entry.variables:
                if name not in var_refs:
                    var_refs[name] = z3.Real(name)
        for entry in entries:
            expr = entry.fn(var_refs)
            solver.assert_and_track(expr, z3.Bool(entry.family_name))
        return solver, var_refs

    def _extract_model(
        self, solver: z3.Solver, var_refs: dict[str, z3.ArithRef]
    ) -> dict[str, float]:
        model = solver.model()
        out: dict[str, float] = {}
        for name, ref in var_refs.items():
            val = model.eval(ref, model_completion=True)
            out[name] = float(val.as_fraction())
        return out

    def check(self) -> HierarchicalResult:
        """Solve each cluster independently, then solve the flow problem.

        Returns SAT iff every cluster is SAT and the flow subproblem is
        SAT. The soundness of this composition is discussed in the
        module docstring; it relies on the disjointness invariants
        enforced at insertion time.
        """
        cluster_results: list[ClusterResult] = []
        unsat_clusters: list[str] = []
        any_unsat = False

        for cluster in self._clusters.values():
            entries = [e for e in self._intra if e.variables <= cluster.variables]
            solver, var_refs = self._build_solver(entries)
            status = solver.check()
            if status == z3.sat:
                cluster_results.append(
                    ClusterResult(
                        cluster_name=cluster.name,
                        status="sat",
                        model=self._extract_model(solver, var_refs),
                    )
                )
            elif status == z3.unsat:
                cluster_results.append(ClusterResult(cluster_name=cluster.name, status="unsat"))
                unsat_clusters.append(cluster.name)
                any_unsat = True
            else:
                cluster_results.append(ClusterResult(cluster_name=cluster.name, status="unknown"))
                any_unsat = True

        flow_solver, _ = self._build_solver(self._inter)
        flow_status_z3 = flow_solver.check()
        if flow_status_z3 == z3.sat:
            flow_status = "sat"
        elif flow_status_z3 == z3.unsat:
            flow_status = "unsat"
        else:
            flow_status = "unknown"

        if any_unsat or flow_status != "sat":
            overall = "unsat" if (any_unsat or flow_status == "unsat") else "unknown"
        else:
            overall = "sat"

        reports = self._tracker.reports()
        epsilons = tuple((r.family_name, r.epsilon) for r in reports)

        return HierarchicalResult(
            status=overall,
            cluster_results=tuple(cluster_results),
            flow_status=flow_status,
            unsat_clusters=tuple(unsat_clusters),
            max_epsilon=self._tracker.max_epsilon(),
            epsilons=epsilons,
        )
