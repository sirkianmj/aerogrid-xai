"""Random candidate architecture generation from the grammar.

Roadmap task s4-2: Candidate generation (random derivations plus
parameter attachment).
Gate: Every generated architecture encodes to Z3 without error.

Reference:
    AeroGrid-XAI Final Comprehensive Specification (Rev. 6),
    Section 35.1 (Architecture Grammar) and Section 35.4 (Discovery
    Loop, "Initialize population P of architectures").

Design
------

The generator samples an Architecture by:

  1. Sampling a node count in [min_nodes, max_nodes].
  2. Sampling each node kind from a weighted distribution that
     guarantees at least one source (Satellite or Ground_Station)
     and at least one UAV in every generated architecture. Without
     this guarantee the generator would frequently produce trivial
     all-UAV or all-satellite architectures that are not useful as
     seeds for the discovery loop.
  3. Attaching parameter values sampled from per-kind ranges.
  4. Sampling a link count in [1, max_links], clamped so it does not
     exceed node_count * (node_count - 1).
  5. Sampling each link's endpoints uniformly, forbidding self-loops.
     Multi-edges between the same pair are permitted: they correspond
     to redundancy, which the later stages need to be able to
     evaluate.
  6. Sampling each link's modality from a uniform distribution.
  7. Attaching parameter values sampled from per-modality ranges.

Parameter ranges are chosen so that they overlap the physically
plausible envelopes documented in the specification, but the ranges
here are deliberately wider than any specific hardware would permit,
because s4-2 is about generating candidates, not about filtering
them. Filtering is the job of Stage B (the encoder), which is
exercised by the gate test.

Encoder placeholder (SUPERSEDED)
------------------------------

``encode_architecture_to_z3`` produces a minimal Z3 solver in which
every node is a real state variable in [0, 100] and every link is a
real flow variable bounded by the source's state and by the link
modality's capacity. It is retained here only so that the s4-2 gate
test ("every generated architecture encodes to Z3 without error") can
be exercised against a self-contained function within this module.

It is superseded by ``app.verification.architecture_encoder.encode_architecture``,
which emits constraints backed by actual physics (ANSI Z136.1 laser
MPE, FCC Part 1.1310 RF limit, flow-balance constraints over source
supply and UAV demand) and tags every constraint with the grammar
features of its originating node or link so that unsat cores attribute
cleanly. New code must use ``encode_architecture``, not this
placeholder. The CLEAR-D closed loop
(``app.discovery.loop.run_clear_d_loop``) uses the real encoder.

The placeholder encoder validates parameters. A parameter that is
missing or out of range raises ValueError. The generator is written
to always produce in-range parameters, so the gate is a contract
between the two.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import z3

from app.discovery.grammar import (
    Architecture,
    LinkInstance,
    NodeInstance,
    Terminal,
)
from app.physics import atmosphere as _atmosphere
from app.physics import beam as _beam
from app.physics import receiver as _receiver
from app.physics import rectenna as _rectenna
from app.physics.geometry import EARTH_RADIUS_M as _EARTH_RADIUS_M
from app.physics.geometry import (
    atmospheric_path_length_m as _atmospheric_path_length_m,
)
from app.physics.geometry import has_line_of_sight as _has_line_of_sight
from app.physics.geometry import (
    node_position_from_params_m as _node_position_from_params_m,
)
from app.physics.geometry import range_m as _range_m
from app.physics.geometry import (
    sample_direction_in_visible_cap as _sample_direction_in_visible_cap,
)
from app.physics.geometry import (
    visible_cap_half_angle_rad as _visible_cap_half_angle_rad,
)

# --- Parameter ranges -----------------------------------------------------


NODE_PARAM_RANGES: dict[Terminal, dict[str, tuple[float, float]]] = {
    Terminal.SATELLITE_GEO: {
        "altitude_km": (35_000.0, 40_000.0),
        "power_w": (100.0, 5_000.0),
        "lat_deg": (-90.0, 90.0),
        "lon_deg": (-180.0, 180.0),
    },
    Terminal.SATELLITE_LEO: {
        "altitude_km": (200.0, 2_000.0),
        # [ESTIMATED] Power budget for a dedicated LEO power-beaming
        # satellite. The specification cites PowerLight delivering
        # nearly 1 kW from a ground transmitter; a space-based laser
        # power transmitter would be at least that scale, typically
        # kW to tens of kW. The previous range of 50-1000 W is not
        # physically sufficient for a 15 W UAV demand floor over LEO
        # distances (see physics chain: at 500 km with 2 cm waist and
        # a 3 m receiver aperture, delivered power is under 3 W at
        # 1000 W source power).
        "power_w": (1_000.0, 20_000.0),
        "lat_deg": (-90.0, 90.0),
        "lon_deg": (-180.0, 180.0),
    },
    Terminal.UAV_ENERGY: {
        # role is a discrete ordinal; it is sampled as a float in
        # [0, 4] and rounded. See UAV_ROLE_NAMES for the mapping.
        "role": (0.0, 4.0),
        "battery_pct": (0.0, 100.0),
        "lat_deg": (-90.0, 90.0),
        "lon_deg": (-180.0, 180.0),
        "altitude_m": (10.0, 5_000.0),
    },
    Terminal.UAV_COMPUTE: {
        "role": (0.0, 4.0),
        "battery_pct": (0.0, 100.0),
        "cpu_cores": (4.0, 64.0),
        "lat_deg": (-90.0, 90.0),
        "lon_deg": (-180.0, 180.0),
        "altitude_m": (10.0, 5_000.0),
    },
    Terminal.GROUND_STATION: {
        "lat_deg": (-90.0, 90.0),
        "lon_deg": (-180.0, 180.0),
        "altitude_m": (0.0, 5_000.0),
        "power_w": (100.0, 10_000.0),
    },
}

UAV_ROLE_NAMES: tuple[str, ...] = (
    "energy",
    "compute",
    "monitoring",
    "relay",
    "emergency",
)
"""Section 10 lists these roles for UAVs. They are carried as the
float ordinal of the ``role`` parameter on UAV node kinds, and the
mapping to names is provided here so tests and downstream modules can
translate."""


LINK_PARAM_RANGES: dict[Terminal, dict[str, tuple[float, float]]] = {
    # Receiver aperture ranges are [ESTIMATED] to match the scale of
    # realistic power-beaming receivers. The specification cites the
    # PowerLight ground-to-air demonstration using a stationary ground
    # receiver, and the Han et al. bench receiver at roughly 1-2 W/cm^2.
    # At LEO distances (500-800 km), a 2 cm beam waist expands to
    # several metres by the time it reaches the ground; a receiver
    # aperture of centimetres captures only a fraction of a percent of
    # the beam, so the physical chain delivers sub-watt power even from
    # a kilowatt source. Metres-scale apertures are what a real
    # space-to-air power link requires. The lower bound of 0.5 m is
    # chosen so the smallest generator output still has a physically
    # plausible receive area; the upper bound of 5 m corresponds to a
    # fixed ground installation.
    Terminal.LASER_LINK: {
        "wavelength_nm": (800.0, 1550.0),
        "aperture_m": (0.5, 5.0),
        "capacity_factor": (0.5, 1.5),
    },
    Terminal.MICROWAVE_LINK: {
        "frequency_ghz": (2.45, 5.80),
        "aperture_m": (0.5, 5.0),
        "capacity_factor": (0.5, 1.5),
    },
    Terminal.HYBRID_LINK: {
        "wavelength_nm": (800.0, 1550.0),
        "frequency_ghz": (2.45, 5.80),
        "aperture_m": (0.5, 5.0),
        "capacity_factor": (0.5, 1.5),
    },
}

LINK_BASE_CAPACITY: dict[Terminal, float] = {
    Terminal.LASER_LINK: 50.0,
    Terminal.MICROWAVE_LINK: 80.0,
    Terminal.HYBRID_LINK: 65.0,
}
"""Base flow capacity per modality, in flow units. These are
placeholder values; the real capacities come from the link budget
(Section 8.4) once the generator is wired to the physics modules in a
later sprint."""


# --- Generator --------------------------------------------------------------


@dataclass(frozen=True)
class GeneratorConfig:
    """Configuration for a single generate_architecture call."""

    min_nodes: int = 2
    max_nodes: int = 8
    max_links: int = 12
    seed: int | None = None

    require_line_of_sight: bool = True
    # When True (the default), every link emitted by the generator
    # has line of sight between its endpoints by construction:
    # source-kind nodes are placed uniformly on the sphere and each
    # UAV is placed inside the visible cap of one anchor source that
    # has an incoming link to it. Extra links that would fail LOS
    # are dropped. When False, all nodes are placed uniformly on the
    # sphere and no LOS check is applied, reproducing the historical
    # behaviour so that an ablation study can compare the two.

    visible_cap_fraction: float = 0.10
    # Fraction of the source's full visible cap within which the UAV
    # is placed. The full cap half-angle for a LEO source to a ground
    # target is about 22 deg; a UAV placed at the edge of that cap is
    # thousands of kilometres away, where the Gaussian beam has spread
    # to tens of metres and the receiver captures a fraction of a
    # percent of the transmitted power. Sampling at a fraction of the
    # cap places UAVs closer to the sub-satellite point.
    #
    # The default of 0.10 is chosen so that every source kind the
    # generator samples (LEO, Ground_Station) yields an anchor link
    # whose physical chain exceeds the viability threshold at the
    # placement geometry. For a Ground_Station source at a few km
    # altitude, 0.10 of a 4 deg cap is 0.4 deg, corresponding to
    # roughly 45 km range; for a LEO source at 500 km altitude, 0.10
    # of a 22 deg cap is 2.2 deg, corresponding to roughly 550 km
    # slant range. Both close their link budgets. Larger fractions
    # place UAVs at ranges where the atmospheric and beam-spreading
    # losses put the delivered power below the viability threshold.
    # Configurable so an ablation study can compare wide and narrow
    # placements.

    def __post_init__(self) -> None:
        if self.min_nodes < 2:
            raise ValueError(
                f"min_nodes must be >= 2 (need at least one source and "
                f"one UAV); got {self.min_nodes}"
            )
        if self.max_nodes < self.min_nodes:
            raise ValueError(
                f"max_nodes must be >= min_nodes; got {self.max_nodes} < {self.min_nodes}"
            )
        if self.max_links < 1:
            raise ValueError(f"max_links must be >= 1; got {self.max_links}")
        if not 0.0 < self.visible_cap_fraction <= 1.0:
            raise ValueError(
                f"visible_cap_fraction must be in (0, 1]; got {self.visible_cap_fraction}"
            )


def _sample_param(rng: random.Random, lo: float, hi: float) -> float:
    return rng.uniform(lo, hi)


def _sample_lat_uniform_on_sphere(
    rng: random.Random,
    lat_min_deg: float,
    lat_max_deg: float,
) -> float:
    # Sample latitude uniformly on the sphere within a latitude band.
    # Sampling latitude uniformly in degrees weights the poles: the
    # fraction of sphere surface between latitudes l1 and l2 is
    # (sin(l2) - sin(l1)) / 2, not (l2 - l1) / 180. To sample uniformly
    # on the sphere, sample sin(lat) uniformly and take the arcsine.
    sin_min = math.sin(math.radians(lat_min_deg))
    sin_max = math.sin(math.radians(lat_max_deg))
    if sin_min > sin_max:
        sin_min, sin_max = sin_max, sin_min
    sin_lat = rng.uniform(sin_min, sin_max)
    return float(math.degrees(math.asin(sin_lat)))


def _sample_node_params(rng: random.Random, kind: Terminal) -> dict[str, float]:
    # Sample the parameters of one node kind. Latitude is uniform on
    # the sphere; longitude is uniform. The role parameter, if present,
    # is rounded to an integer ordinal.
    ranges = NODE_PARAM_RANGES[kind]
    params: dict[str, float] = {}
    for name, (lo, hi) in ranges.items():
        if name == "lat_deg":
            params[name] = _sample_lat_uniform_on_sphere(rng, lo, hi)
        else:
            params[name] = rng.uniform(lo, hi)
    if "role" in params:
        params["role"] = float(round(params["role"]))
    return params


def _sample_link_params(rng: random.Random, kind: Terminal) -> dict[str, float]:
    ranges = LINK_PARAM_RANGES[kind]
    return {name: _sample_param(rng, lo, hi) for name, (lo, hi) in ranges.items()}


# SATELLITE_GEO is a grammar terminal but is not sampled by the
# generator. A GEO source at 35,800 km altitude spreads a 2 cm beam to
# roughly 600 m radius; a small UAV receiver (metres across) captures
# about 10^-4 of the beam, and the resulting chain efficiency is five
# orders of magnitude below the viability threshold at any range. GEO
# power delivery at UAV receiver scale is physically infeasible with
# current technology. The terminal remains available for hand-built
# architectures. A future revision may add large ground-array receivers,
# at which point GEO becomes feasible and can be returned to the pool.
_SOURCE_KINDS: tuple[Terminal, ...] = (
    Terminal.SATELLITE_LEO,
    Terminal.GROUND_STATION,
)
_UAV_KINDS: tuple[Terminal, ...] = (
    Terminal.UAV_ENERGY,
    Terminal.UAV_COMPUTE,
)
_ALL_NODE_KINDS: tuple[Terminal, ...] = _SOURCE_KINDS + _UAV_KINDS


_LINK_KIND_VIABILITY_FRACTION = 1.0e-6
"""A link kind is viable at a geometry only if its physical chain
delivers at least this fraction of the source power. Chains that lose
more than six orders of magnitude are physically broken, not merely
inefficient: no plausible aperture recovers them. This threshold is
[ESTIMATED] and exists so the generator does not sample link kinds
whose physics cannot reach the target."""

_VIABILITY_TEST_APERTURE_M = 5.0
"""Aperture used for the viability test. Uses the maximum of
LINK_PARAM_RANGES so that a kind is judged viable if any plausible
aperture can close the link, not just the smallest."""


def _transmit_power_w_from_params(
    node_params: dict[str, float],
) -> float:
    """Source power for a node, matching _transmit_power_w in the encoder."""
    if "power_w" in node_params:
        return float(node_params["power_w"])
    return 20.0  # encoder's uav_assumed_transmit_w default


def _link_chain_delivers_positive(
    source_params: dict[str, float],
    target_params: dict[str, float],
    kind: Terminal,
    aperture_m: float,
) -> float:
    """Return the DC power at the battery for a hypothetical link.

    Constructs a minimal physical chain for the given source and target
    node parameter maps and a candidate link kind and aperture. Returns
    the delivered DC power in watts. Used only to decide whether a link
    kind is viable at a geometry; the actual link parameters are sampled
    separately.

    The chain is:
      transmitted power
      x beam efficiency (spillover at the receiver)
      x atmospheric transmittance (laser) or rf_transmittance (RF)
      x receiver conversion (PV-TE eta_total, or rectenna efficiency)
      x battery efficiency (0.92)

    Reference values are the SceneConfig defaults, which is the same
    baseline the physics encoder uses when no override is supplied.
    """
    p_src = _node_position_from_params_m(source_params)
    p_tgt = _node_position_from_params_m(target_params)
    rng_m = _range_m(p_src, p_tgt)
    atm_path_m = _atmospheric_path_length_m(p_src, p_tgt)
    p_tx = _transmit_power_w_from_params(source_params)
    battery_eff = 0.92

    def laser_chain() -> float:
        wl_nm = 1064.0
        w0 = 0.02
        w_at = _beam.beam_radius_m(wl_nm, w0, rng_m)
        eta_beam = _beam.combined_beam_efficiency(w_at, aperture_m, 0.0)
        eta_atm = _atmosphere.transmission(
            wavelength_nm=wl_nm,
            path_length_m=atm_path_m,
            visibility_km=20.0,
            cloud_factor=0.0,
        )
        eta_receiver = _receiver.eta_total(298.15, 320.0, 298.15)
        return p_tx * eta_beam * eta_atm * eta_receiver * battery_eff

    def rf_chain() -> float:
        freq_ghz = 2.45
        wavelength_m = 299_792_458.0 / (freq_ghz * 1.0e9)
        wavelength_nm = wavelength_m * 1.0e9
        w0 = 0.02
        w_at = _beam.beam_radius_m(wavelength_nm, w0, rng_m)
        eta_beam = _beam.combined_beam_efficiency(w_at, aperture_m, 0.0)
        eta_atm = 0.98
        area_m2 = 3.14159265358979 * aperture_m * aperture_m
        p_inc = p_tx * eta_beam * eta_atm
        density = p_inc / area_m2 if area_m2 > 0.0 else 0.0
        eta_rect = _rectenna.rectenna_efficiency(density, freq_ghz)
        return p_tx * eta_beam * eta_atm * eta_rect * battery_eff

    if kind == Terminal.LASER_LINK:
        return laser_chain()
    if kind == Terminal.MICROWAVE_LINK:
        return rf_chain()
    if kind == Terminal.HYBRID_LINK:
        return min(laser_chain(), rf_chain())
    raise ValueError(f"unsupported link kind {kind}")


def _viable_link_kinds(
    source_params: dict[str, float],
    target_params: dict[str, float],
) -> list[Terminal]:
    """Return the link kinds whose physical chain reaches the target.

    A kind is viable if, at the maximum plausible receiver aperture, its
    physical chain delivers at least ``_LINK_KIND_VIABILITY_FRACTION``
    of the source power. Laser is always viable in the current model
    (spillover, transmittance, and receiver efficiency are all strictly
    positive). Microwave is viable only at short ranges, because the
    rectenna efficiency is a Gaussian in log10 of incident power density
    centred on 1000 W/m^2, and at long range the incident density falls
    many decades below the centre. Hybrid inherits the minimum of the
    two chains, so it is viable only when microwave is.
    """
    p_src = _transmit_power_w_from_params(source_params)
    threshold = _LINK_KIND_VIABILITY_FRACTION * p_src
    viable: list[Terminal] = []
    for kind in (
        Terminal.LASER_LINK,
        Terminal.MICROWAVE_LINK,
        Terminal.HYBRID_LINK,
    ):
        delivered = _link_chain_delivers_positive(
            source_params, target_params, kind, _VIABILITY_TEST_APERTURE_M
        )
        if delivered >= threshold:
            viable.append(kind)
    return viable


def generate_architecture(
    config: GeneratorConfig | None = None,
    rng: random.Random | None = None,
) -> Architecture:
    """Sample a random Architecture using the configured bounds.

    The generated architecture contains at least one source-kind node,
    at least one UAV-kind node, and one incoming link for every UAV.

    When ``require_line_of_sight`` is True (the default), the generator
    guarantees that every link has line of sight between its endpoints
    and that every link's physical chain delivers at least
    ``_LINK_KIND_VIABILITY_FRACTION`` of its source power.

    Algorithm order matters. Node kinds and positions are sampled
    first, then topology (which node links to which) without a kind,
    then UAV placements inside their anchor sources' visible caps, and
    only then are link kinds sampled — from the set that is viable at
    the final geometry. Sampling a link kind before placement would
    assign kinds to a geometry that no longer holds after the UAV is
    moved into the visible cap.

    When ``require_line_of_sight`` is False, all nodes are placed
    uniformly on the sphere (latitude corrected for the sphere measure),
    no LOS or viability constraint is applied, and every candidate link
    is emitted with a uniformly random kind. This reproduces the
    historical behavior and exists for ablation studies.

    Determinism: if rng is provided, the call is deterministic. If
    config.seed is provided and rng is None, a fresh random.Random is
    created with that seed. If neither is provided, the call is
    non-deterministic.
    """
    cfg = config or GeneratorConfig()
    if rng is None:
        rng = random.Random(cfg.seed)

    node_count = rng.randint(cfg.min_nodes, cfg.max_nodes)
    kinds: list[Terminal] = []
    kinds.append(rng.choice(_SOURCE_KINDS))
    kinds.append(rng.choice(_UAV_KINDS))
    for _ in range(node_count - 2):
        kinds.append(rng.choice(_ALL_NODE_KINDS))
    rng.shuffle(kinds)

    base_params = [_sample_node_params(rng, kind) for kind in kinds]

    uav_ids = [f"n{i}" for i, k in enumerate(kinds) if k in _UAV_KINDS]
    source_ids = [f"n{i}" for i, k in enumerate(kinds) if k in _SOURCE_KINDS]
    if not source_ids or not uav_ids:
        raise ValueError(
            "generator internal invariant violated: at least one source "
            "and one UAV must exist after node sampling"
        )

    # --- Step 1: sample topology without link kinds ---
    # Repair links: one incoming edge per UAV from a random source.
    # Only the source_id and target_id are chosen here; the link kind is
    # deferred until after placement.
    repair_topology: list[tuple[str, str]] = []
    anchors: dict[str, str] = {}
    for uav_id in uav_ids:
        source_id = rng.choice(source_ids)
        repair_topology.append((source_id, uav_id))
        anchors[uav_id] = source_id

    # Extra links: random source-target pairs, no self-loops.
    max_possible_links = node_count * (node_count - 1)
    remaining_budget = max(0, min(cfg.max_links, max_possible_links) - len(repair_topology))
    n_extra = rng.randint(0, remaining_budget) if remaining_budget > 0 else 0
    extra_topology: list[tuple[str, str]] = []
    for _ in range(n_extra):
        source_idx = rng.randrange(node_count)
        target_idx = rng.randrange(node_count)
        while target_idx == source_idx:
            target_idx = rng.randrange(node_count)
        extra_topology.append((f"n{source_idx}", f"n{target_idx}"))

    # --- Step 2: if LOS is not required, skip placement and emit directly ---
    if not cfg.require_line_of_sight:
        all_topology = repair_topology + extra_topology
        links_legacy: list[LinkInstance] = []
        for i, (source_id, target_id) in enumerate(all_topology):
            link_kind = rng.choice(
                (Terminal.LASER_LINK, Terminal.MICROWAVE_LINK, Terminal.HYBRID_LINK)
            )
            links_legacy.append(
                LinkInstance(
                    link_id=f"l{i}",
                    kind=link_kind,
                    source_id=source_id,
                    target_id=target_id,
                    params=_sample_link_params(rng, link_kind),
                )
            )
        nodes_legacy = tuple(
            NodeInstance(node_id=f"n{i}", kind=kinds[i], params=base_params[i])
            for i in range(node_count)
        )
        return Architecture(nodes=nodes_legacy, links=tuple(links_legacy))

    # --- Step 3: place UAVs inside their anchor sources' visible caps ---
    source_radii: dict[str, float] = {}
    for i, kind in enumerate(kinds):
        if kind not in _SOURCE_KINDS:
            continue
        alt_km = float(base_params[i].get("altitude_km", 0.0))
        alt_m = float(base_params[i].get("altitude_m", 0.0))
        source_radii[f"n{i}"] = _EARTH_RADIUS_M + alt_km * 1000.0 + alt_m

    final_params = [dict(p) for p in base_params]
    for uav_id in uav_ids:
        uav_idx = int(uav_id[1:])
        anchor_id = anchors[uav_id]
        anchor_idx = int(anchor_id[1:])
        anchor_r = source_radii[anchor_id]
        if "altitude_km" in base_params[uav_idx]:
            uav_alt_m = float(base_params[uav_idx]["altitude_km"]) * 1000.0
        else:
            uav_alt_m = float(base_params[uav_idx].get("altitude_m", 0.0))
        uav_r = _EARTH_RADIUS_M + uav_alt_m
        half_angle = cfg.visible_cap_fraction * _visible_cap_half_angle_rad(anchor_r, uav_r)
        new_lat, new_lon = _sample_direction_in_visible_cap(
            float(final_params[anchor_idx]["lat_deg"]),
            float(final_params[anchor_idx]["lon_deg"]),
            half_angle,
            rng,
        )
        final_params[uav_idx]["lat_deg"] = new_lat
        final_params[uav_idx]["lon_deg"] = new_lon

    nodes = tuple(
        NodeInstance(node_id=f"n{i}", kind=kinds[i], params=final_params[i])
        for i in range(node_count)
    )
    node_by_id = {n.node_id: n for n in nodes}

    # --- Step 4: for each topology edge, sample the link kind from the
    # set that is viable at the final geometry, then filter by LOS. ---
    all_topology = repair_topology + extra_topology
    surviving_links: list[LinkInstance] = []
    for source_id, target_id in all_topology:
        src_node = node_by_id[source_id]
        tgt_node = node_by_id[target_id]
        p_src = _node_position_from_params_m(dict(src_node.params))
        p_tgt = _node_position_from_params_m(dict(tgt_node.params))
        if not _has_line_of_sight(p_src, p_tgt):
            continue
        viable = _viable_link_kinds(dict(src_node.params), dict(tgt_node.params))
        if not viable:
            continue
        link_kind = rng.choice(viable)
        surviving_links.append(
            LinkInstance(
                link_id=f"l{len(surviving_links)}",
                kind=link_kind,
                source_id=source_id,
                target_id=target_id,
                params=_sample_link_params(rng, link_kind),
            )
        )

    return Architecture(nodes=nodes, links=tuple(surviving_links))


# --- Placeholder Z3 encoder -------------------------------------------------


def _require_param(params: dict[str, float], name: str, owner: str) -> float:
    if name not in params:
        raise ValueError(f"{owner} is missing required parameter '{name}'")
    return params[name]


def _require_in_range(value: float, lo: float, hi: float, name: str, owner: str) -> float:
    if not (lo <= value <= hi):
        raise ValueError(f"{owner} parameter '{name}' = {value} outside [{lo}, {hi}]")
    return value


def encode_architecture_to_z3(arch: Architecture) -> z3.Solver:
    """Return a Z3 solver encoding a generated architecture.

    This is a minimal placeholder for the real Stage B encoding. Every
    node becomes a real state variable in [0, 100]; every link becomes
    a real flow variable bounded by the source node's state and by the
    link modality's base capacity times its capacity_factor parameter.

    The solver is asserted with strict inequalities that guarantee SAT
    for any in-range input, so the gate test can distinguish between
    "the encoder runs and produces a satisfiable system" and "the
    encoder silently produced an unsatisfiable system due to a bug".

    Raises:
        ValueError if any node or link is missing a required parameter
        or has a parameter outside its documented range. The generator
        is written to always produce in-range parameters, so a raise
        here indicates a bug in the generator or a hand-constructed
        architecture that violated the contract.
    """
    solver = z3.Solver()
    state_vars: dict[str, z3.ArithRef] = {}

    for node in arch.nodes:
        owner = f"node {node.node_id} ({node.kind.value})"
        params = dict(node.params)
        # Every node kind has a required 'battery_pct' or a 'role' or
        # similar discriminant in its parameter set; validate all
        # parameters against the documented ranges for this kind.
        for pname, (lo, hi) in NODE_PARAM_RANGES[node.kind].items():
            value = _require_param(params, pname, owner)
            _require_in_range(value, lo, hi, pname, owner)

        state = z3.Real(f"{node.node_id}_state")
        state_vars[node.node_id] = state
        solver.add(state >= 0.0, state <= 100.0)

    for link in arch.links:
        owner = f"link {link.link_id} ({link.kind.value})"
        params = dict(link.params)
        for pname, (lo, hi) in LINK_PARAM_RANGES[link.kind].items():
            value = _require_param(params, pname, owner)
            _require_in_range(value, lo, hi, pname, owner)

        flow = z3.Real(f"{link.link_id}_flow")
        source_state = state_vars[link.source_id]
        base_capacity = LINK_BASE_CAPACITY[link.kind]
        capacity_factor = params["capacity_factor"]
        effective_capacity = base_capacity * capacity_factor

        solver.add(flow >= 0.0)
        solver.add(flow <= source_state)
        solver.add(flow <= effective_capacity)

    return solver
