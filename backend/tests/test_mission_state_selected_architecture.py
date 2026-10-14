"""Selected architecture overrides the generated one.

When a mission carries a selected architecture, the mission's own
encoder evaluates that topology; the ArchitectureSummary reflects the
user's selection, not a freshly sampled architecture. This test pins
that contract.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


_SELECTED = {
    "node_list": [
        {"node_id": "n0", "kind": "Satellite_LEO", "params": {}},
        {"node_id": "n1", "kind": "UAV_Energy", "params": {"battery_pct": 42.0}},
        {"node_id": "n2", "kind": "UAV_Compute", "params": {"battery_pct": 55.0}},
        {"node_id": "n3", "kind": "Ground_Station", "params": {}},
    ],
    "link_list": [
        {"link_id": "l0", "kind": "Laser_Link", "source_id": "n0", "target_id": "n1"},
        {"link_id": "l1", "kind": "Laser_Link", "source_id": "n1", "target_id": "n2"},
        {"link_id": "l2", "kind": "Laser_Link", "source_id": "n1", "target_id": "n3"},
    ],
}


def test_post_without_selection_matches_get() -> None:
    """POST with no selection behaves like the GET default."""
    r = client.post("/mission/state", json={})
    assert r.status_code == 200
    body = r.json()
    assert "architecture" in body
    assert body["architecture"]["nodes"] >= 2


def test_post_with_selection_uses_user_topology() -> None:
    r = client.post(
        "/mission/state",
        json={"selected_architecture": _SELECTED},
    )
    assert r.status_code == 200
    arch = r.json()["architecture"]
    assert arch["nodes"] == 4
    assert arch["links"] == 3
    assert arch["node_kinds"] == {
        "Satellite_LEO": 1,
        "UAV_Energy": 1,
        "UAV_Compute": 1,
        "Ground_Station": 1,
    }
    assert arch["link_kinds"] == {"Laser_Link": 3}
    # The mission's own encoder evaluated the topology; a SAT/UNSAT
    # verdict is present.
    assert arch["sat_verdict"].lower() in {"sat", "unsat"}
    assert arch["n_constraints"] > 0


def test_post_rejects_invalid_node_kind() -> None:
    bad = {
        "node_list": [
            {"node_id": "n0", "kind": "Not_A_Real_Kind", "params": {}},
            {"node_id": "n1", "kind": "UAV_Energy", "params": {}},
        ],
        "link_list": [],
    }
    r = client.post("/mission/state", json={"selected_architecture": bad})
    assert r.status_code == 400
    assert "selected_architecture" in r.json()["detail"]


def test_post_rejects_dangling_link() -> None:
    bad = {
        "node_list": [
            {"node_id": "n0", "kind": "Satellite_LEO", "params": {}},
            {"node_id": "n1", "kind": "UAV_Energy", "params": {}},
        ],
        "link_list": [
            {"link_id": "l0", "kind": "Laser_Link", "source_id": "n0", "target_id": "n99"},
        ],
    }
    r = client.post("/mission/state", json={"selected_architecture": bad})
    assert r.status_code == 400
