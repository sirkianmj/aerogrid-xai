# CLEAR-D: Closed-Loop Generative Discovery of Wireless Energy Architectures with Unsat-Core Feedback

**Status:** draft scaffold. Not submittable. Every numeric result is traced to a test or notebook output at commit `c29f1e4` of `https://github.com/sirkianmj/aerogrid-xai`. Items marked `[PLACEHOLDER]` require information the repository does not supply (funding changes, submission-time review).

**Target venue:** *Nature Energy* (primary), *IEEE Transactions on Aerospace and Electronic Systems* (secondary), *Matter & Light* (secondary).

---

## Authors

**Kian Mansouri Jamshidi** — Forgex4 (founder). Single author.

**Corresponding author:** Kian Mansouri Jamshidi

**Contact:** sirkianmj@forgex4.com

**ORCID:** https://orcid.org/0009-0001-3817-2305

**Affiliation note.** The author is the founder of Forgex4. The software described in this paper was developed under that affiliation; the repository at `https://github.com/sirkianmj/aerogrid-xai` is the canonical public artifact. The dual-license model under which the software is released (AGPL-3.0 for community use; a proprietary commercial EULA for enterprise use) is disclosed in §9 and in the competing-interests statement below.

## Abstract

Wireless power transfer between space, air, and ground nodes has been demonstrated in isolation at various technology readiness levels, but no system-level method exists to identify which architecture — which combination of node types, transmission modalities, and topology — is feasible under jointly binding physical, thermal, regulatory, and network constraints. We present CLEAR-D (Coupled-Loop Epistemic Architecture Reasoning and Discovery), a closed-loop method that couples a two-node electro-thermal receiver model to a piecewise-linear SMT encoding with a tracked approximation error, uses the unsatisfiable core of a rejected architecture to bias the next mutation of a context-free architecture grammar, operates the discovered architecture with a two-tier explanation-fidelity-preserving controller, and refines both the physics model and the formal encoding from operational data. The method's novel mechanism is the mapping from each clause of an unsatisfiable core back to the specific grammar production rule that generated the constraint. On a synthetic evaluator with the real Stage B encoder, the mechanism repairs infeasible architectures at 78.2% versus 23.8% for uniform random mutation at equal step budget (3.29×). The full A→E loop completes 100 generations without error; Stage E reduces the PWL approximation error by a factor of 8 (ratio 0.125) over 100 refinement cycles on a smooth target. All numeric results in this paper are reproduced by the test suite and notebooks committed with the manuscript; 1244 backend tests, 248 frontend tests, and twelve executable notebooks pass at the current commit. The twelve proposed hypotheses in the specification's Section 27 are audited against the repository and reported individually: four are covered by a test whose failure would falsify them, six are partially covered with named gaps, one (H4) is falsified by direct test, and one (H7) requires a capability that does not yet exist. See docs/SCIENTIFIC_CLAIMS.md for the current status of every hypothesis.

## 1. Introduction

Space-based solar power and wireless power transmission have been studied for decades. Recent demonstrations have validated individual components at various technology-readiness levels: ground-to-air laser power beaming to a moving UAV (TRL 6), ground-vehicle-mounted microwave transmission to a drone with both a favorable on-target conversion efficiency and a much lower end-to-end wall-plug-to-battery efficiency (TRL 4–5), airborne laser to fixed ground receivers (TRL 5), and a lab-bench perovskite–thermoelectric tandem laser receiver at 38.49% under 520 nm illumination (TRL 3). None of these demonstrates a large-scale autonomous infrastructure network.

A practical space-to-air wireless energy system would simultaneously face: limited available power, transmission losses, atmospheric attenuation, weather, pointing error, receiver orientation, moving UAVs, battery limits, geographic coverage, communication constraints, node failure, changing mission priorities, thermal constraints, uncertainty in predictions, and laser/RF safety regulation. These variables are strongly coupled. The research question is not whether any individual link works — recent demonstrations say it can — but which architectures across the space-air-ground graph are feasible under the *joint* constraint set, and how to search that space efficiently.

We present CLEAR-D, a closed-loop discovery-and-control method. Its novelty is a mechanism for using the formal verifier not only as an oracle of feasibility, but as a gradient signal for synthesis. When an SMT solver reports an architecture as unsatisfiable, we extract the minimal unsat core, map each clause back to the specific grammar production rule that generated the constraint, and bias the next mutation away from the conflict-prone features. This is distinct from prior work that uses unsat cores to prune a search space for re-verification of a fixed artifact (MUC-G4, §2); our mechanism uses cores to *generate* the next candidate.

The paper makes three contributions:

1. **The unsat-core-to-grammar-feature attribution mechanism** for conflict-directed architecture synthesis (§3.3).
2. **A closed-loop composition** of five stages — coupled electro-thermal physics (A), PWL-SMT encoding with tracked error (B), generative discovery with unsat-core feedback (C), two-tier explanation-fidelity-preserving control (D), and closed-loop refinement (E) — in which each stage's output is the next stage's input (§3).
3. **An open reference implementation and test suite** that reproduces every numeric claim in this paper (§6).

## 2. Related Work

**PWL-SMT encoding of transcendental physics.** Incremental Linearization (Cimatti et al., *ACM TOCL* 2018; formalization in *CPP* 2026) is the prior art for our Stage B encoding. It abstracts nonlinear operators as uninterpreted functions over linear arithmetic, then refines the abstraction lazily with linear constraints; it is implemented in MathSAT and cvc5. Our Stage B is an application of this published method to a new domain (wireless power physics), and is not claimed as novel.

**Unsat-core reuse.** MUC-G4 (Li & Li, *ACM TECS* 2026) extracts Minimal UNSAT Cores from a neural network's verification proof and uses them to prune stable infeasible regions in a compressed network's search space. The reuse of unsat cores as durable proof artifacts is prior art. The distinction relevant to this paper: MUC-G4 reuses cores for re-verification of a fixed artifact under modification; our mechanism maps cores to grammar production rules and uses them to *bias mutation*. The output of the reuse is qualitatively different (a pruned search space vs. a conflict-directed synthesis step). This distinction is asserted as the novel contribution; the citation audit of the accompanying repository records that the MUC-G4 characterization has not been independently verified against the source (item C-3).

**Grammar-based generative design.** Established practice in CAD, structural engineering, and compiler research. Our contribution is not the grammar but the coupling of the grammar to a formal verifier via unsat cores.

**Two-tier interpretable / opaque machine learning.** Multi-level decision architectures exist in the literature. The specific partition in which Tier 2 has no decision authority — its outputs are inputs to Tier 1, never actions — is arguably novel; we claim it only as a dependent feature (§3.4, §5).

**Multi-objective optimization.** NSGA-II is the standard reference for the Pareto-based method used in Stage C; we do not claim novelty for the optimizer.

**The individual physics models** — Gaussian beam propagation (Siegman 1986), pointing loss (Klein & Pappas 1974), Beer-Lambert transmittance with Kruse aerosol extinction (Kruse 1962) and Kim low-visibility refinement (Kim et al. 2001), the Han et al. three-layer perovskite / Sb₂Se₃ / Bi₂Te₃ receiver stack — are prior art. Our contribution is the coupling of these models to the formal verifier and to the discovery loop, not the models themselves.

## 3. Method: CLEAR-D

CLEAR-D is a closed loop across five stages. This section describes each stage, then the mechanism that ties them together.

### 3.1 Stage A — Coupled electro-thermal physics constraint generation

The receiver is a three-layer stack: a CsPbBr₃ perovskite laser cell (PLC) converts 520 nm laser light to electricity; a Sb₂Se₃ nanocrystal thermal barrier sits between PLC and TE; a Bi₂Te₃ thermoelectric (TE) layer recovers additional power from the temperature differential. **The Sb₂Se₃ barrier is a thermal element, not a Seebeck-generating one** — its conductivity appears in the thermal conduction term between the two nodes, not in the efficiency product. This attribution has been corrected since an earlier revision of the specification; the corrected attribution is enforced in code (`backend/app/physics/receiver.py`) and by the test suite.

The PLC efficiency decreases monotonically with temperature over the operating range; the model reproduces the 80–90 °C degradation regime reported for the Han et al. device. In the accompanying notebooks we evaluate `eta_plc(T)` and `eta_total(T_plc, T_te_hot, T_te_cold)` over the pre-cutoff band [280 K, 350 K]. Above `T_max = 358.45 K` the model has a hard material discontinuity (the perovskite cell has degraded); this discontinuity is a step, not a smooth surface, and is documented explicitly (Notebook 10 finding F-1).

The multiplicative form `eta_total = eta_PLC(T_PLC) · eta_TE(T_hot, T_cold)` is labeled a first-order lumped approximation. Real PV-TE tandem power extraction depends on circuit topology; the product form is not rigorously derivable without that assumption.

Output of Stage A: a set of PWL-approximable constraint functions over the receiver's operating envelope (efficiency minimum, thermal-runaway boundary, material degradation temperature, transient thermal-shock limit).

### 3.2 Stage B — PWL-SMT encoding with tracked approximation error

Every transcendental physics function used in a Z3 constraint is replaced by a piecewise-linear over-approximation over the physically relevant range. The approximation is *sound*: `f̂(x) ≤ f(x)` everywhere on the range, so any x that satisfies a constraint on `f̂` satisfies it on `f`. This makes SAT verdicts conservative — an architecture declared feasible by Z3 is feasible under the encoded physics, not falsely feasible.

The maximum approximation error `ε` is carried as a numeric quantity on the approximation and reported with every verification result. A SAT verdict is meaningful "modulo ε".

For network-scale queries, the encoding is decomposed: intra-cluster feasibility problems per cluster of `k` nodes, and inter-cluster flow-conservation constraints as a smaller linear problem. The composition rule is sound: the architecture is feasible iff every cluster is feasible and the inter-cluster flow problem has a solution. The decomposition is a true graph partition with no shared variables.

The Stage B encoder emits five constraint families:
1. Per-link flow bounds (`0 ≤ flow ≤ base_capacity · capacity_factor`).
2. Per-source supply caps.
3. Per-UAV demand floors (unconditional FALSE when a UAV has no incoming link, so the unsat core names that UAV).
4. Regulatory MPE limits (ANSI Z136.1 laser, FCC Part 1.1310 RF).
5. Structural `requires_uav` (FALSE when the architecture has no UAV node).

Every constraint carries the grammar features of its originating node or link, so unsat cores attribute cleanly to architecture elements (Stage C).

### 3.3 Stage C — Generative architecture discovery with unsat-core feedback (the inventive core)

The architecture space is a context-free grammar over node terminals (satellite GEO/LEO, UAV energy/compute, ground station) and link terminals (laser, microwave, hybrid), with numeric parameters attached to each terminal (positions, power levels, frequencies, aperture).

**The novel mechanism.** When Z3 returns UNSAT for a candidate architecture:

1. The minimal unsat core is extracted. The core is a small set of constraints that are jointly infeasible.
2. Each constraint in the core is mapped back to the grammar features that produced it. If a constraint was emitted for a specific `(source_id, target_id, link_kind)` triple, the mapping names that link instance and its terminal kind.
3. Every named feature is marked "conflict-prone" in a `ConflictProneTable` that accumulates across generations.
4. `mutate_conflict_directed` samples mutation operators weighted by the table: an infeasible individual is more likely to be mutated in a way that changes a feature previously implicated in a conflict.

The result is a closed feedback loop from the verifier to the generator. The unsat core is not merely reported; it is a gradient.

**The composition.** Per generation, the loop (i) classifies every individual by encoding and checking satisfiability, (ii) generates offspring — feasible individuals get random mutation, infeasible individuals get conflict-directed mutation, (iii) selects the next generation by NSGA-II with constrained domination (feasible always dominates infeasible). Each individual is classified exactly once; the surviving population's feasibility is derived from the known combined pool, not re-classified.

The loop is deterministic given a fixed seed.

### 3.4 Stage D — Two-tier explanation-fidelity-preserving control

The discovered architecture is operated by a controller with a strict separation:

- **Tier 1** (sole decision authority) is restricted to model classes whose explanation is their computation: sparse rule lists, GAMs with monotonicity constraints, bounded-depth decision trees, transparent-cost MPC. Every action taken by Tier 1 carries an explanation that is, by construction, the literal computation path used to reach the decision.
- **Tier 2** (no decision authority) may use opaque function approximators, but is restricted to producing numeric estimates with calibrated uncertainty intervals. Tier 2 outputs are inputs to Tier 1; they are never actions.

The two-tier partition is enforced by a build-time static analyzer that parses every Python file under the control package, builds a transitive call graph of top-level functions, and reports any `estimate_*` function whose closure reaches a `decide_*` function.

**Trace fidelity is a property of the API shape.** A `SparseRuleList` exposes a single method `score_and_trace(inputs, builder) -> float` that evaluates every rule and mutates a shared trace builder in the same call. There is no `evaluate(inputs)` path that returns a score without touching a trace. `DecisionTrace` and `TraceStep` are frozen dataclasses; the renderer reads only trace fields and cannot diverge.

**Counterfactuals.** Because Tier 1 is inherently interpretable, counterfactual statements ("if UAV-32 battery were > 45%, UAV-18 would become the preferred target") are exact facts about the rule structure, not statistical approximations. The accompanying implementation provides rule-ablation counterfactuals, which are exact.

### 3.5 Stage E — Closed-loop refinement

Two coupled refinements:

1. **Physics parameter update.** Recursive Bayesian estimation updates the physics model's parameters against noisy observations. The posterior variance strictly decreases under nonzero-sensitivity updates — this is a theorem, not an empirical claim, and is verified by a unit test.
2. **PWL error tightening.** The PWL refiner splits the highest-residual segment on each cycle. At fixed underlying `f`, this makes `ε` monotonically non-increasing as a theorem.

The two phases are separated. Interleaving them would change `f` between cycles and break the monotonicity guarantee. The separation is what makes the ε-reduction result a theorem about the refinement procedure rather than an empirical observation about a moving target.

The Digital Twin monitor compares predicted vs observed physics values and raises a refinement trigger when the discrepancy exceeds a configured threshold. The data flow is causal: operational data affects the model, not the reverse.

## 4. Implementation

A complete open implementation is published at `https://github.com/sirkianmj/aerogrid-xai` under AGPL-3.0 (community) and a proprietary commercial EULA. The code is split into:

- `backend/app/physics/` — the physics models (orbital, atmosphere, beam, receiver, thermal, link budget, rectenna, region, geometry, catalog, benchmarks).
- `backend/app/verification/` — the PWL encoder, hierarchical decomposition, regulatory constraints, and the real Stage B architecture encoder.
- `backend/app/discovery/` — Stage C (grammar, generator, unsat-core extraction, attribution, mutation, NSGA-II, loop).
- `backend/app/control/` — Stage D (Tier 1, Tier 2 surrogates, explanation, trajectory, static analyzer).
- `backend/app/refinement/` — Stage E (Bayes, PWL tuning, discrepancy, causality).

The implementation uses Python 3.12, NumPy, SciPy, Skyfield for SGP4/SDP4 orbital propagation, and Z3 for formal verification. No Docker, Kubernetes, or cloud VMs are used; the environment is a single conda environment from `environment.yml`.

## 5. Results

All results in this section were produced by the test suite and notebooks at commit `c29f1e4` of the public repository. Each subsection names the specific artifact that produces the number.

### 5.1 The unsat-core-to-grammar-feature attribution mechanism improves repair rate on infeasible architectures

The headline result for the inventive mechanism is a repair-rate comparison on a deterministic set of infeasible seed architectures. Given 5 infeasible seeds, 100 trials per arm per seed, 10-step budget per trial, with identical RNG streams between arms:

- **Conflict-directed repair:** 391 / 500 = 78.2%
- **Random repair:** 119 / 500 = 23.8%
- **Ratio:** 3.29×

The gate in the notebook requires `conflict_rate > random_rate`, `conflict_rate ≥ 1.5 × random_rate`, and `total_conflict > 0`. The measured ratio is comfortably inside the gate. See `notebooks/06_unsat_core_ablation.ipynb` for the ablation and `notebooks/10_clear_d_end_to_end.ipynb` for the composition.

At the population level (closed-loop, 12 individuals, 6 generations), the two arms tie on the current generator because the seed population is mostly feasible after the generator connectivity fix and both arms saturate quickly. **This is reported, not hidden**; it is the reason the headline test is on the mechanism rather than the loop.

### 5.2 The full A→E loop completes 100 generations without error

`backend/tests/test_z3_end_to_end.py::test_100_generations_completes_without_error` runs `run_clear_d_loop` against the real Stage B encoder for 100 generations on population 4. The loop returns normally; the per-generation statistics and hypervolume history have exactly 100 entries each; the final population size matches the config. Wall time in isolation: 0.23 s.

The loop is deterministic under a fixed seed (`test_100_generations_is_deterministic_under_fixed_seed`).

### 5.3 Stage E reduces the PWL approximation error by a factor of 8 over 100 cycles

On the smooth pre-cutoff band [280 K, 350 K] of `eta_plc(T)`, with 8 initial segments, the PWL refiner reduces ε from 3.281 × 10⁻³ to 4.102 × 10⁻⁴ over 100 cycles with fresh observations each cycle. Ratio: **0.125**, well below the H12 gate of 0.5. The refiner ends with 108 segments.

The 8× reduction is a consequence of the refiner's mechanism (split highest-residual segment each cycle at fixed f) and the smoothness of the target. On the full range including the discontinuity at `T_max`, ε plateaus at the jump height and does not reduce below it — this is a mathematical property of a sound over-approximation on a step function, documented as Notebook 10 finding F-1.

### 5.4 Trace fidelity is preserved at 100% on a 100-point sweep

`test_score_equals_sum_of_weights_across_sweep` runs `decide_charge_uav` on 100 randomly generated candidate vectors with the default charge rule list. For every decision, the winner's score equals the sum of the recorded trace's step weights to floating-point precision. The result is not "fidelity = 1.0 as claimed"; it is "the invariant that defines fidelity is satisfied numerically on this sweep".

The Tier 2 static separation check (`test_real_control_package_is_clean`) reports zero violations of the transitive closure requirement on the current code base.

### 5.5 The Xidian dual efficiency is reproduced from the cascaded link budget

Given the three published stage factors (beam collection 0.880, DC-to-RF 0.50, RF-to-DC 0.47), the product reproduces the Xidian on-target DC-to-DC efficiency of 20.8% within 5% relative error. Extending with wall-plug-to-DC, tracking loss, and battery-charge factors places the end-to-end prediction inside the reported 3–5% band. See `backend/tests/scientific_validation/test_xidian.py`.

### 5.6 The PowerLight 1 kW / 1,524 m benchmark is consistent with a plausible parameter set

Full transmitter and receiver parameters are not publicly disclosed for the PowerLight / Kraus Hamdani demonstration. With 10 kW transmitter power, clear-air atmospheric transmission at 1,064 nm over 1,524 m, and 10.2% optical-to-electrical receiver efficiency, the model reproduces 1 kW delivered within 5%. This is a consistency check, not a parameter fit.

### 5.7 The remaining benchmark reproductions and audits

DARPA POWER (800 W over 8.6 km) yields a clear-air transmission coefficient in the physically plausible range at 1,064 nm. Han et al. (38.49% at 520 nm / 1.2 W/cm²) is preserved in the benchmark table as a receiver efficiency, not folded into a link efficiency. Multi-tenant isolation is enforced by PostgreSQL RLS and independently certified (`docs/ISOLATION_AUDIT.md`). The full claims-to-test map is at `docs/SCIENTIFIC_CLAIMS.md`.

## 6. Reproducibility

Every numeric claim in Section 5 is produced by:

- A test module in `backend/tests/` (1062 tests, all passing at the tagged commit).
- A frontend test module in `frontend/src/**/*.test.ts(x)` (163 tests, all passing).
- A notebook in `notebooks/` (10 notebooks, all executable end-to-end).

The repository is tagged at `c29f1e4`. A reproduction takes a single command:

    conda env create -f environment.yml
    conda activate aerogrid
    make master-test

The nightly workflow at `.github/workflows/notebook-repro.yml` re-executes every notebook in a fresh container. The CI matrix runs the backend, frontend, formal-verification, CLA, RLS-isolation, and master-test jobs on every PR; all six are required branch-protection contexts.

## 7. Limitations and hypothesis status

This paper reports what the current repository supports and what it does
not. The twelve hypotheses in the specification's Section 27 are audited
individually in `docs/SCIENTIFIC_CLAIMS.md`. Summary as of this draft:

**Falsified by direct test:**

- **H4** (uncertainty-aware decisions are more robust under
  environmental variability than point estimates) — **falsified**. The
  platform's Tier 2 interval is constant-width (a single scalar
  residual quantile per estimator). An interval-aware policy that
  proceeds iff ``interval.low >= T`` is algebraically identical to a
  point policy that proceeds iff ``value >= T + q``. At matched
  proceed rate there is no room for the claim to hold on this design.
  Evidence: ``backend/tests/test_h4_uncertainty_decisions.py``.

**Not testable without new capability:**

- **H7** (hybrid laser+microwave outperforms single-modality for
  annual availability in most regions) — **capability absent**. The
  platform has no annual-availability computation and no regional
  aggregation. ``docs/H7_AVAILABILITY_SCOPE.md`` names the six
  components that would have to be built. No test can move H7 off
  this status today.

**Partially tested, with named gaps:**

- **H1** (predictive beam tracking) — mechanism covered on a declared
  scope; the "within disclosed uncertainty" clause is not exercised.
- **H3** (atmosphere-aware scheduling) — mechanism covered on a
  declared weather distribution; "optimization" is a greedy
  max-forecast scheduler, and the failure criterion is an operational
  threshold, not a spec-derived metric.

**Partially tested** (mechanism verified; full scope not):

- **H2** (joint NSGA-II of energy and topology improves resilience over independent management) — the NSGA-II primitives are verified; no matched independent-management baseline has been constructed.
- **H8** (thermal management is the dominant limiting factor) — the thermal model is verified; dominance relative to other factors is not measured.
- **H10** (thermal runaway thresholds consistent with experimental data within uncertainty bounds) — the runaway boundary is verified within the model; comparison against external measured data is not performed (the Han et al. citation lacks a resolvable DOI, finding P5).
- **H11** (two-tier controller achieves fidelity 1.0 while achieving prediction accuracy within 5% of an end-to-end opaque controller) — the fidelity half is verified; the accuracy half cannot be tested because no opaque controller has been built to compare against.

**Known modeling limitations:**

- The multiplicative `eta_PLC · eta_TE` form is a first-order approximation, not derived from tandem-junction circuit equations.
- `eta_plc` has a hard material discontinuity at `T_max = 358.45 K`; the PWL domain is restricted to the pre-cutoff band.
- The static analyzer ignores method calls (`obj.method(...)`); only top-level function calls are tracked.
- The trace format does not record per-value provenance (which input mapping supplied a value to a rule).
- The frontend production bundle is ~1.2 MB (330 KB gzipped), dominated by Three.js.

The full list of open items with priorities is in `docs/SCIENTIFIC_CLAIMS.md` and `docs/CITATION_AUDIT.md`.

## 8. Conclusion

CLEAR-D is a closed-loop method for identifying and operating feasible architectures for wireless energy transfer across space, air, and ground nodes. Its novel mechanism maps each clause of an unsatisfiable core back to the grammar production rule that generated the constraint and uses that mapping to bias subsequent mutation. On a synthetic evaluator with the real Stage B encoder, the mechanism repairs infeasible architectures at 3.29× the rate of uniform random mutation at equal step budget. The full A→E loop completes 100 generations without error, and Stage E reduces the PWL approximation error by a factor of 8 over 100 cycles on a smooth target.

The paper's contribution is the coupling: no prior work uses the formal verifier's unsat cores to *generate* the next candidate. The contribution is asserted as a method, and the accompanying repository provides the full implementation, test suite, and notebooks required to reproduce every numeric claim above.

The status of every specification hypothesis is reported individually in §7 and in `docs/SCIENTIFIC_CLAIMS.md`. No hypothesis is reported as "untested" without an explanation of what would be required to test it.

## 9. Data and code availability

Code and notebooks: `https://github.com/sirkianmj/aerogrid-xai`, tag `c29f1e4`.

License: AGPL-3.0 (community) and a proprietary commercial EULA (enterprise), per `LICENSE-OPEN-SOURCE`, `LICENSE-COMMERCIAL`, and `docs/LICENSING_MATRIX.md`. Documentation: CC BY-NC 4.0. Research notebooks: MIT.

The repository is authored and maintained by K. M. Jamshidi under the Forgex4 affiliation. All numeric results in §5 are reproduced by the test suite and notebooks at the tagged commit; no external data is required.

## Author contributions

The paper describes a single-author project. Under the CRediT taxonomy, the sole author is responsible for all contributions:

- **Conceptualization:** K. M. Jamshidi
- **Methodology:** K. M. Jamshidi
- **Software:** K. M. Jamshidi
- **Validation:** K. M. Jamshidi
- **Formal analysis:** K. M. Jamshidi
- **Investigation:** K. M. Jamshidi
- **Data curation:** K. M. Jamshidi
- **Writing — original draft:** K. M. Jamshidi
- **Writing — review & editing:** K. M. Jamshidi
- **Visualization:** K. M. Jamshidi
- **Supervision:** N/A (single-author project)
- **Project administration:** K. M. Jamshidi
- **Funding acquisition:** N/A (see Funding)

The repository's authorship discipline is recorded in `docs/HANDOFF.md` §0: all commits, docstrings, and documents in the repository are authored by K. M. Jamshidi; no AI-assisted, co-authored, or third-party attribution exists and none may be added.

## Competing interests

The author declares the following non-financial and financial interests, stated in full because they are material to the reader's assessment of this work:

1. **Founder of Forgex4.** The author is the founder of Forgex4. The software described in this paper was developed under that affiliation. This is a direct, non-trivial relationship between the author and the artifact under evaluation.

2. **Commercial licensing of the artifact under study.** The repository and the CLEAR-D method are released under a dual-license model: AGPL-3.0 for community and academic use, and a proprietary Commercial EULA for enterprise and closed-source use (see §9 and `LICENSE-COMMERCIAL` in the repository). The author holds the licensing rights for the commercial path. This is a potential financial interest in the artifact's adoption.

3. **Defensive publication, not patent.** The method is defensively published as prior art (`docs/DEFENSIVE_PUBLICATION.md`). The decision was made on cost grounds and does not represent a patent position. No patent is pending, and no "patent pending" language is used in any project document.

4. **No funding relationship with any cited benchmark source.** The PowerLight, Xidian, Overview Energy, and DARPA demonstrations are third-party works used as benchmarks. No funding, consulting, or other relationship exists between the author and any of these sources.

The declarations above are what the repository's audit trail supports. No competing-interest claim is asserted that the repository cannot substantiate. A submission-time review against the target venue's specific disclosure requirements (e.g., Nature Energy's competing-interests form) is owed before submission.

## Funding

The work was carried out under the author's affiliation with Forgex4. No external grant, award, or contract supported the work described in this paper at the time of writing.

[PLACEHOLDER — if any funding is added after this draft, record the funder name and grant number here. Forgex4 as the sole source is the accurate current state.]

## Ethics

Not applicable. This work does not involve human subjects, animals, or dual-use hardware. The platform is software and simulation only.

---

## References

1. Han, J., et al. "Sb₂Se₃ nanocrystals enable efficient perovskite-thermoelectric tandem devices for laser-powered unmanned aerial vehicles." *Matter & Light*, 2026. **[CITATION AUDIT: item P5 — DOI, volume, and page unverified. See `docs/CITATION_AUDIT.md` §3.11.]**
2. Cimatti, A., et al. "Incremental Linearization for Satisfiability and Verification Modulo Nonlinear Arithmetic and Transcendental Functions." *ACM Transactions on Computational Logic*, 2018.
3. Cimatti, A., et al. "Formalization of a Proof Calculus for Incremental Linearization for Satisfiability Modulo Nonlinear Arithmetic and Transcendental Functions." *CPP 2026*, ACM, January 2026.
4. Li, J., & Li, G. "MUC-G4: Accelerating Incremental Verification of Compressed Neural Networks via Minimal UNSAT Core Reuse." *ACM Transactions on Embedded Computing Systems*, 2026. **[CITATION AUDIT: item C-3 — characterization not independently verified. See `docs/CITATION_AUDIT.md` §3.6.]**
5. PowerLight Technologies / Kraus Hamdani Aerospace, DoD PTROL-UAS program. **[CITATION AUDIT: item C-2 — no DOI; program-level demonstration. See `docs/CITATION_AUDIT.md` §3.7.]**
6. Xidian University microwave power beaming demonstration. **[CITATION AUDIT: item C-2 — no DOI. See `docs/CITATION_AUDIT.md` §3.8.]**
7. Overview Energy airborne laser demonstration. **[CITATION AUDIT: item C-2 — no DOI. See `docs/CITATION_AUDIT.md` §3.9.]**
8. DARPA POWER program, Naval Research Laboratory. **[CITATION AUDIT: item C-2 — no DOI. See `docs/CITATION_AUDIT.md` §3.10.]**
9. Siegman, A. E. *Lasers*. University Science Books, 1986.
10. Klein, B. J., & Pappas, J. J. "Power handling capability of far-infrared laser windows." 1974. **[CITATION AUDIT: item C-1 — title and venue incomplete in code. See `docs/CITATION_AUDIT.md` §3.2.]**
11. Kruse, P. W., McGlauchlin, L. D., & McQuistan, R. B. *Elements of Infrared Technology*. 1962. **[CITATION AUDIT: item P21 — coefficients not cross-checked. See `docs/CITATION_AUDIT.md` §3.3.]**
12. Kim, I. I., McArthur, B., & Korevaar, E. J. "Comparison of laser beam propagation at 785 nm and 1550 nm in fog and haze for optical wireless communications." *SPIE*, 2001. **[CITATION AUDIT: item P21.]**
13. ANSI Z136.1 (American National Standard for Safe Use of Lasers), 2026 revision. **[CITATION AUDIT: item C-4 — specific MPE values not cross-checked. See `docs/CITATION_AUDIT.md` §4.1.]**
14. IEC 60825 series (international laser safety). **[CITATION AUDIT: item C-4.]**
15. FCC Part 15 and FCC Part 18 (ISM bands, RF exposure). **[CITATION AUDIT: item C-4. See `docs/CITATION_AUDIT.md` §4.2.]**
16. KSR International Co. v. Teleflex Inc., 550 U.S. 398 (2007).
17. Alice Corp. Pty. Ltd. v. CLS Bank Int'l, 573 U.S. 208 (2014).
