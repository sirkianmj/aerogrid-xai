# AeroGrid-XAI product architecture

Status: design. Supersedes the current eight-equal-tabs navigation.

## 1. What the app is

A mission design instrument. The user defines a mission, designs the
hardware, discovers feasible architectures, picks one, simulates it,
and produces a report that a reviewer can independently verify.

The app currently presents eight equal nav items and no final
artifact. That is the problem this document fixes.

## 2. The workflow

Six steps in a fixed order, with free navigation.

    1. Mission       define the scenario
    2. Hardware      design the transmitter and receiver
    3. Discovery     CLEAR-D searches the architecture space
    4. Selection     pick an architecture from the Pareto front
    5. Simulation    run the selected architecture over time
    6. Report        export the final artifact

Plus two meta views reachable from the sidebar footer:

    - Trust          the XAI trace and every audit
    - Meta           About, Legal, Status

The steps render top-to-bottom in the sidebar with a visible
"Step N of 6" indicator and a connecting line between them. Each
step shows a completion tick when its output exists. Clicking any
step jumps to it. Clicking forward past an uncompleted step warns
but does not block — the user may explore.

## 3. Shared state

One provider owns every artifact. Each step writes its own slot and
reads any slot above it.

    mission_config          <- Steps 1, 2 write. All steps read.
    discovery_run           <- Step 3 writes. Steps 4, 5, 6 read.
    selected_architecture   <- Step 4 writes. Steps 5, 6 read.
    mission_run             <- Step 5 writes. Step 6 reads.
    report                  <- Step 6 writes. Download source.
    audit_trail             <- Every step appends a decision.

The provider also carries the current step number so the sidebar can
highlight it and the report can record the path taken.

Every write is timestamped, seeded, and versioned. The report needs
that for reproducibility.

## 4. What each step produces

| Step | Input | Output | Exists today |
|---|---|---|---|
| 1 Mission | globe click, satellite pick, env | mission_config | Yes, partial |
| 2 Hardware | design studio, presets | mission_config extended | Yes |
| 3 Discovery | mission + hardware | discovery_run | Yes, but standalone |
| 4 Selection | discovery_run + weights | selected_architecture | No |
| 5 Simulation | selected + mission | mission_run | Partial (mission state) |
| 6 Report | all of the above | report + JSON export | No |

Step 4 is new. Step 5 as a distinct "run the mission" step is new.
Step 6 is new. Steps 1-3 exist in scattered form and need rewiring.

## 5. What the user sees at the end

A report. A single page, printable and downloadable, that contains:

- The mission scenario (satellite, orbit, ground station, environment)
- The hardware design (transmitter, receiver, thermal limits)
- The discovery run (seed, population, generations, attribution)
- The selected architecture (topology, objectives, feasibility proof)
- The simulation (power delivered over time, thermal margins, eclipse)
- Every chart
- The XAI trace
- The audit trail (every decision, every number's source)
- The reproducibility block (seed, versions, git hash, exact commands)
- The limitations section (what is NOT proven)

The DARPA-level export is detailed in section 7.

## 6. Visualizations

Twenty charts, maps, and diagrams. Each is placed where it answers
a question the user is actually asking at that step.

### Step 1 — Mission (4 visualizations)

1. **Ground track map** (2D equirectangular). The satellite's
   sub-point over one orbit, with the ground station, the visibility
   cone, and the eclipse intervals shaded.
2. **3D globe** (Three.js). Existing. Shows satellite position,
   ground station, UAVs on the ground.
3. **Pass elevation profile**. Elevation angle versus time for the
   next visible pass. Shows when the link is usable.
4. **Atmospheric transmittance heatmap**. Transmittance as a
   function of (elevation angle, visibility_km, cloud_factor). One
   panel, three sliders.

### Step 2 — Hardware (4 visualizations)

5. **Satellite profile** (parametric SVG). Existing. Design Studio.
6. **Solar array design chain** (existing). I_AM0, eta_cell,
   packing, PSE, panel dimensions — as a vertical cascade.
7. **Receiver efficiency surface**. eta_total as a heatmap over
   (T_PLC, T_TE). Shows the thermal runaway boundary as a contour.
8. **Power budget waterfall**. From solar input through every loss
   stage to delivered electrical power. A classic Sankey or
   waterfall chart.

### Step 3 — Discovery (4 visualizations)

9. **Unsat-core attribution graph**. A force-directed graph where
   nodes are grammar features and edges are co-occurrence in the
   conflict-prone table. The visual form of CLEAR-D's inventive
   mechanism.
10. **Generation progress**. Feasible vs infeasible counts,
    conflict-prone feature count, hypervolume history — one
    multi-line chart, 3 panels stacked.
11. **Architecture topology sketches** (existing). Each Pareto
    point rendered as a small schematic.
12. **Convergence ribbon**. Population diversity versus generation,
    as a band chart. Shows when the search has saturated.

### Step 4 — Selection (4 visualizations)

13. **Pareto scatter** (existing, upgraded). Colored by rank, with
    a highlighted "selected" point and a shadow showing the
    dominated region.
14. **Parallel coordinates** (existing). Six objectives, with
    brushing to filter.
15. **Radar chart**. The selected architecture versus the Pareto
    median, across all six objectives. One glance comparison.
16. **Sensitivity tornado**. Finite-difference elasticity of
    delivered power to each config parameter. Ranked bar chart.

### Step 5 — Simulation (3 visualizations)

17. **Power delivered over time**. Per-second delivered electrical
    power across a full orbit, with eclipse intervals, pass
    windows, and thermal limit regions shaded.
18. **Thermal margin chart**. T_PLC and T_TE versus time, with
    the runaway threshold as a red line. Shows when the design is
    within 5°C of failure.
19. **Energy accumulation**. Cumulative Joules delivered versus
    time, with the daily total annotated. This is the "how much
    did we actually get" chart.

### Step 6 — Report (1 visualization)

20. **Full report page**. Every chart above, arranged in a fixed
    order with captions, on a printable A4 layout. PDF-ready.
    The export is described in section 7.

That is twenty. Of these, seven exist today (globe, satellite
profile, solar array chain, topology sketches, Pareto scatter,
parallel coordinates, sensitivity tornado) and thirteen need to be
built. Building them is the visible half of this work.

## 7. The DARPA-grade export

The export is what a reviewer at DARPA, AFRL, or a program office
would accept as evidence that the analysis was performed rigorously.
It is not a presentation. It is a reproducible technical package that
an independent team could hand to a verification cell.

One archive, six components:

    aerogrid-mission-<seed>-<timestamp>.zip
      REPORT.pdf                     the human-readable report
      report.json                    the same content, machine-readable
      data/                          every number that feeds every chart
      charts/                        every chart as SVG and PNG
      reproduce.sh                   exact commands to regenerate
      MANIFEST.txt                   SHA-256 of every file
      README.txt                     how to open, how to verify

### 7.1 REPORT.pdf structure

Fixed layout. Forty to sixty pages. Sections in this order.

COVER PAGE
    Title, satellite name, date, author, affiliation, ORCID.
    Report ID (first 12 hex chars of the content hash).
    Classification marking field, blank by default.
    Version, seed.

EXECUTIVE SUMMARY
    One page. What was asked, what was found, what was delivered,
    what was NOT proven. Written for a non-specialist program
    manager.

SECTION 1 — MISSION DEFINITION
    Orbit: TLE source, epoch, elements.
    Ground station: lat, lon, alt, name.
    Environment: visibility, cloud, temperature.
    UAV fleet: count, altitude, receiver type.
    Time window: start, end, duration.
    Every parameter with its value, source, and epistemic tag.

SECTION 2 — HARDWARE DESIGN
    Satellite bus, solar array, transmitter.
    UAV receiver: aperture, type, thermal limits.
    Full design chain from solar input to delivered power.
    Every stage's efficiency, tagged.

SECTION 3 — DISCOVERY
    CLEAR-D configuration: seed, population, generations.
    Generation-by-generation statistics.
    Unsat-core attribution: which grammar features were
    conflict-prone, how often, which mutations resolved them.
    The Pareto front: every non-dominated architecture.
    Convergence evidence.

SECTION 4 — SELECTION
    The selection method and its weights.
    The selected architecture in full.
    Comparison to the Pareto median across all six objectives.
    Sensitivity of the selection to weight changes.

SECTION 5 — SIMULATION
    Hour-by-hour power delivery.
    Thermal state over time.
    Eclipse intervals and pass windows.
    Cumulative energy delivered.
    Every number tagged.

SECTION 6 — XAI TRACE
    Every decision the controller made.
    Rule weights, trace steps, winning score.
    Counterfactuals: what would have changed the decision.
    Fidelity audit: score equals sum of step weights.

SECTION 7 — REPRODUCIBILITY
    Git commit hash.
    Python, numpy, scipy, Z3, Skyfield versions.
    The exact seed.
    The exact command line.
    SHA-256 of every file.

SECTION 8 — LIMITATIONS
    Every scientific limitation, stated plainly.
    Which claims are verified by test, by notebook, by inspection.
    Which hypotheses are PARTIAL and why.
    Which are FALSIFIED (H4) and what that means.
    Which require capability that does not exist (H7).
    Every unresolved citation.

APPENDIX A — Glossary
APPENDIX B — Full parameter list with JSON paths
APPENDIX C — Audit trail, every user action and its state

### 7.2 report.json

Same content, structured for programmatic consumption. Every
numeric field carries its epistemic tag and its provenance.

    {
      "delivered_power_w": {
        "value": 42.7,
        "tag": "simulation_result",
        "source": "simulation_timeseries.csv:row 3600",
        "computed_by": "physics/link_budget.py:142",
        "verified_by": "tests/test_link_budget.py::test_delivered_power"
      }
    }

That provenance block is what makes it DARPA-grade. Any reviewer
can trace any number to the code that produced it and the test
that guards it.

### 7.3 reproduce.sh

One shell script that regenerates the whole report from the archive:

    #!/bin/bash
    set -euo pipefail
    cd "$(dirname "$0")"
    python3 -m pip install -r requirements.txt
    python3 tests/reproduce_report.py --seed 20261015 --out ./reproduced
    sha256sum --check MANIFEST.txt --ignore-missing
    echo "Compare ./reproduced/REPORT.pdf to ./REPORT.pdf."

### 7.4 MANIFEST.txt

Standard sha256sum format, generated at export time. A reviewer
runs sha256sum --check MANIFEST.txt. If it passes, the archive has
not been tampered with.

### 7.5 What makes it acceptable

Three properties, in order of importance.

1. Reproducibility. Given the archive and the git commit, any
   competent team can regenerate every number.
2. Traceability. Every number points to the code that computed it
   and the test that verifies it.
3. Honesty. The limitations section is a full section, not a
   footnote. Falsified hypotheses are named. Open citations are
   named. A report that hides its limitations is not DARPA-grade
   regardless of how many charts it has.

### 7.6 Not in the export

No proprietary third-party libraries. No external data the reviewer
cannot obtain. No claim outside the epistemic hierarchy. No number
without a source and a test.

## 8. Build sequence

Ten PRs, ordered so each one ships something visible. Each is
independently reviewable, each passes the six-context CI gate,
each leaves the app usable.

### PR 1 — Shared state (foundation)

Widen MissionProvider with six slots: mission_config,
discovery_run, selected_architecture, mission_run, report,
audit_trail. Every panel still does its own thing; the slots
exist but nothing writes them yet. Wire the sidebar to show a
"Step N of 6" indicator that reads only the current step.

Files: MissionProvider.tsx, missionContext.ts, AppShell.tsx.
Estimated: 1 session. Tests: provider tests for slot writes.

### PR 2 — Nav rewrite

Reorder the sidebar: six steps, two meta (Trust, Meta) in a
footer section. Each step clickable, all steps reachable, a
visible connecting line and a tick when the step's output
exists. Add a "Next" button at the bottom of each step that
jumps to the next.

Files: App.tsx, AppShell.tsx, new Nav component.
Estimated: 1 session. Tests: nav order, tick rendering,
next-button navigation.

### PR 3 — Step 1: Mission

Collect the existing Globe, MissionConfigBar, and digital-twin
scenario into a single page. Add the three new visualizations:
ground track map, pass elevation profile, atmospheric
transmittance heatmap. Globe click writes to mission_config.
Estimated: 1 session. Tests: each visualization renders with
real backend data.

### PR 4 — Step 2: Hardware

Collect the existing DesignStudio and solar array chain into a
single page. Add the two new visualizations: receiver
efficiency surface, power budget waterfall. Design edits write
to mission_config. Estimated: 1 session.

### PR 5 — Step 3: Discovery

Collect the existing ClearDDashboard and ArchitecturesView into
a single page. Add two new visualizations: unsat-core
attribution graph, convergence ribbon. Running CLEAR-D writes
discovery_run. Estimated: 1-2 sessions. This is the most
complex of the step pages.

### PR 6 — Step 4: Selection (new)

New page. Takes discovery_run, shows the Pareto front with the
post-hoc weight sliders, lets the user pick an architecture,
records the choice in selected_architecture. Two new
visualizations: Pareto scatter with selection highlight, radar
comparison. Sensitivity tornado moves here from the CLEAR-D
view. Estimated: 1 session.

### PR 7 — Step 5: Simulation (new)

New page. Takes selected_architecture and mission_config, runs
the simulation, produces mission_run. Three new visualizations:
power over time, thermal margin, cumulative energy. Estimated:
1-2 sessions. The simulation itself exists in the backend; the
work is packaging it as a coherent step.

### PR 8 — Step 6: Report

New page. Takes all five prior slots, produces the archive
described in section 7. PDF generation, JSON schema, chart
export, manifest, reproduce.sh. Estimated: 2 sessions. The
largest single PR.

### PR 9 — Trust view

Collect XAITrace and every audit into a single view. Add the
fidelity audit visualization and the counterfactual panel.
Estimated: 1 session.

### PR 10 — Polish

Keyboard navigation across steps, progress persistence to
localStorage, empty-state copy for each step, loading states,
error states. Estimated: 1 session.

## 9. Effort summary

    Shared state                1 session
    Nav rewrite                 1 session
    Step 1 Mission              1 session
    Step 2 Hardware             1 session
    Step 3 Discovery            1-2 sessions
    Step 4 Selection            1 session
    Step 5 Simulation           1-2 sessions
    Step 6 Report               2 sessions
    Trust view                  1 session
    Polish                      1 session

    Total                       11-12 sessions

At one session per working day, that is two and a half weeks of
focused work. Not a weekend. Not an evening. A real product
takes real time.

## 10. What ships after each phase

After PRs 1-2: the app looks the same but has the new nav and
the shared state slots. No functionality change. Users can
still use everything.

After PRs 3-5: steps 1-3 are coherent pages. Each produces its
artifact and the next step can read it. The user can go from
"define mission" to "have architectures" without leaving the
flow.

After PRs 6-8: steps 4-6 exist. The user can go from mission
definition to a DARPA-grade report. The app is one instrument.

After PRs 9-10: the app is polished. Every step is smooth.
Every chart is instrumented. Every number is traceable.

## 11. What this document is NOT

It is not a promise that all ten PRs will ship in two weeks. It
is not a claim that the twenty visualizations are trivial. It is
not a plan that ignores risk.

The risks, stated plainly:

- Step 3 (Discovery) may take longer than two sessions because
  the unsat-core attribution visualization requires new backend
  endpoints to expose the graph structure.
- Step 5 (Simulation) may take longer than two sessions because
  the current backend computes mission_state as a snapshot, not
  a timeseries. A timeseries endpoint is needed.
- Step 6 (Report) is the largest single PR. PDF generation in
  Python is a known-difficult problem; the plan is to use
  ReportLab or WeasyPrint, not to hand-roll it.
- The DARPA-grade export is the most consequential deliverable.
  If it is not right, the whole product is a demo. The plan is
  to write the report generator test-first: specify the JSON
  schema, then the PDF, then the manifest.

## 12. What to do next

1. Review this document. Change anything that is wrong.
2. Confirm the effort estimate is acceptable.
3. Decide whether to start with PR 1 (foundation) or PR 3
   (first visible step). PR 1 is faster but invisible. PR 3 is
   slower but produces the first coherent page.
4. When ready, start a fresh session. This document is the
   plan; the next session implements it.

---

**Author:** Kian Mansouri Jamshidi
**Date:** 2026-10-17
**Status:** design — awaiting review
