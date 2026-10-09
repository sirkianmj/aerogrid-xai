"""Causal data-flow audit for the closed-loop refinement.

Roadmap task s6-5: Scientific gate - loop is causal.
Gate: Operational data affects model, not vice versa (no data leakage).

Reference:
    AeroGrid-XAI Final Comprehensive Specification (Rev. 6),
    Section 37 (Stage E - Closed-Loop Refinement).

The causal question
-------------------

Stage E refines the physics model from operational data. For the
refinement to be scientifically valid, the causal arrow must point
one way:

    operational_data -> refinement_decision -> model_state

and never the other way:

    model_state -> operational_data

If the second arrow exists, the loop is subject to data leakage: the
model would be fitting its own output instead of independent
observations. This module provides two independent checks plus one
declared DAG.

Unrolled iteration
------------------

The Stage E loop updates theta each iteration: theta_t0 feeds the
Bayesian update, which produces theta_t1, which becomes theta_t0 of
the next iteration. In a causal DAG, that time evolution is modeled
by *unrolling* one iteration into distinct nodes theta_t0 and
theta_t1. Two nodes with the same persistent name would create a
spurious cycle: theta_t0 -> bayes_update -> theta_t0, which is not
a causal cycle, it is a state transition.

Structural check (AST)
----------------------

Every Python module under app/refinement/ is parsed, and any import
whose module name begins with a prefix in FORBIDDEN_IMPORT_ROOTS is
reported as a violation. A refinement module that cannot import the
physics model cannot fabricate observations from it.

Declared DAG check
------------------

The Stage E loop is declared as a directed graph with kinds:
"external_data", "model_state", "operation". The audit verifies:

  1. The graph is acyclic.
  2. There is a path from at least one external_data node to at
     least one model_state node (data DOES affect the model).
  3. There is NO path from any model_state node to any external_data
     node (the model does NOT affect the data).

Behavioral confirmation lives in the test file: two runs with
different initial model state but the same observation seed produce
identical observation sequences.
"""

from __future__ import annotations

import ast
from collections import deque
from dataclasses import dataclass
from pathlib import Path

FORBIDDEN_IMPORT_ROOTS: tuple[str, ...] = ("app.physics",)


@dataclass(frozen=True)
class CausalNode:
    """A single node in the causal graph."""

    name: str
    kind: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("node name must be non-empty")
        if self.kind not in {
            "external_data",
            "model_state",
            "operation",
            "encoder_state",
        }:
            raise ValueError(
                f"unknown node kind {self.kind!r}; allowed: external_data, "
                "model_state, operation, encoder_state"
            )


@dataclass(frozen=True)
class CausalEdge:
    """A directed edge in the causal graph."""

    source: str
    target: str
    description: str = ""

    def __post_init__(self) -> None:
        if not self.source or not self.target:
            raise ValueError("edge endpoints must be non-empty")
        if self.source == self.target:
            raise ValueError(f"self-loop on {self.source!r} is not allowed")


@dataclass(frozen=True)
class ImportViolation:
    """A forbidden import found by the AST audit."""

    file: str
    line: int
    imported_module: str


class StageECausalGraph:
    """Declared causal graph of the Stage E loop with audit methods."""

    def __init__(
        self,
        nodes: list[CausalNode],
        edges: list[CausalEdge],
    ) -> None:
        seen: set[str] = set()
        for node in nodes:
            if node.name in seen:
                raise ValueError(f"duplicate node name {node.name!r}")
            seen.add(node.name)
        for edge in edges:
            if edge.source not in seen:
                raise ValueError(f"edge source {edge.source!r} is not a declared node")
            if edge.target not in seen:
                raise ValueError(f"edge target {edge.target!r} is not a declared node")
        self._nodes = tuple(nodes)
        self._edges = tuple(edges)

    @property
    def nodes(self) -> tuple[CausalNode, ...]:
        return self._nodes

    @property
    def edges(self) -> tuple[CausalEdge, ...]:
        return self._edges

    def kind_of(self, name: str) -> str:
        for node in self._nodes:
            if node.name == name:
                return node.kind
        raise KeyError(f"unknown node {name!r}")

    def nodes_of_kind(self, kind: str) -> tuple[CausalNode, ...]:
        return tuple(n for n in self._nodes if n.kind == kind)

    def _adjacency(self) -> dict[str, list[str]]:
        adj: dict[str, list[str]] = {n.name: [] for n in self._nodes}
        for e in self._edges:
            adj[e.source].append(e.target)
        return adj

    def has_path(self, source: str, target: str) -> bool:
        if source == target:
            return True
        adj = self._adjacency()
        visited = {source}
        queue: deque[str] = deque([source])
        while queue:
            current = queue.popleft()
            for nxt in adj[current]:
                if nxt == target:
                    return True
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)
        return False

    def verify_acyclic(self) -> None:
        in_degree: dict[str, int] = {n.name: 0 for n in self._nodes}
        adj = self._adjacency()
        for edges_from in adj.values():
            for target in edges_from:
                in_degree[target] += 1
        queue: deque[str] = deque(name for name, deg in in_degree.items() if deg == 0)
        processed = 0
        while queue:
            current = queue.popleft()
            processed += 1
            for nxt in adj[current]:
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    queue.append(nxt)
        if processed != len(self._nodes):
            remaining = [n for n, d in in_degree.items() if d > 0]
            raise ValueError(f"causal graph contains a cycle through nodes {remaining}")

    def check_no_path_between_kinds(
        self, source_kind: str, target_kind: str
    ) -> list[tuple[str, str]]:
        sources = [n.name for n in self._nodes if n.kind == source_kind]
        targets = [n.name for n in self._nodes if n.kind == target_kind]
        bad: list[tuple[str, str]] = []
        for s in sources:
            for t in targets:
                if self.has_path(s, t):
                    bad.append((s, t))
        return bad

    def check_path_exists_between_kinds(self, source_kind: str, target_kind: str) -> bool:
        sources = [n.name for n in self._nodes if n.kind == source_kind]
        targets = [n.name for n in self._nodes if n.kind == target_kind]
        for s in sources:
            for t in targets:
                if self.has_path(s, t):
                    return True
        return False


def stage_e_causal_graph() -> StageECausalGraph:
    """Return the declared causal graph of the Stage E loop, unrolled
    one iteration.

    Time indices t0 and t1 distinguish model state at the start and
    end of one loop iteration. This is the standard way to represent
    a state-update loop in a causal DAG.
    """
    nodes = [
        CausalNode("external_source", "external_data"),
        CausalNode("observed_values", "external_data"),
        CausalNode("theta_t0", "model_state"),
        CausalNode("theta_t1", "model_state"),
        CausalNode("pwl_t0", "model_state"),
        CausalNode("pwl_t1", "model_state"),
        CausalNode("prediction", "operation"),
        CausalNode("discrepancy", "operation"),
        CausalNode("trigger_decision", "operation"),
        CausalNode("bayes_update", "operation"),
        CausalNode("pwl_refine", "operation"),
    ]
    edges = [
        CausalEdge("external_source", "observed_values", "measurement generation is external"),
        CausalEdge("theta_t0", "prediction", "prior state feeds prediction"),
        CausalEdge("pwl_t0", "prediction", "prior PWL feeds prediction"),
        CausalEdge("prediction", "discrepancy", "prediction compared to observation"),
        CausalEdge("observed_values", "discrepancy", "observation compared to prediction"),
        CausalEdge("discrepancy", "trigger_decision", "discrepancy drives trigger"),
        CausalEdge("trigger_decision", "bayes_update", "trigger gates update"),
        CausalEdge("observed_values", "bayes_update", "observation is the data"),
        CausalEdge("theta_t0", "bayes_update", "prior belief is the state"),
        CausalEdge("bayes_update", "theta_t1", "posterior is the new state"),
        CausalEdge("observed_values", "pwl_refine", "observations drive segment selection"),
        CausalEdge("pwl_t0", "pwl_refine", "current approximation is split target"),
        CausalEdge("pwl_refine", "pwl_t1", "split produces new approximation"),
    ]
    return StageECausalGraph(nodes, edges)


def _iter_imported_modules(tree: ast.AST) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.append((node.lineno, node.module))
    return out


def ast_audit_refinement_imports(
    package_dir: Path | None = None,
) -> list[ImportViolation]:
    """Return forbidden imports of physics modules from refinement."""
    if package_dir is None:
        package_dir = Path(__file__).resolve().parent
    violations: list[ImportViolation] = []
    for path in sorted(package_dir.rglob("*.py")):
        try:
            source = path.read_text()
        except OSError as exc:
            raise RuntimeError(f"cannot read {path}: {exc}") from exc
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            raise RuntimeError(f"cannot parse {path}: {exc}") from exc
        for lineno, module_name in _iter_imported_modules(tree):
            for forbidden in FORBIDDEN_IMPORT_ROOTS:
                if module_name == forbidden or module_name.startswith(forbidden + "."):
                    violations.append(
                        ImportViolation(
                            file=str(path),
                            line=lineno,
                            imported_module=module_name,
                        )
                    )
    return violations
