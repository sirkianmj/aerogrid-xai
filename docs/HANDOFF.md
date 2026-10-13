# Handoff Document — AeroGrid-XAI (next AI agent)

**Written:** 2026-10-13 (revised)
**Repository state:** `main` at commit `ef428bf`
**Supersedes:** the prior handoff document describing commit `aab8a42`
**Platform:** AeroGrid-XAI
**Method:** CLEAR-D (Coupled-Loop Epistemic Architecture Reasoning and Discovery)
**Owner:** sirkianmj (GitHub), single maintainer
**Repo:** https://github.com/sirkianmj/aerogrid-xai (public, GitHub Free)
**Local path:** `~/aerogrid-xai` on macOS
**License:** AGPL-3.0 (community) + Proprietary Commercial EULA
**Correct URL spelling:** `sirkianmj` — older documents that say `sirikianmi` or `sirkanim` are wrong.

This document is grounded in what was verified on disk at commit `ef428bf`,
not in prior handoff claims. Where a claim has not been verified, the
text says so explicitly.

---

## 0. Read this first

Do not trust docstrings or roadmap claims over the code. The prior handoff
contained several statements that turned out to be inaccurate when checked:

- It claimed the s6-4 Kalman fix was unmerged. It was already merged as PR #40.
- It said "the build fails" when a Tier 2 function reaches the Tier 1 action
  interface. The mechanism is a pytest assertion, not a build step.
- It implied the s3-7 hierarchical scaling gate reproduced. It does not;
  the reformulation is documented in `docs/ROADMAP_STATUS.md`.

Every claim in this document has been verified by reading the file or
running the command, unless prefixed with [UNVERIFIED].

---

## 1. Environment

Activate the correct conda environment before anything else.

    conda activate aerogrid
    conda env list

If the shell prompt shows `(base)`, the environment is wrong and
`ruff`/`mypy`/`pytest` will not resolve to the correct binaries.

Verified versions at `ef428bf`:

    Python      3.12.14
    Node        v20.20.2
    ruff        0.16.9
    mypy        2.3.1 (compiled)
    pytest      9.1.1
    z3          5.1.0
    numpy       2.5.3
    scipy       1.18.1
    skyfield    1.54

`backend/pyproject.toml` is the sole source of ruff / mypy / pytest
configuration. There are no `mypy.ini`, `setup.cfg`, or `ruff.toml` files.

---

## 2. Gates and CI

Local gate command (from `backend/`):

    ruff format .
    ruff check --fix .
    ruff check .
    ruff format --check .
    mypy .
    pytest --cov=app --cov-report=term-missing -q

State at `ef428bf`: 813 passed, 95% coverage, 8 s wall time.

CI: `.github/workflows/ci.yml` defines exactly four jobs, matching the
branch protection required contexts:

    backend               ruff + mypy + pytest --cov
    frontend              oxlint + tsc -b + vitest + vite build
    formal-verification   Z3 sanity check (no Lean — Z3 only)
    cla-check             PR author must appear in signatures/cla-v1.json

Branch protection on `main`: `enforce_admins: true`, `strict: true`,
force-push blocked, deletion blocked, conversation resolution required,
zero required approving reviews.

**Merge procedure.** `gh pr checks --watch` returns immediately when no
checks have registered yet, and `gh pr merge` fired at that moment will
be rejected by branch protection. Wait for at least four checks to
appear (poll `gh pr checks <N>` in a loop) before attempting the merge.
`gh pr merge <N> --squash --delete-branch` is the only merge command
used. `--admin` and `--force` are never used.

---

## 3. Layout

    backend/        FastAPI app + all scientific code (app/ subpackages)
    frontend/       React 19.2 + Vite 8.3 + TS 6.0 + Vitest 4 (Sprint 0 scaffold)
    docs/           specifications, roadmap tracker, handoff (this file)
    infrastructure/ empty (Sprint 11 deliverable)
    saas/           empty (Sprint 8 deliverable)
    notebooks/      01–08 built; 09–12 not started
    scripts/        build_notebook_0N.py generators (notebooks are never edited by hand)
    .github/        CI workflow
    signatures/     cla-v1.json (currently lists sirkianmj only)

`backend/app/` subpackages, all present:
    physics/        orbital, region, receiver, thermal, link_budget, benchmarks
    verification/   pwl, encoder, hierarchical, regulatory, architecture_encoder
    discovery/      grammar, generator, unsat, attribution, mutation, nsga2, loop
    control/        tier1, tier2, trajectory, static_analyzer, explain
    refinement/     bayes, pwl_tune, discrepancy, causality
    saas/           empty (Sprint 8)

---

## 4. CLEAR-D: what exists and what is now composed

    Stage A  coupled physics      physics/receiver.py, physics/thermal.py
    Stage B  PWL-SMT encoding     verification/pwl.py, encoder.py,
                                  hierarchical.py, regulatory.py
             real encoder         verification/architecture_encoder.py
    Stage C  discovery            discovery/grammar.py, generator.py,
                                  unsat.py, attribution.py, mutation.py,
                                  nsga2.py, loop.py
    Stage D  two-tier control     control/tier1.py, tier2.py, trajectory.py,
                                  static_analyzer.py, explain.py
    Stage E  closed-loop refine   refinement/bayes.py, pwl_tune.py,
                                  discrepancy.py, causality.py

`discovery/loop.py` composes A→B→C→D in a single executable pipeline:
per generation it encodes, checks, attributes, produces offspring
(feasible → random mutation; infeasible → conflict-directed mutation
weighted by the accumulated ConflictProneTable), and selects the next
generation with `nsga2_select`. It does not modify `nsga2.py`.

`verification/architecture_encoder.py` is the real Stage B encoder. It
emits five constraint families backed by actual physics:

1. per-link flow bounds (0 ≤ flow ≤ base_capacity · capacity_factor)
2. per-source supply caps (Σ outgoing flow ≤ source power_w)
3. per-UAV demand floors (Σ incoming flow ≥ NODE_DEFAULT_DEMAND_W);
   a UAV with no incoming link emits constant FALSE so the UNSAT core
   is a singleton naming that UAV
4. per-link ANSI Z136.1 laser MPE / FCC Part 1.1310 RF limits, via
   `app.verification.regulatory`
5. structural `requires_uav` that fires FALSE for UAV-free architectures

Every emitted constraint carries the grammar features of its originating
node or link, so UNSAT cores attribute cleanly through
`attribution.attribute_and_mark`.

**The placeholder `encode_architecture_to_z3` in `generator.py` has not
been removed.** It is now superseded by `architecture_encoder.encode_architecture`
and its docstring says so, but it remains in the tree.

---

## 4b. Work merged since the previous handoff (`e50529a` -> `aab8a42`)

Six PRs merged in this session. Thematically they close the gap
between the CLEAR-D module set and the physics the modules claim to
operate on.

| PR | Commit | Summary |
|----|--------|---------|
| #45 | `b83c843` | `EncoderConfig` extracted with `human_accessible_kinds`; hybrid MPE conservatism documented; `generator.encode_architecture_to_z3` marked SUPERSEDED |
| #46 | `b4f7f6a` | MPE gated by target-node kind (only Ground_Station links trigger laser/RF MPE); generator connectivity guarantee (every UAV gets an incoming link at construction); constrained selection in `run_clear_d_loop`; `use_conflict_directed` flag on `ClearDLoopConfig`; Notebook 10 rewritten to demonstrate the CLEAR-D repair mechanism at 3.29x |
| #47 | `aab8a42` | New `physics/atmosphere.py`: Kruse (1962) / Kim et al. (2001) aerosol extinction, Beer-Lambert transmittance, sourced coefficients, 32 tests |

### Notebook 10 result (measured, PR #46)

Given 5 infeasible seed architectures (deterministic seeds 10000..10199),
100 trials per arm per architecture, 10-step budget, identical RNG streams:

    conflict-directed:  391/500 repaired  (78.2%)
    random:             119/500 repaired  (23.8%)
    ratio:              3.29x

Gate assertions: `conflict_rate > random_rate` AND `conflict_rate >= 1.5 * random_rate` AND `total_conflict > 0`.
Strict inequality. A tie fails.

At the loop level (population of 12, 6 generations, 6 seed architectures)
the two arms tie, because the seed population is ~80% feasible after the
generator connectivity fix and, once saturated, both arms are literally
the same algorithm (feasible parents always receive random mutation in
both). This is reported in the notebook as honest context, not hidden.

### Seed feasibility audit (30 seeds, min_nodes=4, max_nodes=8, max_links=6)

    before encoder MPE fix:    0/30 sat
    after encoder MPE fix:     4/30 sat
    after generator repair:   24/30 sat

Remaining 6/30 UNSAT are all genuine MPE violations.

## 4c. Phase 2 physics work (PRs #47 through #57)

The specification's Development Phases (Section 25) list the Multi-Modal
Wireless Power Model as Phase 2. In the PR titles this work was labelled
"Sprint 10", which collides with the roadmap Rev. 2's Sprint 10 (Q1
article, DARPA DID docs). The label is a documentation error, not a
roadmap change. Future references should call this "Phase 2" or
"Sprint 2d".

| PR | Commit | Summary |
|----|--------|---------|
| #47 | `aab8a42` | physics/atmosphere.py: Kruse-Kim aerosol extinction, Beer-Lambert transmittance, 32 tests |
| #49 | `9873389` | physics/beam.py + build_physical_link_budget: Gaussian beam geometry and pointing loss |
| #50 | `87c8e99` | tier2.py rewired to physics/atmosphere as single source of truth |
| #51 | `b229bfc` | physics/rectenna.py: peaked RF-to-DC conversion efficiency |
| #52 | `6e8431b` | docs/ENCODER_PHYSICS_INTEGRATION.md: seven design decisions before code |
| #53 | `9ed3012` | encode_architecture_with_physics: additive physics extension, no change to base encoder |
| #54 | `0301c3e` | physics/geometry.py extracted; rectenna zero-density soundness fix |
| #56 | `648d210` | generator LOS-compliant placement + pole-corrected latitude sampling |
| #57 | `ef428bf` | generator physics-aware link kind sampling |

### Measured effect on the generator's output

30 generator samples, min_nodes=4, max_nodes=8, max_links=6, seeds
20000..20029, evaluated by encode_architecture_with_physics with
SceneConfig(receiver_conversion_efficiency=0.25):

    before PR #57:   0/30 SAT (generator sampled link kinds independently of geometry)
    after  PR #57:  20/30 SAT (generator samples link kinds from the viable set at final geometry)

The remaining 10/30 UNSAT are genuine physics: LEO links at the outer
edge of the placement distribution where delivered power falls below
the 15 W demand floor, or multi-UAV architectures whose combined demand
exceeds one source's supply.

### Two source kinds in _SOURCE_KINDS

SATELLITE_GEO was removed from the generator's source-kind pool in PR
#57. At 35,800 km altitude a 2 cm beam spreads to a 600 m radius; a
metre-scale UAV receiver captures about 1e-4 of the beam, and the chain
is five orders of magnitude below viability. The GEO terminal remains
in the grammar for hand-built architectures.

## 5. Known discrepancies (documented, not fixed)

1. **s3-8 encoding direction.** Spec §34.2 writes `f_hat(x) ≤ f(x)` and
   calls it sound over-approximation, then claims SAT never falsely
   declares infeasible architecture feasible. Those two do not follow
   from each other. Under `f_hat ≤ f`: UNSAT is definitive; SAT may be
   a false positive. `pwl.py`, `encoder.py`, and `test_fuzz_soundness.py`
   document this and implement the literal spec direction. Flipping the
   PWL sampling direction (segment maxima instead of minima) would make
   the strong claim true but would require re-running every downstream
   test.

2. **s3-7 hierarchical scaling gate.** The Rev. 2 gate ("hierarchical
   solves >50 nodes; monolithic times out") does not reproduce. Measured
   ratio hierarchical/monolithic was 0.78×–0.96× on structurally
   independent cluster constraints — hierarchical is 10–20% slower,
   because Z3 decomposes internally. The reformulated gate (linear
   scaling in cluster count, bounded composition overhead, soundness
   invariant preserved) is in `docs/ROADMAP_STATUS.md`.

3. **`estimate_*` reachability.** The "build fails if Tier 2 reaches
   `decide_*`" claim is enforced by `test_static_analyzer.py` calling
   `analyze_default_package()`, not by a build step. Functionally
   equivalent (both block merge), but the mechanism differs.

---

## 6. Open items

| ID | Item | Action |
|----|------|--------|
| P5 | Han et al. citation in `physics/benchmarks.py` has no DOI or volume. Paper existence unverified. | Browser check by maintainer |
| s3-8 | `docs/ROADMAP_STATUS.md` marks PENDING; `test_fuzz_soundness.py` exists but verifies the sound direction (UNSAT) rather than the roadmap's literal wording. | Tracker/status decision |
| P14 | `architecture_encoder` constants `UAV_ASSUMED_TRANSMIT_W = 20.0` and `NODE_DEFAULT_DEMAND_W = 15.0` are marked `[ESTIMATED]` and are not sourced. | Source or keep flagged |
| P15 | `Hybrid_Link` emits *both* laser MPE and RF MPE constraints, treating the link as simultaneously both modalities. A real hybrid link selects one at a time. | Modelling decision |
| P16 | `generator.encode_architecture_to_z3` is superseded by `architecture_encoder.encode_architecture` but not removed. | Removal or deprecation mark |
| P17 | `notebooks/06_unsat_core_ablation.ipynb` still uses a synthetic 2-constraint fixture. It could now use `architecture_encoder` for a stronger demonstration. | Notebook update |
| P18 | `ROADMAP_STATUS.md` previously said "Sprints 4–12 not started" — now corrected in the same PR as this handoff. | Closed by docs PR |
| P19 | `CHANGELOG.md` ended at Sprint 2b — now updated through Sprint 7. | Closed by docs PR |
| P20 | Upstream `anyio` `BlockingPortal` DeprecationWarning from `fastapi`/`starlette`. Not our code. | Watch upstream |
| P21 | `physics/atmosphere.py` coefficients for the Kruse-Kim model are sourced by citation only; the exact branch values were not verified against the source PDFs in-session. | Browser check by maintainer |
| P22 | `tier2.py` still uses its own unsourced atmospheric coefficients instead of `physics/atmosphere.py`. A follow-up PR should rewire it to call the new module. | Next Phase 2 PR |
| P23 | The cascaded link budget (`build_canonical_link_budget`) takes four bare floats; spec Section 8.4 mandates thirteen physical inputs. Phase 2 work in progress. | Phase 2 |
| P24 | No rectenna model exists; only the PV-TE tandem receiver. Spec Section 8.2 requires an RF-to-DC chain. | Phase 2 |
| P25 | `architecture_encoder.py` does not invoke `physics/link_budget`, `physics/atmosphere`, or `physics/receiver`. Encoder feasibility is currently driven only by flow balance and MPE. | Phase 2 |
| P26 | The generator samples link kinds from the viable set at final geometry, but does not verify that every UAV's combined incoming supply exceeds its demand. 10/30 sampled architectures are UNSAT for this reason. | Follow-up |
| P27 | `physics/beam.py` `combined_beam_efficiency` uses a first-order product of spillover and pointing losses. A rigorous treatment integrates the Gaussian over the shifted aperture. Labelled [ESTIMATED] in the module. | Deferred |
| P28 | The encoder's `encode_architecture_with_physics` is still opt-in. `run_clear_d_loop` calls the base `encode_architecture`, not the physics variant. Decision 6 of the design doc covers the semantic consequences of flipping. | PR-C |
| P29 | `visible_cap_fraction=0.10` is a modelling choice: the generator produces physically feasible but not boundary-pushing architectures. An ablation at 1.0 reproduces wide-placement behaviour. | Documented |
| P30 | `atmospheric_path_length_m` returns the full chord when both endpoints are inside the atmosphere shell. Correct for ground-to-ground links of any length because those chords dip into the Earth; for two points at moderate altitude whose chord exits the top of the shell, the function over-counts. Not currently triggered by the generator. | Latent |

---

## 7. Workflow contract

The maintainer has repeatedly asked for **small, self-contained blocks**
because large pastes into zsh with bracketed paste mode corrupt mid-block.

Default: three separate blocks per task.

    Block 1 — write + gate
        git checkout -B <branch>
        write files (Python heredoc preferred over shell heredoc)
        ast.parse every written .py before trusting it
        cd backend && ruff format . && ruff check --fix . && ruff check . \
          && ruff format --check . && mypy . && pytest --cov=app -q
        echo "block-end"

    Block 2 — commit + push + open PR
        git add -A
        git commit -m "..."
        git push -u origin <branch>
        gh pr create --base main --head <branch> --title "..." --body "..."
        echo "block-end"

    Block 3 — watch + merge
        poll gh pr checks <N> until ≥4 visible
        gh pr checks <N> --watch
        gh pr merge <N> --squash --delete-branch
        git checkout main && git pull && git fetch --prune
        echo "block-end"

**Never in a block:**
- `exit` (bare or with a code) — kills the interactive zsh session
- `#` at column 0 — zsh treats it as a command
- nested heredocs (heredoc inside heredoc)
- `--admin` or `--force` on `gh pr merge`
- `sat.smt.core.minimize` — this is **not** a valid Z3 parameter.
  The correct name is `core.minimize` (bool, default false). An
  invalid parameter is accepted by `Solver.set()` and rejected later
  at `assert_and_track`, so probe before use.

**Prefer Python heredocs (`python3 - << 'PYEOF'`) over shell heredocs
for any content with quotes or newlines.** Inside a quoted heredoc,
`"\n"` in the Python source is two characters (backslash, n), not a
newline. Use triple-quoted strings or `splitlines()`/`join`.

---

## 8. Terminal / tooling facts

- `gh` CLI is installed and authenticated as `sirkianmj`.
- PRs merge with `gh pr merge --squash --delete-branch`.
- Every change goes through a feature branch and a PR; `main` is
  protected.
- `signatures/cla-v1.json` currently lists only `sirkianmj`. If a PR
  is ever opened under a different account, that account must be added
  to the file before the `cla-check` job will pass.

---

## 9. What comes next

    Sprint 7   React mission-control UI
               frontend/src/features/{Globe,Telemetry,XAITrace,
               DigitalTwin,TradeSpace}
               WCAG 2.1 AA ≥ 4.5:1; every UI output carries an
               epistemic-hierarchy tag (spec §21)
    Sprint 8   Multi-tenant SaaS, MinIO introduced here (per D3)
               backend/app/saas/tenant.py, quota.py, Stripe
               PostgreSQL RLS via current_setting('app.tenant_id')
               notebooks/09_tenant_isolation.ipynb
    Sprint 9   Master test harness, notebooks/10_clear_d_end_to_end.ipynb
               — this is where the closed loop was originally
               scheduled; loop.py is already in place from PR #43
    Sprint 10  Q1 article, DARPA DID docs, notebooks/11_binder_ready.ipynb
    Sprint 11  Production deployment via launchd (no Docker)
    Sprint 12  MAT, final acceptance, notebooks/12_final_reproducibility.ipynb

---

## 10. Constants that must not be changed casually

    Stefan-Boltzmann          5.670374419e-8 W/(m²·K⁴)   receiver.py
    T_REF_K                   298.15 K                    receiver.py
    PLC t_max_kelvin          358.45 K (= 85.3 °C)        receiver.py
    ANSI Z136.1, 1064 nm, 0.25 s   2.55 mW/cm²           regulatory.py
    ANSI Z136.1, 1064 nm, 10 s     1.0 mW/cm²            regulatory.py
    FCC Part 1.1310           1.0 mW/cm²                  regulatory.py
    mW/cm² → W/m²             10, not 1                   regulatory.py

Xidian dual efficiency: 20.8% (on-target DC-to-DC) and 3–5%
(end-to-end wall-plug-to-battery) must always be reported together.
`physics/link_budget.py` enforces this by construction of the
`DualEfficiencyReport` container.

---

## 11. Physical attributions that must not be swapped

The Han et al. three-layer receiver stack is:

    Layer 1  CsPbBr₃ perovskite laser cell   — photovoltaic
    Layer 2  Sb₂Se₃ nanocrystal              — THERMAL BARRIER
    Layer 3  Bi₂Te₃                          — thermoelectric

`Sb₂Se₃` appears in the thermal conduction equation between PLC and
TE nodes. It does NOT appear in `eta_te`. The complementary rule is
also true: `eta_te(t_hot, t_cold)` takes only temperatures and
Bi₂Te₃ parameters, never Sb₂Se₃ conductivity.

---

## 12. End of handoff

Verified at commit `ef428bf`, working tree clean, all four CI checks
green on the three most recent merge commits (#41, #42, #43).

If a claim in this document does not match the code you find on disk,
the code is authoritative and this document is wrong. Say so and
update it.
