"""Static analyzer enforcing the two-tier separation invariant.

Roadmap task s5-4: Static analyzer: Tier 2 never reaches action interface.
Gate: Build fails if a Tier 2 function reaches decide_*().

Reference:
    AeroGrid-XAI Final Comprehensive Specification (Rev. 6),
    Section 36.1 (Stage D - The Invariant).

The invariant
-------------

Tier 2 modules expose only functions of the form
estimate_*(*) -> (value, uncertainty_interval). Tier 1 modules
expose only functions of the form decide_*(*, estimates) ->
(action, explanation). Tier 1 may call Tier 2 to obtain estimates;
Tier 2 must never call Tier 1. If Tier 2 could invoke a decide_*
function, it could indirectly select an action, which would break
the architectural invariant.

This module parses every Python file under the control package,
builds a call graph of top-level functions, and asserts that the
transitive closure of any estimate_* function contains no decide_*
function. A violation is reported with the source file, line number,
and the offending call.

Why a call-graph check rather than a name check
-----------------------------------------------

A name check would only catch direct estimate -> decide calls. A
transitive call (estimate -> helper -> decide) would slip through.
The invariant is transitive, so the check must be transitive.

Scope
-----

Only direct top-level calls of the form name(...) are tracked. Method
calls (obj.method(...)) are ignored because the two-tier separation
is defined at the module-function level and our Tier 2 functions are
not methods. If a future Tier 2 class method starts reaching decide_*
functions, this analyzer will need to be extended.
"""

from __future__ import annotations

import ast
import sys
from collections import defaultdict, deque
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

TIER1_PREFIX = "decide_"
TIER2_PREFIX = "estimate_"


@dataclass(frozen=True)
class Violation:
    """A single violation of the two-tier separation invariant.

    Attributes:
        source_file: The file containing the offending estimate_* call.
        source_line: The line number of the estimate_* function
            definition, not the offending call. This is the origin
            from which the reachability was computed.
        offending_function: The decide_* function that is reachable.
        path: The call path from source to offending_function, as a
            tuple of function names. Useful for debugging.
    """

    source_file: str
    source_line: int
    offending_function: str
    path: tuple[str, ...]


@dataclass(frozen=True)
class FunctionDefRecord:
    """A top-level function definition recorded during parsing."""

    name: str
    file: str
    line: int
    calls: frozenset[str]


def _iter_toplevel_functions(
    module: ast.Module,
) -> Iterable[ast.FunctionDef | ast.AsyncFunctionDef]:
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _collect_direct_calls(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> frozenset[str]:
    """Return names of top-level functions called directly by fn.

    Only ast.Call nodes with a bare ast.Name func are recorded. Method
    calls and calls through attributes are ignored, per the module
    docstring.
    """
    names: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            names.add(node.func.id)
    return frozenset(names)


def parse_file(path: Path) -> list[FunctionDefRecord]:
    """Parse one Python file and return one record per top-level function."""
    try:
        source = path.read_text()
    except OSError as exc:
        raise RuntimeError(f"cannot read {path}: {exc}") from exc
    tree = ast.parse(source, filename=str(path))
    records: list[FunctionDefRecord] = []
    for fn in _iter_toplevel_functions(tree):
        records.append(
            FunctionDefRecord(
                name=fn.name,
                file=str(path),
                line=fn.lineno,
                calls=_collect_direct_calls(fn),
            )
        )
    return records


def build_call_graph(records: list[FunctionDefRecord]) -> dict[str, set[str]]:
    """Build a name -> set-of-called-names graph.

    Because function names are assumed unique within the control
    package, the graph is keyed by function name only. A future
    refactor that introduces duplicate names will require extending
    this to key by (module, name).
    """
    graph: dict[str, set[str]] = defaultdict(set)
    known = {r.name for r in records}
    for r in records:
        for called in r.calls:
            if called in known:
                graph[r.name].add(called)
    return graph


def reachable_from(
    graph: dict[str, set[str]],
    start: str,
) -> dict[str, tuple[str, ...]]:
    """BFS from start; return {reached_name: path_tuple}.

    The path includes start as the first element and the reached name
    as the last. Starting name maps to a single-element tuple.
    """
    paths: dict[str, tuple[str, ...]] = {start: (start,)}
    queue: deque[str] = deque([start])
    while queue:
        current = queue.popleft()
        for nxt in graph.get(current, ()):
            if nxt not in paths:
                paths[nxt] = paths[current] + (nxt,)
                queue.append(nxt)
    return paths


def analyze_package(package_dir: Path) -> list[Violation]:
    """Analyze every .py file under package_dir and return violations.

    A violation is recorded for every estimate_* function whose
    transitive call closure contains a decide_* function.
    """
    records: list[FunctionDefRecord] = []
    for path in sorted(package_dir.rglob("*.py")):
        records.extend(parse_file(path))

    graph = build_call_graph(records)

    violations: list[Violation] = []
    for record in records:
        if not record.name.startswith(TIER2_PREFIX):
            continue
        reachable = reachable_from(graph, record.name)
        for name, call_path in reachable.items():
            if name.startswith(TIER1_PREFIX) and name != record.name:
                violations.append(
                    Violation(
                        source_file=record.file,
                        source_line=record.line,
                        offending_function=name,
                        path=call_path,
                    )
                )
    return violations


def analyze_default_package() -> list[Violation]:
    """Analyze the control package that contains this module."""
    package_dir = Path(__file__).resolve().parent
    return analyze_package(package_dir)


def main() -> int:
    """CLI entry point. Exits 0 if clean, 1 on violations."""
    violations = analyze_default_package()
    if not violations:
        print("static_analyzer: no two-tier violations found")
        return 0
    print(f"static_analyzer: {len(violations)} violation(s) found")
    for v in violations:
        path_str = " -> ".join(v.path)
        print(f"  {v.source_file}:{v.source_line}: {v.offending_function} reachable via {path_str}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
