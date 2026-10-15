# Interactive tutorial — design

A guided tour that teaches the AeroGrid-XAI desktop app end to end.
This document is the plan. The build is incremental (see section 7).

## 1. Scope

The tutorial has three goals, in order:

1. Orientation. In 60 seconds, a first-time user learns what the seven
   views are and what each one is for.
2. Competence. In 10 minutes, they can configure a mission, run
   CLEAR-D, read the XAI trace, and export a report.
3. Honesty. At every step that shows a number, the tutorial names its
   epistemic status. This is not decoration; it is the app's central
   claim.

Out of scope: teaching the physics, the SMT encoding, or the research
hypotheses. Those live in docs/ and the notebooks. The tutorial
teaches the UI.

## 2. Structure

Two modes:

- First-run tour. Auto-offered on first launch. 7 steps, one per
  view, ~60 seconds total. Skippable. Dismissable permanently.
- Full course. Reachable from About, "Take the tour". ~35 steps
  across 7 chapters. Persisted progress. Can be restarted.

The first-run tour ends with a button that offers the full course.

## 3. Chapters and steps

### Chapter 0 — Welcome (3 steps)

| # | Anchor | Text |
|---|---|---|
| 0.1 | app root | What AeroGrid-XAI is: a software-only research instrument for architecture discovery in space-to-air wireless power. Not hardware. |
| 0.2 | sidebar | The sidebar carries identity, navigation, and the theme toggle. Each nav item is one workspace view. |
| 0.3 | invariant badge | The green badges: the Tier-2 firewall invariant and the license. Both are CI-enforced. |

### Chapter 1 — Digital Twin & Orbit (6 steps)

| # | Anchor | Text |
|---|---|---|
| 1.1 | globe canvas | The 3D globe is a real SGP4 propagation of a packaged TLE. Not an animation. |
| 1.2 | satellite picker | Choose which TLE. Currently three: ISS, Vanguard R3, GEO-TEST (synthetic). |
| 1.3 | time control | Scrub through the first visible pass. The default opens at peak elevation. |
| 1.4 | mission config bar | Change the mission parameters. Every change recomputes the mission state on the server. |
| 1.5 | mission control panel | The vertical pipeline view. Each stage is a Section-4 element. |
| 1.6 | telemetry panel | Live WebSocket feed of thermal and orbital snapshots. |

### Chapter 2 — CLEAR-D Synthesis (7 steps)

| # | Anchor | Text |
|---|---|---|
| 2.1 | ClearD dashboard | What CLEAR-D is: a closed loop that generates, verifies, attributes, mutates, selects. |
| 2.2 | seed control | The seed is a real number. Same seed gives same output, verified. |
| 2.3 | run button | Hit it. Population 6, 3 generations. The whole loop runs on the backend. |
| 2.4 | attribution panel | The inventive core: unsat core to grammar feature to conflict-prone table. This is the paper's novel claim. |
| 2.5 | generation stats | Feasible vs infeasible count per generation. |
| 2.6 | architecture cards | The Pareto front as topology sketches. |
| 2.7 | sensitivity panel | Which parameter moves the delivered power the most. Ranked elasticity. |

### Chapter 3 — Two-Tier XAI Core (5 steps)

| # | Anchor | Text |
|---|---|---|
| 3.1 | XAITrace panel | The Tier-1 decision trace: every charge decision is a sum of rule weights, no black box. |
| 3.2 | candidate table | The two UAVs the loop is choosing between. |
| 3.3 | trace steps | Each row is a rule and its contribution. Fidelity means score equals the sum of weights. |
| 3.4 | counterfactual panel | Rule ablation: turn a rule off, see whether the decision flips. |
| 3.5 | Tier-2 firewall | Explanation: this panel is the reason the two-tier design exists. Tier-2 estimates never touch the decision. |

### Chapter 4 — Trade Space (4 steps)

| # | Anchor | Text |
|---|---|---|
| 4.1 | Pareto scatter | Every point is one architecture. Axes are objectives. |
| 4.2 | axis picker | Choose which objectives to plot. The Pareto front is invariant; the projection is not. |
| 4.3 | parallel coordinates | Six-objective view. Drag a slider to filter. |
| 4.4 | hypervolume | The single number that ranks a whole front. Monotone in coverage. |

### Chapter 5 — Design Studio (5 steps)

| # | Anchor | Text |
|---|---|---|
| 5.1 | satellite designer | Parametric SVG of a satellite bus. Drag handles change the design. |
| 5.2 | solar array chain | Full design chain: I_AM0, eta_cell, packing, PSE, effective specific power, panel dimensions. Each stage feeds the next. |
| 5.3 | drone designer | Same idea for fixed-wing and multirotor. Three-view engineering drawings. |
| 5.4 | preset library | Anonymous presets SAT-A1..A5 and UAV-A1..A6. Starting points, not conclusions. |
| 5.5 | design evaluation | The feasibility verdict. Not a certification. |

### Chapter 6 — Status and About (3 steps)

| # | Anchor | Text |
|---|---|---|
| 6.1 | status view | Dependency health. Postgres, Redis, HTTP API. In the desktop app, Postgres and Redis are expected to be down. |
| 6.2 | about view | The Section-21 epistemic hierarchy, all seven categories. This is where the app explains its own epistemics. |
| 6.3 | epistemic badge | Every output carries one of these seven tags. Click any badge to see the category definition. |

### Chapter 7 — Export and done (2 steps)

| # | Anchor | Text |
|---|---|---|
| 7.1 | export button | The CLEAR-D dashboard exports a full JSON of the run. This is the artifact you take away. |
| 7.2 | wrap-up | You have seen every view. The app is an instrument: every number is tagged, every decision is traced, every claim is in SCIENTIFIC_CLAIMS.md. |

Total: 35 steps across 8 chapters.

## 4. Engine

One component: `frontend/src/features/Tour/`.

    TourProvider.tsx        context that owns the current tour state
    TourOverlay.tsx         the dimming + highlight + card
    TourCard.tsx            the card content (title, body, next/back/skip)
    tourDefinitions.ts      the step list — data, not logic
    useTourProgress.ts      localStorage persistence ("aerogrid.tour")

The overlay:

- dims the whole page
- punches a transparent hole over the anchored element (CSS clip-path or four shadow divs)
- positions the card near the anchor, above/below/left/right chosen to fit
- three buttons: Back, Next, Skip
- Escape closes the tour

Anchoring: each anchored element gets `data-tour-id="<id>"`. The overlay queries the DOM at step-change time and reads the element's bounding box. No refs are threaded through React.

The tour does not block input outside the highlighted area. The user can click the anchor and interact with the highlighted element. This is what makes it interactive rather than a slideshow.

## 5. Persistence

`localStorage["aerogrid.tour"]` holds:

    {
      "firstRunDone": true,
      "completedChapters": [0, 1, 2],
      "lastStepId": "2.4",
      "neverShow": false
    }

`neverShow: true` means the first-run offer never appears again. The
full course is still reachable from About.

## 6. Tests

Unit tests (`src/features/Tour/*.test.ts`):

- tourDefinitions: every step has a valid anchor id, no duplicates
- useTourProgress: persistence round-trips, `neverShow` gates the
  first-run offer
- TourOverlay: renders the current step, Next advances, Back
  retreats, Skip exits
- TourCard: title and body render, buttons call the right callbacks

Integration test (`src/App.test.tsx` addendum):

- First-run offer appears when the store is empty
- Completing the first-run tour sets `firstRunDone`
- Clicking "Take the tour" from About opens the full course

Anchor test (`src/features/Tour/anchors.test.ts`):

- For every `data-tour-id` in the definitions, render `<App />` and
  assert the element exists in the DOM. This is the key test: it
  catches a renamed component before the user hits a broken step.

## 7. Build plan

The work is 4 PRs, each independently reviewable and shippable:

1. PR A — engine + Chapter 0. TourProvider, TourOverlay, TourCard,
   useTourProgress, tourDefinitions with 3 welcome steps, first-run
   offer, tests. Ships a working 3-step intro.
2. PR B — Chapters 1-3. Digital Twin, CLEAR-D, XAI. 18 steps. Adds
   `data-tour-id` attributes to the existing panels.
3. PR C — Chapters 4-7. Trade Space, Design Studio, Status, About,
   wrap-up. 14 steps. Export button anchor.
4. PR D — polish. Keyboard navigation, responsive card positioning,
   a "replay this chapter" menu, About to "Take the tour" entry point
   if it does not ship in PR A.

Each PR passes the full CI gate (6 contexts) before merge.

## 8. What is not planned

- Video. The tour is text and DOM highlighting, not screen recording.
- Voice-over. No audio.
- Separate web page. The tour lives inside the app.
- Translation. English only.
- Analytics. No telemetry. The tour does not phone home.

## 9. Reviewer checklist

Before PR A merges, verify:

- [ ] The 35 steps in section 3 match the actual app views and controls
- [ ] The first-run offer is skippable and dismissable permanently
- [ ] The anchor test catches a renamed component
- [ ] Keyboard-only navigation works (Tab through the card)
- [ ] Screen readers announce the current step and the anchor
- [ ] The tour does not obscure the epistemic badges when showing a
      step that mentions them

---

**Author:** Kian Mansouri Jamshidi
**Date:** 2026-10-16
**Status:** design — awaiting review before PR A
