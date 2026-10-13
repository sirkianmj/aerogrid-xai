# Encoder physics integration — design

**Status:** design proposal, no code yet
**Target commit base:** `b229bfc`
**Spec references:** Rev. 6, Sections 8.4, 9, 16, 20, 21, 32, 34.3, 35.4

## 1. Scope

`backend/app/verification/architecture_encoder.py` currently emits five
constraint families:

1. `<link>_flow_lb` / `<link>_flow_cap` — flow bounds with a placeholder
   capacity `LINK_BASE_CAPACITY[kind] * capacity_factor`
2. `<source>_supply` — sum of outgoing flows ≤ source `power_w`
3. `<uav>_demand` / `<uav>_demand_unmet` — incoming flow floor
4. per-link regulatory MPE (laser, RF, or both for hybrid)
5. `requires_uav` — FALSE if the architecture has no UAV

The flow capacity bound in family 1 is a placeholder. It does not
reference the physical link budget (`build_physical_link_budget`),
the atmospheric model (`physics/atmosphere.py`), the beam geometry
(`physics/beam.py`), the PV-TE receiver (`physics/receiver.py`), or
the rectenna (`physics/rectenna.py`). This design fixes that.

The goal: an architecture is SAT under the encoder **if and only if**
it is feasible under the real physics this platform models.

This document states the design decisions required to get there. It
contains no code. The code lands in PR-B (additive, backward
compatible) and PR-C (semantic flip), described in §6.

## 2. The six decisions

Each section states the question, the options considered, the chosen
answer, the reasoning, and the disclosure.

### Decision 1 — Range: where does propagation distance come from?

**Question.** The physical link budget requires a propagation range
in metres. Node parameters in the generator carry `lat_deg`,
`lon_deg`, and `altitude_m` (or `altitude_km` for satellites). How is
range derived?

**Options.**

- (a) Skyfield `look_angle(node, t)` from `physics/orbital.py`. Uses
  SGP4/SDP4 with a `Time` argument.
- (b) Euclidean distance in 3D Cartesian coordinates on a spherical
  Earth of radius 6371 km.
- (c) Great-circle distance on the surface, altitude ignored.

**Chosen: (b).**

**Reasoning.**

The specification requires SGP4/SDP4 for *orbital state* (Section 7.1)
— computing a satellite's position and velocity at a given time for
visibility-window analysis, eclipse detection, and pass scheduling.
It does not require the encoder to know the satellite's instantaneous
position; the encoder classifies architectures, not passes.

Option (a) would force every `check()` to take a `Time` argument and
depend on ephemeris state. That breaks the s4-8 determinism gate ("same
UNSAT core → same bias, twice"), because the encoder's output would
depend on an external TLE and the current clock. It would also make
`run_clear_d_loop` depend on ephemeris state during an NSGA-II run,
which is a category error: architecture feasibility is a property of
the *design*, not of the current moment.

Option (c) ignores altitude, which for satellite-to-ground links is
the dominant term. The Euclidean 3D distance on a spherical Earth is
the minimal correct treatment.

**Line of sight.** With 3D coordinates, the encoder also emits a
new constraint family `<link>_los`: FALSE if the straight segment
between the two node positions passes below the Earth's surface.
This is the physically meaningful "can the beam reach" test. A LEO
satellite on the far side of the Earth is then correctly infeasible
by a singleton core naming the satellite and the link.

**Coordinate conversion.** For node at latitude `lat` (deg), longitude
`lon` (deg), altitude `alt` (m):

    R = 6_371_000.0  # metres, spherical Earth radius
    r = R + alt
    x = r * cos(radians(lat)) * cos(radians(lon))
    y = r * cos(radians(lat)) * sin(radians(lon))
    z = r * sin(radians(lat))

**Line-of-sight test.** For endpoints A, B with position vectors
`p_A`, `p_B`, let `AB = p_B - p_A`. The minimum distance from the
origin (Earth centre) to the segment [A, B] is:

    t*  = clamp(-p_A · AB / (AB · AB), 0, 1)
    d_min = |p_A + t* · AB|

LOS holds iff `d_min >= R`. Equality is grazing; the constraint is
emitted as `d_min > R` with a small tolerance (`1e-6 * R`) to avoid
numerical edge cases.

**Disclosure.** A spherical Earth with R = 6371 km differs from WGS-84
ellipsoid geometry by up to ~21 km radius at any point. For links of
thousands of kilometres this shifts the horizon by kilometres; for
link-budget range it shifts distance by percent. The choice is
documented in the encoder; if the platform later requires ellipsoidal
accuracy, `physics/orbital.py` already has the Skyfield primitives,
but the design decision here is that the encoder uses a pure,
deterministic geometric model, not an ephemeris.

### Decision 2 — Environmental inputs: where do visibility, cloud, and temperature live?

**Question.** The atmospheric transmittance model needs
`visibility_km` and `cloud_factor`. The PV-TE receiver model needs
hot-side and cold-side temperatures. The battery stage needs a
charging efficiency. These are scene properties, not architectural
properties. Where do they live in the encoder's public interface?

**Options.**

- (a) Add fields to `EncoderConfig`.
- (b) Add a new frozen dataclass `SceneConfig` alongside
  `EncoderConfig`.
- (c) Read from module-level defaults.

**Chosen: (b).**

**Reasoning.**

`EncoderConfig` currently holds two categories of thing:
algorithm choices (`human_accessible_kinds`, `uav_assumed_transmit_w`)
and demand floors (`node_default_demand_w`). These are properties of
*how the encoder is configured for a study*.

Environmental conditions (visibility, cloud cover, ambient
temperature) and receiver defaults are properties of *a specific run
of the encoder against a specific scene*. They have different
lifetimes and different provenance.

The specification's epistemic hierarchy (Section 21) draws the same
distinction: a "validated physical model" is a model fit against
measurements for a specific configuration; a "simulation result"
depends on the scene in which the simulation is run. Keeping scene
inputs separate from encoder algorithm choices preserves this
distinction in the type system.

**`SceneConfig` fields (proposed).**

    visibility_km: float = 20.0         [ESTIMATED] default
    cloud_factor: float = 0.0           [ESTIMATED] default (clear sky)
    ambient_temperature_k: float = 298.15   [MEASURED] CODATA 25 C
    receiver_plc_temperature_k: float = 298.15   [ESTIMATED]
    receiver_te_hot_temperature_k: float = 320.0 [ESTIMATED]
    receiver_te_cold_temperature_k: float = 298.15 [ESTIMATED]
    battery_efficiency: float = 0.92    [ESTIMATED] Li-ion typical
    transmitter_waist_radius_m: float = 0.02 [ESTIMATED] typical laser/RF
                                       transmitter waist; the link's own
                                       aperture_m is the receiver aperture
    rf_transmittance: float = 0.98      [ESTIMATED] scalar microwave-link
                                       transmittance; a full RF atmospheric
                                       model is deferred (physics/atmosphere
                                       is a laser-wavelength model, valid
                                       for 400-1550 nm)

All `[ESTIMATED]` fields carry the standard warning: replace with
sourced values before any publication or commercial use. Every field
is validated on construction (finite, positive where applicable,
cloud factor in [0, 1]).

**Placement.** `SceneConfig` lives in `architecture_encoder.py`, not
in a new file. It is small, it has exactly one consumer (the physics
encoder), and adding a file for it would be structure without
purpose.

### Decision 3 — Hybrid links: which modality governs feasibility?

**Question.** A `Hybrid_Link` carries both `wavelength_nm` and
`frequency_ghz`. The physics has both a laser chain and an RF chain.
Which one bounds the link's flow capacity?

**Options.**

- (a) Take the maximum of the two — hybrid delivers whichever is
  better at this scene.
- (b) Take the minimum of the two — hybrid must be capable in both.
- (c) Add a `mode` parameter per link choosing one modality.

**Chosen: (b).**

**Reasoning.**

This matches the existing conservative treatment in
`_regulatory_constraints`: a hybrid link currently emits **both**
laser MPE and RF MPE constraints, on the stated rationale that "a
hybrid link may switch modality at any time, so both limits must hold
simultaneously."

The same rationale applies to capacity. If the operator may switch to
laser in clear air and to microwave in cloud, the *architecture's*
guarantee is that the link works in whichever mode the operator
chooses at the moment of operation. If laser is blocked by fog but
microwave is available, the link still works. If microwave is
interfered but laser is available, still works. The promised capacity
is therefore the *minimum* of the two, because in the worst-moded
case the operator is limited to the weaker modality.

Taking the maximum (option a) would claim a capacity the link cannot
deliver in the mode the operator is forced into by conditions. That
is a soundness failure in the false-SAT direction, which is the
dangerous direction for Stage B.

**Disclosure.** Option (c) — a per-link `mode` parameter — is a
richer model that would let the operator commit to one modality at
construction time. That is deferred; the generator does not currently
sample a `mode` parameter, and adding one is a grammar extension
which per `grammar.py`'s own docstring requires a matching Stage B
constraint family and a migration note.

### Decision 4 — Receiver conversion efficiency

**Question.** The physical link budget's receiver stage needs a
conversion efficiency. For a laser-to-UAV link that is the PV-TE
tandem `receiver.eta_total(t_plc, t_hot, t_cold)`. For an RF link
that is a rectenna, whose efficiency depends on incident power
density — which the link budget itself computes. How is this handled?

**Chosen: for laser, use the receiver model with reference
temperatures from `SceneConfig`. For RF, use the rectenna model at the
incident power density the link budget produces.**

**Reasoning.**

For **laser**: `receiver.eta_total(t_plc, t_hot, t_cold)` takes only
temperatures (verified in earlier sessions; the load-bearing
attribution correction from Section 33.1: Sb₂Se₃ is not an input). The
encoder does not solve the thermal ODE, but it can evaluate the
efficiency at the reference temperatures from `SceneConfig`. This is
not the transient state — that is Tier 2 / digital-twin territory —
but it is the steady-state efficiency at the scene's nominal operating
point. Disclosed in the docstring as a reference-evaluation, not a
thermal solve.

For **RF**: the rectenna efficiency depends on the incident power
density, which depends on the transmitted power and the beam and
atmospheric losses *upstream* of the rectenna. Those upstream terms
do not depend on the rectenna efficiency. Therefore there is **no
fixed point**: compute the chain in order.

    1. P_transmit      = source_power_w
    2. beam_eff        = spillover * pointing (physics/beam)
    3. atmos_eff       = transmittance (physics/atmosphere)
    4. P_incident      = P_transmit * beam_eff * atmos_eff
    5. incident_density = P_incident / (pi * aperture^2)
    6. rectenna_eff    = rectenna_efficiency(incident_density, freq)
    7. receiver_chain  = P_transmit * beam_eff * atmos_eff * rectenna_eff
    8. final_flow_cap  = receiver_chain * battery_efficiency

Step 6 is closed-form. No iteration.

**Disclosure.** This is one sweep of the chain, not a self-consistent
solve for equilibrium. If the platform later adds feedback (e.g.,
rectenna heating affects efficiency, which affects power delivered,
which affects heating), a fixed-point solve would be required. The
current model has no such feedback and does not need one.

**Override for the laser receiver.** During implementation the
`receiver.eta_total` model at the reference temperatures was found to
return approximately 0.15 percent efficiency (the PLC contribution is
`eta_plc` ~ 15 percent, the TE contribution is ~ 1 percent at a
20 K hot-cold differential; their product is ~ 0.15 percent). This is
far below the 38.49 percent champion figure the specification quotes
for the Han et al. receiver (Section 6), because the tandem model is
an acknowledged first-order lumped approximation (see `receiver.py`
and spec Section 33.2).

Rather than resolve this discrepancy in the encoder (which would
require re-parameterizing the tandem model, a separate task),
`SceneConfig` gains a `receiver_conversion_efficiency: float | None`
field. When `None` (the default) the physics model is used, and the
resulting low efficiency is disclosed. When a float is given, it
overrides the model for laser chains. Callers running parameter
studies, or using a datasheet value for a specific receiver, set it
explicitly. The default is `None` so that no hidden number is
substituted for the model.

### Decision 5 — Replace flow-cap, or add alongside?

**Question.** The current `_flow_cap` uses `LINK_BASE_CAPACITY[kind] *
capacity_factor`. The physical chain produces a different number for
the same link. Do we replace `_flow_cap` or emit a second constraint?

**Chosen: add alongside, gated by a new function.**

**Reasoning.**

Three reasons.

1. **Backward compatibility of tests.** `test_architecture_encoder.py`
   has tests that directly exercise `_flow_cap`, `LINK_BASE_CAPACITY`,
   and the `flow_cap` family name in UNSAT cores. Replacing the
   constraint wholesale would silently change those tests' meaning.

2. **Two-part diagnosis.** Keeping both families lets the UNSAT core
   distinguish "the architecture violates the abstract capacity
   placeholder" from "the architecture violates the physical chain."
   That distinction is diagnostically useful: the first is a modeling
   limit, the second is physics.

3. **Staged rollout.** PR-B adds the physical family *without* changing
   existing behavior. PR-C promotes the physical encoding to be the
   default. The two PRs are cleanly separable only if the new
   constraint is additive.

**New constraint family naming.** `<link_id>_physical_flow_cap` and
`<link_id>_physical_los`. Family names follow the same convention as
existing families: lowercase, prefixed with the link ID, tagged with
the link's grammar features so attribution works unchanged.

**Interface.** A new function `encode_architecture_with_physics(arch,
config=None, scene=None)` in the same module. It calls
`encode_architecture(arch, config)` internally and then appends the
physics families. `encode_architecture` remains unchanged and remains
the default that `run_clear_d_loop` calls.

### Decision 6 — What Stage B SAT means, after

**Question.** Under the current encoder, an architecture is SAT iff
the flow-balance constraints are satisfiable, MPE is respected, and a
UAV is present. Under the physics extension, SAT additionally requires
every link's physical chain to support the flow it must carry. This is
a change in the *meaning* of the verdict. It must be stated.

**Disclosed statement, to appear verbatim in the encoder docstring
after PR-C:**

> A SAT verdict under this encoder means the architecture is feasible
> under the encoded constraint set: flow-balance, MPE, UAV presence,
> and — when the physics extension is enabled — the physical link
> chain (beam geometry, atmospheric transmittance, receiver conversion,
> battery efficiency) evaluated at the scene's reference conditions.
>
> It does not mean the architecture is feasible in reality. The
> physical coefficients carry [SOURCED] and [ESTIMATED] tags; the
> [ESTIMATED] values must be replaced with sourced values before any
> publication or commercial use. The Stage B verdict is bounded by
> the encoding's approximation error (spec Section 20.2).
>
> When the physics extension is disabled, the verdict additionally
> does not account for real geometry, atmosphere, or receiver
> efficiency. Any SAT verdict from that mode should be treated as
> provisional.

**Consequence for Notebook 10.** The H9 measurement (3.29×) was
computed against the current encoder without the physics extension.
After PR-C flips the default, the composition of the infeasible set
changes: some previously-SAT architectures become UNSAT because they
violate the physical chain or line of sight. The measurement must be
re-run and re-reported. This is expected and is the correct scientific
response — the mechanism is unchanged, the population it operates on
is.

### Decision 7 — The atmosphere is a finite-thickness shell

**Question.** The atmospheric transmittance model is Beer-Lambert over
a path length. For a terrestrial link of a few km, the entire path is
in atmosphere and the model applies directly. For a satellite link of
hundreds of kilometres, only a thin shell near the ground contains air.
What is the correct treatment?

**Options.**

- (a) Apply the atmospheric model over the full geometric path length.
- (b) Apply it over the length of the segment that lies inside a shell
  of thickness `H_ATMOSPHERE_M` near the surface; the rest of the path
  is vacuum, transmittance 1.

**Chosen: (b).**

**Reasoning.**

Option (a) is what the initial implementation did, and it is
physically wrong. The extinction coefficient returned by
physics/atmosphere is a ground-level value for the aerosol and
molecular terms. Over a 500 km path the Beer-Lambert exponent
`-alpha * L` underflows IEEE 754 double precision to exactly 0.0,
declaring the link unpowerable by construction for reasons unrelated
to the actual physics. A LEO satellite at 500 km altitude is in
vacuum; the beam crosses approximately 20 km of atmosphere near the
ground.

**Shell thickness.** `H_ATMOSPHERE_M = 20_000.0` metres. [ESTIMATED]
The atmosphere has no sharp boundary; 20 km is a first-order choice
covering the troposphere plus the low stratosphere where most
extinction occurs. A more accurate treatment would integrate a
density-dependent extinction profile against altitude (the exponential
scale height of water vapour is about 2 km, of aerosols about 1 km).
The single-slab model over-estimates slightly, which is the safe
direction for a physics-envelope constraint.

**Integration.** The atmospheric path length is computed
geometrically: find the point along the segment at which the radial
distance from the Earth's centre first exceeds `R + H_ATMOSPHERE_M`,
and use the distance from the source to that point. When both
endpoints are inside the shell, the full range is used. When both are
outside, no atmospheric loss is applied (transmittance 1).

**RF links.** RF (2.45 / 5.8 GHz) propagation is not modelled by
physics/atmosphere (which is a 400-1550 nm laser model). RF links use
the scalar `rf_transmittance` field of `SceneConfig`, marked
[ESTIMATED]. The same shell reasoning applies physically, but at
these frequencies atmospheric transmittance is essentially unity over
the whole path in clear air, so the scalar is a placeholder for a
fuller RF atmospheric model that is deferred.

## 3. What this design does NOT change

- The Tier 1 / Tier 2 invariant (Section 15.3 / 36.1). The encoder is
  a Tier 0 verifier: it does not produce estimates, does not consume
  estimates, and does not decide actions. It emits constraints.
- The Stage A/B/C/D/E labels. Encoder extension is Stage B; it does
  not touch Stages A, D, or E.
- The regulatory MPE constraints. The existing MPE logic is
  unchanged. Only its inputs (which links get an MPE constraint) were
  recently revised in PR #45.
- The flow-balance constraints. Supply and demand floors are unchanged.
- The `nsga2.py` module. No change to the optimizer.

## 4. Sourcing status of the coefficients

After this design is implemented, every numeric input to the encoder
will have a declared epistemic tag. The current state:

| Coefficient | Source | Tag |
|---|---|---|
| Kruse q-exponent branches | Kruse 1962 / Kim 2001 | [SOURCED] |
| Molecular extinction default | — | [ESTIMATED] |
| Cloud extinction coefficient | — | [ESTIMATED] |
| Beam waist, divergence formulas | Siegman 1986 | [SOURCED] |
| Pointing loss formula | Klein & Pappas 1974 | [SOURCED] |
| Rectenna peak efficiency (0.82) | McSpadden 1998 | [SOURCED] |
| Rectenna peak density (1000 W/m²) | McSpadden 1998 | [SOURCED] |
| Rectenna curve widths | — | [ESTIMATED] |
| PV-TE reference efficiencies | Han et al. 2026 | [SOURCED] (paper existence unverified in-session) |
| SceneConfig defaults | various | [ESTIMATED] except 298.15 K |
| Battery efficiency (0.92) | — | [ESTIMATED] |
| UAV assumed transmit power (20 W) | — | [ESTIMATED] |
| Node default demand (15 W) | — | [ESTIMATED] |

The [ESTIMATED] values are not defects. They are disclosed. The
platform's epistemic discipline (spec Section 21) requires them to be
labeled, not to be absent.

## 5. What remains open

- **WGS-84 vs spherical Earth for range.** Decision 1 uses a sphere.
  If the platform later requires ellipsoidal range, it is a change
  inside the geometry helper, not a change to the encoder's interface.
- **Multipath / scattering** are not modeled. The atmosphere model
  assumes direct line of sight with molecular + aerosol + cloud
  extinction. Real links can be affected by scattering that reaches
  the receiver off-axis; that is a follow-up model.
- **Beam turbulence** is not modeled. Real laser beams spread more
  in the atmosphere than the vacuum Gaussian formula predicts.
  Turbulence-induced spreading (the Cn² parameterization) is a
  substantial additional model; deferred.
- **Rectenna at 2.45 GHz vs 5.8 GHz.** The current model uses one
  `RectennaConfig`; the frequency dependence is in the rolloff term.
  A 2.45 GHz design would have different peak efficiency and width.
  If this becomes important, `RectennaConfig` can be per-band.

None of these are blockers. They are honest scope boundaries.

## 6. Proposed PR plan

**PR-A (this document).** Design. No code. Merged when the decisions
above are approved or amended.

**PR-B (additive).** Add `encode_architecture_with_physics` to
`architecture_encoder.py`. Add `SceneConfig`. Add the geometry helper
(in the same file, not a new module — it is small and single-purpose).
Add `_physical_link_chain(link, scene, config)` returning the chain
efficiency as a plain float. Emit `<link>_physical_flow_cap` and
`<link>_physical_los`. Do NOT change `encode_architecture` or the
loop. Tests verify:
- physical encoding is strictly stronger than flow-only (any
  architecture UNSAT under flow-only is UNSAT under physics; some
  architectures SAT under flow-only become UNSAT under physics)
- geometry helper matches hand-computed distances on known coordinates
- line-of-sight correctly returns FALSE for antipodal ground nodes
- chain efficiency is bounded in [0, 1] and monotonic in the expected
  directions (more distance, worse; more cloud, worse)
- backward compatibility: `encode_architecture` unchanged

**PR-C (semantic flip).** Make `encode_architecture` call
`encode_architecture_with_physics` internally with a default
`SceneConfig`, OR change `run_clear_d_loop` to call the physics
variant directly. Re-run Notebook 10 with the physics encoder and
re-report the H9 result. Update the encoder docstring with the
disclosed statement from Decision 6. Update `docs/ROADMAP_STATUS.md`
to record the semantic change.

PR-A is the gate for the other two. If the maintainer wants to
change any decision in §2, that happens here, before code.

## 7. Approval checklist

Before PR-A merges, confirm:

- [ ] Decision 1: spherical Earth, 3D Euclidean range, LOS test
- [ ] Decision 2: `SceneConfig` separate from `EncoderConfig`
- [ ] Decision 3: hybrid capacity = min(laser, RF)
- [ ] Decision 4: laser receiver at reference temperatures, RF via
      rectenna at incident density, no fixed point
- [ ] Decision 5: additive (`encode_architecture_with_physics` new,
      `encode_architecture` unchanged)
- [ ] Decision 6: the disclosed statement in the encoder docstring is
      acceptable

If any is not approved, the fix lands in this document before PR-B is
written.
