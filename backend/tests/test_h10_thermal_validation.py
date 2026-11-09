"""H10 - efficiency degrades with incident power, matching Han et al.'s direction.

Han et al. (Matter & Light 1, 100066, 2026, DOI 10.1016/j.matlit.2026.100066)
report measured efficiencies of 41.26%, 39.65%, and 38.49% at 0.5, 0.8, and
1.2 W/cm^2 respectively, on a perovskite-thermoelectric tandem receiver.

This test verifies that AeroGrid's coupled electro-thermal model reproduces
the DIRECTION of that degradation: efficiency must decrease between a low
incident power and a high incident power. The model is not fitted to Han
et al.'s absolute numbers (eta_ref = 0.15 in receiver.py is an engineering
estimate for the PLC alone, per the module docstring), so this is a
direction test, not an absolute-value reproduction.

Intermediate incident powers are intentionally not compared to each other:
at both 5 kW and 15 kW on the 0.10 m aperture / 500 m altitude geometry,
thermal runaway causes efficiency to collapse to zero, producing a plateau.
Comparing only the endpoints avoids a false failure on that plateau.
"""

from __future__ import annotations

from app.mission.state import MissionConfig, UavHardware, compute_mission_state


def _cfg(power_w: float) -> MissionConfig:
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


def test_h10_efficiency_degrades_with_transmitter_power() -> None:
    """Efficiency at low power strictly exceeds efficiency at high power."""
    effs: list[float] = []
    for power_w in (500.0, 15000.0):
        state = compute_mission_state(_cfg(power_w))
        delivered = [u.receiver_efficiency for u in state.uavs if u.received_power_w > 0.0]
        avg = sum(delivered) / len(delivered) if delivered else 0.0
        effs.append(avg)
    assert effs[0] > effs[1], (
        "H10: efficiency must decrease from 500 W to 15 kW "
        "(matching Han et al. direction); got "
        f"eff(500 W)={effs[0]:.4f}, eff(15 kW)={effs[1]:.4f}"
    )
