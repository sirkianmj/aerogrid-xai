"""Tests for the additive physics extension of the encoder."""

from __future__ import annotations

import pytest

from app.discovery.attribution import ConflictProneTable, attribute_and_mark
from app.discovery.grammar import Architecture, LinkInstance, NodeInstance, Terminal
from app.discovery.unsat import UnsatCoreExtractor
from app.verification.architecture_encoder import (
    EncoderConfig,
    SceneConfig,
    _has_line_of_sight,
    _node_position_m,
    _range_m,
    encode_architecture,
    encode_architecture_with_physics,
)

# -- Helpers ---------------------------------------------------------------


def _leo_at(lat: float, lon: float, alt_km: float = 500.0) -> NodeInstance:
    return NodeInstance(
        node_id="n_sat",
        kind=Terminal.SATELLITE_LEO,
        params={
            "altitude_km": alt_km,
            "power_w": 1000.0,
            "lat_deg": lat,
            "lon_deg": lon,
        },
    )


def _ground_at(lat: float, lon: float, node_id: str = "n_gs") -> NodeInstance:
    return NodeInstance(
        node_id=node_id,
        kind=Terminal.GROUND_STATION,
        params={
            "lat_deg": lat,
            "lon_deg": lon,
            "altitude_m": 0.0,
            "power_w": 100.0,
        },
    )


def _uav_at(lat: float, lon: float, alt_m: float = 100.0) -> NodeInstance:
    return NodeInstance(
        node_id="n_uav",
        kind=Terminal.UAV_ENERGY,
        params={
            "role": 0.0,
            "battery_pct": 50.0,
            "lat_deg": lat,
            "lon_deg": lon,
            "altitude_m": alt_m,
        },
    )


def _laser_link(
    source_id: str,
    target_id: str,
    wavelength_nm: float = 1064.0,
    aperture_m: float = 0.5,
) -> LinkInstance:
    return LinkInstance(
        link_id="l0",
        kind=Terminal.LASER_LINK,
        source_id=source_id,
        target_id=target_id,
        params={
            "wavelength_nm": wavelength_nm,
            "aperture_m": aperture_m,
            "capacity_factor": 1.0,
        },
    )


def _microwave_link(
    source_id: str,
    target_id: str,
    frequency_ghz: float = 2.45,
    aperture_m: float = 0.5,
) -> LinkInstance:
    return LinkInstance(
        link_id="l0",
        kind=Terminal.MICROWAVE_LINK,
        source_id=source_id,
        target_id=target_id,
        params={
            "frequency_ghz": frequency_ghz,
            "aperture_m": aperture_m,
            "capacity_factor": 1.0,
        },
    )


def _hybrid_link(
    source_id: str,
    target_id: str,
    wavelength_nm: float = 1064.0,
    frequency_ghz: float = 2.45,
    aperture_m: float = 0.5,
) -> LinkInstance:
    return LinkInstance(
        link_id="l0",
        kind=Terminal.HYBRID_LINK,
        source_id=source_id,
        target_id=target_id,
        params={
            "wavelength_nm": wavelength_nm,
            "frequency_ghz": frequency_ghz,
            "aperture_m": aperture_m,
            "capacity_factor": 1.0,
        },
    )


# -- SceneConfig -----------------------------------------------------------


def test_scene_config_defaults_are_valid() -> None:
    s = SceneConfig()
    assert s.visibility_km > 0.0
    assert 0.0 <= s.cloud_factor <= 1.0
    assert 0.0 < s.battery_efficiency <= 1.0
    assert s.transmitter_waist_radius_m > 0.0
    assert 0.0 < s.rf_transmittance <= 1.0


def test_scene_config_rejects_bad_visibility() -> None:
    with pytest.raises(ValueError, match="visibility_km"):
        SceneConfig(visibility_km=0.0)
    with pytest.raises(ValueError, match="visibility_km"):
        SceneConfig(visibility_km=-1.0)


def test_scene_config_rejects_bad_cloud_factor() -> None:
    with pytest.raises(ValueError, match="cloud_factor"):
        SceneConfig(cloud_factor=-0.1)
    with pytest.raises(ValueError, match="cloud_factor"):
        SceneConfig(cloud_factor=1.1)


def test_scene_config_rejects_bad_battery_efficiency() -> None:
    with pytest.raises(ValueError, match="battery_efficiency"):
        SceneConfig(battery_efficiency=0.0)
    with pytest.raises(ValueError, match="battery_efficiency"):
        SceneConfig(battery_efficiency=1.5)


def test_scene_config_rejects_bad_waist() -> None:
    with pytest.raises(ValueError, match="transmitter_waist_radius_m"):
        SceneConfig(transmitter_waist_radius_m=0.0)


def test_scene_config_rejects_bad_rf_transmittance() -> None:
    with pytest.raises(ValueError, match="rf_transmittance"):
        SceneConfig(rf_transmittance=0.0)
    with pytest.raises(ValueError, match="rf_transmittance"):
        SceneConfig(rf_transmittance=1.5)


# -- Geometry helper -------------------------------------------------------


def test_node_position_at_origin_meridian() -> None:
    """lat=0, lon=0, alt=0 -> (R, 0, 0)."""
    node = _ground_at(0.0, 0.0)
    x, y, z = _node_position_m(node)
    assert x == pytest.approx(6_371_000.0, rel=1e-12)
    assert y == pytest.approx(0.0, abs=1e-6)
    assert z == pytest.approx(0.0, abs=1e-6)


def test_node_position_at_north_pole() -> None:
    """lat=90, lon=0, alt=0 -> (0, 0, R)."""
    node = _ground_at(90.0, 0.0)
    x, y, z = _node_position_m(node)
    assert x == pytest.approx(0.0, abs=1e-6)
    assert y == pytest.approx(0.0, abs=1e-6)
    assert z == pytest.approx(6_371_000.0, rel=1e-12)


def test_node_position_accounts_for_altitude_km() -> None:
    """A LEO satellite at 500 km altitude has radius R + 500 km."""
    node = _leo_at(0.0, 0.0, alt_km=500.0)
    x, _, _ = _node_position_m(node)
    assert x == pytest.approx(6_371_000.0 + 500_000.0, rel=1e-12)


def test_range_between_antipodal_ground_points() -> None:
    """Two points on the surface at antipodes: distance is 2R."""
    a = _node_position_m(_ground_at(0.0, 0.0, "n1"))
    b = _node_position_m(_ground_at(0.0, 180.0, "n2"))
    assert _range_m(a, b) == pytest.approx(2.0 * 6_371_000.0, rel=1e-9)


def test_range_between_satellite_and_subpoint() -> None:
    """Satellite at 500 km altitude directly above a ground point:
    distance equals altitude."""
    sat = _node_position_m(_leo_at(0.0, 0.0, alt_km=500.0))
    ground = _node_position_m(_ground_at(0.0, 0.0))
    assert _range_m(sat, ground) == pytest.approx(500_000.0, rel=1e-9)


# -- Line of sight ---------------------------------------------------------


def test_line_of_sight_between_antipodal_ground_points_is_false() -> None:
    """The straight segment between antipodal ground points passes
    through the Earth's centre."""
    a = _node_position_m(_ground_at(0.0, 0.0, "n1"))
    b = _node_position_m(_ground_at(0.0, 180.0, "n2"))
    assert not _has_line_of_sight(a, b)


def test_line_of_sight_from_satellite_to_far_side_is_false() -> None:
    """A LEO satellite on one side does not see a ground station on
    the opposite side."""
    sat = _node_position_m(_leo_at(0.0, 0.0, alt_km=500.0))
    far_ground = _node_position_m(_ground_at(0.0, 180.0))
    assert not _has_line_of_sight(sat, far_ground)


def test_line_of_sight_from_satellite_to_near_side_is_true() -> None:
    """A LEO satellite at 500 km sees a ground point a few degrees away."""
    sat = _node_position_m(_leo_at(0.0, 0.0, alt_km=500.0))
    near_ground = _node_position_m(_ground_at(0.0, 5.0))
    assert _has_line_of_sight(sat, near_ground)


def test_line_of_sight_between_two_points_at_same_location_is_true() -> None:
    """Coincident points have trivially cleared line of sight."""
    p = _node_position_m(_ground_at(45.0, 45.0))
    assert _has_line_of_sight(p, p)


# -- Encoder: superset relation --------------------------------------------


def test_physics_encoding_is_superset_of_flow_encoding() -> None:
    """Every base family appears in the physics encoding."""
    sat = _leo_at(0.0, 0.0, alt_km=500.0)
    gs = _ground_at(0.0, 5.0)
    uav = _uav_at(0.0, 3.0)
    link = _laser_link("n_sat", "n_uav", aperture_m=1.0)
    arch = Architecture(nodes=(sat, gs, uav), links=(link,))

    base = encode_architecture(arch)
    physics = encode_architecture_with_physics(arch)
    base_names = {c.family_name for c in base}
    phys_names = {c.family_name for c in physics}
    assert base_names.issubset(phys_names)


def test_physics_encoding_is_strictly_larger_when_los_holds() -> None:
    """With LOS, the physics set has strictly more constraints than base."""
    sat = _leo_at(0.0, 0.0, alt_km=500.0)
    gs = _ground_at(0.0, 5.0)
    uav = _uav_at(0.0, 3.0)
    link = _laser_link("n_sat", "n_uav", aperture_m=1.0)
    arch = Architecture(nodes=(sat, gs, uav), links=(link,))

    base = encode_architecture(arch)
    physics = encode_architecture_with_physics(arch)
    assert len(physics) > len(base)
    assert any("physical_flow_cap" in c.family_name for c in physics)


# -- Encoder: LOS makes an architecture UNSAT ------------------------------


def test_physics_encoder_unsat_when_link_crosses_earth() -> None:
    """A satellite-to-UAV link that passes through the Earth is UNSAT
    under the physics encoder, via the physical_los family."""
    sat = _leo_at(0.0, 0.0, alt_km=500.0)
    uav = _uav_at(0.0, 180.0)  # antipodal UAV
    link = _laser_link("n_sat", "n_uav", aperture_m=1.0)
    arch = Architecture(nodes=(sat, uav), links=(link,))

    ext = UnsatCoreExtractor()
    for c in encode_architecture_with_physics(arch):
        ext.add(c.to_named())
    result = ext.check()
    assert result.status == "unsat"
    assert "l0_physical_los" in result.core_names


def test_physics_encoder_sat_when_los_holds_and_power_sufficient() -> None:
    """A satellite-to-UAV link in direct view with generous power,
    a large aperture, and an explicit receiver efficiency is SAT.

    The receiver override is required because the tandem model at
    reference temperatures returns ~0.15 percent, which is far below
    any defensible number for a real receiver (see Decision 4)."""
    sat = _leo_at(0.0, 0.0, alt_km=500.0)
    uav = _uav_at(0.0, 1.0)
    link = _laser_link("n_sat", "n_uav", aperture_m=5.0)
    arch = Architecture(nodes=(sat, uav), links=(link,))
    scene = SceneConfig(receiver_conversion_efficiency=0.25)

    ext = UnsatCoreExtractor()
    for c in encode_architecture_with_physics(arch, scene=scene):
        ext.add(c.to_named())
    assert ext.check().status == "sat"


# -- Encoder: monotonicity -------------------------------------------------


def test_physical_flow_cap_decreases_with_distance() -> None:
    """For a fixed source and aperture, further targets have lower
    physical flow cap (more beam spreading and atmospheric loss)."""
    from app.verification.architecture_encoder import _physical_link_delivered_w

    sat = _leo_at(0.0, 0.0, alt_km=500.0)
    near_uav = _uav_at(0.0, 1.0)
    far_uav = _uav_at(0.0, 30.0)
    link_near = _laser_link("n_sat", "n_uav", aperture_m=1.0)
    link_far = _laser_link("n_sat", "n_uav", aperture_m=1.0)
    # Both use same link ID; separate calls with different UAV positions
    arch_near = Architecture(nodes=(sat, near_uav), links=(link_near,))
    arch_far = Architecture(nodes=(sat, far_uav), links=(link_far,))

    scene = SceneConfig()
    cfg = EncoderConfig()

    pos_sat = _node_position_m(sat)
    pos_near = _node_position_m(near_uav)
    pos_far = _node_position_m(far_uav)
    range_near = _range_m(pos_sat, pos_near)
    range_far = _range_m(pos_sat, pos_far)
    assert range_far > range_near

    delivered_near = _physical_link_delivered_w(arch_near, link_near, range_near, scene, cfg)
    delivered_far = _physical_link_delivered_w(arch_far, link_far, range_far, scene, cfg)
    assert delivered_far < delivered_near


def test_physical_flow_cap_decreases_with_cloud() -> None:
    from app.verification.architecture_encoder import _physical_link_delivered_w

    sat = _leo_at(0.0, 0.0, alt_km=500.0)
    uav = _uav_at(0.0, 2.0)
    link = _laser_link("n_sat", "n_uav", aperture_m=1.0)
    arch = Architecture(nodes=(sat, uav), links=(link,))

    p_sat = _node_position_m(sat)
    p_uav = _node_position_m(uav)
    range_m = _range_m(p_sat, p_uav)

    cfg = EncoderConfig()
    clear = SceneConfig(cloud_factor=0.0)
    cloudy = SceneConfig(cloud_factor=0.9)

    delivered_clear = _physical_link_delivered_w(arch, link, range_m, clear, cfg)
    delivered_cloudy = _physical_link_delivered_w(arch, link, range_m, cloudy, cfg)
    assert delivered_cloudy < delivered_clear


# -- Hybrid: min of two modalities -----------------------------------------


def test_hybrid_uses_weaker_modality() -> None:
    """Hybrid delivered power is the minimum of the laser and RF chains."""
    from app.verification.architecture_encoder import (
        _laser_chain_efficiency,
        _physical_link_delivered_w,
        _rf_chain_efficiency,
    )

    sat = _leo_at(0.0, 0.0, alt_km=500.0)
    uav = _uav_at(0.0, 2.0)
    hybrid = _hybrid_link("n_sat", "n_uav", aperture_m=1.0)
    arch = Architecture(nodes=(sat, uav), links=(hybrid,))

    p_sat = _node_position_m(sat)
    p_uav = _node_position_m(uav)
    range_m = _range_m(p_sat, p_uav)
    from app.verification.architecture_encoder import _atmospheric_path_length_m

    atmospheric_path_m = _atmospheric_path_length_m(p_sat, p_uav)
    scene = SceneConfig()
    cfg = EncoderConfig()

    p_tx = 1000.0  # source power_w
    laser = p_tx * _laser_chain_efficiency(hybrid, range_m, atmospheric_path_m, scene)
    rf = p_tx * _rf_chain_efficiency(hybrid, range_m, p_tx, scene)
    hybrid_delivered = _physical_link_delivered_w(arch, hybrid, range_m, scene, cfg)
    assert hybrid_delivered == pytest.approx(min(laser, rf), rel=1e-12)


# -- Encoder: backward compatibility ---------------------------------------


def test_encode_architecture_unchanged_by_physics_extension() -> None:
    """The base encoder's output is unchanged by the addition of the
    physics extension."""
    sat = _leo_at(0.0, 0.0, alt_km=500.0)
    gs = _ground_at(0.0, 5.0)
    uav = _uav_at(0.0, 3.0)
    link = _laser_link("n_sat", "n_uav", aperture_m=1.0)
    arch = Architecture(nodes=(sat, gs, uav), links=(link,))

    base = encode_architecture(arch)
    names = {c.family_name for c in base}
    assert "l0_flow_lb" in names
    assert "l0_flow_cap" in names
    assert "l0_physical_flow_cap" not in names
    assert "l0_physical_los" not in names


# -- Attribution integration -----------------------------------------------


def test_attribution_marks_link_features_when_physics_los_fails() -> None:
    """The physics LOS failure attributes to the link's grammar features."""
    from app.discovery.attribution import features_of_link

    sat = _leo_at(0.0, 0.0, alt_km=500.0)
    uav = _uav_at(0.0, 180.0)
    link = _laser_link("n_sat", "n_uav", aperture_m=1.0)
    arch = Architecture(nodes=(sat, uav), links=(link,))

    constraints = encode_architecture_with_physics(arch)
    table = ConflictProneTable()
    attribution = attribute_and_mark(constraints, table)
    assert attribution.status == "unsat"

    link_features = features_of_link(link)
    marked = set(table.all_marked())
    assert link_features & marked


# -- Atmospheric shell (Decision 7) ----------------------------------------


def test_atmospheric_path_for_ground_link_equals_full_range() -> None:
    """A short ground-to-ground link is entirely inside the shell."""
    from app.verification.architecture_encoder import _atmospheric_path_length_m

    a = _node_position_m(_ground_at(0.0, 0.0, "n1"))
    b = _node_position_m(_ground_at(0.1, 0.0, "n2"))
    range_m = _range_m(a, b)
    atm_m = _atmospheric_path_length_m(a, b)
    assert atm_m == pytest.approx(range_m, rel=1e-9)


def test_atmospheric_path_for_satellite_link_is_shell_thickness() -> None:
    """A ground-to-LEO link has a much shorter atmospheric path than the
    full geometric range; only the ~20 km shell near the ground counts."""
    from app.verification.architecture_encoder import _atmospheric_path_length_m

    sat = _node_position_m(_leo_at(0.0, 0.0, alt_km=500.0))
    gnd = _node_position_m(_ground_at(0.0, 0.0))
    range_m = _range_m(sat, gnd)
    atm_m = _atmospheric_path_length_m(sat, gnd)
    assert atm_m < range_m
    assert atm_m == pytest.approx(20_000.0, rel=1e-3)


def test_atmospheric_path_between_two_vacuum_points_is_zero() -> None:
    """Two points both above the shell have no atmospheric path."""
    from app.verification.architecture_encoder import _atmospheric_path_length_m

    a = _node_position_m(_leo_at(0.0, 0.0, alt_km=500.0))
    b = _node_position_m(_leo_at(0.5, 0.0, alt_km=500.0))
    atm_m = _atmospheric_path_length_m(a, b)
    assert atm_m == 0.0


def test_satellite_laser_with_default_receiver_is_unsat() -> None:
    """With the default tandem model and its ~0.15 percent efficiency,
    a satellite link at 500 km cannot deliver the demand floor. This is
    a correct physical result and is why Decision 4 introduces an
    override."""
    sat = _leo_at(0.0, 0.0, alt_km=500.0)
    uav = _uav_at(0.0, 1.0)
    link = _laser_link("n_sat", "n_uav", aperture_m=5.0)
    arch = Architecture(nodes=(sat, uav), links=(link,))

    ext = UnsatCoreExtractor()
    for c in encode_architecture_with_physics(arch):
        ext.add(c.to_named())
    result = ext.check()
    assert result.status == "unsat"


# -- SceneConfig override validation ----------------------------------------


def test_scene_config_accepts_receiver_override() -> None:
    s = SceneConfig(receiver_conversion_efficiency=0.25)
    assert s.receiver_conversion_efficiency == 0.25


def test_scene_config_rejects_out_of_range_receiver_override() -> None:
    with pytest.raises(ValueError, match="receiver_conversion_efficiency"):
        SceneConfig(receiver_conversion_efficiency=0.0)
    with pytest.raises(ValueError, match="receiver_conversion_efficiency"):
        SceneConfig(receiver_conversion_efficiency=1.5)


def test_scene_config_default_receiver_override_is_none() -> None:
    s = SceneConfig()
    assert s.receiver_conversion_efficiency is None
