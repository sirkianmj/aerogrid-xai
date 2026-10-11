"""Real Stage B encoder: architecture -> FeatureConstraint tuple.

Unlike the placeholder ``encode_architecture_to_z3`` in
``app.discovery.generator``, this module emits constraints that
reference actual physics: ANSI Z136.1 laser MPE, FCC Part 1.1310 RF
power-density limit, and linear flow-balance constraints over Z3 real
variables. Each emitted constraint is tagged with the grammar features
of the nodes and links that generated it, so the unsat core can be
attributed back to specific grammar elements via
``app.discovery.attribution``.

Constraint families emitted
---------------------------

1. Per-link flow variable bounds:
   - ``<link_id>_flow_lb``: flow >= 0.
   - ``<link_id>_flow_cap``: flow <= LINK_BASE_CAPACITY[kind] * capacity_factor.

2. Per-source supply bound:
   - ``<source_id>_supply``: sum of outgoing flows <= source supply_w.

3. Per-UAV demand floor:
   - ``<uav_id>_demand``: sum of incoming flows >= NODE_DEFAULT_DEMAND_W.
   - If the UAV has no incoming links, emits ``<uav_id>_demand_unmet``
     as a constant FALSE constraint, which is a minimal UNSAT core of
     size 1 attributable to that UAV's features.

4. Per-link regulatory MPE:
   - ``<link_id>_laser_mpe`` for Laser_Link.
   - ``<link_id>_rf_mpe`` for Microwave_Link.
   - Both families for Hybrid_Link.
   Intensity is P / (pi * aperture^2) W/m^2. MPE is from
   app.verification.regulatory. A laser link whose intensity exceeds
   MPE is UNSAT with a singleton core naming that link.

5. UAV-presence structural constraint:
   - ``requires_uav``: FALSE if the architecture contains no UAV node.
     Prevents the discovery loop from converging on source-only
     degenerate architectures.
"""

from __future__ import annotations

import math

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
    Terminal,
)
from app.verification.regulatory import (
    RF_LIMIT_GENERAL_POPULATION,
    laser_mpe,
)

UAV_ASSUMED_TRANSMIT_W = 20.0
"""Assumed transmit power for a link whose source is a UAV. UAV node
kinds do not carry a ``power_w`` parameter in the current generator;
20 W is a first-order estimate for a small airborne transmitter."""

NODE_DEFAULT_DEMAND_W = 15.0
"""Assumed minimum power demand of each UAV node per unit time. Used
as the demand floor in the flow-balance constraints."""

_LASER_MPE_BOUNDARY_NM = 792.0
"""Midpoint between the two MPE table wavelengths (520 nm and 1064 nm).
Wavelengths below this use the 520 nm MPE; above, the 1064 nm MPE."""


def _nearest_laser_wavelength_nm(wavelength_nm: float) -> float:
    """Return the closest MPE table wavelength for a given wavelength."""
    return 520.0 if wavelength_nm < _LASER_MPE_BOUNDARY_NM else 1064.0


def _transmit_power_w(arch: Architecture, link: LinkInstance) -> float:
    """Return the transmit power assigned to a link.

    Uses the source node's ``power_w`` when present; falls back to
    ``UAV_ASSUMED_TRANSMIT_W`` otherwise.
    """
    source = next((n for n in arch.nodes if n.node_id == link.source_id), None)
    if source is not None and "power_w" in source.params:
        return float(source.params["power_w"])
    return UAV_ASSUMED_TRANSMIT_W


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
) -> list[FeatureConstraint]:
    """Return the MPE constraint(s) for one link."""
    out: list[FeatureConstraint] = []
    p_tx = _transmit_power_w(arch, link)
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


def encode_architecture(arch: Architecture) -> tuple[FeatureConstraint, ...]:
    """Encode an architecture as a tuple of real Stage B constraints.

    Returns a tuple of ``FeatureConstraint`` objects. Asserting them
    all into an ``UnsatCoreExtractor`` and calling ``check()`` yields
    SAT or UNSAT. On UNSAT, the returned core names map to grammar
    features via ``app.discovery.attribution.attribute_core``.
    """
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
        out.extend(_regulatory_constraints(arch, link))

    for source in arch.nodes:
        outgoing = [ln for ln in arch.links if ln.source_id == source.node_id]
        if not outgoing:
            continue
        supply = float(source.params.get("power_w", UAV_ASSUMED_TRANSMIT_W))
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
                expression=total >= z3.RealVal(repr(NODE_DEFAULT_DEMAND_W)),
                features=node_features,
            )
        )

    return tuple(out)
