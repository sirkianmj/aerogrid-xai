"""Per-UAV physical link budget tests.

Verifies that every UAV in the mission state carries a delivered-power
number computed from the Section 8.4 cascade: transmitter wall-plug,
beam spreading + atmosphere, receiver conversion, battery efficiency.
The tests check physical monotonicity against the configuration inputs
rather than against hard-coded values.
"""

from __future__ import annotations

from app.mission.state import (
    MissionConfig,
    UavHardware,
    compute_mission_state,
)


def _default() -> MissionConfig:
    return MissionConfig(seed=20261014, satellite_key="iss")


def test_every_uav_has_delivered_power_field() -> None:
    s = compute_mission_state(_default())
    assert len(s.uavs) > 0
    for uav in s.uavs:
        assert uav.delivered_power_w >= 0.0
        assert uav.received_power_w >= 0.0
        assert uav.link_slant_range_m > 0.0
        assert -90.0 <= uav.link_elevation_deg <= 90.0
        assert 0.0 <= uav.receiver_efficiency <= 1.0


def test_delivered_power_is_monotone_in_receiver_aperture() -> None:
    small = compute_mission_state(
        MissionConfig(
            seed=1, satellite_key="iss", uav_hardware=UavHardware(receiver_aperture_m2=0.2)
        )
    )
    large = compute_mission_state(
        MissionConfig(
            seed=1, satellite_key="iss", uav_hardware=UavHardware(receiver_aperture_m2=2.0)
        )
    )
    # Same seed, same geometry, same weather. Delivered power at the
    # larger aperture must be greater (or equal in the pathological
    # zero-power case).
    assert large.uavs[0].received_power_w >= small.uavs[0].received_power_w
    assert large.uavs[0].delivered_power_w >= small.uavs[0].delivered_power_w


def test_received_power_scales_with_aperture_area() -> None:
    # Optical power captured by a circular aperture grows with the
    # square of radius, i.e. linearly with area, up to spillover
    # saturation.
    a = compute_mission_state(
        MissionConfig(
            seed=1, satellite_key="iss", uav_hardware=UavHardware(receiver_aperture_m2=0.5)
        )
    )
    b = compute_mission_state(
        MissionConfig(
            seed=1, satellite_key="iss", uav_hardware=UavHardware(receiver_aperture_m2=1.0)
        )
    )
    pa = a.uavs[0].received_power_w
    pb = b.uavs[0].received_power_w
    # Not a strict ratio assertion (spillover saturates), but the
    # doubled aperture cannot receive less.
    assert pb >= pa


def test_receiver_type_selects_the_model() -> None:
    pv = compute_mission_state(
        MissionConfig(
            seed=1,
            satellite_key="iss",
            uav_hardware=UavHardware(receiver_type="laser_photovoltaic"),
        )
    )
    rf = compute_mission_state(
        MissionConfig(
            seed=1, satellite_key="iss", uav_hardware=UavHardware(receiver_type="rectenna")
        )
    )
    # Both paths must produce a physically representable efficiency.
    # They may not equal each other (different models), but each must
    # be in [0, 1]. If delivered power is exactly zero for both, the
    # test would be vacuous; require the laser path to deliver
    # non-zero when the default configuration is used.
    assert 0.0 <= pv.uavs[0].receiver_efficiency <= 1.0
    assert 0.0 <= rf.uavs[0].receiver_efficiency <= 1.0
    assert pv.uavs[0].delivered_power_w > 0.0


def test_determinism() -> None:
    cfg = MissionConfig(seed=42, satellite_key="iss")
    a = compute_mission_state(cfg)
    b = compute_mission_state(cfg)
    assert a.uavs[0].delivered_power_w == b.uavs[0].delivered_power_w
    assert a.uavs[0].received_power_w == b.uavs[0].received_power_w
    assert a.uavs[0].receiver_efficiency == b.uavs[0].receiver_efficiency
