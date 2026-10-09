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

Encoder placeholder
-------------------

encode_architecture_to_z3 produces a minimal Z3 solver in which
every node is a real state variable in [0, 100] and every link is a
real flow variable bounded by the source's state and by the link
modality's capacity. This is a placeholder: the real Stage B
encoding lives in backend/app/verification/. The placeholder exists
here so that s4-2's gate ("every generated architecture encodes to
Z3 without error") can be exercised. When s4-4 lands and wires the
discovery loop to the real encoder, this function will be replaced
by a call into the verification package.

The placeholder encoder validates parameters. A parameter that is
missing or out of range raises ValueError. The generator is written
to always produce in-range parameters, so the gate is a contract
between the two.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import z3

from app.discovery.grammar import (
    Architecture,
    LinkInstance,
    NodeInstance,
    Terminal,
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
        "power_w": (50.0, 1_000.0),
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
    Terminal.LASER_LINK: {
        "wavelength_nm": (800.0, 1550.0),
        "aperture_m": (0.01, 1.0),
        "capacity_factor": (0.5, 1.5),
    },
    Terminal.MICROWAVE_LINK: {
        "frequency_ghz": (2.45, 5.80),
        "aperture_m": (0.01, 5.0),
        "capacity_factor": (0.5, 1.5),
    },
    Terminal.HYBRID_LINK: {
        "wavelength_nm": (800.0, 1550.0),
        "frequency_ghz": (2.45, 5.80),
        "aperture_m": (0.01, 5.0),
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


def _sample_param(rng: random.Random, lo: float, hi: float) -> float:
    return rng.uniform(lo, hi)


def _sample_node_params(rng: random.Random, kind: Terminal) -> dict[str, float]:
    ranges = NODE_PARAM_RANGES[kind]
    params = {name: _sample_param(rng, lo, hi) for name, (lo, hi) in ranges.items()}
    # Round the role parameter for UAVs to the nearest integer so it
    # is a valid role ordinal.
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

    The generated architecture is guaranteed to contain at least one
    source-kind node (Satellite or Ground_Station) and at least one
    UAV-kind node, so that it represents a meaningful wireless-energy
    topology rather than a degenerate one.

    Determinism: if rng is provided, the call is deterministic. If
    config.seed is provided and rng is None, a fresh random.Random is
    created with that seed. If neither is provided, the call is
    non-deterministic.

    Raises:
        ValueError if the config is inconsistent with the requirement
        of at least one source and one UAV (which min_nodes >= 2
        implies).
    """
    cfg = config or GeneratorConfig()
    if rng is None:
        rng = random.Random(cfg.seed)

    node_count = rng.randint(cfg.min_nodes, cfg.max_nodes)
    # Sample node kinds ensuring at least one source and one UAV.
    kinds: list[Terminal] = []
    kinds.append(rng.choice(_SOURCE_KINDS))
    kinds.append(rng.choice(_UAV_KINDS))
    for _ in range(node_count - 2):
        kinds.append(rng.choice(_ALL_NODE_KINDS))
    rng.shuffle(kinds)

    nodes = tuple(
        NodeInstance(
            node_id=f"n{i}",
            kind=kind,
            params=_sample_node_params(rng, kind),
        )
        for i, kind in enumerate(kinds)
    )

    max_possible_links = node_count * (node_count - 1)
    link_count = rng.randint(1, min(cfg.max_links, max_possible_links))

    links: list[LinkInstance] = []
    for i in range(link_count):
        source_idx = rng.randrange(node_count)
        target_idx = rng.randrange(node_count)
        while target_idx == source_idx:
            target_idx = rng.randrange(node_count)
        link_kind = rng.choice((Terminal.LASER_LINK, Terminal.MICROWAVE_LINK, Terminal.HYBRID_LINK))
        links.append(
            LinkInstance(
                link_id=f"l{i}",
                kind=link_kind,
                source_id=nodes[source_idx].node_id,
                target_id=nodes[target_idx].node_id,
                params=_sample_link_params(rng, link_kind),
            )
        )

    return Architecture(nodes=nodes, links=tuple(links))


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
