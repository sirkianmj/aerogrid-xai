"""Build Notebook 12 - Final reproducibility.

Sprint 12. The reproducibility acceptance demonstration: at a fixed
commit, the same inputs produce the same outputs, across the
scientific layers the platform claims.

Does not require PostgreSQL, Redis, MinIO, or the SaaS layer. The
notebook-repro workflow applies the migrations and provides
PostgreSQL, but Notebook 12 does not depend on them.

Notebook-specific constraint: Jupyter code cells already run inside
an asyncio event loop. ``asyncio.run(...)`` raises RuntimeError in
that context. The concurrency cell uses top-level ``await`` instead,
which is valid in a notebook cell but not in a plain .py file.
"""

from pathlib import Path

import nbformat as nbf

NB = nbf.v4.new_notebook()
CELLS = []


def md(text):
    CELLS.append(nbf.v4.new_markdown_cell(text))


def code(text):
    CELLS.append(nbf.v4.new_code_cell(text))


md("""# Notebook 12 - Final reproducibility

**Sprint:** S12 (Master Acceptance Test)
**Deliverable:** the reproducibility half of the acceptance record.

## What this notebook demonstrates

Reproducibility is the property that *the same inputs produce the
same outputs*. For AeroGrid-XAI this is claimed at four layers:

| Layer | Claim | Cell |
|---|---|---|
| Discovery loop | Same seed -> byte-identical outputs | Full pipeline determinism |
| Pipeline stages | Two passes agree at every generation | Pipeline stages |
| Concurrency | Two concurrent POSTs return identical bodies | Concurrency |
| XAI trace | Score = sum of trace step weights | Trace fidelity |

The requirement-to-verifier mapping is asserted separately by
`tests/mat.py`, which this notebook embeds and reports.

**Does not require** PostgreSQL, Redis, MinIO, or the SaaS layer.
""")

md("## Setup")

code("""import asyncio
import random
import sys
from pathlib import Path

repo_root = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(repo_root / "backend"))

import httpx
from fastapi.testclient import TestClient

from app.control.tier1 import decide_charge_uav, default_charge_rule_list
from app.discovery.attribution import (
    ConflictProneTable, attribute_and_mark,
)
from app.discovery.generator import GeneratorConfig, generate_architecture
from app.discovery.loop import ClearDLoopConfig, run_clear_d_loop
from app.discovery.nsga2 import synthetic_evaluator
from app.main import app
from app.verification.architecture_encoder import encode_architecture

BASE_SEED = 20261015
print(f"repo root: {repo_root}")
print("imports OK")
""")

md("""## Full pipeline determinism

Run the same CLEAR-D loop twice with the same seed and the same
generator configuration. The two runs must agree byte for byte on the
four serialisable outputs of the loop:

- `generation_stats` (one entry per generation)
- `hypervolume_history` (one entry per generation)
- `conflict_prone_table` (attribution map)
- `final_population` (Pareto-selected individuals)
""")


code("""def run_loop_once(seed_offset: int):
    seeds = [
        generate_architecture(
            GeneratorConfig(min_nodes=4, max_nodes=6, max_links=5, seed=seed_offset + i)
        )
        for i in range(4)
    ]
    cfg = ClearDLoopConfig(population_size=4, n_generations=8)
    return run_clear_d_loop(
        seeds,
        encode_architecture,
        synthetic_evaluator(),
        cfg,
        random.Random(BASE_SEED),
        hypervolume_samples=16,
    )


a = run_loop_once(seed_offset=31000)
b = run_loop_once(seed_offset=31000)

assert a.generation_stats == b.generation_stats, "generation_stats differ"
assert a.hypervolume_history == b.hypervolume_history, "hypervolume_history differ"
assert a.conflict_prone_table.to_mapping() == b.conflict_prone_table.to_mapping(), \
    "conflict_prone_table differs"
assert [id(ind.architecture) for ind in a.final_population] != \
       [id(ind.architecture) for ind in b.final_population], \
    "final_population shares object identity (should be fresh each run)"
assert [
    (tuple((n.node_id, n.kind.value) for n in ind.architecture.nodes),
     tuple((ln.link_id, ln.kind.value, ln.source_id, ln.target_id)
           for ln in ind.architecture.links))
    for ind in a.final_population
] == [
    (tuple((n.node_id, n.kind.value) for n in ind.architecture.nodes),
     tuple((ln.link_id, ln.kind.value, ln.source_id, ln.target_id)
           for ln in ind.architecture.links))
    for ind in b.final_population
], "final_population architecture structure differs"

print(f"generations: {len(a.generation_stats)}")
print(f"final population size: {len(a.final_population)}")
print(f"conflict-prone features marked: {len(a.conflict_prone_table)}")
print("Full pipeline determinism OK")
""")

md("""## Pipeline stages

Determinism is asserted at each stage independently, not only on the
composite output. A composite match that came from a compensating
error at two stages would pass the previous cell; this cell would not.
""")


code("""gen_a = generate_architecture(GeneratorConfig(min_nodes=4, max_nodes=6, seed=777))
gen_b = generate_architecture(GeneratorConfig(min_nodes=4, max_nodes=6, seed=777))
assert gen_a == gen_b, "generator not deterministic at fixed seed"

enc_a = encode_architecture(gen_a)
enc_b = encode_architecture(gen_b)
assert [
    (fc.family_name, str(fc.expression), sorted(str(f) for f in fc.features))
    for fc in enc_a
] == [
    (fc.family_name, str(fc.expression), sorted(str(f) for f in fc.features))
    for fc in enc_b
], "encoder not deterministic at fixed architecture"

tbl_a = ConflictProneTable()
att_a = attribute_and_mark(enc_a, tbl_a)
tbl_b = ConflictProneTable()
att_b = attribute_and_mark(enc_b, tbl_b)
assert att_a.status == att_b.status
assert att_a.conflict_prone == att_b.conflict_prone
assert tbl_a.to_mapping() == tbl_b.to_mapping()

print(f"generator:  nodes={len(gen_a.nodes)} links={len(gen_a.links)}")
print(f"encoder:    {len(enc_a)} feature constraints")
print(f"attribution status: {att_a.status}")
print("Pipeline stage-level determinism OK")
""")

md("""## Concurrency

Two `POST /discovery/run` requests with the same body, scheduled on
one event loop via `asyncio.gather` against an in-process ASGI
transport, must return identical response bodies.

**Why ASGI, not threaded `TestClient`:** the s11-7 test found two
defects, neither in the endpoint. Starlette's `TestClient` SIGSEGVs
under thread concurrency, and Z3's Python bindings use a
process-global context. The endpoint itself is `async def` with no
`await`, so single-worker uvicorn runs it one request at a time on
the event loop, which is exactly what this cell exercises.
""")


code("""REQ = {
    "population_size": 6,
    "n_generations": 3,
    "seed": 20261015,
    "min_nodes": 4,
    "max_nodes": 8,
    "max_links": 6,
    "use_conflict_directed": True,
}


async def run_pair():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        ra, rb = await asyncio.gather(
            c.post("/discovery/run", json=REQ),
            c.post("/discovery/run", json=REQ),
        )
    assert ra.status_code == 200, ra.text
    assert rb.status_code == 200, rb.text
    return ra.json(), rb.json()


body_a, body_b = await run_pair()
for key in ("generation_stats", "hypervolume_history",
            "conflict_prone_table", "trace", "discovered"):
    assert body_a[key] == body_b[key], f"concurrent responses differ on {key!r}"

with TestClient(app) as client:
    serial = client.post("/discovery/run", json=REQ).json()
for key in ("generation_stats", "hypervolume_history",
            "conflict_prone_table", "trace", "discovered"):
    assert body_a[key] == serial[key], \
        f"concurrent diverges from serial on {key!r}"

print(f"discovered architectures per response: {len(body_a['discovered'])}")
print(f"conflict-prone entries per response:   {len(body_a['conflict_prone_table'])}")
print("Concurrency determinism OK")
""")

md("""## XAI trace fidelity

For every decision in a 100-point sweep, the winner score must equal
the sum of the recorded trace step weights. This is the operative
form of the Tier 1 fidelity invariant, and the numeric claim the
paper's Section 5.4 depends on.
""")


code("""rng = random.Random(BASE_SEED)


def candidate(rng, index):
    return {
        "uav_id": float(index),
        "battery_pct": rng.uniform(0.0, 100.0),
        "mission_priority": rng.uniform(0.0, 1.0),
        "network_centrality": rng.uniform(0.0, 1.0),
        "coverage_contribution": rng.uniform(0.0, 0.20),
        "workload_urgency": rng.uniform(0.0, 1.0),
        "thermal_headroom_c": rng.uniform(0.0, 80.0),
        "atmospheric_factor": rng.uniform(0.0, 1.0),
        "beam_alignment": rng.uniform(0.0, 1.0),
        "transfer_loss": rng.uniform(0.0, 0.5),
    }


rule_list = default_charge_rule_list()
max_diff = 0.0
for i in range(100):
    cand = candidate(rng, i)
    trace = decide_charge_uav([cand], rule_list)
    diff = abs(sum(step.weight for step in trace.steps) - trace.score)
    max_diff = max(max_diff, diff)

print(f"max |score - sum(step weights)| over 100 sweeps: {max_diff:.2e}")
assert max_diff < 1e-12, f"trace fidelity violated: max_diff={max_diff:.2e}"
print("Trace fidelity preserved on 100-point sweep")
""")

md("""## Requirement-to-verifier mapping

Sprint 12's other deliverable, `tests/mat.py`, asserts that every
requirement in `docs/DID/SRS.md` has an existing verifier, as declared
in `docs/DID/STR.md` section 6.3. This cell runs it and reports the
summary line.
""")


code("""import subprocess

mat = subprocess.run(
    [sys.executable, str(repo_root / "tests" / "mat.py")],
    capture_output=True, text=True, cwd=repo_root, timeout=180,
)
tail = [ln for ln in mat.stdout.splitlines() if ln.strip()][-3:]
for line in tail:
    print(line)
assert mat.returncode == 0, f"mat.py exited {mat.returncode}"
print("MAT result: PASS")
""")

md("""## Gate

The four reproducibility claims hold. Any mismatch fails its cell with
a specific message.
""")


code("""print("Notebook 12 - Final reproducibility")
print("=" * 60)
print(f"Loop generation_stats determinism:   OK ({len(a.generation_stats)} generations)")
print(f"Loop hypervolume_history determinism: OK")
print(f"Loop conflict_prone_table determinism: OK")
print(f"Pipeline stage determinism:          OK")
print(f"Concurrency determinism:             OK")
print(f"Trace fidelity max diff:             {max_diff:.2e}  (gate: <1e-12)")
print()
print("ALL GATES PASS")
""")

md("""## Summary

At a fixed commit, the same inputs produce the same outputs across
every scientific layer the platform claims: the discovery loop, the
pipeline stages, concurrent request handling, and the XAI trace.
The requirement-to-verifier mapping declared in the STR is asserted
by `tests/mat.py`, which this notebook runs and reports.

To rerun this notebook locally:

    cd backend && python -m pip install nbclient  # if not already present
    cd ..
    python scripts/build_notebook_12.py
    jupyter nbconvert --to notebook --execute notebooks/12_final_reproducibility.ipynb \\
        --output-dir /tmp/nb12-out

The notebook-repro workflow executes every `notebooks/*.ipynb`
top-to-bottom against a fresh conda environment nightly. If the
numeric claims above do not hold, the workflow fails.
""")

NB["cells"] = CELLS
NB["metadata"] = {
    "kernelspec": {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    },
    "language_info": {"name": "python", "version": "3.12"},
}

out = Path("notebooks/12_final_reproducibility.ipynb")
out.parent.mkdir(parents=True, exist_ok=True)
nbf.write(NB, str(out))
print(f"Wrote {out}")
print(f"Cells: {len(CELLS)}")
