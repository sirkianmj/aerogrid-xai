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
     for Hybrid_Link. Deliberately conservative: a hybrid link may
     switch modality at any time, so it must satisfy both safety limits
     simultaneously.

5. UAV-presence structural constraint:
   - ``requires_uav``: FALSE if the architecture contains no UAV node.

6. Physics extension (opt-in via ``encode_architecture_with_physics``):
   - ``<link_id>_physical_los``: FALSE if the segment between source and
     target passes below the Earth's surface.
   - ``<link_id>_physical_flow_cap``: flow <= delivered_w computed from
     the physical chain (beam geometry, atmospheric transmittance,
     receiver conversion, battery efficiency).

Configuration
-------------

``EncoderConfig`` holds study-level choices (transmit power fallback,
demand floor, which node kinds are human-accessible for MPE).

``SceneConfig`` holds environmental and receiver conditions (visibility,
cloud, temperatures, battery efficiency, transmitter waist, RF
transmittance, optional receiver-efficiency override). The two are
separate so that the epistemic distinction between "study choices" and
"scene properties" is preserved in the type system. See
docs/ENCODER_PHYSICS_INTEGRATION.md for the design reasoning.
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
from app.physics import geometry as _geometry
from app.physics import receiver as _receiver
from app.physics import rectenna as _rectenna
from app.verification.regulatory import (
    RF_LIMIT_GENERAL_POPULATION,
    laser_mpe,
)


@dataclass(frozen=True)
class EncoderConfig:
    """Study-level configuration for ``encode_architecture``.

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
            the specification.

            WARNING — configuring this set too narrowly (omitting
            GROUND_STATION, for example) causes the encoder to declare
            unsafe architectures SAT. UNSAT is the definitive verdict
            in Stage B; a false SAT is a soundness failure.
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
"""Default configuration. uav_assumed_transmit_w and
node_default_demand_w are [ESTIMATED]; callers running parameter studies
should construct their own EncoderConfig."""


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
    ``aperture_m``: I = P / (pi * r^2). Over-estimates intensity
    relative to a properly beam-spread link (no diffraction losses);
    conservative for a safety constraint.
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
    ``config.human_accessible_kinds``. MPE governs human exposure; a
    beam terminating on a UAV in flight or a satellite is not subject
    to MPE at the target.

    For a Hybrid_Link to a human-accessible target, both a laser and an
    RF MPE constraint are emitted. Conservative: a hybrid link may
    switch modality at any time, so both limits must hold.
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


# --- Physics extension ----------------------------------------------------


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
    """Return the 3D Cartesian position of an architecture node.

    Thin wrapper around ``physics.geometry.node_position_from_params_m``
    so that call sites within this module remain unchanged.
    """
    return _geometry.node_position_from_params_m(node.params)


_range_m = _geometry.range_m
_has_line_of_sight = _geometry.has_line_of_sight
_atmospheric_path_length_m = _geometry.atmospheric_path_length_m
_EARTH_RADIUS_M = _geometry.EARTH_RADIUS_M
_SPEED_OF_LIGHT_M_PER_S = _geometry.SPEED_OF_LIGHT_M_PER_S
_H_ATMOSPHERE_M = _geometry.H_ATMOSPHERE_M


def _laser_chain_efficiency(
    link: LinkInstance,
    range_m: float,
    atmospheric_path_m: float,
    scene: SceneConfig,
) -> float:
    """Beam * atmosphere * PV-TE receiver * battery efficiency.

    ``range_m`` is the full geometric distance from source to target,
    used for beam spreading. ``atmospheric_path_m`` is the portion of
    the path that lies inside the atmosphere shell, used for
    Beer-Lambert transmittance (design doc, Decision 7).

    The receiver efficiency is evaluated at the reference temperatures
    in ``scene`` unless ``scene.receiver_conversion_efficiency`` is set,
    in which case the scalar override is used.
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

    ``encode_architecture`` is unchanged by this addition.

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
