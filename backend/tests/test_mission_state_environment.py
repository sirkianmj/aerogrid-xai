"""Environment parameter variation tests for /mission/state.

Exercises the two atmospheric parameters MissionConfig carries
(visibility_km, cloud_factor) and verifies that the state reacts to
them through the Kruse-Kim extinction model.

All tests use an explicit ``t_utc`` at a moment the default satellite
is above the default ground station. The satellite is not visible at
its TLE epoch from (40.798, -77.86), and the offline branch returns
``transmittance=0.0`` by design; the assertions below have nothing to
measure in that case. The timestamp is the first moment in the
24-hour window around the TLE epoch at which elevation exceeds 20°,
found by scanning the propagation in 10-minute steps.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.mission.state import MissionConfig, compute_mission_state

# First moment the ISS is above 20° elevation at the default site,
# within 24 hours of its TLE epoch.
_T_ABOVE_HORIZON = datetime(2014, 1, 21, 8, 3, 4, tzinfo=UTC)


def _state(
    *,
    visibility_km: float = 10.0,
    cloud_factor: float = 0.0,
) -> MissionConfig:
    return MissionConfig(
        seed=1,
        visibility_km=visibility_km,
        cloud_factor=cloud_factor,
    )


def test_online_branch_is_reached() -> None:
    """Sanity check: the test time really is above the horizon."""
    s = compute_mission_state(_state(), t_utc=_T_ABOVE_HORIZON)
    assert s.transmission.modality == "laser", (
        f"expected an online link at {_T_ABOVE_HORIZON}, got modality={s.transmission.modality!r}"
    )
    assert s.atmosphere.transmittance > 0.0


def test_higher_visibility_raises_transmittance() -> None:
    """Less aerosol (higher visibility) means more light gets through."""
    low = compute_mission_state(_state(visibility_km=2.0), t_utc=_T_ABOVE_HORIZON)
    high = compute_mission_state(_state(visibility_km=40.0), t_utc=_T_ABOVE_HORIZON)
    assert low.atmosphere.transmittance > 0.0
    assert high.atmosphere.transmittance > 0.0
    assert high.atmosphere.transmittance > low.atmosphere.transmittance


def test_higher_cloud_lowers_transmittance() -> None:
    """More cloud cover means more attenuation."""
    clear = compute_mission_state(_state(cloud_factor=0.0), t_utc=_T_ABOVE_HORIZON)
    cloudy = compute_mission_state(_state(cloud_factor=0.1), t_utc=_T_ABOVE_HORIZON)
    assert clear.atmosphere.transmittance > 0.0
    assert clear.atmosphere.transmittance > cloudy.atmosphere.transmittance


def test_reported_extinction_matches_visibility() -> None:
    """The reported extinction coefficient should track visibility."""
    low_vis = compute_mission_state(_state(visibility_km=2.0), t_utc=_T_ABOVE_HORIZON)
    high_vis = compute_mission_state(_state(visibility_km=40.0), t_utc=_T_ABOVE_HORIZON)
    assert low_vis.atmosphere.extinction_coeff_per_m > high_vis.atmosphere.extinction_coeff_per_m


def test_same_config_is_deterministic() -> None:
    """Two calls with the same parameters give the same result."""
    cfg = _state(visibility_km=5.0, cloud_factor=0.05)
    a = compute_mission_state(cfg, t_utc=_T_ABOVE_HORIZON)
    b = compute_mission_state(cfg, t_utc=_T_ABOVE_HORIZON)
    assert a.atmosphere.transmittance == b.atmosphere.transmittance
    assert a.atmosphere.extinction_coeff_per_m == b.atmosphere.extinction_coeff_per_m
