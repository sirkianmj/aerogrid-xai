# Citation Audit — AeroGrid-XAI

**Audit date:** 2026-10-14
**Repository state:** `main` at commit `368e291` (PR #88)
**Sprint task:** s10-6 (Scientific gate: all references verified)
**Deliverable:** this document; supersedes no prior artifact.
**Related:** P5 and P21 in `docs/ROADMAP_STATUS.md`.

## 1. Purpose and method

The roadmap gate for s10-6 is *"all references verified"*. That gate
needs a specific, honest operationalization, because "verified" means
different things for a peer-reviewed article, a defence-ministry
program, a standards body, and a federal court. Three questions are
distinct and are answered separately for each citation:

1. **Is the citation well-formed?** Does it contain enough
   bibliographic detail (author, year, venue, page) for a reader to
   locate the source?
2. **Does the source exist?** Has an independent record of the source
   (DOI resolution, library catalogue entry, court reporter page,
   standards-body publication) been confirmed?
3. **Do the numerical values attributed to the source appear in the
   source as claimed?** For efficiency figures and coefficients, is
   the value attributed to the reference actually documented there?

An audit that conflates these can only produce a binary "verified /
unverified" label, which hides the underlying structure. The
categories used below are separate for each question.

**Method.** Every citation string in the repository was collected by
`grep` across `backend/app/`, `docs/`, `notebooks/`, `README.md`, and
the specification extract. Each was then classified. No external
network access was used in this audit; that is stated explicitly
because it bounds what can be claimed.

## 2. Verification categories

- **WELL-FORMED** — the citation contains author, year, and venue, or
  an equivalent unique identifier (standard designation, court reporter
  citation, statute). A reader can locate the source.
- **INCOMPLETE** — the citation identifies the source but lacks DOI,
  volume, page, or equivalent. A reader can search for the source but
  cannot resolve it deterministically.
- **INTERNAL-CONSISTENT** — the citation appears in the repository in
  every location where it is claimed to appear, with identical author
  and year. This is a property of the repository, not of the external
  source.
- **EXTERNAL-UNCONFIRMED** — no independent record of the source has
  been confirmed. This is not a statement that the source is fake; it
  is a statement that confirmation was not performed here.

Every citation is scored on all four. A source that is well-formed
and internally consistent, but externally unconfirmed, is not the same
thing as a source that is missing a DOI — the two failure modes are
reported separately.

## 3. Scientific sources

### 3.1 Siegman, "Lasers", University Science Books, 1986

| Property | Value |
|---|---|
| Cited in | `backend/app/physics/beam.py` (docstring, Eq. 17.27, Eq. 17.29, Eq. 17.32, Sec. 17.5); `backend/app/physics/link_budget.py`; `docs/ENCODER_PHYSICS_INTEGRATION.md` |
| WELL-FORMED | YES. Author, title, publisher, year, and specific equation numbers. |
| INTERNAL-CONSISTENT | YES. Same author/year/equation numbers in every location. |
| EXTERNAL-UNCONFIRMED | The equations used are standard Gaussian-beam formulas (Rayleigh range, beam radius, far-field divergence, Gaussian spillover fraction). Their well-known form is consistent with this citation. The equation *numbers* attributed to Siegman 1986 were not checked against a copy of the book. |

**Assessment:** WELL-FORMED and INTERNAL-CONSISTENT. The equation
numbers are a residual risk — they are what a reader would need to
check if the underlying formula were ever questioned. Low priority
because the formulas themselves are textbook-standard and independently
reproducible from first principles.

### 3.2 Klein & Pappas, "Power handling capability of far-infrared laser windows", 1974

| Property | Value |
|---|---|
| Cited in | `backend/app/physics/beam.py` (line 13, line 196); `backend/app/physics/link_budget.py`; `docs/ENCODER_PHYSICS_INTEGRATION.md` |
| WELL-FORMED | PARTIAL. Author and year present; title and venue not quoted in code. |
| INTERNAL-CONSISTENT | YES. |
| EXTERNAL-UNCONFIRMED | The pointing-loss formula (exp of a squared offset over beam radius squared) is standard; whether this specific 1974 paper is its canonical source is not confirmed here. |

**Assessment:** The formula is correct; the citation attributing its
canonical form to this paper is a claim that would benefit from an
external check. Recommend adding the full title and venue so the
citation is well-formed, then external verification at a later audit.

### 3.3 Kruse, McGlauchlin & McQuistan, "Elements of Infrared Technology", 1962

| Property | Value |
|---|---|
| Cited in | `backend/app/physics/atmosphere.py` (three-branch extinction model); `docs/ENCODER_PHYSICS_INTEGRATION.md`; `docs/ROADMAP_STATUS.md` |
| WELL-FORMED | YES. Authors and year present; the standard reference for the three-branch aerosol extinction model. |
| INTERNAL-CONSISTENT | YES. |
| EXTERNAL-UNCONFIRMED | The three-branch form (q = 1.6, 1.3, 0.585 in the standard visibility ranges) is the well-known Kruse model. The **specific numerical values used in the code** have not been cross-checked against the source (this is finding **P21**). |

**Assessment:** **P21 remains open.** The form is correct; the exact
coefficients require a cross-check against the source PDF. Until that
is done, the citation should be read as "Kruse-model form" rather than
"Kruse 1962 coefficients, verified."

### 3.4 Kim, McArthur & Korevaar, "Comparison of laser beam propagation at 785 nm and 1550 nm in fog and haze for optical wireless communications", SPIE 2001

| Property | Value |
|---|---|
| Cited in | `backend/app/physics/atmosphere.py` (low-visibility refinement branch) |
| WELL-FORMED | YES. Authors, title, year, and the SPIE venue are documented in the module docstring. |
| INTERNAL-CONSISTENT | YES. |
| EXTERNAL-UNCONFIRMED | The Kim refinement is the standard low-visibility correction to the Kruse model. The specific branch values were not cross-checked (this is part of **P21**). |

**Assessment:** Same status as Kruse — form is correct, coefficients
require cross-check. **P21 remains open.**

### 3.5 Cimatti et al., "Incremental Linearization for Satisfiability and Verification Modulo Nonlinear Arithmetic and Transcendental Functions", ACM TOCL 2018; formalization in CPP 2026

| Property | Value |
|---|---|
| Cited in | `backend/app/verification/encoder.py`; `docs/DEFENSIVE_PUBLICATION.md` §4.1 |
| WELL-FORMED | YES. Authors, title, venue, year; formalization attribution is separate. |
| INTERNAL-CONSISTENT | YES. |
| EXTERNAL-UNCONFIRMED | The two references (2018 paper and 2026 formalization) are cited as prior art in the specification and in the defensive-publication memo. Their existence is asserted, not checked against a library or publisher page. |

**Assessment:** The citation is well-formed and its role in the project
(Stage B is an application, not a novel contribution) is clearly
stated. External verification is a low-risk check but would strengthen
`docs/DEFENSIVE_PUBLICATION.md` §4.1.

### 3.6 Li & Li, "MUC-G4: Accelerating Incremental Verification of Compressed Neural Networks via Minimal UNSAT Core Reuse", ACM TECS 2026

| Property | Value |
|---|---|
| Cited in | `backend/app/discovery/attribution.py`; `docs/DEFENSIVE_PUBLICATION.md` §4.2 |
| WELL-FORMED | YES. Authors, title, venue, year. |
| INTERNAL-CONSISTENT | YES. |
| EXTERNAL-UNCONFIRMED | The characterization of MUC-G4 as "unsat-core reuse for verification of a fixed artifact" is the author's reading of the paper as described in the specification. The paper itself was not consulted during this audit. |

**Assessment:** The distinctiveness argument for CLEAR-D depends on the
accuracy of the characterization. If the paper in fact already uses
unsat cores to guide synthesis in some narrower sense, the novelty
position would need revisiting. This is the highest-priority external
check for the defensive-publication memo.

### 3.7 PowerLight Technologies / Kraus Hamdani Aerospace — DoD PTROL-UAS program, Shaw AFB

| Property | Value |
|---|---|
| Cited in | `backend/app/physics/benchmarks.py` (Benchmark entry); `notebooks/01_trl_benchmark_validation.ipynb`; `docs/SCIENTIFIC_CLAIMS.md` |
| WELL-FORMED | NO DOI. Program name, organization, location, and figures are documented, but there is no peer-reviewed publication. |
| INTERNAL-CONSISTENT | YES. |
| EXTERNAL-UNCONFIRMED | The program is widely reported in defence and trade press. Figures (~1 kW delivered at up to 1,524 m) are consistent with those reports but were not checked here. |

**Assessment:** This is a program-level demonstration, not a journal
article. The TRL-6 tag and the scope note (single ground transmitter,
single cooperative target) are the qualifiers. Recommend a specific
public citation be identified for the record (DoD press release, trade
publication). No DOI is expected; the scope note is the safety valve.

### 3.8 Xidian University — microwave power beaming to moving drone

| Property | Value |
|---|---|
| Cited in | `backend/app/physics/benchmarks.py`; `backend/app/physics/link_budget.py` (`XIDIAN_DUAL_REPORT`); `notebooks/01_trl_benchmark_validation.ipynb` |
| WELL-FORMED | PARTIAL. Institution and figures cited; no DOI or specific publication. |
| INTERNAL-CONSISTENT | YES. Both 20.8% and 3-5% figures present in every location. |
| EXTERNAL-UNCONFIRMED | The 20.8% DC-to-DC and 3-5% end-to-end figures are consistent with press reporting. Neither figure was checked here against a primary source. |

**Assessment:** The dual-figure reporting rule is enforced in code
(`DualEfficiencyReport`). The numbers should be traced to a specific
publication (paper or press release) for the s10-1 Q1 draft.

### 3.9 Overview Energy — airborne laser to ground, Pennsylvania

| Property | Value |
|---|---|
| Cited in | `backend/app/physics/benchmarks.py`; `notebooks/01_trl_benchmark_validation.ipynb` |
| WELL-FORMED | PARTIAL. Company and demonstration described; no DOI. |
| INTERNAL-CONSISTENT | YES. Scope note disclaims satellite-to-UAV analogy. |
| EXTERNAL-UNCONFIRMED | Not checked here. |

**Assessment:** The scope disclaimer is the substantive content (this
is a ground-receiver architecture analog, not a satellite-to-mobile-UAV
demonstration). That claim is enforced by
`test_scientific_validation/test_overview_energy.py`. The specific
altitude (~5,000 m) should be traced to a public report for s10-1.

### 3.10 DARPA POWER program / Naval Research Laboratory — 800 W over 8.6 km

| Property | Value |
|---|---|
| Cited in | `backend/app/physics/benchmarks.py`; `notebooks/01_trl_benchmark_validation.ipynb` |
| WELL-FORMED | PARTIAL. Program name, organization, site (White Sands). No DOI. |
| INTERNAL-CONSISTENT | YES. |
| EXTERNAL-UNCONFIRMED | Not checked here. Widely reported. |

**Assessment:** Fixed-to-fixed demonstration; scope note preserved. The
"record" claim (>800 W over 8.6 km) should be traced to a DoD or NRL
release for the s10-1 Q1 draft.

### 3.11 Han et al., "Sb₂Se₃ nanocrystals enable efficient perovskite-thermoelectric tandem devices for laser-powered unmanned aerial vehicles", Matter & Light, 2026

| Property | Value |
|---|---|
| Cited in | `backend/app/physics/benchmarks.py`; `backend/app/physics/receiver.py`; `backend/app/physics/thermal.py`; `backend/app/physics/link_budget.py`; `notebooks/03_receiver_efficiency_surface.ipynb`; `docs/ENCODER_PHYSICS_INTEGRATION.md`; `docs/DEFENSIVE_PUBLICATION.md` |
| WELL-FORMED | **NO.** Title and authors partially identified; **no DOI, no volume, no page number**, and the journal *Matter & Light* was not located in this audit. This is finding **P5**. |
| INTERNAL-CONSISTENT | YES. The three-layer attribution (CsPbBr₃ / Sb₂Se₃ / Bi₂Te₃) is consistent across code, docs, and tests. |
| EXTERNAL-UNCONFIRMED | The paper's existence has never been independently verified in this repository. |

**Assessment:** **P5 remains open.** This is the highest-priority
citation to verify because (a) the 38.49% champion efficiency and the
80-90 °C degradation regime are attributed to it, and (b) no DOI or
volume exists in any public record consulted by the project. Until the
paper is resolved, the values are preserved in the benchmark table as
*stated reference figures*, not as validated model parameters. The
`docs/SCIENTIFIC_CLAIMS.md` entry for H10 marks this half explicitly
as `PARTIAL`.

## 4. Regulatory and legal sources

### 4.1 ANSI Z136.1 (2026 revision) and IEC 60825 series

| Property | Value |
|---|---|
| Cited in | `backend/app/verification/regulatory.py`; specification §16 |
| WELL-FORMED | YES. Standard designation and year. |
| INTERNAL-CONSISTENT | YES. |
| EXTERNAL-UNCONFIRMED | The specific MPE values (2.55 mW/cm² at 1064 nm for 0.25 s; 1.0 mW/cm² at 1064 nm for 10 s) were not cross-checked against the 2026 revision. |

**Assessment:** Standards are identified by designation; the specific
values require a standards-body cross-check for the s10-1 Q1 draft.
The **regulatory-model tests** (`test_regulatory.py`) verify the code
uses the values it claims, not that the values match the standard.

### 4.2 FCC Part 15 and Part 18

| Property | Value |
|---|---|
| Cited in | `backend/app/verification/regulatory.py`; specification §16 |
| WELL-FORMED | YES. Part and section numbers; the FCC Part 1.1310 limit (1.0 mW/cm² over 1500-100000 MHz, 30-minute average) is quoted. |
| INTERNAL-CONSISTENT | YES. |
| EXTERNAL-UNCONFIRMED | The 1.0 mW/cm² value was not cross-checked against the current FCC rule text. |

**Assessment:** The specific value should be checked against a
current eCFR entry. Low risk (the value is stable and widely quoted).

### 4.3 KSR International Co. v. Teleflex Inc., 550 U.S. 398 (2007)

| Property | Value |
|---|---|
| Cited in | `docs/DEFENSIVE_PUBLICATION.md` §6 (indirect); specification §40.2 |
| WELL-FORMED | YES. Full reporter citation. |
| INTERNAL-CONSISTENT | YES. |
| EXTERNAL-UNCONFIRMED | The holding is well-known and correctly characterized in the specification. Not checked against the reporter volume here. |

**Assessment:** The case is famous and the citation form is standard.
No action needed.

### 4.4 Alice Corp. v. CLS Bank Int'l, 573 U.S. 208 (2014)

| Property | Value |
|---|---|
| Cited in | specification §40.1 |
| WELL-FORMED | YES. Full reporter citation. |
| INTERNAL-CONSISTENT | YES. |
| EXTERNAL-UNCONFIRMED | Well-known; not checked against the reporter here. |

**Assessment:** No action needed.

### 4.5 Burroughs Wellcome Co. v. Barr Laboratories, 40 F.3d 1223 (Fed. Cir. 1994)

| Property | Value |
|---|---|
| Cited in | specification §44 (Legal Sources, item 15) |
| WELL-FORMED | YES. Full reporter citation. |
| INTERNAL-CONSISTENT | YES. |
| EXTERNAL-UNCONFIRMED | Not checked here. |

**Assessment:** Not cited elsewhere in the repository. If it is not
relied on in any Sprint 10 document, consider removing it from the
specification's Legal Sources list; if it *is* relied on (e.g., for a
conception argument in a hypothetical patent filing), keep it and
cross-check.

## 5. Findings summary

| ID | Source | Issue | Priority |
|----|--------|-------|----------|
| **P5** | Han et al., *Matter & Light* 2026 | No DOI, volume, or page; paper existence unverified. | **HIGH** — directly supports the 38.49% and 80-90 °C claims. |
| **P21** | Kruse 1962 / Kim 2001 | Coefficients cited by reference; not cross-checked against source PDFs. | **MEDIUM** — form is standard; exact values matter for the physics-model fidelity claim. |
| **C-1** (new) | Klein & Pappas 1974 | Citation lacks title and venue; the formula is correct but the canonical attribution is not verified. | LOW |
| **C-2** (new) | PowerLight / Xidian / Overview / DARPA | Non-peer-reviewed demonstrations; each lacks a specific public release citation. | MEDIUM — needed for the s10-1 Q1 draft to be submittable. |
| **C-3** (new) | MUC-G4 | The novelty argument depends on the accuracy of the paper characterization; the paper was not consulted. | **HIGH** — the entire distinctiveness claim for CLEAR-D rests on this. |
| **C-4** (new) | ANSI Z136.1 / FCC Part 1.1310 values | Standards and regulations are identified by designation; the specific numeric limits were not cross-checked against current versions. | LOW |
| **C-5** (new) | Burroughs Wellcome | Cited in specification §44 but not relied on elsewhere in the repository. | TRIVIAL — remove if unused, or keep with a note. |
| **CIT-1** (new) | DID standard numbers (DI-IPSC-81428, 81433, 81434) | The DID documents in `docs/DID/` cite these as the templates they follow. The numbers are widely reported; the exact current revision of each template was not cross-checked against a DoD source. | LOW — a verifiable external check. |

## 6. What this audit does not do

- **It does not verify external sources.** No browser, no library, no
  publisher page, no court reporter, no standards body. Every external
  source is marked `EXTERNAL-UNCONFIRMED`. That is a factual statement
  about the method, not a defect in any citation.
- **It does not attribute intent.** A `PARTIAL` or `EXTERNAL-UNCONFIRMED`
  entry means the check was not performed here; it does not imply the
  citation is wrong.
- **It is not a substitute for the P5/P21 follow-up tasks.** Those
  require external access and are tracked separately.

## 7. Recommended external-verification actions (in priority order)

1. **Verify the Han et al. paper (P5).** Search for the authors and
   title on the journal site, on arXiv, or via DOI resolution. If the
   paper exists, add the DOI to `backend/app/physics/benchmarks.py` and
   `docs/ENCODER_PHYSICS_INTEGRATION.md`. If it does not exist, remove
   the citation and downgrade the 38.49% figure from `[PHYSICAL
   MEASUREMENT]` to `[ESTIMATED MODEL]` in every location that carries
   the tag.
2. **Verify the MUC-G4 characterization (C-3).** Read the paper and
   confirm that its reuse of unsat cores is confined to verification of
   a fixed artifact (compressed network). If the paper already uses
   cores to bias synthesis in any form, the novelty argument in
   `docs/DEFENSIVE_PUBLICATION.md` §4.2 must be revised.
3. **Verify the Kruse and Kim coefficient values (P21).** Cross-check
   the three-branch coefficients against the 1962 and 2001 sources.
4. **Identify specific public citations for the four defence-program
   demonstrations (C-2).** One DoD press release, one trade article, or
   one conference paper per program.
5. **Add full title and venue to the Klein & Pappas citation (C-1).**
6. **Cross-check the ANSI Z136.1 and FCC Part 1.1310 numeric limits
   (C-4).** Two values each.
7. **Decide the fate of the Burroughs Wellcome citation (C-5).**

## 8. Certification

Within the method described in §1 and the limits stated in §6, every
citation in the repository has been collected, classified, and its
internal consistency verified. The four High/Medium-priority items
(**P5**, **P21**, **C-2**, **C-3**) are the ones that require external
access and are the object of the follow-up actions in §7. Nothing has
been silently upgraded from `EXTERNAL-UNCONFIRMED` to `VERIFIED`;
sources the audit could not check are recorded as unchecked.

Signed: Kian Mansouri Jamshidi
