"""Tests for ground transmitter mission path."""

from __future__ import annotations

from app.mission.state import (
    MissionConfig,
    UavHardware,
    _ground_to_uav_slant_range_m,
    compute_mission_state,
)


def test_ground_geometry_near_directly_overhead() -> None:
    """UAV directly above transmitter: elevation near 90 deg."""
    d_3d, elev = _ground_to_uav_slant_range_m(
        transmitter_lat_deg=40.0,
        transmitter_lon_deg=-77.0,
        transmitter_alt_m=350.0,
        uav_lat_deg=40.0,
        uav_lon_deg=-77.0,
        uav_alt_m=1350.0,
    )
    assert elev > 85.0
    assert 999.0 < d_3d < 1100.0


def test_ground_geometry_horizon_reject() -> None:
    """UAV far beyond horizon: returns zero."""
    d_3d, elev = _ground_to_uav_slant_range_m(
        transmitter_lat_deg=40.0,
        transmitter_lon_deg=-77.0,
        transmitter_alt_m=350.0,
        uav_lat_deg=40.0,
        uav_lon_deg=-60.0,  # ~1400 km east, way past horizon for 1 km UAV
        uav_alt_m=1000.0,
    )
    assert d_3d == 0.0
    assert elev == 0.0


def test_ground_geometry_elevation_decreases_with_range() -> None:
    """Elevation should decrease monotonically with horizontal distance."""
    _, elev_1 = _ground_to_uav_slant_range_m(
        transmitter_lat_deg=40.0,
        transmitter_lon_deg=-77.0,
        transmitter_alt_m=350.0,
        uav_lat_deg=40.01,
        uav_lon_deg=-77.0,
        uav_alt_m=1000.0,
    )
    _, elev_2 = _ground_to_uav_slant_range_m(
        transmitter_lat_deg=40.0,
        transmitter_lon_deg=-77.0,
        transmitter_alt_m=350.0,
        uav_lat_deg=40.1,
        uav_lon_deg=-77.0,
        uav_alt_m=1000.0,
    )
    assert elev_1 > elev_2 > 0


def test_mission_config_defaults_to_satellite() -> None:
    cfg = MissionConfig()
    assert cfg.transmitter_type == "satellite"
    assert cfg.transmitter_min_elevation_deg == 5.0


def test_mission_state_ground_transmitter() -> None:
    """When transmitter_type='ground', the mission uses the ground link."""
    cfg = MissionConfig(
        transmitter_type="ground",
        ground_lat_deg=40.798,
        ground_lon_deg=-77.86,
        ground_alt_m=350.0,
        n_uavs=3,
        transmitter_power_w=20_000.0,
        transmitter_aperture_m=0.5,
        uav_alt_m=1000.0,
        uav_hardware=UavHardware(
            receiver_aperture_m2=0.5,
            receiver_type="laser_photovoltaic",
        ),
        visibility_km=20.0,
        cloud_factor=0.0,
    )
    state = compute_mission_state(cfg)
    assert state.transmission.modality in {"laser_ground", "offline"}
    assert len(state.uavs) == 3


def test_mission_state_ground_with_power() -> None:
    """Ground transmitter with clear sky at short range delivers power."""
    # 1 kW class ground laser at ~5 km slant range — matches the PowerLight
    # PTROL-UAS DoD benchmark in spec §6. Higher power at this range drives
    # the receiver into thermal runaway (steady_state returns None), which is
    # physically correct but produces a zero delivered-power result that is
    # not what this test intends to verify.
    cfg = MissionConfig(
        transmitter_type="ground",
        ground_lat_deg=40.798,
        ground_lon_deg=-77.86,
        ground_alt_m=350.0,
        n_uavs=1,
        transmitter_power_w=1_000.0,
        transmitter_aperture_m=0.1,
        uav_alt_m=500.0,
        uav_hardware=UavHardware(
            receiver_aperture_m2=0.5,
            receiver_type="laser_photovoltaic",
        ),
        visibility_km=20.0,
        cloud_factor=0.0,
        transmitter_min_elevation_deg=1.0,
    )
    state = compute_mission_state(cfg)
    total = sum(u.delivered_power_w for u in state.uavs)
    assert total > 0.0, f"expected positive power, got {total}"


def test_mission_state_satellite_unchanged() -> None:
    """Default transmitter_type='satellite' preserves existing behavior."""
    cfg = MissionConfig(satellite_key="iss", n_uavs=2)
    state = compute_mission_state(cfg)
    assert state.transmission.modality in {"laser", "offline"}


def test_ground_geometry_symmetric_haversine() -> None:
    """Haversine is symmetric: swapping endpoints gives same horizontal distance."""
    d_ab, _ = _ground_to_uav_slant_range_m(
        transmitter_lat_deg=40.0,
        transmitter_lon_deg=-77.0,
        transmitter_alt_m=350.0,
        uav_lat_deg=40.1,
        uav_lon_deg=-76.9,
        uav_alt_m=1000.0,
    )
    d_ba, _ = _ground_to_uav_slant_range_m(
        transmitter_lat_deg=40.1,
        transmitter_lon_deg=-76.9,
        transmitter_alt_m=350.0,
        uav_lat_deg=40.0,
        uav_lon_deg=-77.0,
        uav_alt_m=1000.0,
    )
    # Same horizontal distance, same dz magnitude → same 3D distance
    assert abs(d_ab - d_ba) < 1.0


def test_get_mission_state_ground_transmitter() -> None:
    """GET /mission/state?transmitter_type=ground returns ground modality.

    Regression guard: the /mission/state endpoint must accept the
    transmitter_type query param. Without this test, only the
    MissionConfig-level code paths are exercised, and a missing HTTP
    wire-up goes undetected.
    """
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    r = client.get(
        "/mission/state",
        params={
            "transmitter_type": "ground",
            "ground_lat_deg": 40.798,
            "ground_lon_deg": -77.86,
            "n_uavs": 2,
            "transmitter_power_w": 1000.0,
            "transmitter_aperture_m": 0.1,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # Transmission modality should be laser_ground (or offline if geometry failed)
    assert body["transmission"]["modality"] in {"laser_ground", "offline"}


def test_get_mission_state_satellite_default() -> None:
    """GET /mission/state with no transmitter_type uses satellite (backward compat)."""
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    r = client.get("/mission/state")
    assert r.status_code == 200
    body = r.json()
    assert body["transmission"]["modality"] in {"laser", "offline"}
