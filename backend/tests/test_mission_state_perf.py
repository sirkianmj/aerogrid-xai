"""The pass-scan helper is cached.

The scan is 91 percent of compute_mission_state runtime - Skyfield is
called 1440 times over the 24-hour window. Every call with the same
satellite and ground station must hit the cache after the first.
"""

from __future__ import annotations

import time

from app.mission.state import (
    MissionConfig,
    _next_visible_time,
    _scan_first_visible_pass_cached,
)
from app.physics.catalog import get_satellite


def test_second_call_is_cached() -> None:
    _scan_first_visible_pass_cached.cache_clear()
    sat = get_satellite("iss")
    cfg = MissionConfig(seed=1, satellite_key="iss")

    t0 = time.perf_counter()
    first = _next_visible_time(sat, cfg)
    first_ms = (time.perf_counter() - t0) * 1000.0

    t0 = time.perf_counter()
    second = _next_visible_time(sat, cfg)
    second_ms = (time.perf_counter() - t0) * 1000.0

    assert first == second
    assert second_ms < 5.0, f"second call took {second_ms:.1f} ms; first was {first_ms:.1f} ms"


def test_cache_clear_still_returns_correct_value() -> None:
    sat = get_satellite("iss")
    cfg = MissionConfig(seed=1, satellite_key="iss")
    a = _next_visible_time(sat, cfg)
    _scan_first_visible_pass_cached.cache_clear()
    b = _next_visible_time(sat, cfg)
    assert a == b


def test_different_ground_station_is_a_cache_miss() -> None:
    _scan_first_visible_pass_cached.cache_clear()
    sat = get_satellite("iss")
    cfg_a = MissionConfig(seed=1, satellite_key="iss", ground_lat_deg=40.798, ground_lon_deg=-77.86)
    cfg_b = MissionConfig(seed=1, satellite_key="iss", ground_lat_deg=0.0, ground_lon_deg=0.0)
    a = _next_visible_time(sat, cfg_a)
    b = _next_visible_time(sat, cfg_b)
    info = _scan_first_visible_pass_cached.cache_info()
    assert info.misses == 2, info
    assert a != b
