"""Tests for multi-hop UAV relay chain."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.mission.state import (
    MissionConfig,
    UavHardware,
    compute_mission_state,
)


def _base_cfg(relay: tuple[int, ...] | None) -> MissionConfig:
    return MissionConfig(
        n_uavs=3,
        ground_lat_deg=40.798,
        ground_lon_deg=-77.86,
        ground_alt_m=350.0,
        transmitter_type="ground",
        transmitter_power_w=5000.0,
        transmitter_aperture_m=0.15,
        uav_alt_m=1000.0,
        uav_hardware=UavHardware(
            receiver_aperture_m2=0.5,
            receiver_type="laser_photovoltaic",
        ),
        visibility_km=15.0,
        cloud_factor=0.0,
        transmitter_min_elevation_deg=1.0,
        relay_topology=relay,
        relay_fraction=0.7,
    )


def test_direct_mode_no_relay_note() -> None:
    """When relay_topology is None, relay_note is empty."""
    cfg = _base_cfg(None)
    state = compute_mission_state(cfg)
    assert state.transmission.relay_note == ""
    for u in state.uavs:
        assert u.relay_hop_index == -1


def test_relay_chain_3uavs_completes() -> None:
    """A chain of 3 UAVs runs without error and produces a relay note."""
    cfg = _base_cfg((0, 1, 2))
    state = compute_mission_state(cfg)
    assert "UAV-0" in state.transmission.relay_note
    assert "UAV-1" in state.transmission.relay_note
    assert "UAV-2" in state.transmission.relay_note


def test_relay_chain_hop_indices() -> None:
    """Chain members have correct hop indices; non-members have -1."""
    cfg = _base_cfg((0, 1, 2))
    state = compute_mission_state(cfg)
    uav_by_id = {u.uav_id: u for u in state.uavs}
    assert uav_by_id[0].relay_hop_index == 0
    assert uav_by_id[1].relay_hop_index == 1
    assert uav_by_id[2].relay_hop_index == 2


def test_relay_chain_all_roles_relay() -> None:
    """All chain members get role='relay'."""
    cfg = _base_cfg((0, 1))
    state = compute_mission_state(cfg)
    uav_by_id = {u.uav_id: u for u in state.uavs}
    assert uav_by_id[0].role == "relay"
    assert uav_by_id[1].role == "relay"
    # UAV-2 is not in chain, keeps its old role
    assert uav_by_id[2].role != "relay"


def test_relay_power_decreases_per_hop() -> None:
    """Received power should decrease through the chain (losses at each hop)."""
    cfg = _base_cfg((0, 1, 2))
    state = compute_mission_state(cfg)
    uav_by_id = {u.uav_id: u for u in state.uavs}
    # Each hop loses power; delivered must be non-increasing through the chain
    d0 = uav_by_id[0].delivered_power_w
    d1 = uav_by_id[1].delivered_power_w
    d2 = uav_by_id[2].delivered_power_w
    assert d0 > 0.0, f"first hop delivered must be positive, got {d0}"
    assert d1 <= d0 + 1e-9, f"hop 1 ({d1}) must be <= hop 0 ({d0})"
    assert d2 <= d1 + 1e-9, f"hop 2 ({d2}) must be <= hop 1 ({d1})"


def test_relay_non_chain_uav_zero_power() -> None:
    """UAV not in the chain gets zero delivered power."""
    cfg = _base_cfg((0, 1))  # chain only includes 0 and 1, not 2
    state = compute_mission_state(cfg)
    uav_by_id = {u.uav_id: u for u in state.uavs}
    assert uav_by_id[2].delivered_power_w == 0.0


def test_relay_forwarded_power_on_intermediate_hops() -> None:
    """Intermediate hops forward power; terminal hop does not."""
    cfg = _base_cfg((0, 1, 2))
    state = compute_mission_state(cfg)
    uav_by_id = {u.uav_id: u for u in state.uavs}
    # UAV-0 forwards to UAV-1
    assert uav_by_id[0].relay_forwarded_power_w > 0.0
    # UAV-1 forwards to UAV-2
    assert uav_by_id[1].relay_forwarded_power_w > 0.0
    # UAV-2 is terminal, forwards nothing
    assert uav_by_id[2].relay_forwarded_power_w == 0.0


def test_relay_out_of_range_rejected() -> None:
    """UAV ID outside [0, n_uavs) raises ValueError."""
    cfg = _base_cfg((0, 5))
    with pytest.raises(ValueError, match="outside"):
        compute_mission_state(cfg)


def test_relay_duplicate_rejected() -> None:
    """Duplicate UAV IDs raise ValueError."""
    cfg = _base_cfg((0, 1, 1))
    with pytest.raises(ValueError, match="duplicate"):
        compute_mission_state(cfg)


def test_relay_empty_tuple_rejected() -> None:
    """An empty non-None relay_topology raises ValueError."""
    cfg = _base_cfg(())
    with pytest.raises(ValueError, match="non-empty"):
        compute_mission_state(cfg)


def test_relay_fraction_validation() -> None:
    """relay_fraction outside (0, 1] raises ValueError."""
    cfg = _base_cfg((0, 1))
    cfg = MissionConfig(
        n_uavs=cfg.n_uavs,
        ground_lat_deg=cfg.ground_lat_deg,
        ground_lon_deg=cfg.ground_lon_deg,
        ground_alt_m=cfg.ground_alt_m,
        transmitter_type="ground",
        transmitter_power_w=cfg.transmitter_power_w,
        transmitter_aperture_m=cfg.transmitter_aperture_m,
        uav_alt_m=cfg.uav_alt_m,
        uav_hardware=cfg.uav_hardware,
        visibility_km=cfg.visibility_km,
        cloud_factor=cfg.cloud_factor,
        transmitter_min_elevation_deg=cfg.transmitter_min_elevation_deg,
        relay_topology=(0, 1),
        relay_fraction=1.5,
    )
    with pytest.raises(ValueError, match="relay_fraction"):
        compute_mission_state(cfg)


def test_get_mission_state_with_relay() -> None:
    """GET /mission/state with relay_topology query param works."""
    client = TestClient(app)
    r = client.get(
        "/mission/state",
        params={
            "transmitter_type": "ground",
            "relay_topology": "0,1",
            "n_uavs": 3,
            "transmitter_power_w": 5000.0,
            "transmitter_aperture_m": 0.15,
            "transmitter_min_elevation_deg": 1.0,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "UAV-0" in body["transmission"].get("relay_note", "")


def test_post_mission_state_with_relay() -> None:
    """POST /mission/state with relay_topology in body works."""
    client = TestClient(app)
    r = client.post(
        "/mission/state",
        json={
            "transmitter_type": "ground",
            "relay_topology": [0, 1],
            "n_uavs": 3,
            "transmitter_power_w": 5000.0,
            "transmitter_aperture_m": 0.15,
            "transmitter_min_elevation_deg": 1.0,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "UAV-0" in body["transmission"].get("relay_note", "")


def test_simulation_run_with_relay() -> None:
    """POST /simulation/run with relay_topology produces non-error response."""
    client = TestClient(app)
    r = client.post(
        "/simulation/run",
        json={
            "preset": "10min",
            "transmitter_type": "ground",
            "relay_topology": [0, 1],
            "n_uavs": 3,
            "transmitter_power_w": 5000.0,
            "transmitter_aperture_m": 0.15,
            "transmitter_min_elevation_deg": 1.0,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["n_samples"] >= 2
    assert len(body["samples"]) > 0
