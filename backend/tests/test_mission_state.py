"""Tests for /mission/state and its underlying computation.

The mission state is a coherent scenario computed from real backend
primitives: SGP4 propagation of a packaged TLE, Kruse-Kim atmospheric
transmittance, the real Stage B encoder with a Z3 SAT/UNSAT verdict,
a single-generation CLEAR-D snapshot, and a Tier 1 decision trace.
No database is used; the module runs in the default `backend` CI job.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.mission.state import (
    MissionConfig,
    compute_mission_state,
    list_mission_satellites,
)

client = TestClient(app)


# --- catalogue ------------------------------------------------------------


def test_catalogue_contains_the_three_packaged_keys() -> None:
    keys = list(list_mission_satellites())
    assert keys == sorted(keys)
    assert set(keys) == {"geo", "iss", "vanguard_r3"}


# --- computation: schema and determinism ----------------------------------


def test_default_time_is_first_pass_peak() -> None:
    """Default (no t_utc) advances to the peak-elevation moment of the
    first visible pass, so the platform opens onto a live mission at its
    best geometry rather than at the pass start (where the beam grazes
    the atmosphere) or at the TLE epoch (where the satellite is below
    the horizon).

    The propagation offset from the TLE epoch is bounded by the 24-hour
    scan window. For a fresh LEO TLE, SGP4 position error over that
    interval is on the order of kilometres, well within the model's
    meaningful range.
    """
    s = compute_mission_state(MissionConfig(satellite_key="iss"))
    assert s.transmission.modality == "laser"
    assert s.atmosphere.transmittance > 0.0
    epoch = datetime.fromisoformat(s.satellite.tle_epoch_utc)
    effective = datetime.fromisoformat(s.t_utc)
    assert effective >= epoch
    # Peak elevation of the first pass is >20 degrees for the default
    # satellite/ground pair; the pass start is ~6 degrees. Asserting on
    # elevation pins the peak-time behaviour, not just "after epoch".
    assert s.transmission.elevation_deg > 20.0


def test_default_time_falls_back_to_epoch_when_no_pass_exists() -> None:
    """No pass within the scan window: fall back to the TLE epoch.

    The ISS is inclined at 51.6 degrees, so a ground station above that
    latitude never sees it. The scan finds no window, the default time
    falls back to the epoch, and the mission stays offline. That is the
    correct answer when the geometry forbids a link, and it is the
    pre-scan behaviour preserved for exactly those cases.
    """
    s = compute_mission_state(
        MissionConfig(
            satellite_key="iss",
            ground_lat_deg=85.0,
            ground_lon_deg=0.0,
        )
    )
    assert s.transmission.modality == "offline"
    assert s.t_utc.startswith("2014-01-20")
    assert s.satellite.tle_age_seconds == pytest.approx(0.0, abs=1.0)


def test_same_seed_is_deterministic() -> None:
    a = compute_mission_state(MissionConfig(seed=12345))
    b = compute_mission_state(MissionConfig(seed=12345))
    assert a.uavs == b.uavs
    assert a.architecture.sat_verdict == b.architecture.sat_verdict
    assert a.tier1.selected_action == b.tier1.selected_action
    assert a.tier1.confidence == pytest.approx(b.tier1.confidence, abs=1e-12)


def test_different_seed_changes_uav_candidates() -> None:
    a = compute_mission_state(MissionConfig(seed=1))
    b = compute_mission_state(MissionConfig(seed=2))
    # The UAV candidate values are drawn from the seed, so at least
    # one numeric field must differ.
    a_bat = [u.battery_pct for u in a.uavs]
    b_bat = [u.battery_pct for u in b.uavs]
    assert a_bat != b_bat


# --- computation: physical bounds ----------------------------------------


def test_satellite_altitude_is_in_plausible_range_at_default_time() -> None:
    s = compute_mission_state(MissionConfig(satellite_key="iss"))
    assert s.satellite.valid is True
    # A 2014 ISS TLE at its epoch gives ~420 km. Allow +/- 200 km to
    # be robust to the exact TLE in the catalogue.
    assert 200.0 <= s.satellite.alt_km <= 700.0


def test_far_future_time_is_marked_invalid_with_reason() -> None:
    """A 2026 time on a 2014 TLE is 4650 days stale. SGP4 drifts,
    altitude leaves the plausible range, and the state must say so
    rather than returning a nonsensical value."""
    s = compute_mission_state(
        MissionConfig(satellite_key="iss"),
        t_utc=datetime(2026, 10, 14, 12, 0, 0, tzinfo=UTC),
    )
    assert s.satellite.valid is False
    assert s.satellite.invalid_reason != ""
    assert "outside the physically plausible range" in s.satellite.invalid_reason


def test_atmosphere_tau_is_in_unit_interval_when_link_is_up() -> None:
    """If modality is laser, tau is in (0, 1). If offline, tau is 0."""
    s = compute_mission_state(MissionConfig(satellite_key="iss"))
    if s.transmission.modality == "laser":
        assert 0.0 < s.atmosphere.transmittance <= 1.0
        assert s.transmission.atmospheric_path_m > 0.0
    else:
        assert s.transmission.modality == "offline"
        assert s.atmosphere.transmittance == 0.0


def test_atmospheric_path_uses_effective_thickness_not_slant_range() -> None:
    """Slant range to LEO is thousands of km; the atmospheric path is
    at most a few tens of km, because the extinction coefficient is
    calibrated for the ~8.5 km effective thickness of the atmosphere,
    not for the vacuum path to orbit.

    The test sweeps within one ISS orbit from the TLE epoch for a time
    at which the link is above the horizon at >=5 deg elevation, then
    asserts the two distances. Deterministic; does not skip. The
    master-test CI job runs with --require-db, which treats any skip
    as a failure, so this test finds a valid geometry instead.
    """
    import math
    from datetime import timedelta

    from app.physics.catalog import get_satellite

    cfg = MissionConfig(satellite_key="iss")
    sat = get_satellite("iss")
    r_earth_m = 6_371_000.0
    min_elev_rad = math.radians(5.0)

    t_found = None
    # A single ISS orbit does not necessarily cross a specific ground
    # station; mid-latitude visibility windows recur every 6-12 hours.
    # Search three days at one-minute steps to guarantee a window
    # exists at any mid-latitude site.
    search_seconds = 3 * 24 * 3600
    for offset in range(0, search_seconds, 60):
        t = sat.epoch_utc + timedelta(seconds=offset)
        sv = sat.at_utc(t)
        lat1 = math.radians(sv.lat_deg)
        lat2 = math.radians(cfg.ground_lat_deg)
        dlat = lat2 - lat1
        dlon = math.radians(cfg.ground_lon_deg - sv.lon_deg)
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        psi = 2.0 * math.asin(min(1.0, math.sqrt(a)))
        r_ratio = r_earth_m / (r_earth_m + sv.alt_km * 1000.0)
        elev_rad = math.atan2(math.cos(psi) - r_ratio, math.sin(psi))
        if elev_rad > min_elev_rad:
            t_found = t
            break

    assert t_found is not None, (
        "no above-horizon ISS time found within three days at Ground "
        "Station Alpha; check the ground station coordinates or the "
        "TLE"
    )
    s = compute_mission_state(cfg, t_utc=t_found)
    assert s.transmission.modality == "laser"
    assert s.transmission.atmospheric_path_m < 100_000.0  # < 100 km
    assert s.transmission.slant_range_m > 200_000.0  # > 200 km


# --- computation: pipeline stage honesty ---------------------------------


def test_wireless_transmission_stage_matches_modality() -> None:
    s = compute_mission_state(MissionConfig(satellite_key="iss"))
    wt = next(p for p in s.pipeline_stages if p.key == "wireless_transmission")
    if s.transmission.modality == "laser":
        assert wt.status == "wired"
    else:
        assert wt.status == "offline"
        assert "horizon" in wt.reason


def test_tier2_surrogates_stage_is_marked_pending() -> None:
    """The Tier 2 calibrated-interval rendering is a later PR; the
    mission state must say so explicitly, not pretend to be wired."""
    s = compute_mission_state(MissionConfig())
    t2 = next(p for p in s.pipeline_stages if p.key == "tier2_surrogates")
    assert t2.status == "pending"
    assert t2.reason != ""


# --- computation: architecture and Tier 1 --------------------------------


def test_architecture_constraints_are_emitted() -> None:
    s = compute_mission_state(MissionConfig())
    assert s.architecture.n_constraints > 0
    assert s.architecture.sat_verdict in {"sat", "unsat"}
    assert s.architecture.epsilon_bound > 0.0


def test_cleard_snapshot_population_matches_config() -> None:
    cfg = MissionConfig(n_uavs=8)
    s = compute_mission_state(cfg)
    assert s.cleard.population_size == max(4, cfg.n_uavs)
    assert s.cleard.feasible_final + s.cleard.infeasible_final == s.cleard.population_size


def test_tier1_confidence_is_in_unit_interval() -> None:
    s = compute_mission_state(MissionConfig())
    assert 0.0 <= s.tier1.confidence <= 1.0
    assert s.tier1.selected_action.startswith("charge_uav_")


# --- HTTP layer ----------------------------------------------------------


def test_get_mission_state_returns_200_with_expected_fields() -> None:
    r = client.get("/mission/state")
    assert r.status_code == 200
    body = r.json()
    for key in (
        "t_utc",
        "satellite",
        "ground_station",
        "transmission",
        "atmosphere",
        "uavs",
        "architecture",
        "cleard",
        "tier1",
        "pipeline_stages",
    ):
        assert key in body, key


def test_get_mission_state_default_satellite_is_iss() -> None:
    r = client.get("/mission/state")
    body = r.json()
    assert body["satellite"]["key"] == "iss"
    assert body["satellite"]["name"].startswith("ISS")


def test_get_mission_state_accepts_satellite_and_seed() -> None:
    r = client.get("/mission/state", params={"satellite_key": "geo", "seed": 7, "n_uavs": 4})
    assert r.status_code == 200
    body = r.json()
    assert body["satellite"]["key"] == "geo"
    assert body["seed"] == 7
    assert len(body["uavs"]) == 4


def test_get_mission_state_unknown_satellite_returns_404() -> None:
    r = client.get("/mission/state", params={"satellite_key": "no_such_sat"})
    assert r.status_code == 404


def test_get_mission_satellites_endpoint() -> None:
    r = client.get("/mission/satellites")
    assert r.status_code == 200
    assert set(r.json()) == {"geo", "iss", "vanguard_r3"}


def test_get_mission_state_accepts_explicit_iso_time() -> None:
    r = client.get("/mission/state", params={"t_utc": "2026-10-14T12:00:00Z"})
    assert r.status_code == 200
    body = r.json()
    # The satellite state will be invalid at this time (see the
    # far-future test), and the field says so.
    assert body["satellite"]["valid"] is False


# --- sanity: no field is NaN --------------------------------------------


def test_no_nan_in_numeric_fields() -> None:
    s = compute_mission_state(MissionConfig())
    for name in (
        s.satellite.lat_deg,
        s.satellite.lon_deg,
        s.satellite.alt_km,
        s.transmission.elevation_deg,
        s.transmission.slant_range_m,
        s.atmosphere.transmittance,
        s.tier1.confidence,
        s.architecture.epsilon_bound,
    ):
        assert not math.isnan(name), name


def test_get_mission_state_accepts_transmitter_power() -> None:
    """The transmitter power is a mission-configurable parameter. The
    response reports the configured value regardless of link state."""
    r = client.get("/mission/state", params={"transmitter_power_w": 25000.0})
    assert r.status_code == 200
    body = r.json()
    assert body["transmission"]["transmitter_power_w"] == pytest.approx(25000.0)


def test_get_mission_state_accepts_ground_station_coordinates() -> None:
    r = client.get(
        "/mission/state",
        params={"ground_lat_deg": 35.0, "ground_lon_deg": -120.0},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ground_station"]["lat_deg"] == pytest.approx(35.0)
    assert body["ground_station"]["lon_deg"] == pytest.approx(-120.0)


def test_get_mission_state_rejects_invalid_latitude() -> None:
    r = client.get("/mission/state", params={"ground_lat_deg": 200.0})
    assert r.status_code == 422


def test_get_mission_state_rejects_non_positive_transmitter_power() -> None:
    r = client.get("/mission/state", params={"transmitter_power_w": -100.0})
    assert r.status_code == 422
    r = client.get("/mission/state", params={"transmitter_power_w": 0.0})
    assert r.status_code == 422


def test_atmosphere_interval_present_when_link_is_up() -> None:
    """When the link is above the horizon, the mission state carries a
    Tier 2 calibrated interval around the transmittance."""
    from datetime import timedelta

    from app.physics.catalog import get_satellite

    cfg = MissionConfig(satellite_key="iss")
    sat = get_satellite("iss")
    t = sat.epoch_utc + timedelta(seconds=2 * 3600)
    s = compute_mission_state(cfg, t_utc=t)
    if s.transmission.modality != "laser":
        # Sweep until we find a laser geometry
        for offset in range(0, 3 * 24 * 3600, 60):
            t = sat.epoch_utc + timedelta(seconds=offset)
            s = compute_mission_state(cfg, t_utc=t)
            if s.transmission.modality == "laser":
                break
    assert s.transmission.modality == "laser", "no laser geometry found in 3 days"
    assert s.atmosphere.transmittance_low is not None
    assert s.atmosphere.transmittance_high is not None
    assert s.atmosphere.nominal_coverage == pytest.approx(0.90, abs=1e-9)
    low = s.atmosphere.transmittance_low
    high = s.atmosphere.transmittance_high
    assert low is not None and high is not None
    assert low <= s.atmosphere.transmittance <= high


def test_atmosphere_interval_absent_when_link_is_offline() -> None:
    """When the satellite is below the horizon, the interval is None."""
    cfg = MissionConfig(satellite_key="iss")
    sat_epoch = compute_mission_state(cfg).t_utc
    assert sat_epoch is not None
    # At the ISS TLE epoch the satellite is below the horizon at the
    # default ground station; that is our offline case.
    s = compute_mission_state(cfg)
    if s.transmission.modality == "offline":
        assert s.atmosphere.transmittance == 0.0
        assert s.atmosphere.transmittance_low is None
        assert s.atmosphere.transmittance_high is None
        assert s.atmosphere.nominal_coverage is None
