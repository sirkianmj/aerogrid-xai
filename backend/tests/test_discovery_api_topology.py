"""Topology is exposed on /discovery/run, not just counts.

The architecture-explorer panel renders the discovered architectures
as cards with mini schematics. That requires the node and link lists
per individual, not just their lengths. This test pins the contract.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.discovery.grammar import Terminal
from app.main import app

client = TestClient(app)
_VALID_KINDS = {t.value for t in Terminal}


def test_discovered_individuals_carry_topology() -> None:
    r = client.post(
        "/discovery/run",
        json={"population_size": 4, "n_generations": 1, "seed": 1},
    )
    assert r.status_code == 200
    body = r.json()
    discovered = body["discovered"]
    assert len(discovered) > 0

    for ind in discovered:
        assert ind["nodes"] == len(ind["node_list"])
        assert ind["links"] == len(ind["link_list"])
        for node in ind["node_list"]:
            assert node["kind"] in _VALID_KINDS
            assert isinstance(node["params"], dict)
        for link in ind["link_list"]:
            assert link["kind"] in _VALID_KINDS
            assert link["source_id"]
            assert link["target_id"]
