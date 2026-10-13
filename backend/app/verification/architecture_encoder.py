"""Real Stage B encoder: architecture -> FeatureConstraint tuple.

Unlike the placeholder ``encode_architecture_to_z3`` in
``app.discovery.generator`` (now marked SUPERSEDED there), this module
emits constraints that reference actual physics: ANSI Z136.1 laser MPE,
FCC Part 1.1310 RF power-density limit, and linear flow-balance
constraints over Z3 real variables. Each emitted constraint is tagged
with the grammar features of the nodes and links that generated it, so
the unsat core can be attributed back to specific grammar elements via
``app.discovery.attribution``.

Constraint families emitted
---------------------------

1. Per-link flow variable bounds:
   - ``<link_id>_flow_lb``: flow >= 0.
   - ``<link_id>_flow_cap``: flow <= LINK_BASE_CAPACITY[kind] * capacity_factor.

2. Per-source supply bound:
   - ``<source_id>_supply``: sum of outgoing flows <= source supply_w.

3. Per-UAV demand floor:
   - ``<uav_id>_demand``: sum of incoming flows >= config.node_default_demand_w.
   - If the UAV has no incoming links, emits ``<uav_id>_demand_unmet``
     as a constant FALSE constraint, which is a minimal UNSAT core of
     size 1 attributable to that UAV's features.

4. Per-link regulatory MPE:
   - ``<link_id>_laser_mpe`` for Laser_Link.
   - ``<link_id>_rf_mpe`` for Microwave_Link.
   - BOTH ``<link_id>_hybrid_laser_mpe`` and ``<link_id>_hybrid_rf_mpe``
     for Hybrid_Link. This is deliberately conservative: a hybrid link
     may switch modality at any time, so it must satisfy both safety
     limits simultaneously. A hybrid link that is laser-safe but
     RF-unsafe is UNSAT, with a minimal core containing only the
     violated family.

5. UAV-presence structural constraint:
   - ``requires_uav``: FALSE if the architecture contains no UAV node.

Configuration
-------------

Two encoder constants are engineering estimates and are exposed through
``EncoderConfig`` so that parameter studies can vary them without
editing source:

    uav_assumed_transmit_w  [ESTIMATED] fallback transmit power for
                            a link whose source node has no power_w
    node_default_demand_w   [ESTIMATED] demand floor applied to every
                            UAV node

Both are marked ``[ESTIMATED]`` in ``EncoderConfig``'s docstring. They
are not sourced. Any commercial or publication use that depends on
their specific values must source them first.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from dataclasses import field as dataclass_field

import z3

from app.discovery.attribution import (
    FeatureConstraint,
    FeatureKind,
    GrammarFeature,
    features_of_link,
)
from app.discovery.generator import LINK_BASE_CAPACITY
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
from app.verification.regulatory import (
    RF_LIMIT_GENERAL_POPULATION,
    laser_mpe,
)

_EARTH_RADIUS_M = 6_371_000.0
"""[ESTIMATED] Spherical-Earth radius. WGS-84 differs by up to ~21 km
at any given point; a spherical model is a documented simplification
(see docs/ENCODER_PHYSICS_INTEGRATION.md, Decision 1)."""

_SPEED_OF_LIGHT_M_PER_S = 299_792_458.0
"""[SOURCED] Exact speed of light in vacuum, m/s (SI definition)."""

_H_ATMOSPHERE_M = 20_000.0
"""[ESTIMATED] Thickness of the atmosphere shell used for atmospheric
path-length clipping. The atmosphere has no sharp boundary; 20 km is a
first-order choice covering the troposphere plus low stratosphere. A
density-resolved profile is deferred (docs/ENCODER_PHYSICS_INTEGRATION.md,
Decision 7)."""


@dataclass(frozen=True)
class EncoderConfig:
    """Configuration for ``encode_architecture``.

    uav_assumed_transmit_w and node_default_demand_w are engineering
    estimates marked ``[ESTIMATED]``; they are not measured values and
    are not sourced from a specific published reference. They exist as
    tunable defaults so that parameter studies can vary them by
    construction rather than by editing source.

    Attributes:
        uav_assumed_transmit_w: Transmit power assigned to a link whose
            source is a UAV. [ESTIMATED] UAV node kinds in the current
            generator do not carry a ``power_w`` parameter, so this
            value is used as a fallback. 20 W is a first-order estimate
            for a small airborne transmitter.
        node_default_demand_w: Minimum power demand of each UAV node
            per unit time, used as the demand floor in flow-balance
            constraints. [ESTIMATED] 15 W is a first-order estimate.
        human_accessible_kinds: Node kinds treated as human-accessible
            for MPE purposes. MPE constraints are emitted only for
            links whose target node kind is in this set. Default is
            {GROUND_STATION}: in the current node-kind set that is the
            only location where an unshielded person may be present
            at the beam target.

            IMPORTANT — this is a first-order simplification, not a
            complete safety model. A ground-launched or satellite-
            launched beam passes through human-accessible altitude near
            the transmitter and near the target; the air column above
            both endpoints is not human-accessible, but the terminal
            segments are. A complete model would additionally constrain
            the beam path where it crosses regions in which people may
            be present. That extension is deferred; see Section 16 of
            the specification. The current model treats only the
            target node kind as the discriminator.

            WARNING — configuring this set too narrowly (omitting
            GROUND_STATION, for example) causes the encoder to declare
            unsafe architectures SAT. UNSAT is the definitive verdict
            in Stage B; a false SAT is a soundness failure. Every
            caller that overrides this field must justify the override
            and, where applicable, add an MPE constraint family for the
            omitted case.
    """

    uav_assumed_transmit_w: float = 20.0
    node_default_demand_w: float = 15.0
    human_accessible_kinds: frozenset[Terminal] = frozenset({Terminal.GROUND_STATION})

    def __post_init__(self) -> None:
        if self.uav_assumed_transmit_w <= 0.0:
            raise ValueError(
                f"uav_assumed_transmit_w must be > 0; got {self.uav_assumed_transmit_w}"
            )
        if self.node_default_demand_w <= 0.0:
            raise ValueError(f"node_default_demand_w must be > 0; got {self.node_default_demand_w}")
        if not self.human_accessible_kinds:
            raise ValueError("human_accessible_kinds must be non-empty")


DEFAULT_ENCODER_CONFIG = EncoderConfig()
"""Default configuration. Both values are [ESTIMATED]; callers running
parameter studies should construct their own EncoderConfig."""


_LASER_MPE_BOUNDARY_NM = 792.0
"""Midpoint between the two MPE table wavelengths (520 nm and 1064 nm).
Wavelengths below this use the 520 nm MPE; above, the 1064 nm MPE."""


def _nearest_laser_wavelength_nm(wavelength_nm: float) -> float:
    """Return the closest MPE table wavelength for a given wavelength."""
    return 520.0 if wavelength_nm < _LASER_MPE_BOUNDARY_NM else 1064.0


def _transmit_power_w(
    arch: Architecture,
    link: LinkInstance,
    config: EncoderConfig,
) -> float:
    """Return the transmit power assigned to a link.

    Uses the source node's ``power_w`` when present; falls back to
    ``config.uav_assumed_transmit_w`` otherwise.
    """
    source = next((n for n in arch.nodes if n.node_id == link.source_id), None)
    if source is not None and "power_w" in source.params:
        return float(source.params["power_w"])
    return config.uav_assumed_transmit_w


def _peak_intensity_w_per_m2(power_w: float, aperture_m: float) -> float:
    """Peak intensity at the receiver aperture.

    Treats the aperture as a circular collecting area of radius
    ``aperture_m``: I = P / (pi * r^2). This over-estimates intensity
    relative to a properly beam-spread link because it does not model
    diffraction losses; it is the conservative choice for a safety
    constraint.
    """
    if aperture_m <= 0.0:
        return float("inf")
    return power_w / (math.pi * aperture_m * aperture_m)


def _z3_sum(terms: list[z3.ArithRef]) -> z3.ArithRef:
    """Sum a list of Z3 arithmetic terms, returning 0.0 for an empty list."""
    if not terms:
        return z3.RealVal(0.0)
    total: z3.ArithRef = terms[0]
    for t in terms[1:]:
        total = total + t
    return total


def _regulatory_constraints(
    arch: Architecture,
    link: LinkInstance,
    config: EncoderConfig,
) -> list[FeatureConstraint]:
    """Return the MPE constraint(s) for one link.

    MPE is emitted only when the link's target node kind is in
    ``config.human_accessible_kinds``. MPE governs human exposure;
    a beam terminating on a UAV in flight or a satellite is not
    subject to MPE at the target.

    This is a first-order simplification. It does not model beam-path
    exposure near the transmitter or near the target, where the beam
    passes through airspace that may contain people. That extension
    is deferred (see specification Section 16 and the note on
    ``EncoderConfig.human_accessible_kinds``).

    For a Hybrid_Link to a human-accessible target, both a laser and
    an RF MPE constraint are emitted. This is conservative: a hybrid
    link may switch modality at any time, so both limits must hold
    simultaneously.
    """
    target = next((n for n in arch.nodes if n.node_id == link.target_id), None)
    if target is None or target.kind not in config.human_accessible_kinds:
        return []

    out: list[FeatureConstraint] = []
    p_tx = _transmit_power_w(arch, link, config)
    aperture = float(link.params["aperture_m"])
    intensity = _peak_intensity_w_per_m2(p_tx, aperture)
    features = features_of_link(link)

    if link.kind == Terminal.LASER_LINK:
        wl = _nearest_laser_wavelength_nm(float(link.params["wavelength_nm"]))
        mpe = laser_mpe(wl).mpe_w_per_m2()
        out.append(
            FeatureConstraint(
                family_name=f"{link.link_id}_laser_mpe",
                expression=z3.RealVal(repr(intensity)) <= z3.RealVal(repr(mpe)),
                features=features,
            )
        )
    elif link.kind == Terminal.MICROWAVE_LINK:
        mpe_rf = RF_LIMIT_GENERAL_POPULATION.limit_w_per_m2()
        out.append(
            FeatureConstraint(
                family_name=f"{link.link_id}_rf_mpe",
                expression=z3.RealVal(repr(intensity)) <= z3.RealVal(repr(mpe_rf)),
                features=features,
            )
        )
    elif link.kind == Terminal.HYBRID_LINK:
        wl = _nearest_laser_wavelength_nm(float(link.params["wavelength_nm"]))
        mpe_l = laser_mpe(wl).mpe_w_per_m2()
        mpe_rf = RF_LIMIT_GENERAL_POPULATION.limit_w_per_m2()
        out.append(
            FeatureConstraint(
                family_name=f"{link.link_id}_hybrid_laser_mpe",
                expression=z3.RealVal(repr(intensity)) <= z3.RealVal(repr(mpe_l)),
                features=features,
            )
        )
        out.append(
            FeatureConstraint(
                family_name=f"{link.link_id}_hybrid_rf_mpe",
                expression=z3.RealVal(repr(intensity)) <= z3.RealVal(repr(mpe_rf)),
                features=features,
            )
        )
    return out


def encode_architecture(
    arch: Architecture,
    config: EncoderConfig | None = None,
) -> tuple[FeatureConstraint, ...]:
    """Encode an architecture as a tuple of real Stage B constraints.

    Returns a tuple of ``FeatureConstraint`` objects. Asserting them
    all into an ``UnsatCoreExtractor`` and calling ``check()`` yields
    SAT or UNSAT. On UNSAT, the returned core names map to grammar
    features via ``app.discovery.attribution.attribute_core``.

    Args:
        arch: The architecture to encode.
        config: Optional encoder configuration. Defaults to
            ``DEFAULT_ENCODER_CONFIG``.
    """
    cfg = config if config is not None else DEFAULT_ENCODER_CONFIG
    out: list[FeatureConstraint] = []

    uav_kinds = (Terminal.UAV_ENERGY, Terminal.UAV_COMPUTE)
    has_uav = any(n.kind in uav_kinds for n in arch.nodes)

    if not has_uav:
        out.append(
            FeatureConstraint(
                family_name="requires_uav",
                expression=z3.BoolVal(False),
                features=frozenset(
                    {
                        GrammarFeature(FeatureKind.NODE_TYPE, Terminal.UAV_ENERGY.value),
                        GrammarFeature(FeatureKind.NODE_TYPE, Terminal.UAV_COMPUTE.value),
                    }
                ),
            )
        )

    for link in arch.links:
        flow = z3.Real(f"{link.link_id}_flow")
        cap = LINK_BASE_CAPACITY[link.kind] * float(link.params["capacity_factor"])
        features = features_of_link(link)
        out.append(
            FeatureConstraint(
                family_name=f"{link.link_id}_flow_lb",
                expression=flow >= 0.0,
                features=features,
            )
        )
        out.append(
            FeatureConstraint(
                family_name=f"{link.link_id}_flow_cap",
                expression=flow <= z3.RealVal(repr(cap)),
                features=features,
            )
        )
        out.extend(_regulatory_constraints(arch, link, cfg))

    for source in arch.nodes:
        outgoing = [ln for ln in arch.links if ln.source_id == source.node_id]
        if not outgoing:
            continue
        supply = float(source.params.get("power_w", cfg.uav_assumed_transmit_w))
        flows = [z3.Real(f"{ln.link_id}_flow") for ln in outgoing]
        total = _z3_sum(flows)
        out.append(
            FeatureConstraint(
                family_name=f"{source.node_id}_supply",
                expression=total <= z3.RealVal(repr(supply)),
                features=frozenset(
                    {
                        GrammarFeature(FeatureKind.NODE_INSTANCE, source.node_id),
                        GrammarFeature(FeatureKind.NODE_TYPE, source.kind.value),
                    }
                ),
            )
        )

    for node in arch.nodes:
        if node.kind not in uav_kinds:
            continue
        incoming = [ln for ln in arch.links if ln.target_id == node.node_id]
        node_features = frozenset(
            {
                GrammarFeature(FeatureKind.NODE_INSTANCE, node.node_id),
                GrammarFeature(FeatureKind.NODE_TYPE, node.kind.value),
            }
        )
        if not incoming:
            out.append(
                FeatureConstraint(
                    family_name=f"{node.node_id}_demand_unmet",
                    expression=z3.BoolVal(False),
                    features=node_features,
                )
            )
            continue
        flows = [z3.Real(f"{ln.link_id}_flow") for ln in incoming]
        total = _z3_sum(flows)
        out.append(
            FeatureConstraint(
                family_name=f"{node.node_id}_demand",
                expression=total >= z3.RealVal(repr(cfg.node_default_demand_w)),
                features=node_features,
            )
        )

    return tuple(out)


@dataclass(frozen=True)
class SceneConfig:
    """Environmental and receiver conditions for the physics encoder.

    These are properties of a scene, not of how the encoder is
    configured for a study. They live in a separate dataclass from
    ``EncoderConfig`` to preserve that distinction in the type system
    (see docs/ENCODER_PHYSICS_INTEGRATION.md, Decision 2).

    Every field marked [ESTIMATED] must be replaced with a sourced
    value before any publication or commercial use. The only [MEASURED]
    field is ``ambient_temperature_k`` at CODATA 25 C.

    Attributes:
        visibility_km: Meteorological visibility in km.
            [ESTIMATED] 20 km corresponds to a clear day with slight
            haze. Physical range 0.05 to 100 km (physics/atmosphere
            Kruse-Kim validity).
        cloud_factor: Cloud cover fraction in [0, 1]. [ESTIMATED] 0.0
            is a clear sky; 1.0 is overcast.
        ambient_temperature_k: Ambient air temperature. [MEASURED]
            298.15 K is the CODATA 25 C reference.
        receiver_plc_temperature_k: Reference PLC temperature for the
            PV-TE receiver efficiency evaluation. [ESTIMATED] 298.15 K
            is ambient; a real receiver under illumination runs hotter.
        receiver_te_hot_temperature_k: Reference TE hot-side temperature.
            [ESTIMATED] 320 K is a modest differential above ambient.
        receiver_te_cold_temperature_k: Reference TE cold-side
            temperature. [ESTIMATED] 298.15 K is ambient.
        battery_efficiency: Battery charging efficiency. [ESTIMATED]
            0.92 is typical for Li-ion.
        transmitter_waist_radius_m: Beam waist radius at the transmitter.
            [ESTIMATED] 0.02 m (2 cm) is a reasonable aperture for a
            modest laser or RF transmitter. The link's own aperture_m
            parameter is the *receiver* aperture, not the transmitter
            waist.
        rf_transmittance: Scalar transmittance for microwave links.
            [ESTIMATED] 0.98 corresponds to very small atmospheric loss
            at 2.45/5.8 GHz over km-scale paths in clear air.
            physics/atmosphere is a laser-wavelength model (valid for
            400-1550 nm) and is not applied to RF links. A full RF
            atmospheric model is deferred.
        receiver_conversion_efficiency: Optional scalar override for
            the laser receiver conversion efficiency. When None (the
            default), physics/receiver.eta_total is evaluated at the
            reference temperatures above. That model returns
            approximately 0.15 percent at any reasonable reference
            temperature, far below the 38.49 percent champion value
            the specification quotes for the Han et al. receiver,
            because the tandem model is an acknowledged first-order
            lumped approximation (receiver.py docstring; spec Section
            33.2). Setting this field to a float replaces the model
            for laser chains. The default of None ensures no hidden
            number is substituted for the model.
        atmosphere_config: Configuration for physics/atmosphere. Uses
            the module default when not overridden.
    """

    visibility_km: float = 20.0
    cloud_factor: float = 0.0
    ambient_temperature_k: float = 298.15
    receiver_plc_temperature_k: float = 298.15
    receiver_te_hot_temperature_k: float = 320.0
    receiver_te_cold_temperature_k: float = 298.15
    battery_efficiency: float = 0.92
    transmitter_waist_radius_m: float = 0.02
    rf_transmittance: float = 0.98
    receiver_conversion_efficiency: float | None = None
    atmosphere_config: _atmosphere.AtmosphereConfig = dataclass_field(
        default_factory=_atmosphere.AtmosphereConfig
    )

    def __post_init__(self) -> None:
        if self.visibility_km <= 0.0:
            raise ValueError(f"visibility_km must be > 0; got {self.visibility_km}")
        if not 0.0 <= self.cloud_factor <= 1.0:
            raise ValueError(f"cloud_factor must be in [0, 1]; got {self.cloud_factor}")
        if self.ambient_temperature_k <= 0.0:
            raise ValueError(f"ambient_temperature_k must be > 0; got {self.ambient_temperature_k}")
        if self.receiver_plc_temperature_k <= 0.0:
            raise ValueError(
                f"receiver_plc_temperature_k must be > 0; got {self.receiver_plc_temperature_k}"
            )
        if self.receiver_te_hot_temperature_k <= 0.0:
            raise ValueError(
                "receiver_te_hot_temperature_k must be > 0; got "
                f"{self.receiver_te_hot_temperature_k}"
            )
        if self.receiver_te_cold_temperature_k <= 0.0:
            raise ValueError(
                "receiver_te_cold_temperature_k must be > 0; got "
                f"{self.receiver_te_cold_temperature_k}"
            )
        if not 0.0 < self.battery_efficiency <= 1.0:
            raise ValueError(f"battery_efficiency must be in (0, 1]; got {self.battery_efficiency}")
        if self.transmitter_waist_radius_m <= 0.0:
            raise ValueError(
                f"transmitter_waist_radius_m must be > 0; got {self.transmitter_waist_radius_m}"
            )
        if not 0.0 < self.rf_transmittance <= 1.0:
            raise ValueError(f"rf_transmittance must be in (0, 1]; got {self.rf_transmittance}")
        if self.receiver_conversion_efficiency is not None and not (
            0.0 < self.receiver_conversion_efficiency <= 1.0
        ):
            raise ValueError(
                "receiver_conversion_efficiency must be in (0, 1] when set; "
                f"got {self.receiver_conversion_efficiency}"
            )


DEFAULT_SCENE_CONFIG = SceneConfig()


def _node_position_m(node: NodeInstance) -> tuple[float, float, float]:
    """Return the 3D Cartesian position of a node on a spherical Earth.

    Latitude and longitude in degrees; altitude from either
    ``altitude_km`` (satellites) or ``altitude_m`` (UAVs and ground
    stations). Earth-centre origin, z-axis through the north pole,
    x-axis through the (0, 0) meridian. Units are metres.
    """
    lat_rad = math.radians(float(node.params["lat_deg"]))
    lon_rad = math.radians(float(node.params["lon_deg"]))
    if "altitude_km" in node.params:
        alt_m = float(node.params["altitude_km"]) * 1000.0
    elif "altitude_m" in node.params:
        alt_m = float(node.params["altitude_m"])
    else:
        alt_m = 0.0
    r = _EARTH_RADIUS_M + alt_m
    return (
        r * math.cos(lat_rad) * math.cos(lon_rad),
        r * math.cos(lat_rad) * math.sin(lon_rad),
        r * math.sin(lat_rad),
    )


def _range_m(
    pos_a: tuple[float, float, float],
    pos_b: tuple[float, float, float],
) -> float:
    """Euclidean distance between two 3D positions, in metres."""
    dx = pos_b[0] - pos_a[0]
    dy = pos_b[1] - pos_a[1]
    dz = pos_b[2] - pos_a[2]
    return float(math.sqrt(dx * dx + dy * dy + dz * dz))


def _atmospheric_path_length_m(
    p_source: tuple[float, float, float],
    p_target: tuple[float, float, float],
    *,
    earth_radius_m: float = _EARTH_RADIUS_M,
    h_atmosphere_m: float = _H_ATMOSPHERE_M,
) -> float:
    """Length of the segment [source, target] inside the atmosphere shell.

    The atmosphere is modelled as a spherical shell between radii
    ``earth_radius_m`` and ``earth_radius_m + h_atmosphere_m``. The
    segment may be entirely inside, entirely outside, or cross the
    shell once. Returns the length of the in-shell portion.

    This is the correct path length to feed to
    ``physics/atmosphere.transmission``. Using the full geometric
    distance would apply a ground-level extinction coefficient to a
    vacuum path and underflow to zero (docs/ENCODER_PHYSICS_INTEGRATION.md,
    Decision 7).
    """
    r_outer = earth_radius_m + h_atmosphere_m

    def radius_squared(p: tuple[float, float, float]) -> float:
        return p[0] * p[0] + p[1] * p[1] + p[2] * p[2]

    source_inside = radius_squared(p_source) <= r_outer * r_outer
    target_inside = radius_squared(p_target) <= r_outer * r_outer

    if source_inside and target_inside:
        return _range_m(p_source, p_target)
    if not source_inside and not target_inside:
        return 0.0

    if source_inside:
        p_inside, p_outside = p_source, p_target
    else:
        p_inside, p_outside = p_target, p_source

    dx = p_outside[0] - p_inside[0]
    dy = p_outside[1] - p_inside[1]
    dz = p_outside[2] - p_inside[2]
    a = dx * dx + dy * dy + dz * dz
    b = 2.0 * (p_inside[0] * dx + p_inside[1] * dy + p_inside[2] * dz)
    c = radius_squared(p_inside) - r_outer * r_outer

    if a <= 0.0:
        return 0.0

    disc = b * b - 4.0 * a * c
    if disc < 0.0:
        return _range_m(p_source, p_target)

    sqrt_disc = math.sqrt(disc)
    t1 = (-b + sqrt_disc) / (2.0 * a)
    t2 = (-b - sqrt_disc) / (2.0 * a)
    positive_roots = [t for t in (t1, t2) if t > 0.0]
    if not positive_roots:
        return 0.0
    t_exit = min(min(positive_roots), 1.0)
    return float(t_exit * math.sqrt(a))


def _has_line_of_sight(
    pos_a: tuple[float, float, float],
    pos_b: tuple[float, float, float],
    *,
    earth_radius_m: float = _EARTH_RADIUS_M,
    grazing_tolerance: float = 1e-6,
) -> bool:
    """True if the straight segment between two points clears the Earth.

    Computes the minimum distance from the Earth's centre to the
    closed segment [A, B] and compares to the Earth radius. A small
    grazing tolerance (``grazing_tolerance * earth_radius_m``) allows
    tangent segments to count as line of sight.
    """
    abx = pos_b[0] - pos_a[0]
    aby = pos_b[1] - pos_a[1]
    abz = pos_b[2] - pos_a[2]
    ab_dot_ab = abx * abx + aby * aby + abz * abz
    if ab_dot_ab <= 0.0:
        # Coincident points; the segment has zero length and lies at A.
        d_min = math.sqrt(pos_a[0] ** 2 + pos_a[1] ** 2 + pos_a[2] ** 2)
    else:
        t_star = -(pos_a[0] * abx + pos_a[1] * aby + pos_a[2] * abz) / ab_dot_ab
        t_clamped = max(0.0, min(1.0, t_star))
        cx = pos_a[0] + t_clamped * abx
        cy = pos_a[1] + t_clamped * aby
        cz = pos_a[2] + t_clamped * abz
        d_min = math.sqrt(cx * cx + cy * cy + cz * cz)
    return d_min >= earth_radius_m * (1.0 - grazing_tolerance)


def _laser_chain_efficiency(
    link: LinkInstance,
    range_m: float,
    atmospheric_path_m: float,
    scene: SceneConfig,
) -> float:
    """Beam * atmosphere * PV-TE receiver * battery efficiency.

    The receiver efficiency is evaluated at the reference temperatures
    in ``scene``, not at the transient operating point. This is a
    reference evaluation, not a thermal solve; the transient state is
    Tier 2 territory.
    """
    wl_nm = float(link.params["wavelength_nm"])
    receiver_radius_m = float(link.params["aperture_m"])
    w_at_receiver = _beam.beam_radius_m(wl_nm, scene.transmitter_waist_radius_m, range_m)
    eta_beam = _beam.combined_beam_efficiency(w_at_receiver, receiver_radius_m, 0.0)
    eta_atm = _atmosphere.transmission(
        wavelength_nm=wl_nm,
        path_length_m=atmospheric_path_m,
        visibility_km=scene.visibility_km,
        cloud_factor=scene.cloud_factor,
        config=scene.atmosphere_config,
    )
    if scene.receiver_conversion_efficiency is not None:
        eta_receiver = scene.receiver_conversion_efficiency
    else:
        eta_receiver = _receiver.eta_total(
            t_plc_k=scene.receiver_plc_temperature_k,
            t_te_hot_k=scene.receiver_te_hot_temperature_k,
            t_te_cold_k=scene.receiver_te_cold_temperature_k,
        )
    return float(eta_beam * eta_atm * eta_receiver * scene.battery_efficiency)


def _rf_chain_efficiency(
    link: LinkInstance,
    range_m: float,
    transmit_power_w: float,
    scene: SceneConfig,
) -> float:
    """Beam * RF transmittance * rectenna * battery efficiency.

    The rectenna efficiency depends on the incident power density at
    the receiver aperture. That density depends on the transmit power
    and the upstream beam and atmospheric losses, none of which depend
    on the rectenna efficiency. There is no fixed point; the chain
    evaluates in one forward sweep.
    """
    freq_ghz = float(link.params["frequency_ghz"])
    wavelength_m = _SPEED_OF_LIGHT_M_PER_S / (freq_ghz * 1.0e9)
    wavelength_nm = wavelength_m * 1.0e9
    receiver_radius_m = float(link.params["aperture_m"])

    w_at_receiver = _beam.beam_radius_m(wavelength_nm, scene.transmitter_waist_radius_m, range_m)
    eta_beam = _beam.combined_beam_efficiency(w_at_receiver, receiver_radius_m, 0.0)
    eta_atm = scene.rf_transmittance

    aperture_area_m2 = math.pi * receiver_radius_m * receiver_radius_m
    p_incident_w = transmit_power_w * eta_beam * eta_atm
    if aperture_area_m2 > 0.0:
        incident_density_w_per_m2 = p_incident_w / aperture_area_m2
    else:
        incident_density_w_per_m2 = float("inf")
    eta_rectenna = _rectenna.rectenna_efficiency(incident_density_w_per_m2, freq_ghz)

    return float(eta_beam * eta_atm * eta_rectenna * scene.battery_efficiency)


def _physical_link_delivered_w(
    arch: Architecture,
    link: LinkInstance,
    range_m: float,
    scene: SceneConfig,
    config: EncoderConfig,
) -> float:
    """DC power delivered at the battery for one link, in watts.

    For a Hybrid_Link the delivered power is the minimum of the laser
    chain and the RF chain: the operator may be forced into either
    modality by conditions, so the promised capacity is the weaker of
    the two (see docs/ENCODER_PHYSICS_INTEGRATION.md, Decision 3).
    """
    p_tx = _transmit_power_w(arch, link, config)
    source = next((n for n in arch.nodes if n.node_id == link.source_id), None)
    target = next((n for n in arch.nodes if n.node_id == link.target_id), None)
    if source is None or target is None:
        return 0.0
    atmospheric_path_m = _atmospheric_path_length_m(
        _node_position_m(source), _node_position_m(target)
    )

    if link.kind == Terminal.LASER_LINK:
        return float(p_tx * _laser_chain_efficiency(link, range_m, atmospheric_path_m, scene))

    if link.kind == Terminal.MICROWAVE_LINK:
        return float(p_tx * _rf_chain_efficiency(link, range_m, p_tx, scene))

    if link.kind == Terminal.HYBRID_LINK:
        laser = p_tx * _laser_chain_efficiency(link, range_m, atmospheric_path_m, scene)
        rf = p_tx * _rf_chain_efficiency(link, range_m, p_tx, scene)
        return float(min(laser, rf))

    raise ValueError(f"unsupported link kind {link.kind}")


def _physics_constraints(
    arch: Architecture,
    scene: SceneConfig,
    config: EncoderConfig,
) -> list[FeatureConstraint]:
    """Emit the physics constraint families for every link.

    Two families per link, when applicable:

    - ``<link_id>_physical_los``: FALSE if the straight segment between
      the source and target nodes passes below the Earth's surface.
    - ``<link_id>_physical_flow_cap``: flow <= delivered_w computed from
      the physical chain (beam geometry, atmospheric transmittance,
      receiver conversion, battery efficiency).

    When line of sight fails the flow-cap constraint is not emitted;
    the LOS FALSE constraint alone makes the architecture UNSAT.
    """
    out: list[FeatureConstraint] = []
    for link in arch.links:
        source = next((n for n in arch.nodes if n.node_id == link.source_id), None)
        target = next((n for n in arch.nodes if n.node_id == link.target_id), None)
        if source is None or target is None:
            # Architecture validation forbids dangling references; this
            # guard exists for defensive type narrowing only.
            continue

        features = features_of_link(link)
        p_source = _node_position_m(source)
        p_target = _node_position_m(target)

        if not _has_line_of_sight(p_source, p_target):
            out.append(
                FeatureConstraint(
                    family_name=f"{link.link_id}_physical_los",
                    expression=z3.BoolVal(False),
                    features=features,
                )
            )
            continue

        range_m = _range_m(p_source, p_target)
        delivered_w = _physical_link_delivered_w(arch, link, range_m, scene, config)
        if not math.isfinite(delivered_w) or delivered_w < 0.0:
            # Non-physical chain value; skip the constraint rather than
            # emitting an unbounded or invalid bound. This should not
            # occur for architectures produced by the current generator.
            continue
        flow = z3.Real(f"{link.link_id}_flow")
        out.append(
            FeatureConstraint(
                family_name=f"{link.link_id}_physical_flow_cap",
                expression=flow <= z3.RealVal(repr(delivered_w)),
                features=features,
            )
        )
    return out


def encode_architecture_with_physics(
    arch: Architecture,
    config: EncoderConfig | None = None,
    scene: SceneConfig | None = None,
) -> tuple[FeatureConstraint, ...]:
    """Encode an architecture with both flow constraints and physics.

    Calls ``encode_architecture`` first, then appends the physics
    constraint families. The result is a strict superset of the base
    encoding: every architecture UNSAT under ``encode_architecture``
    is UNSAT under this function, and some architectures SAT under the
    base encoding are UNSAT under this function because they violate
    line of sight or the physical chain.

    ``encode_architecture`` is unchanged by this addition. This
    function is the additive step (PR-B) of the encoder physics
    integration; the semantic flip (PR-C) will either make the base
    function delegate here or change the loop's call site.

    Args:
        arch: The architecture to encode.
        config: Optional ``EncoderConfig``. Defaults to
            ``DEFAULT_ENCODER_CONFIG``.
        scene: Optional ``SceneConfig``. Defaults to
            ``DEFAULT_SCENE_CONFIG``.

    Returns:
        A tuple of ``FeatureConstraint`` objects: the base set plus
        the physics families.
    """
    cfg = config if config is not None else DEFAULT_ENCODER_CONFIG
    sc = scene if scene is not None else DEFAULT_SCENE_CONFIG
    base = list(encode_architecture(arch, cfg))
    base.extend(_physics_constraints(arch, sc, cfg))
    return tuple(base)
