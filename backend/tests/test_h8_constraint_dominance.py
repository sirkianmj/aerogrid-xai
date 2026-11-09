"""H8 — thermal limiting in the high-power small-UAV regime.

The claim (docs/SCIENTIFIC_CLAIMS.md, H8):

    Thermal management is the dominant limiting factor on continuous
    high-power laser reception for small UAVs.

The scope is explicit: high-power reception, small UAVs. The correct
test of a thermal-limiting claim is that the receiver's conversion
efficiency *drops* as incident power grows — same geometry, same
atmosphere, only the input power changes. That isolates the thermal
contribution from atmospheric and geometric losses.

The test does not compare the ground-station transmittance to the
per-UAV receiver efficiency: those reflect different links and would be
comparing apples to oranges. It compares the SAME UAV, at two power
levels, with everything else held constant.
"""

from __future__ import annotations

from app.mission.state import (
    MissionConfig,
    MissionState,
    UavHardware,
    UavState,
    compute_mission_state,
)


def _base_cfg(power_w: float) -> MissionConfig:
    """A short-range ground-to-air link at fixed geometry."""
    return MissionConfig(
        n_uavs=2,
        transmitter_type="ground",
        transmitter_min_elevation_deg=1.0,
        ground_lat_deg=40.798,
        ground_lon_deg=-77.86,
        ground_alt_m=350.0,
        transmitter_power_w=power_w,
        transmitter_aperture_m=0.10,
        uav_alt_m=500.0,
        uav_hardware=UavHardware(
            receiver_aperture_m2=0.5,
            receiver_type="laser_photovoltaic",
        ),
        visibility_km=20.0,
        cloud_factor=0.0,
    )


def _avg_receiver_efficiency(state: MissionState) -> tuple[float, list[float]]:
    effs = [u.receiver_efficiency for u in state.uavs if u.received_power_w > 0.0]
    if not effs:
        return 0.0, []
    return sum(effs) / len(effs), effs


def test_h8_receiver_efficiency_drops_with_power() -> None:
    """Same geometry, same atmosphere — only power changes. Efficiency drops.

    This is the direct demonstration of a thermal limiting factor: if
    efficiency fell because of atmosphere or beam geometry, it would
    not change with transmitter power at fixed geometry.
    """
    low = compute_mission_state(_base_cfg(500.0))
    high = compute_mission_state(_base_cfg(15000.0))

    avg_low, effs_low = _avg_receiver_efficiency(low)
    avg_high, effs_high = _avg_receiver_efficiency(high)

    # Both runs must deliver power so the comparison is meaningful.
    assert len(effs_low) > 0, (
        "low-power run must deliver power to at least one UAV; "
        f"received_power_w={[u.received_power_w for u in low.uavs]}"
    )
    assert len(effs_high) > 0, (
        "high-power run must deliver power to at least one UAV; "
        f"received_power_w={[u.received_power_w for u in high.uavs]}"
    )

    # The high-power run must show LOWER efficiency than the low-power
    # run. The drop is the thermal effect made visible.
    assert avg_high < avg_low, (
        f"receiver efficiency must drop as incident power grows "
        f"(thermal limiting); low={avg_low:.4f} effs={effs_low}, "
        f"high={avg_high:.4f} effs={effs_high}"
    )


def test_h8_high_power_reaches_thermal_runaway_or_reduced_efficiency() -> None:
    """At the claim's high-power end, either thermal runaway or efficiency < 30%.

    The claim is about *high-power* reception. At 15 kW with a 0.10 m
    aperture on a 500 m altitude UAV, the incident power is far above
    what a small perovskite-TE receiver can reject. The result must be
    either thermal runaway (delivered = 0, receiver_efficiency = 0) or
    a strongly reduced efficiency. A run where efficiency stays near
    nominal would contradict the thermal-dominance claim.
    """
    state = compute_mission_state(_base_cfg(15000.0))

    uavs_with_power = [u for u in state.uavs if u.received_power_w > 0.0]
    assert len(uavs_with_power) > 0, (
        "high-power run must deliver power to at least one UAV; "
        f"received_power_w={[u.received_power_w for u in state.uavs]}"
    )

    def is_thermally_limited(u: UavState) -> bool:
        return u.thermal_runaway or u.receiver_efficiency < 0.30

    assert all(is_thermally_limited(u) for u in uavs_with_power), (
        "all UAVs at 15 kW should be thermally limited "
        "(runaway or efficiency < 0.30); got "
        f"{[(u.thermal_runaway, u.receiver_efficiency) for u in uavs_with_power]}"
    )
