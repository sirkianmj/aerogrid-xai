"""Per-UAV hardware overrides.

MissionConfig carries an optional tuple of UavHardware. When set, UAV i
uses entry i; entries beyond the tuple fall back to the uniform
uav_hardware. This is what the design studio needs to assign distinct
receivers to distinct drones.
"""

from __future__ import annotations

from app.mission.state import (
    MissionConfig,
    UavHardware,
    compute_mission_state,
)


def test_per_uav_list_overrides_uniform() -> None:
    """UAV 0 with 5 m^2 aperture must receive more power than UAV 1
    with 0.2 m^2, all else being equal."""
    big = UavHardware(receiver_aperture_m2=5.0)
    small = UavHardware(receiver_aperture_m2=0.2)
    cfg = MissionConfig(
        seed=1,
        satellite_key="iss",
        n_uavs=2,
        uav_hardware_list=(big, small),
    )
    s = compute_mission_state(cfg)
    assert len(s.uavs) == 2
    assert s.uavs[0].delivered_power_w > s.uavs[1].delivered_power_w
    assert s.uavs[0].receiver_aperture_m2 == 5.0
    assert s.uavs[1].receiver_aperture_m2 == 0.2


def test_list_shorter_than_n_uavs_falls_back() -> None:
    """A single-entry list applies to UAV 0; the rest use uniform."""
    big = UavHardware(receiver_aperture_m2=5.0)
    uniform = UavHardware(receiver_aperture_m2=0.5)
    cfg = MissionConfig(
        seed=1,
        satellite_key="iss",
        n_uavs=3,
        uav_hardware=uniform,
        uav_hardware_list=(big,),
    )
    s = compute_mission_state(cfg)
    assert len(s.uavs) == 3
    assert s.uavs[0].receiver_aperture_m2 == 5.0
    assert s.uavs[1].receiver_aperture_m2 == 0.5
    assert s.uavs[2].receiver_aperture_m2 == 0.5


def test_none_list_uses_uniform() -> None:
    uniform = UavHardware(receiver_aperture_m2=1.0)
    cfg = MissionConfig(seed=1, satellite_key="iss", n_uavs=3, uav_hardware=uniform)
    s = compute_mission_state(cfg)
    for u in s.uavs:
        assert u.receiver_aperture_m2 == 1.0


def test_uav_hardware_carries_bus_fields() -> None:
    hw = UavHardware(
        receiver_aperture_m2=0.5,
        mass_kg=15.0,
        wingspan_m=3.5,
        battery_wh=250.0,
        thermal_limit_c=95.0,
    )
    cfg = MissionConfig(seed=1, satellite_key="iss", n_uavs=1, uav_hardware=hw)
    s = compute_mission_state(cfg)
    u = s.uavs[0]
    assert u.mass_kg == 15.0
    assert u.wingspan_m == 3.5
    assert u.battery_wh == 250.0
    assert u.thermal_limit_c == 95.0
    assert u.receiver_aperture_m2 == 0.5


def test_wing_loading_flag_is_consistent() -> None:
    """The lift flag must flip on the rule-of-thumb threshold."""
    light = UavHardware(mass_kg=2.0, wingspan_m=3.0)
    heavy = UavHardware(mass_kg=200.0, wingspan_m=3.0)
    s_light = compute_mission_state(
        MissionConfig(seed=1, satellite_key="iss", n_uavs=1, uav_hardware=light)
    )
    s_heavy = compute_mission_state(
        MissionConfig(seed=1, satellite_key="iss", n_uavs=1, uav_hardware=heavy)
    )
    assert s_light.uavs[0].lift_feasible is True
    assert s_heavy.uavs[0].lift_feasible is False
    # And the reported wing loading is mass / (0.15 * span^2).
    expected_light = 2.0 / (0.15 * 3.0**2)
    assert abs(s_light.uavs[0].wing_loading_kg_per_m2 - expected_light) < 1e-9
