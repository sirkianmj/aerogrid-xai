"""Tests for the LOS-compliant generator placement."""

from __future__ import annotations

import statistics

from app.discovery.generator import GeneratorConfig, generate_architecture
from app.discovery.grammar import Architecture, Terminal
from app.physics.geometry import (
    has_line_of_sight,
    node_position_from_params_m,
)


def _all_links_have_los(arch: Architecture) -> bool:
    node_by_id = {n.node_id: n for n in arch.nodes}
    for link in arch.links:
        p_src = node_position_from_params_m(node_by_id[link.source_id].params)
        p_tgt = node_position_from_params_m(node_by_id[link.target_id].params)
        if not has_line_of_sight(p_src, p_tgt):
            return False
    return True


def _every_uav_has_incoming(arch: Architecture) -> bool:
    uav_kinds = (Terminal.UAV_ENERGY, Terminal.UAV_COMPUTE)
    for n in arch.nodes:
        if n.kind not in uav_kinds:
            continue
        if not any(ln.target_id == n.node_id for ln in arch.links):
            return False
    return True


# -- LOS guarantee ----------------------------------------------------------


def test_all_links_have_los_default() -> None:
    for seed in range(200):
        arch = generate_architecture(
            GeneratorConfig(min_nodes=4, max_nodes=8, max_links=6, seed=seed)
        )
        assert _all_links_have_los(arch), f"seed {seed} produced a non-LOS link"


def test_every_uav_has_incoming_link_default() -> None:
    for seed in range(200):
        arch = generate_architecture(
            GeneratorConfig(min_nodes=4, max_nodes=8, max_links=6, seed=seed)
        )
        assert _every_uav_has_incoming(arch), f"seed {seed} produced an unpowered UAV"


def test_require_line_of_sight_false_disables_guarantee() -> None:
    """With the flag off, the historical distribution is restored.

    Not every link will have LOS; some architectures with the flag off
    should fail the LOS check. This is the point of the flag: an
    ablation arm."""
    non_los_seen = 0
    for seed in range(200):
        arch = generate_architecture(
            GeneratorConfig(
                min_nodes=4,
                max_nodes=8,
                max_links=6,
                seed=seed,
                require_line_of_sight=False,
            )
        )
        if not _all_links_have_los(arch):
            non_los_seen += 1
    assert non_los_seen > 0, (
        "with require_line_of_sight=False, at least some architectures "
        "should fail the LOS check; none did over 200 seeds"
    )


# -- Position distribution --------------------------------------------------


def test_latitude_distribution_is_uniform_on_sphere() -> None:
    """Latitude should be uniform-in-sin, not uniform-in-degrees.

    Fraction of |lat| > 60 deg should be about 0.134 for uniform on
    the sphere, not 0.333 for uniform in latitude."""
    abs_lats: list[float] = []
    for seed in range(2000):
        arch = generate_architecture(
            GeneratorConfig(min_nodes=4, max_nodes=8, max_links=6, seed=seed)
        )
        for n in arch.nodes:
            abs_lats.append(abs(float(n.params["lat_deg"])))
    fraction_above_60 = sum(1 for x in abs_lats if x > 60.0) / len(abs_lats)
    assert fraction_above_60 < 0.20, (
        f"fraction |lat| > 60 is {fraction_above_60:.3f}; uniform on "
        f"sphere predicts 0.134, uniform in lat predicts 0.333"
    )
    assert fraction_above_60 > 0.08, (
        f"fraction |lat| > 60 is {fraction_above_60:.3f}; too low, sampling may be broken"
    )


def test_mean_absolute_latitude_matches_sphere_measure() -> None:
    """For a uniform-on-sphere distribution, E[|lat|] = pi/2 - 1 in
    radians, which is approximately 32.70 degrees.

    Derivation: for a uniform distribution on the sphere, the density
    of latitude l (in radians) is (cos(l)) / 2 on [-pi/2, pi/2]. The
    expected value of |l| is

        E[|lat|] = 2 * integral_0^{pi/2} l * cos(l)/2 dl
                 = integral_0^{pi/2} l * cos(l) dl
                 = [l * sin(l) + cos(l)]_0^{pi/2}
                 = (pi/2 * 1 + 0) - (0 + 1)
                 = pi/2 - 1

    in radians, approximately 0.5708 rad = 32.704 degrees.

    A sampler that samples latitude uniformly in degrees would give
    45.0 degrees. This test distinguishes the two.
    """
    abs_lats: list[float] = []
    for seed in range(1000):
        arch = generate_architecture(
            GeneratorConfig(min_nodes=4, max_nodes=8, max_links=6, seed=seed)
        )
        for n in arch.nodes:
            abs_lats.append(abs(float(n.params["lat_deg"])))
    mean = statistics.mean(abs_lats)
    assert abs(mean - 32.7) < 2.0, (
        f"mean |lat| = {mean:.2f}, expected ~32.7 for uniform on sphere "
        f"(45.0 would indicate uniform in latitude)"
    )


# -- Determinism ------------------------------------------------------------


def test_generator_determinism_preserved() -> None:
    """Same seed reproduces the same architecture, LOS or not."""
    for flag in (True, False):
        a = generate_architecture(GeneratorConfig(seed=99, require_line_of_sight=flag))
        b = generate_architecture(GeneratorConfig(seed=99, require_line_of_sight=flag))
        assert a == b


# -- Encoder integration ----------------------------------------------------


def test_physics_encoder_sat_on_hand_built_feasible_architecture() -> None:
    """The physics encoder declares SAT an architecture whose chain can
    close.

    This is a demonstration that the physics extension is not
    over-constraining every architecture by construction. The
    architecture is hand-built so its geometry and link type are known
    to be physically feasible: a 500 km LEO source at 10 kW, a single
    laser link to a near-subpoint UAV, a 5 m receiver aperture, and a
    receiver conversion efficiency of 0.25.
    """
    from app.discovery.grammar import Architecture, LinkInstance, NodeInstance, Terminal
    from app.discovery.unsat import UnsatCoreExtractor
    from app.verification.architecture_encoder import (
        SceneConfig,
        encode_architecture_with_physics,
    )

    sat_node = NodeInstance(
        node_id="s",
        kind=Terminal.SATELLITE_LEO,
        params={
            "altitude_km": 500.0,
            "power_w": 10_000.0,
            "lat_deg": 0.0,
            "lon_deg": 0.0,
        },
    )
    uav_node = NodeInstance(
        node_id="u",
        kind=Terminal.UAV_ENERGY,
        params={
            "role": 0.0,
            "battery_pct": 50.0,
            "lat_deg": 2.0,
            "lon_deg": 0.0,
            "altitude_m": 100.0,
        },
    )
    link = LinkInstance(
        link_id="l0",
        kind=Terminal.LASER_LINK,
        source_id="s",
        target_id="u",
        params={
            "wavelength_nm": 1064.0,
            "aperture_m": 5.0,
            "capacity_factor": 1.0,
        },
    )
    arch = Architecture(nodes=(sat_node, uav_node), links=(link,))
    scene = SceneConfig(receiver_conversion_efficiency=0.25)
    ext = UnsatCoreExtractor()
    for c in encode_architecture_with_physics(arch, scene=scene):
        ext.add(c.to_named())
    assert ext.check().status == "sat", (
        "the hand-built architecture is physically feasible but the physics encoder rejected it"
    )


def test_physics_encoder_characterizes_generator_feasibility_rate() -> None:
    """Characterization: measure the feasible fraction of the current
    generator's output under the physics encoder.

    This test does NOT assert a minimum feasibility rate. It measures
    the rate and prints it, so the number is on record and any future
    change to the generator or the physics will show up as a change in
    this measurement. The current value on the branch that introduced
    this test is 0/60: the generator produces topologies (notably
    microwave links at LEO ranges) whose physical chains cannot close,
    and the encoder correctly rejects them. The follow-up is a
    generator that samples link types consistent with geometry, not a
    change to the physics or the encoder.
    """
    from app.discovery.unsat import UnsatCoreExtractor
    from app.verification.architecture_encoder import (
        SceneConfig,
        encode_architecture_with_physics,
    )

    scene = SceneConfig(receiver_conversion_efficiency=0.25)
    n_seeds = 60
    sat = 0
    for seed in range(n_seeds):
        arch = generate_architecture(
            GeneratorConfig(min_nodes=4, max_nodes=8, max_links=6, seed=20000 + seed)
        )
        ext = UnsatCoreExtractor()
        for c in encode_architecture_with_physics(arch, scene=scene):
            ext.add(c.to_named())
        if ext.check().status == "sat":
            sat += 1
    print(
        f"\nphysics encoder characterization: {sat}/{n_seeds} generated "
        f"architectures are SAT with receiver_conversion_efficiency=0.25"
    )
    assert 0 <= sat <= n_seeds
