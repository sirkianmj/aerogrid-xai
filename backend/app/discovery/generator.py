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
from app.physics.geometry import EARTH_RADIUS_M as _EARTH_RADIUS_M
from app.physics.geometry import has_line_of_sight as _has_line_of_sight
from app.physics.geometry import (
    node_position_from_params_m as _node_position_from_params_m,
)
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

    visible_cap_fraction: float = 0.25
    # Fraction of the source's full visible cap within which the UAV
    # is placed. The full cap half-angle for a LEO source to a ground
    # target is about 22 deg; a UAV placed at the edge of that cap is
    # thousands of kilometres away, where the Gaussian beam has spread
    # to tens of metres and the receiver captures a fraction of a
    # percent of the transmitted power. Sampling at a fraction of the
    # cap places UAVs closer to the sub-satellite point, where the
    # physical link budget can close. 0.25 keeps the sampled angle
    # within about 5.5 deg for a LEO source, corresponding to a range
    # of roughly 600-800 km at 500-1000 km altitude. Configurable so
    # an ablation study can compare wide and narrow placements.

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


_SOURCE_KINDS: tuple[Terminal, ...] = (
    Terminal.SATELLITE_GEO,
    Terminal.SATELLITE_LEO,
    Terminal.GROUND_STATION,
)
_UAV_KINDS: tuple[Terminal, ...] = (
    Terminal.UAV_ENERGY,
    Terminal.UAV_COMPUTE,
)
_ALL_NODE_KINDS: tuple[Terminal, ...] = _SOURCE_KINDS + _UAV_KINDS


def generate_architecture(
    config: GeneratorConfig | None = None,
    rng: random.Random | None = None,
) -> Architecture:
    """Sample a random Architecture using the configured bounds.

    The generated architecture contains at least one source-kind node,
    at least one UAV-kind node, and one incoming link for every UAV.

    When ``require_line_of_sight`` is True (the default), the generator
    additionally guarantees that every link has line of sight between
    its endpoints. Source-kind nodes are placed uniformly on the
    sphere; each UAV is placed inside the visible cap of the anchor
    source chosen for its repair link. Extra links that would fail the
    line-of-sight check are dropped.

    When ``require_line_of_sight`` is False, all nodes are placed
    uniformly on the sphere (latitude corrected for the sphere measure)
    and no LOS constraint is applied. This reproduces the historical
    behavior and exists so that an ablation study can compare the two
    distributions.

    Determinism: if rng is provided, the call is deterministic. If
    config.seed is provided and rng is None, a fresh random.Random is
    created with that seed. If neither is provided, the call is
    non-deterministic.

    Raises:
        ValueError if no source or no UAV could be sampled (guaranteed
        not to happen for min_nodes >= 2, since the sampler inserts one
        of each before the shuffle).
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

    repair_links: list[LinkInstance] = []
    anchors: dict[str, str] = {}
    for i, uav_id in enumerate(uav_ids):
        source_id = rng.choice(source_ids)
        link_kind = rng.choice((Terminal.LASER_LINK, Terminal.MICROWAVE_LINK, Terminal.HYBRID_LINK))
        repair_links.append(
            LinkInstance(
                link_id=f"l{i}",
                kind=link_kind,
                source_id=source_id,
                target_id=uav_id,
                params=_sample_link_params(rng, link_kind),
            )
        )
        anchors[uav_id] = source_id

    max_possible_links = node_count * (node_count - 1)
    remaining_budget = max(0, min(cfg.max_links, max_possible_links) - len(repair_links))
    n_extra = rng.randint(0, remaining_budget) if remaining_budget > 0 else 0

    extra_links: list[LinkInstance] = []
    for i in range(n_extra):
        source_idx = rng.randrange(node_count)
        target_idx = rng.randrange(node_count)
        while target_idx == source_idx:
            target_idx = rng.randrange(node_count)
        link_kind = rng.choice((Terminal.LASER_LINK, Terminal.MICROWAVE_LINK, Terminal.HYBRID_LINK))
        extra_links.append(
            LinkInstance(
                link_id=f"l{len(repair_links) + i}",
                kind=link_kind,
                source_id=f"n{source_idx}",
                target_id=f"n{target_idx}",
                params=_sample_link_params(rng, link_kind),
            )
        )

    all_links = repair_links + extra_links

    if not cfg.require_line_of_sight:
        nodes_legacy = tuple(
            NodeInstance(
                node_id=f"n{i}",
                kind=kinds[i],
                params=base_params[i],
            )
            for i in range(node_count)
        )
        return Architecture(nodes=nodes_legacy, links=tuple(all_links))

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
        NodeInstance(
            node_id=f"n{i}",
            kind=kinds[i],
            params=final_params[i],
        )
        for i in range(node_count)
    )

    node_by_id = {n.node_id: n for n in nodes}
    surviving_links: list[LinkInstance] = []
    for link in all_links:
        src_node = node_by_id[link.source_id]
        tgt_node = node_by_id[link.target_id]
        p_src = _node_position_from_params_m(src_node.params)
        p_tgt = _node_position_from_params_m(tgt_node.params)
        if _has_line_of_sight(p_src, p_tgt):
            surviving_links.append(link)

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
