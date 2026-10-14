"""Tests for POST /discovery/run and the loop's optional trace.

The endpoint is the CLEAR-D live dashboard's data source: it exposes
the attribution mechanism — unsat core -> grammar features ->
conflict-prone table -> biased mutation — as a serializable stream.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# --- endpoint basics ------------------------------------------------------


def test_run_returns_200_with_expected_fields() -> None:
    r = client.post("/discovery/run", json={"population_size": 6, "n_generations": 2, "seed": 1})
    assert r.status_code == 200
    body = r.json()
    for key in (
        "epistemic_tag",
        "population_size",
        "n_generations",
        "generation_stats",
        "hypervolume_history",
        "conflict_prone_table",
        "trace",
        "trace_truncated",
        "discovered",
    ):
        assert key in body, key


def test_generation_stats_length_matches_request() -> None:
    r = client.post("/discovery/run", json={"population_size": 4, "n_generations": 3, "seed": 1})
    body = r.json()
    assert len(body["generation_stats"]) == 3
    assert len(body["hypervolume_history"]) == 3


def test_trace_length_is_at_least_population_size() -> None:
    """Every individual in the initial population is classified once,
    so the trace has at least ``population_size`` entries even for a
    single-generation run."""
    r = client.post("/discovery/run", json={"population_size": 10, "n_generations": 1, "seed": 2})
    body = r.json()
    assert len(body["trace"]) >= 10


def test_trace_has_sat_entries_with_empty_conflict_prone() -> None:
    r = client.post("/discovery/run", json={"population_size": 8, "n_generations": 3, "seed": 7})
    body = r.json()
    sat_events = [e for e in body["trace"] if e["status"] == "sat"]
    assert sat_events, "expected at least one SAT classification"
    for ev in sat_events:
        assert ev["conflict_prone"] == []
        assert ev["n_constraints"] > 0


def test_trace_unsat_events_carry_conflict_prone_features() -> None:
    """Every UNSAT classification must map to at least one grammar
    feature; that is the whole point of the attribution mechanism."""
    r = client.post("/discovery/run", json={"population_size": 10, "n_generations": 5, "seed": 7})
    body = r.json()
    unsat = [e for e in body["trace"] if e["status"] == "unsat"]
    assert unsat, "expected at least one UNSAT classification for seed 7 with 5 generations"
    for ev in unsat:
        assert len(ev["conflict_prone"]) >= 1, ev
        for feature in ev["conflict_prone"]:
            assert ":" in feature, feature


def test_conflict_prone_table_entries_have_kind_and_count() -> None:
    r = client.post("/discovery/run", json={"population_size": 8, "n_generations": 4, "seed": 7})
    body = r.json()
    assert body["conflict_prone_table"], "expected non-empty conflict-prone table"
    for entry in body["conflict_prone_table"]:
        assert entry["count"] >= 1
        assert entry["kind"] in {
            "node_instance",
            "link_instance",
            "node_type",
            "link_type",
        }
        assert entry["identifier"]


def test_deterministic_same_seed_produces_identical_trace() -> None:
    r1 = client.post("/discovery/run", json={"population_size": 6, "n_generations": 3, "seed": 99})
    r2 = client.post("/discovery/run", json={"population_size": 6, "n_generations": 3, "seed": 99})
    assert r1.json()["trace"] == r2.json()["trace"]
    assert r1.json()["conflict_prone_table"] == r2.json()["conflict_prone_table"]


def test_rejects_inconsistent_node_bounds() -> None:
    r = client.post("/discovery/run", json={"min_nodes": 10, "max_nodes": 5})
    assert r.status_code == 400
    assert "max_nodes" in r.json()["detail"]


def test_rejects_population_below_two() -> None:
    r = client.post("/discovery/run", json={"population_size": 1})
    assert r.status_code == 422


def test_rejects_generations_above_cap() -> None:
    r = client.post("/discovery/run", json={"n_generations": 10_000})
    assert r.status_code == 422


def test_epistemic_tag_is_simulation_result() -> None:
    r = client.post("/discovery/run", json={"population_size": 4, "n_generations": 1, "seed": 1})
    assert r.json()["epistemic_tag"] == "simulation_result"


# --- underlying loop: trace parameter does not change results ------------


def test_trace_parameter_does_not_change_loop_result() -> None:
    """Passing trace should be purely observational; the resulting
    statistics, hypervolume history, and conflict-prone table must
    match a run without trace, given the same seed."""
    import random

    from app.discovery.generator import GeneratorConfig, generate_architecture
    from app.discovery.loop import ClearDLoopConfig, run_clear_d_loop
    from app.discovery.nsga2 import synthetic_evaluator
    from app.verification.architecture_encoder import encode_architecture

    seeds = [
        generate_architecture(GeneratorConfig(min_nodes=4, max_nodes=6, max_links=4, seed=100 + i))
        for i in range(6)
    ]
    cfg = ClearDLoopConfig(population_size=6, n_generations=3)

    r_plain = run_clear_d_loop(
        seeds,
        encode_architecture,
        synthetic_evaluator(),
        cfg,
        random.Random(5),
        hypervolume_samples=32,
    )
    trace: list[dict[str, object]] = []
    r_traced = run_clear_d_loop(
        seeds,
        encode_architecture,
        synthetic_evaluator(),
        cfg,
        random.Random(5),
        hypervolume_samples=32,
        trace=trace,
        max_trace=1000,
    )
    assert r_plain.hypervolume_history == r_traced.hypervolume_history
    assert [gs.n_feasible for gs in r_plain.generation_stats] == [
        gs.n_feasible for gs in r_traced.generation_stats
    ]
    assert r_plain.conflict_prone_table.to_mapping() == r_traced.conflict_prone_table.to_mapping()
    assert len(trace) > 0
