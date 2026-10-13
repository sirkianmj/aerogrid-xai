# Defensive Publication Record — AeroGrid-XAI / CLEAR-D

**Revision 2.** Supersedes the initial 1.7 KB record dated 2026-10-03.

| Field | Value |
|---|---|
| Project | AeroGrid-XAI |
| Inventive method | CLEAR-D (Coupled-Loop Epistemic Architecture Reasoning and Discovery) |
| Disclosure date | 2026-10-03 |
| Disclosure repository | `https://github.com/sirkianmj/aerogrid-xai` (public, GitHub Free) |
| Earliest repository commit | `5a8a6c0` — Phase 0.2: Repository initialization with Miniforge environment spec |
| Legal-foundation commit | `974bb63` — P0.2: Legal foundation (dual-license files + CLA) |
| Commit that introduced this record | `59eacaf` — Maintenance: close S1 partials and CLA enforcement (#7) |
| Current HEAD at this revision | `edd034d` |
| Total commits at this revision | 92 |
| Repository license | AGPL-3.0 (community) + Proprietary Commercial EULA (enterprise) |
| Owner / sole author | Kian Mansouri Jamshidi (GitHub `sirkianmj`) |

## 1. Purpose of this document

This is the repository's public, timestamped, prior-art record. It
serves three distinct functions, and mixing them has caused confusion in
earlier drafts of this document:

1. **Prior-art disclosure.** Establish the method as publicly available
   so that no later patent applicant can claim it as novel.
2. **Scope statement.** Name exactly what is and is not claimed as the
   inventive contribution, so third parties can determine whether their
   own work overlaps.
3. **Record of actions owed.** Track the steps required before the
   project could ever transition from defensive publication to an actual
   patent filing. As of this revision, none of those steps has been
   performed, and this document does not represent legal advice.

The companion project policy — *any scientific claim not covered by an
automated test is invalid* — is enforced in
`docs/SCIENTIFIC_CLAIMS.md`. The present document is the legal-policy
counterpart to that one: any *novelty* claim not recorded here is not
asserted.

## 2. What is disclosed

The CLEAR-D method as specified in Part V (Sections 31–42) of the
*AeroGrid-XAI Final Comprehensive Specification (Rev. 6)* and implemented
in this repository under `backend/app/discovery/`.

CLEAR-D is a closed-loop discovery-and-control method spanning five
coupled stages:

| Stage | Function | Implementation |
|---|---|---|
| A | Coupled electro-thermal receiver physics → constraint functions | `backend/app/physics/receiver.py`, `backend/app/physics/thermal.py` |
| B | PWL-SMT encoding with tracked approximation error ε | `backend/app/verification/pwl.py`, `backend/app/verification/architecture_encoder.py` |
| C | Generative architecture discovery with UNSAT-core feedback | `backend/app/discovery/` (grammar, generator, unsat, attribution, mutation, nsga2, loop) |
| D | Two-tier explanation-fidelity-preserving control | `backend/app/control/tier1.py`, `tier2.py`, `explain.py`, `static_analyzer.py` |
| E | Closed-loop refinement of the physics model and the formal encoding | `backend/app/refinement/` (bayes, pwl_tune, discrepancy, causality) |

### 2.1 The inventive core

Per specification §35.3, §40.3, and §41, the sole defensible novel
feature is:

> **The unsat-core-to-grammar-feature attribution mechanism**, which
> maps each clause of a Z3 unsatisfiable core back to the specific
> grammar production rule that generated the constraint, and uses that
> mapping to bias a subsequent mutation of the architecture grammar
> toward conflict-prone features.

Implementation reference: `backend/app/discovery/attribution.py`
(public in this repository since Sprint 4, PR #21).

The precise operational form is:

1. A candidate architecture is encoded as a set of `FeatureConstraint`
   objects (Stage B). Each constraint carries the grammar features of
   its originating node or link.
2. Z3 reports UNSAT. The unsat core is a minimal set of jointly
   infeasible constraints.
3. `attribute_and_mark` traces each constraint in the core back to its
   grammar features and records them in a `ConflictProneTable`.
4. `mutate_conflict_directed` samples mutation operators weighted by the
   `ConflictProneTable`, so future candidates are biased away from the
   features that produced the previous conflict.

The result is a closed feedback loop from the formal verifier (Stage B)
back into the generative engine (Stage C), with the unsat core as the
signal.

### 2.2 Dependent inventive concept

The **closed-loop composition** of all five stages is claimed as a
dependent concept: each stage's output is the next stage's input, and
Stage E feeds refinements back to Stages A and B. The specification
(§42) states that no prior art closes this loop; the individual stage
techniques are prior art or obvious combinations.

## 3. When and where — the verifiable record

- The repository became public with its earliest commit `5a8a6c0`
  (Phase 0.2 — repository initialization with Miniforge environment
  spec).
- The dual-license files and the CLA landed at commit `974bb63`
  (P0.2 — Legal foundation). Commits before `974bb63` did not constitute
  a complete publication of the method because the license terms were
  not yet fixed.
- This record was introduced at commit `59eacaf` (Maintenance: close S1
  partials and CLA enforcement, PR #7), which is the date on which the
  method's formal prior-art disclosure was first published in its
  present form.
- Every subsequent commit is visible in the public Git history with an
  author and timestamp. A `git log` at the repository URL therefore
  provides an independently verifiable chain from the earliest commit
  to any future revision.

The disclosure is complete as of `59eacaf`. This revision (Revision 2)
adds explanatory text but does not change the substantive disclosure;
its only effect on the prior-art date is to strengthen the record
already published on 2026-10-03 at that commit.

## 4. Acknowledged prior art

Two references are directly on-point and are cited here in the form the
specification requires.

### 4.1 Incremental Linearization (Cimatti et al., 2018; formalized 2026)

- **What it is.** An SMT solving approach for nonlinear real arithmetic
  (NRA) and nonlinear transcendental arithmetic (NTA). The approach
  abstracts nonlinear operators as uninterpreted functions in a base
  theory of linear arithmetic, then lazily refines the abstraction with
  linear constraints. It is implemented in MathSAT and cvc5; a formal
  proof calculus was published in CPP 2026.

- **What CLEAR-D takes from it.** Stage B's PWL-SMT encoding is an
  application of Incremental Linearization to a new domain (wireless
  power physics constraints) and is explicitly *not* claimed as novel
  (specification §34.1, §41).

- **What CLEAR-D does differently.** Nothing in Stage B alone. The
  patentability argument does not rest on Stage B.

### 4.2 MUC-G4 (Li & Li, ACM TECS 2026)

- **What it is.** Minimal Unsat Core-Guided Incremental Verification for
  compressed neural networks. It identifies Minimal UNSAT Cores (MUCs)
  as robust proof artifacts that capture the local logical reasons for
  safety, extracts them from the original network's verification proof,
  and uses them to prune stable infeasible regions in the compressed
  network's search space.

- **What CLEAR-D takes from it.** The general observation that unsat
  cores are reusable proof artifacts that can drive search-space
  reduction.

- **What CLEAR-D does differently — the critical distinction.**
  MUC-G4 reuses unsat cores **for verification of a fixed artifact
  under modification**: the cores prune the search space for
  re-verification of a compressed network. CLEAR-D uses unsat cores
  **for synthesis of new artifacts**: each core clause is mapped back to
  the grammar production rule that generated the constraint, and the
  resulting feature set biases mutation operators so the generative
  engine explores the feasible region selectively.

  The output of the reuse is qualitatively different: MUC-G4 produces
  a **pruned search space**; CLEAR-D produces a **conflict-directed
  synthesis step**. In MUC-G4 the artifact under test is fixed and the
  search space shrinks; in CLEAR-D the artifact itself is regenerated,
  and its successor is biased by the failure of its predecessor.

  The mapping from SMT unsat-core clauses to grammar production rules
  to mutation-operator biases — specifically for physical-architecture
  topology synthesis rather than for re-verifying a fixed neural
  network — is the novel contribution.

## 5. What is not claimed

Per specification §41, the following are prior art or obvious
combinations and are not asserted as inventive:

- PWL encoding of transcendental physics constraints in SMT
  (Incremental Linearization).
- UNSAT-core reuse as a technique in verification (MUC-G4 and earlier
  work on minimal unsatisfiable subsets).
- Grammar-based generative design (established practice in CAD,
  structural engineering, and compiler research).
- Two-tier interpretable/opaque machine learning (multi-level decision
  architectures exist in the literature; the specific "no decision
  authority" invariant for Tier 2 is arguably novel but is claimed only
  as a dependent feature).
- The individual physics models (Siegman Gaussian-beam propagation,
  Beer-Lambert transmittance, Kruse-Kim aerosol extinction, the
  Han et al. three-layer receiver stack).
- The multi-objective optimizer (NSGA-II is a standard reference).

## 6. Required actions before any patent filing

The specification (§40.4) names four actions. Their status as of this
revision is:

1. **Remove the "SOVER" citation from any document intended to support
   a patent's non-obviousness argument.** *Status: COMPLETE.* The
   erroneous citation was removed before Rev. 6 and does not appear in
   the repository or in any tracked document.

2. **Perform a formal prior-art search by a registered patent agent or
   attorney, covering aerospace/electrical-engineering patent classes
   (not just arXiv/cs.AI), specifically for generative design with
   formal-verification-in-the-loop.** *Status: NOT PERFORMED.* The
   novelty argument in §4 is a plausible claim, not a verified one. No
   such search has been commissioned. Until it is, §4's characterization
   of MUC-G4 as the closest prior art remains an author's assessment.

3. **Correct the Bi₂Te₃ / Sb₂Se₃ attribution in all governing equations
   before any technical peer review.** *Status: COMPLETE.* The
   attribution is corrected in specification §33.1 and enforced in
   code: `Sb₂Se₃` is a thermal barrier whose properties enter the
   thermal model only; it does not appear in the `eta_te` efficiency
   product. See `backend/app/physics/receiver.py`.

4. **File a provisional patent application anchored on the
   unsat-core-to-grammar-feature attribution mechanism, with the
   closed-loop integration as dependent claims.** *Status: NOT
   PERFORMED.* This document reflects the project's decision (D1) to
   pursue defensive publication instead of patent filing. Action 4 is
   listed here so that the record states what would have been required;
   the project has elected not to perform it.

## 7. What this disclosure does not affect

- Copyright in the source code, retained by the author and enforced
  under AGPL-3.0 and the Commercial License (see
  `docs/LICENSING_MATRIX.md`).
- Trade secrets in components not yet published (e.g. private deployment
  configuration and customer data).
- Third-party prior art cited in the specification.
- Any future patent on unrelated improvements.

## 8. Verification of this record

The following commands verify the substantive claims of this document
against the public repository:

    # The disclosure commit is present.
    git log --oneline | grep 59eacaf
    git log --follow --format='%H %s' -- docs/DEFENSIVE_PUBLICATION.md

    # The current HEAD matches this revision's record.
    git rev-parse HEAD

    # The commit count matches.
    git rev-list --count HEAD

    # The method's implementation is public.
    git ls-files backend/app/discovery/attribution.py

    # The dual-license files are present.
    git ls-files | grep -E '^LICENSE-(OPEN-SOURCE|COMMERCIAL)$'

A reader who runs these commands against the repository at a later
revision will find a longer `git log` and, potentially, a different
HEAD. The commit `59eacaf` and everything between it and the reader's
HEAD remain in the history, so the disclosure date is stable.

## 9. Open items and honest limitations

- **No formal prior-art search has been performed** (see §6, item 2).
  The novelty assessment is the author's, not a registered agent's. No
  patentability conclusion can be drawn from this document.

- **P5 — Han et al. citation lacks a DOI.** The receiver-material
  reference cited in specification §33.1 and in
  `backend/app/physics/benchmarks.py` has no DOI, volume, or page in
  any public document available to the author. The paper's existence
  has never been independently verified. If the 38.49% figure is ever
  treated as a validated model parameter, a browser check against a
  citable source is required. The current position: the value is
  preserved in the benchmark table as a stated reference figure; the
  source is not asserted.

- **P21 — Kruse-Kim coefficients cited by reference.** The aerosol
  extinction coefficients in `backend/app/physics/atmosphere.py` are
  cited to Kruse (1962) and Kim et al. (2001) but have not been
  cross-checked against the source PDFs. A follow-up audit is owed.

- **No patent counsel has reviewed this document.** It is a technical
  record, not a legal instrument.

- **Authorship.** The repository has a single author (`sirkianmj`).
  Every commit, docstring, and document in this repository is authored
  by Kian Mansouri Jamshidi. No AI-assisted, co-authored, or third-party
  attribution exists and none may be added.

## 10. Related documents

| Document | Purpose |
|---|---|
| `docs/LICENSING_MATRIX.md` | Per-path license declaration. |
| `LICENSE-OPEN-SOURCE` | AGPL-3.0. |
| `LICENSE-COMMERCIAL` | Proprietary Commercial EULA. |
| `CLA.md` | Contributor License Agreement. |
| `docs/SCIENTIFIC_CLAIMS.md` | Claims-to-test coverage map. |
| `docs/XAI_FIDELITY_AUDIT.md` | Tier 1 / Tier 2 separation audit. |
| `docs/ISOLATION_AUDIT.md` | Multi-tenant database isolation audit. |
| The AeroGrid-XAI Final Comprehensive Specification (Rev. 6) | Full specification; Part V is the inventive method. |

Signed: Kian Mansouri Jamshidi
