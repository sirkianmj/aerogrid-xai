"""Tests for the real Stage B architecture encoder."""

from __future__ import annotations

import z3

from app.discovery.attribution import (
    ConflictProneTable,
    attribute_and_mark,
    features_of_link,
)
from app.discovery.generator import (
    GeneratorConfig,
    generate_architecture,
)
from app.discovery.grammar import Architecture, LinkInstance, NodeInstance, Terminal
from app.discovery.unsat import UnsatCoreExtractor
from app.verification.architecture_encoder import (
    DEFAULT_ENCODER_CONFIG,
    EncoderConfig,
    _nearest_laser_wavelength_nm,
    _peak_intensity_w_per_m2,
    _transmit_power_w,
    encode_architecture,
)


def _make_arch_with_link(
    kind: Terminal,
    params: dict[str, float],
    source_power_w: float = 100.0,
) -> Architecture:
    """Return a minimal source -> UAV architecture with one link."""
    src = NodeInstance(
        node_id="n0",
        kind=Terminal.GROUND_STATION,
        params={"lat_deg": 0.0, "lon_deg": 0.0, "altitude_m": 0.0, "power_w": source_power_w},
    )
    uav = NodeInstance(
        node_id="n1",
        kind=Terminal.UAV_ENERGY,
        params={
            "role": 0.0,
            "battery_pct": 50.0,
            "lat_deg": 0.0,
            "lon_deg": 0.0,
            "altitude_m": 100.0,
        },
    )
    link = LinkInstance(
        link_id="l0",
        kind=kind,
        source_id="n0",
        target_id="n1",
        params=params,
    )
    return Architecture(nodes=(src, uav), links=(link,))


def test_nearest_wavelength_picks_520_below_boundary() -> None:
    assert _nearest_laser_wavelength_nm(500.0) == 520.0
    assert _nearest_laser_wavelength_nm(791.9) == 520.0


def test_nearest_wavelength_picks_1064_above_boundary() -> None:
    assert _nearest_laser_wavelength_nm(792.1) == 1064.0
    assert _nearest_laser_wavelength_nm(1500.0) == 1064.0


def test_peak_intensity_zero_for_nonpositive_aperture() -> None:
    assert _peak_intensity_w_per_m2(100.0, 0.0) == float("inf")


def test_peak_intensity_matches_formula() -> None:
    import math

    intensity = _peak_intensity_w_per_m2(100.0, 0.5)
    expected = 100.0 / (math.pi * 0.25)
    assert abs(intensity - expected) < 1e-9


def test_transmit_power_uses_source_param_when_present() -> None:
    arch = _make_arch_with_link(
        Terminal.LASER_LINK,
        {"wavelength_nm": 1064.0, "aperture_m": 0.5, "capacity_factor": 1.0},
        source_power_w=250.0,
    )
    assert _transmit_power_w(arch, arch.links[0], DEFAULT_ENCODER_CONFIG) == 250.0


def test_transmit_power_falls_back_for_uav_source() -> None:
    uav = NodeInstance(
        node_id="n0",
        kind=Terminal.UAV_ENERGY,
        params={
            "role": 0.0,
            "battery_pct": 50.0,
            "lat_deg": 0.0,
            "lon_deg": 0.0,
            "altitude_m": 100.0,
        },
    )
    other = NodeInstance(
        node_id="n1",
        kind=Terminal.UAV_COMPUTE,
        params={
            "role": 0.0,
            "battery_pct": 50.0,
            "cpu_cores": 8.0,
            "lat_deg": 0.0,
            "lon_deg": 0.0,
            "altitude_m": 100.0,
        },
    )
    link = LinkInstance(
        link_id="l0",
        kind=Terminal.LASER_LINK,
        source_id="n0",
        target_id="n1",
        params={"wavelength_nm": 1064.0, "aperture_m": 0.5, "capacity_factor": 1.0},
    )
    arch = Architecture(nodes=(uav, other), links=(link,))
    assert (
        _transmit_power_w(arch, link, DEFAULT_ENCODER_CONFIG)
        == DEFAULT_ENCODER_CONFIG.uav_assumed_transmit_w
    )


def test_encoder_emits_constraints_for_valid_architecture() -> None:
    arch = generate_architecture(GeneratorConfig(seed=42))
    constraints = encode_architecture(arch)
    assert len(constraints) > 0
    names = {c.family_name for c in constraints}
    assert any(n.endswith("_flow_cap") for n in names)


def test_encoder_unsat_for_high_intensity_laser_link() -> None:
    """A Laser_Link with small aperture and high source power violates
    the MPE constraint and the system is UNSAT."""
    arch = _make_arch_with_link(
        Terminal.LASER_LINK,
        {"wavelength_nm": 1064.0, "aperture_m": 0.05, "capacity_factor": 1.0},
        source_power_w=1000.0,
    )
    constraints = encode_architecture(arch)
    ext = UnsatCoreExtractor()
    for c in constraints:
        ext.add(c.to_named())
    result = ext.check()
    assert result.status == "unsat"
    assert any("laser_mpe" in name for name in result.core_names)


def test_encoder_sat_for_low_intensity_laser_link() -> None:
    """A Laser_Link with large aperture and modest power satisfies the
    MPE constraint if the flow-balance constraints are also satisfiable."""
    arch = _make_arch_with_link(
        Terminal.LASER_LINK,
        {"wavelength_nm": 1064.0, "aperture_m": 1.0, "capacity_factor": 1.0},
        source_power_w=20.0,
    )
    constraints = encode_architecture(arch)
    ext = UnsatCoreExtractor()
    for c in constraints:
        ext.add(c.to_named())
    result = ext.check()
    assert result.status == "sat", (
        f"expected SAT for low-intensity laser; core = {result.core_names}"
    )


def test_encoder_unsat_for_uav_with_no_incoming_link() -> None:
    src = NodeInstance(
        node_id="n0",
        kind=Terminal.GROUND_STATION,
        params={"lat_deg": 0.0, "lon_deg": 0.0, "altitude_m": 0.0, "power_w": 100.0},
    )
    uav = NodeInstance(
        node_id="n1",
        kind=Terminal.UAV_ENERGY,
        params={
            "role": 0.0,
            "battery_pct": 50.0,
            "lat_deg": 0.0,
            "lon_deg": 0.0,
            "altitude_m": 100.0,
        },
    )
    arch = Architecture(nodes=(src, uav), links=())
    constraints = encode_architecture(arch)
    ext = UnsatCoreExtractor()
    for c in constraints:
        ext.add(c.to_named())
    result = ext.check()
    assert result.status == "unsat"
    assert "n1_demand_unmet" in result.core_names


def test_encoder_unsat_for_architecture_without_uav() -> None:
    a = NodeInstance(
        node_id="n0",
        kind=Terminal.GROUND_STATION,
        params={"lat_deg": 0.0, "lon_deg": 0.0, "altitude_m": 0.0, "power_w": 100.0},
    )
    b = NodeInstance(
        node_id="n1",
        kind=Terminal.SATELLITE_LEO,
        params={"altitude_km": 500.0, "power_w": 100.0, "lat_deg": 0.0, "lon_deg": 0.0},
    )
    arch = Architecture(nodes=(a, b), links=())
    constraints = encode_architecture(arch)
    ext = UnsatCoreExtractor()
    for c in constraints:
        ext.add(c.to_named())
    result = ext.check()
    assert result.status == "unsat"
    assert "requires_uav" in result.core_names


def test_attribution_marks_laser_link_features_for_mpe_violation() -> None:
    """Feeding the encoder output through attribute_and_mark must mark
    the offending link's LINK_INSTANCE and LINK_TYPE features."""
    arch = _make_arch_with_link(
        Terminal.LASER_LINK,
        {"wavelength_nm": 1064.0, "aperture_m": 0.05, "capacity_factor": 1.0},
        source_power_w=1000.0,
    )
    constraints = encode_architecture(arch)
    table = ConflictProneTable()
    attribution = attribute_and_mark(constraints, table)
    assert attribution.status == "unsat"
    link = arch.links[0]
    link_features = features_of_link(link)
    marked = set(table.all_marked())
    assert link_features & marked, f"expected link features {link_features} in marked set {marked}"


def test_encoder_is_deterministic() -> None:
    arch = generate_architecture(GeneratorConfig(seed=123))
    c1 = encode_architecture(arch)
    c2 = encode_architecture(arch)
    assert len(c1) == len(c2)
    assert {c.family_name for c in c1} == {c.family_name for c in c2}


def test_encoder_flow_variables_are_present() -> None:
    arch = _make_arch_with_link(
        Terminal.MICROWAVE_LINK,
        {"frequency_ghz": 2.45, "aperture_m": 1.0, "capacity_factor": 1.0},
        source_power_w=10.0,
    )
    constraints = encode_architecture(arch)
    flow_names = {c.family_name for c in constraints if "flow" in c.family_name}
    assert flow_names, "expected flow constraints"
    assert any(isinstance(c.expression, z3.BoolRef) for c in constraints)


# -- P14: EncoderConfig ----------------------------------------------------


def test_encoder_config_default_values() -> None:
    cfg = EncoderConfig()
    assert cfg.uav_assumed_transmit_w == 20.0
    assert cfg.node_default_demand_w == 15.0
    assert DEFAULT_ENCODER_CONFIG.uav_assumed_transmit_w == 20.0
    assert DEFAULT_ENCODER_CONFIG.node_default_demand_w == 15.0


def test_encoder_config_rejects_nonpositive_values() -> None:
    import pytest

    with pytest.raises(ValueError, match="uav_assumed_transmit_w"):
        EncoderConfig(uav_assumed_transmit_w=0.0)
    with pytest.raises(ValueError, match="uav_assumed_transmit_w"):
        EncoderConfig(uav_assumed_transmit_w=-1.0)
    with pytest.raises(ValueError, match="node_default_demand_w"):
        EncoderConfig(node_default_demand_w=0.0)
    with pytest.raises(ValueError, match="node_default_demand_w"):
        EncoderConfig(node_default_demand_w=-1.0)


def test_encoder_config_is_frozen() -> None:
    import dataclasses

    import pytest

    cfg = EncoderConfig()
    assert dataclasses.is_dataclass(cfg)
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.uav_assumed_transmit_w = 100.0  # type: ignore[misc]


def test_encoder_config_overrides_uav_transmit_power() -> None:
    uav = NodeInstance(
        node_id="n0",
        kind=Terminal.UAV_ENERGY,
        params={
            "role": 0.0,
            "battery_pct": 50.0,
            "lat_deg": 0.0,
            "lon_deg": 0.0,
            "altitude_m": 100.0,
        },
    )
    other = NodeInstance(
        node_id="n1",
        kind=Terminal.UAV_COMPUTE,
        params={
            "role": 0.0,
            "battery_pct": 50.0,
            "cpu_cores": 8.0,
            "lat_deg": 0.0,
            "lon_deg": 0.0,
            "altitude_m": 100.0,
        },
    )
    link = LinkInstance(
        link_id="l0",
        kind=Terminal.LASER_LINK,
        source_id="n0",
        target_id="n1",
        params={"wavelength_nm": 1064.0, "aperture_m": 0.5, "capacity_factor": 1.0},
    )
    arch = Architecture(nodes=(uav, other), links=(link,))
    cfg = EncoderConfig(uav_assumed_transmit_w=42.0)
    assert _transmit_power_w(arch, link, cfg) == 42.0


def test_encoder_config_demand_override_changes_satisfiability() -> None:
    arch = _make_arch_with_link(
        Terminal.MICROWAVE_LINK,
        {"frequency_ghz": 2.45, "aperture_m": 1.0, "capacity_factor": 1.0},
        source_power_w=5.0,
    )
    ext_default = UnsatCoreExtractor()
    for c in encode_architecture(arch):
        ext_default.add(c.to_named())
    assert ext_default.check().status == "unsat"

    small_demand = EncoderConfig(node_default_demand_w=2.0)
    ext_small = UnsatCoreExtractor()
    for c in encode_architecture(arch, small_demand):
        ext_small.add(c.to_named())
    assert ext_small.check().status == "sat"


# -- P15: Hybrid_Link conservative MPE -------------------------------------


def test_hybrid_link_emits_both_mpe_constraints() -> None:
    arch = _make_arch_with_link(
        Terminal.HYBRID_LINK,
        {
            "wavelength_nm": 1064.0,
            "frequency_ghz": 2.45,
            "aperture_m": 1.0,
            "capacity_factor": 1.0,
        },
        source_power_w=5.0,
    )
    names = {c.family_name for c in encode_architecture(arch)}
    assert "l0_hybrid_laser_mpe" in names
    assert "l0_hybrid_rf_mpe" in names


def test_hybrid_link_unsat_when_rf_mpe_violated() -> None:
    """15 W through a 0.5 m radius aperture gives 19.1 W/m^2.
    Laser MPE at 1064 nm is 25.5 W/m^2 (satisfied); RF MPE is
    10.0 W/m^2 (violated). The minimal core must name only RF."""
    arch = _make_arch_with_link(
        Terminal.HYBRID_LINK,
        {
            "wavelength_nm": 1064.0,
            "frequency_ghz": 2.45,
            "aperture_m": 0.5,
            "capacity_factor": 1.0,
        },
        source_power_w=15.0,
    )
    ext = UnsatCoreExtractor()
    for c in encode_architecture(arch):
        ext.add(c.to_named())
    result = ext.check()
    assert result.status == "unsat"
    assert "l0_hybrid_rf_mpe" in result.core_names
    assert "l0_hybrid_laser_mpe" not in result.core_names
