"""Tests for the random candidate architecture generator.

Roadmap task s4-2: Candidate generation (random derivations plus
parameter attachment).
Gate: Every generated architecture encodes to Z3 without error.
"""

from __future__ import annotations

import pytest
import z3

from app.discovery.generator import (
    LINK_PARAM_RANGES,
    NODE_PARAM_RANGES,
    UAV_ROLE_NAMES,
    GeneratorConfig,
    encode_architecture_to_z3,
    generate_architecture,
)
from app.discovery.grammar import (
    LINK_TERMINALS,
    NODE_TERMINALS,
    Architecture,
    LinkInstance,
    NodeInstance,
    Terminal,
)

# -- Config validation ------------------------------------------------------


def test_config_rejects_single_node() -> None:
    with pytest.raises(ValueError, match="min_nodes must be >= 2"):
        GeneratorConfig(min_nodes=1, max_nodes=5)


def test_config_rejects_inverted_bounds() -> None:
    with pytest.raises(ValueError, match="max_nodes must be >= min_nodes"):
        GeneratorConfig(min_nodes=5, max_nodes=3)


def test_config_rejects_zero_max_links() -> None:
    with pytest.raises(ValueError, match="max_links must be >= 1"):
        GeneratorConfig(max_links=0)


# -- Generator structure ----------------------------------------------------


def test_generator_produces_node_count_in_bounds() -> None:
    cfg = GeneratorConfig(min_nodes=3, max_nodes=6, seed=1)
    for _ in range(20):
        arch = generate_architecture(cfg)
        assert cfg.min_nodes <= arch.node_count <= cfg.max_nodes


def test_generator_produces_at_least_one_source_and_one_uav() -> None:
    cfg = GeneratorConfig(seed=42)
    source_kinds = {
        Terminal.SATELLITE_GEO,
        Terminal.SATELLITE_LEO,
        Terminal.GROUND_STATION,
    }
    uav_kinds = {Terminal.UAV_ENERGY, Terminal.UAV_COMPUTE}
    for _ in range(30):
        arch = generate_architecture(cfg)
        kinds = {n.kind for n in arch.nodes}
        assert kinds & source_kinds, f"No source kind in {kinds}"
        assert kinds & uav_kinds, f"No UAV kind in {kinds}"


def test_generator_never_produces_self_loops() -> None:
    cfg = GeneratorConfig(seed=7)
    for _ in range(30):
        arch = generate_architecture(cfg)
        for link in arch.links:
            assert link.source_id != link.target_id


def test_generator_uses_only_spec_terminals() -> None:
    cfg = GeneratorConfig(seed=11)
    for _ in range(30):
        arch = generate_architecture(cfg)
        for node in arch.nodes:
            assert node.kind in NODE_TERMINALS
        for link in arch.links:
            assert link.kind in LINK_TERMINALS


def test_generator_attaches_required_params_to_every_node() -> None:
    cfg = GeneratorConfig(seed=13)
    for _ in range(20):
        arch = generate_architecture(cfg)
        for node in arch.nodes:
            expected = set(NODE_PARAM_RANGES[node.kind].keys())
            assert set(node.params.keys()) == expected


def test_generator_attaches_required_params_to_every_link() -> None:
    cfg = GeneratorConfig(seed=17)
    for _ in range(20):
        arch = generate_architecture(cfg)
        for link in arch.links:
            expected = set(LINK_PARAM_RANGES[link.kind].keys())
            assert set(link.params.keys()) == expected


def test_generator_respects_max_links() -> None:
    cfg = GeneratorConfig(min_nodes=4, max_nodes=4, max_links=3, seed=23)
    for _ in range(20):
        arch = generate_architecture(cfg)
        assert arch.link_count <= 3


# -- Determinism ------------------------------------------------------------


def test_generator_is_deterministic_given_seed() -> None:
    cfg_a = GeneratorConfig(seed=99)
    cfg_b = GeneratorConfig(seed=99)
    a1 = generate_architecture(cfg_a)
    a2 = generate_architecture(cfg_b)
    assert a1 == a2


def test_generator_differs_across_seeds() -> None:
    a = generate_architecture(GeneratorConfig(seed=1))
    b = generate_architecture(GeneratorConfig(seed=2))
    # It is astronomically unlikely that two seeds produce the same
    # architecture, but not impossible. Compare structural content
    # instead of asserting inequality directly.
    structural_difference = (
        a.node_count != b.node_count
        or a.link_count != b.link_count
        or tuple(n.kind for n in a.nodes) != tuple(n.kind for n in b.nodes)
    )
    assert structural_difference


def test_uav_role_names_are_the_section_10_set() -> None:
    assert UAV_ROLE_NAMES == (
        "energy",
        "compute",
        "monitoring",
        "relay",
        "emergency",
    )


# -- Encoder: gate -----------------------------------------------------------


def test_encoder_returns_z3_solver() -> None:
    arch = generate_architecture(GeneratorConfig(seed=1))
    solver = encode_architecture_to_z3(arch)
    assert isinstance(solver, z3.Solver)


def test_encoder_solver_is_satisfiable_for_generated_architectures() -> None:
    """The gate test: every generated architecture encodes to a Z3
    system that is satisfiable."""
    cfg = GeneratorConfig(seed=31)
    for _ in range(30):
        arch = generate_architecture(cfg)
        solver = encode_architecture_to_z3(arch)
        assert solver.check() == z3.sat, (
            f"Encoding UNSAT for architecture: {arch.node_count} nodes, {arch.link_count} links"
        )


def test_fuzz_gate_200_architectures_all_encode_sat() -> None:
    """Fuzz gate: 200 random architectures with varied seeds all
    encode to satisfiable Z3 systems."""
    for seed in range(200):
        cfg = GeneratorConfig(seed=seed, min_nodes=2, max_nodes=8, max_links=12)
        arch = generate_architecture(cfg)
        solver = encode_architecture_to_z3(arch)
        result = solver.check()
        assert result == z3.sat, (
            f"seed={seed} produced architecture that encodes to {result}: "
            f"{arch.node_count} nodes, {arch.link_count} links"
        )


# -- Encoder: validation ----------------------------------------------------


def test_encoder_rejects_out_of_range_lat() -> None:
    node_bad = NodeInstance(
        node_id="n0",
        kind=Terminal.GROUND_STATION,
        params={
            "lat_deg": 100.0,  # invalid: max is 90
            "lon_deg": 0.0,
            "altitude_m": 100.0,
            "power_w": 1000.0,
        },
    )
    node_ok = NodeInstance(
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
        kind=Terminal.LASER_LINK,
        source_id="n0",
        target_id="n1",
        params={
            "wavelength_nm": 1064.0,
            "aperture_m": 0.1,
            "capacity_factor": 1.0,
        },
    )
    arch = Architecture(nodes=(node_bad, node_ok), links=(link,))
    with pytest.raises(ValueError, match="lat_deg"):
        encode_architecture_to_z3(arch)


def test_encoder_rejects_missing_parameter() -> None:
    node_incomplete = NodeInstance(
        node_id="n0",
        kind=Terminal.UAV_ENERGY,
        params={"role": 0.0},  # missing the rest
    )
    node_ok = NodeInstance(
        node_id="n1",
        kind=Terminal.GROUND_STATION,
        params={
            "lat_deg": 0.0,
            "lon_deg": 0.0,
            "altitude_m": 0.0,
            "power_w": 100.0,
        },
    )
    link = LinkInstance(
        link_id="l0",
        kind=Terminal.LASER_LINK,
        source_id="n1",
        target_id="n0",
        params={
            "wavelength_nm": 1064.0,
            "aperture_m": 0.1,
            "capacity_factor": 1.0,
        },
    )
    arch = Architecture(nodes=(node_incomplete, node_ok), links=(link,))
    with pytest.raises(ValueError, match="missing required parameter"):
        encode_architecture_to_z3(arch)
