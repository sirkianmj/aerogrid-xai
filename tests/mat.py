#!/usr/bin/env python3
"""Master Acceptance Test harness (Sprint 12).

Executable form of the requirement-to-verifier mapping declared in
``docs/DID/STR.md`` section 6.3. That section is the authoritative
statement of which artifact verifies each requirement in
``docs/DID/SRS.md`` section 3. MAT asserts, mechanically, that the
mapping is intact at the current HEAD:

  * every test file named as a T-verifier exists and collects at
    least one test under ``pytest --collect-only``;
  * every specific ``file::test_name`` named as a T-verifier is
    actually collected (the file alone is not enough);
  * every document named as an I-verifier exists on disk;
  * every workflow or command named as a D-verifier exists.

The STR's own rule for a requirement to be considered *verified* is:
the named artifact exists, runs green in CI, and would fail if the
requirement were violated. MAT enforces existence and collection
mechanically and defers "runs green in CI" to the six required CI
jobs, each of which runs on every PR. MAT does not re-run the suite.

A requirement whose verifier is missing, or whose Python test file
collects zero tests, is UNVERIFIED and causes MAT to exit non-zero.

Requirements marked PARTIAL in the STR are reported as PARTIAL and do
not by themselves cause a non-zero exit. The ``--strict`` flag
promotes them to failures.

Usage::

    python3 tests/mat.py               # human-readable table
    python3 tests/mat.py --json        # machine-readable
    python3 tests/mat.py --strict      # treat PARTIAL as failure
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"
DOCS_DIR = REPO_ROOT / "docs"
NOTEBOOKS_DIR = REPO_ROOT / "notebooks"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

METHOD_TEST = "T"  # automated test
METHOD_INSPECT = "I"  # inspection
METHOD_DEMO = "D"  # demonstration


@dataclass(frozen=True)
class Requirement:
    req_id: str
    method: str
    verifiers: tuple[str, ...]
    partial: bool = False
    note: str = ""


# ---------------------------------------------------------------------------
# The requirement table, transcribed from docs/DID/STR.md section 6.3.
# When a row in the STR changes, this table must change with it.
# ---------------------------------------------------------------------------
REQUIREMENTS: tuple[Requirement, ...] = (
    # 6.3.1 Orbital and geographic
    Requirement(
        "SRS-FUN-001",
        METHOD_TEST,
        ("backend/tests/test_orbital.py", "backend/tests/test_sgp4_reference.py"),
    ),
    Requirement("SRS-FUN-002", METHOD_TEST, ("test_visibility.py",)),
    Requirement("SRS-FUN-003", METHOD_TEST, ("test_eclipse_conical.py",)),
    Requirement("SRS-FUN-004", METHOD_TEST, ("test_region.py",)),
    Requirement("SRS-FUN-005", METHOD_TEST, ("test_no_hardcoded_positions.py",)),
    # 6.3.2 Wireless power transmission
    Requirement("SRS-FUN-010", METHOD_TEST, ("test_beam_and_physical_link_budget.py",)),
    Requirement("SRS-FUN-011", METHOD_TEST, ("test_link_budget.py",)),
    Requirement("SRS-FUN-012", METHOD_TEST, ("test_link_budget_gate.py", "test_xidian.py")),
    Requirement(
        "SRS-FUN-013",
        METHOD_TEST,
        ("test_link_budget.py::test_end_to_end_efficiency_is_product_of_stages",),
    ),
    # 6.3.3 Atmosphere
    Requirement("SRS-FUN-020", METHOD_TEST, ("test_atmosphere.py",)),
    Requirement("SRS-FUN-021", METHOD_TEST, ("test_atmosphere.py",)),
    Requirement(
        "SRS-FUN-022", METHOD_TEST, ("test_tier2.py::test_gate_90pct_coverage_at_least_85pct",)
    ),
    # 6.3.4 Receiver and thermal
    Requirement("SRS-FUN-030", METHOD_TEST, ("test_receiver.py", "test_thermal.py")),
    Requirement("SRS-FUN-031", METHOD_TEST, ("test_receiver.py",)),
    Requirement("SRS-FUN-032", METHOD_TEST, ("test_thermal.py",)),
    Requirement("SRS-FUN-033", METHOD_TEST, ("test_thermal.py",)),
    # 6.3.5 CLEAR-D discovery
    Requirement("SRS-FUN-040", METHOD_TEST, ("test_grammar.py",)),
    Requirement("SRS-FUN-041", METHOD_TEST, ("test_generator.py", "test_generator_los.py")),
    Requirement("SRS-FUN-042", METHOD_TEST, ("test_unsat.py",)),
    Requirement("SRS-FUN-043", METHOD_TEST, ("test_attribution.py",)),
    Requirement("SRS-FUN-044", METHOD_TEST, ("test_h9_convergence.py", "test_mutation.py")),
    Requirement(
        "SRS-FUN-045",
        METHOD_TEST,
        ("test_z3_end_to_end.py::test_100_generations_completes_without_error",),
    ),
    Requirement("SRS-FUN-046", METHOD_TEST, ("test_nsga2.py",)),
    Requirement(
        "SRS-FUN-047",
        METHOD_TEST,
        (
            "test_discovery_determinism.py",
            "test_z3_end_to_end.py::test_100_generations_is_deterministic_under_fixed_seed",
        ),
    ),
    # 6.3.6 Two-tier XAI
    Requirement("SRS-FUN-050", METHOD_INSPECT, ("docs/XAI_FIDELITY_AUDIT.md",)),
    Requirement("SRS-FUN-051", METHOD_TEST, ("test_tier2.py", "test_xai_fidelity_audit.py")),
    Requirement(
        "SRS-FUN-052", METHOD_TEST, ("test_static_analyzer.py::test_real_control_package_is_clean",)
    ),
    Requirement("SRS-FUN-053", METHOD_TEST, ("test_tier1.py", "test_xai_fidelity_audit.py")),
    Requirement(
        "SRS-FUN-054",
        METHOD_TEST,
        ("test_explain.py::test_counterfactual_ablating_decisive_rule_flips_decision",),
    ),
    # 6.3.7 Formal verification
    Requirement("SRS-FUN-060", METHOD_TEST, ("test_pwl.py",)),
    Requirement("SRS-FUN-061", METHOD_TEST, ("test_pwl.py", "test_pwl_tune.py")),
    Requirement("SRS-FUN-062", METHOD_TEST, ("test_fuzz_soundness.py",)),
    Requirement("SRS-FUN-063", METHOD_TEST, ("test_hierarchical.py",)),
    Requirement("SRS-FUN-064", METHOD_TEST, ("test_regulatory.py",)),
    # 6.3.8 Closed-loop refinement
    Requirement("SRS-FUN-070", METHOD_TEST, ("test_bayes.py",)),
    Requirement(
        "SRS-FUN-071",
        METHOD_TEST,
        ("test_bayes.py::test_posterior_variance_strictly_less_than_prior",),
    ),
    Requirement(
        "SRS-FUN-072",
        METHOD_TEST,
        ("test_pwl_tune.py::test_h12_epsilon_reduces_by_half_over_100_cycles",),
    ),
    Requirement("SRS-FUN-073", METHOD_TEST, ("test_discrepancy.py",)),
    Requirement("SRS-FUN-074", METHOD_TEST, ("test_causality.py",)),
    # 6.3.9 SaaS
    Requirement("SRS-FUN-080", METHOD_TEST, ("test_rls_isolation.py", "docs/ISOLATION_AUDIT.md")),
    Requirement(
        "SRS-FUN-081",
        METHOD_TEST,
        ("test_rls_isolation.py::test_app_role_with_unset_guc_sees_zero_rows",),
    ),
    Requirement("SRS-FUN-082", METHOD_TEST, ("test_saas_auth.py",)),
    Requirement("SRS-FUN-083", METHOD_TEST, ("test_saas_quota.py",)),
    Requirement("SRS-FUN-084", METHOD_TEST, ("test_saas_admin_routes.py",)),
    # 6.3.10 Epistemic hierarchy
    Requirement("SRS-FUN-090", METHOD_TEST, ("EpistemicBadge.test.tsx",)),
    Requirement(
        "SRS-FUN-091",
        METHOD_INSPECT,
        ("docs/EPISTEMIC_HIERARCHY_AUDIT.md",),
        partial=True,
        note="P34 open; infrastructure exists, audit remains",
    ),
    Requirement("SRS-FUN-092", METHOD_TEST, ("XAITrace.test.tsx",)),
    Requirement("SRS-FUN-093", METHOD_TEST, ("contrast.test.ts",)),
    # 6.3.11 Performance
    Requirement("SRS-PER-001", METHOD_TEST, ("test_z3_end_to_end.py",)),
    Requirement("SRS-PER-002", METHOD_TEST, ("Telemetry.test.tsx",)),
    Requirement("SRS-PER-003", METHOD_INSPECT, ("notebooks/05_smt_scaling.ipynb",)),
    Requirement(
        "SRS-PER-004",
        METHOD_DEMO,
        ("frontend/package.json",),
        note="P31 bundle-size advisory, not a hard requirement",
    ),
    # 6.3.12 Interface
    Requirement("SRS-INT-001", METHOD_TEST, ("test_health.py",)),
    Requirement("SRS-INT-002", METHOD_TEST, ("test_health.py",)),
    Requirement(
        "SRS-INT-003", METHOD_TEST, ("test_tradespace_api.py::test_openapi_lists_all_routers",)
    ),
    Requirement("SRS-INT-004", METHOD_TEST, ("test_telemetry_ws.py",)),
    # 6.3.13 Safety
    Requirement("SRS-SAF-001", METHOD_TEST, ("test_regulatory.py",)),
    Requirement("SRS-SAF-002", METHOD_TEST, ("test_regulatory.py",)),
    Requirement(
        "SRS-SAF-003", METHOD_TEST, ("test_encoder_physics.py", "test_architecture_encoder.py")
    ),
    Requirement("SRS-SAF-004", METHOD_TEST, ("test_dimensional_consistency.py",)),
    # 6.3.14 Security
    Requirement("SRS-SEC-001", METHOD_TEST, ("test_saas_auth.py",)),
    Requirement("SRS-SEC-002", METHOD_INSPECT, ("docs/ISOLATION_AUDIT.md",)),
    Requirement("SRS-SEC-003", METHOD_TEST, ("test_saas_billing_routes.py",)),
    # 6.3.15 Verification / certification
    Requirement("SRS-VER-001", METHOD_INSPECT, ("docs/SCIENTIFIC_CLAIMS.md",)),
    Requirement(
        "SRS-VER-002",
        METHOD_INSPECT,
        ("docs/CITATION_AUDIT.md",),
        note="open items P5, C-3 recorded",
    ),
    Requirement("SRS-VER-003", METHOD_DEMO, ("tests/master_test.py",)),
    Requirement("SRS-VER-004", METHOD_INSPECT, ("docs/ISOLATION_AUDIT.md",)),
    Requirement(
        "SRS-VER-005",
        METHOD_DEMO,
        (".github/workflows/notebook-repro.yml",),
        note="workflow present; first scheduled run pending",
    ),
)


@dataclass
class VerifierResult:
    raw: str
    path: Path | None
    status: str  # OK | MISSING | EMPTY | NOT-FOUND-NODE


@dataclass
class RequirementResult:
    req: Requirement
    verifiers: list[VerifierResult]
    status: str  # PASS | PARTIAL | UNVERIFIED | INSPECTION | DEMO


def _collect_pytest() -> tuple[dict[str, int], set[str]]:
    """One subprocess, return (file-to-count map, collected-node-id set).

    Node IDs are relative to backend/ and look like
    ``tests/test_orbital.py::test_foo``.
    """
    if not BACKEND_DIR.is_dir():
        return {}, set()
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        timeout=180,
    )
    counts: dict[str, int] = {}
    ids: set[str] = set()
    pat = re.compile(r"^(tests/[^:]+\.py)::")
    for line in proc.stdout.splitlines():
        line = line.strip()
        m = pat.match(line)
        if m:
            f = m.group(1)
            counts[f] = counts.get(f, 0) + 1
            ids.add(line)
    return counts, ids


def _resolve(raw: str) -> Path | None:
    """Map a verifier name from STR 6.3 to a path on disk."""
    name = raw.split("::", 1)[0]
    p = Path(name)
    if p.is_absolute() and p.exists():
        return p
    cand = REPO_ROOT / p
    if cand.exists():
        return cand
    if name.endswith(".py"):
        for base in (BACKEND_DIR / "tests", BACKEND_DIR):
            c = base / name
            if c.exists():
                return c
        if (BACKEND_DIR / "tests").is_dir():
            for hit in (BACKEND_DIR / "tests").rglob(name):
                return hit
    if name.endswith((".ts", ".tsx")) and FRONTEND_SRC.is_dir():
        for hit in FRONTEND_SRC.rglob(name):
            return hit
    if name.endswith(".ipynb"):
        c = NOTEBOOKS_DIR / name
        if c.exists():
            return c
    if name.endswith((".md", ".yml", ".yaml", ".json")):
        for hit in DOCS_DIR.rglob(name):
            return hit
        c = WORKFLOWS_DIR / name
        if c.exists():
            return c
    return None


def _check(req: Requirement, counts: dict[str, int], ids: set[str]) -> RequirementResult:
    results: list[VerifierResult] = []
    for raw in req.verifiers:
        path = _resolve(raw)
        if path is None:
            results.append(VerifierResult(raw, None, "MISSING"))
            continue
        status = "OK"
        if "::" in raw and path.suffix == ".py" and BACKEND_DIR in path.parents:
            rel = path.relative_to(BACKEND_DIR).as_posix()
            node = raw.split("::", 1)[1]
            full = f"{rel}::{node}"
            if full not in ids:
                status = "NOT-FOUND-NODE"
        elif path.suffix == ".py" and BACKEND_DIR in path.parents:
            rel = path.relative_to(BACKEND_DIR).as_posix()
            if counts.get(rel, 0) == 0:
                status = "EMPTY"
        results.append(VerifierResult(raw, path, status))

    ok = all(r.status == "OK" for r in results)
    if req.method == METHOD_TEST:
        agg = "PASS" if ok else "UNVERIFIED"
    elif req.method == METHOD_INSPECT:
        agg = "INSPECTION" if ok else "UNVERIFIED"
    else:
        agg = "DEMO" if ok else "UNVERIFIED"
    if agg != "UNVERIFIED" and req.partial:
        agg = "PARTIAL"
    return RequirementResult(req, results, agg)


def _run(strict: bool) -> tuple[list[RequirementResult], int]:
    counts, ids = _collect_pytest()
    results = [_check(r, counts, ids) for r in REQUIREMENTS]
    failed = [r for r in results if r.status == "UNVERIFIED"]
    partial = [r for r in results if r.status == "PARTIAL"]
    exit_code = 1 if failed else (1 if strict and partial else 0)
    return results, exit_code


def _print_human(results: list[RequirementResult]) -> None:
    width = max(len(r.req.req_id) for r in results)
    print("=" * 78)
    print("Master Acceptance Test -- requirement -> verifier mapping")
    print("=" * 78)
    for r in results:
        mark = {
            "PASS": "OK ",
            "PARTIAL": "PRT",
            "INSPECTION": "INS",
            "DEMO": "DEM",
            "UNVERIFIED": "FAIL",
        }.get(r.status, "???")
        print(f"  [{mark}] {r.req.req_id:<{width}}  {r.req.method}  {r.req.verifiers[0]}")
        for v in r.verifiers[1:]:
            print(f"        {'':<{width}}     {v.raw}")
        for v in r.verifiers:
            if v.status != "OK":
                print(f"        !! {v.raw}  ->  {v.status}")
        if r.req.note:
            print(f"        note: {r.req.note}")
    print("=" * 78)
    total = len(results)
    n_pass = sum(1 for r in results if r.status == "PASS")
    n_part = sum(1 for r in results if r.status == "PARTIAL")
    n_ins = sum(1 for r in results if r.status == "INSPECTION")
    n_dem = sum(1 for r in results if r.status == "DEMO")
    n_fail = sum(1 for r in results if r.status == "UNVERIFIED")
    print(
        f"  {total} requirements: {n_pass} PASS, {n_part} PARTIAL, "
        f"{n_ins} INSPECTION, {n_dem} DEMO, {n_fail} UNVERIFIED"
    )
    print(f"RESULT: {'PASS' if n_fail == 0 else 'FAIL'}")


def _print_json(results: list[RequirementResult]) -> None:
    out = {
        "total": len(results),
        "pass": sum(1 for r in results if r.status == "PASS"),
        "partial": sum(1 for r in results if r.status == "PARTIAL"),
        "inspection": sum(1 for r in results if r.status == "INSPECTION"),
        "demo": sum(1 for r in results if r.status == "DEMO"),
        "unverified": sum(1 for r in results if r.status == "UNVERIFIED"),
        "requirements": [
            {
                "id": r.req.req_id,
                "method": r.req.method,
                "status": r.status,
                "verifiers": [
                    {
                        "raw": v.raw,
                        "path": str(v.path.relative_to(REPO_ROOT)) if v.path else None,
                        "status": v.status,
                    }
                    for v in r.verifiers
                ],
                "note": r.req.note,
            }
            for r in results
        ],
    }
    print(json.dumps(out, indent=2))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--strict", action="store_true", help="treat PARTIAL requirements as failures")
    args = ap.parse_args(argv)

    results, code = _run(strict=args.strict)
    if args.json:
        _print_json(results)
    else:
        _print_human(results)
    return code


if __name__ == "__main__":
    sys.exit(main())
