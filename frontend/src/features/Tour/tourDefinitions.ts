/**
 * Tour step definitions.
 *
 * Pure data. The overlay component reads these; nothing here touches
 * the DOM or React. Adding a step is a data change, not a code change.
 *
 * Anchor ids refer to `data-tour-id` attributes placed on elements
 * elsewhere in the app. The `anchors.test.ts` file asserts every
 * anchor in this list resolves to a real element when <App /> renders.
 *
 * PR A ships only Chapter 0 (Welcome). Later PRs append their own
 * chapters to `ALL_STEPS`.
 */

export type TourPlacement = "top" | "bottom" | "left" | "right" | "center"

export type TourStep = {
  /** Unique within the whole tour, e.g. "0.1" for chapter 0 step 1. */
  id: string
  chapterId: number
  chapterTitle: string
  title: string
  body: string
  /** Value of the target element's data-tour-id attribute. */
  anchor: string
  /** Preferred card placement; the overlay may override if it does not fit. */
  placement?: TourPlacement
}

export const WELCOME_STEPS: TourStep[] = [
  {
    id: "0.1",
    chapterId: 0,
    chapterTitle: "Welcome",
    title: "AeroGrid-XAI",
    body: "A software-only research instrument for architecture discovery in space-to-air wireless power transfer. Not hardware.",
    anchor: "app-root",
    placement: "center",
  },
  {
    id: "0.2",
    chapterId: 0,
    chapterTitle: "Welcome",
    title: "The sidebar",
    body: "The sidebar carries identity, navigation, and the theme toggle. Each nav item is one workspace view.",
    anchor: "app-sidebar",
    placement: "right",
  },
  {
    id: "0.3",
    chapterId: 0,
    chapterTitle: "Welcome",
    title: "Invariants",
    body: "The green badges above the theme toggle: the Tier-2 firewall invariant and the license. Both are enforced by CI on every pull request.",
    anchor: "app-invariants",
    placement: "top",
  },
]

export const CHAPTER_1_STEPS: TourStep[] = [
  {
    id: "1.1",
    chapterId: 1,
    chapterTitle: "Digital Twin & Orbit",
    title: "The globe",
    body: "A real SGP4 propagation of a packaged TLE, rendered live. Not an animation. Click anywhere on the surface to place a ground station.",
    anchor: "globe-canvas",
    placement: "right",
  },
  {
    id: "1.2",
    chapterId: 1,
    chapterTitle: "Digital Twin & Orbit",
    title: "Satellite picker",
    body: "Choose which TLE to propagate. Three are packaged: ISS, Vanguard R3 (1958), and GEO-TEST (synthetic).",
    anchor: "globe-controls",
    placement: "bottom",
  },
  {
    id: "1.3",
    chapterId: 1,
    chapterTitle: "Digital Twin & Orbit",
    title: "Time control",
    body: "Scrub through the first visible pass. The default opens at peak elevation, not at the pass start, because the beam grazes the atmosphere at low elevation.",
    anchor: "globe-controls",
    placement: "bottom",
  },
  {
    id: "1.4",
    chapterId: 1,
    chapterTitle: "Digital Twin & Orbit",
    title: "Mission configuration",
    body: "Change the mission parameters here. Every change recomputes the mission state on the server. This panel drives every view that reads mission state.",
    anchor: "mission-config",
    placement: "bottom",
  },
  {
    id: "1.5",
    chapterId: 1,
    chapterTitle: "Digital Twin & Orbit",
    title: "The pipeline view",
    body: "The vertical stage view. Each stage is one element of the specification's Section 4.",
    anchor: "mission-control",
    placement: "bottom",
  },
  {
    id: "1.6",
    chapterId: 1,
    chapterTitle: "Digital Twin & Orbit",
    title: "Telemetry",
    body: "Live WebSocket stream. Each snapshot carries the satellite's orbital state and the current Digital Twin thermal state.",
    anchor: "telemetry",
    placement: "top",
  },
]

export const REMAINING_STEPS: TourStep[] = [
  {
    id: "2.1",
    chapterId: 2,
    chapterTitle: "CLEAR-D Synthesis",
    title: "What CLEAR-D is",
    body: "A closed loop: generate, verify, attribute, mutate, select. The unsat-core attribution is the paper's novel claim.",
    anchor: "cleard-dashboard",
    placement: "bottom",
  },
  {
    id: "2.2",
    chapterId: 2,
    chapterTitle: "CLEAR-D Synthesis",
    title: "The seed",
    body: "Same seed gives the same output. Determinism is tested.",
    anchor: "cleard-dashboard",
    placement: "bottom",
  },
  {
    id: "2.3",
    chapterId: 2,
    chapterTitle: "CLEAR-D Synthesis",
    title: "Run it",
    body: "Hit the run button. Population 6, 3 generations, executed on the backend.",
    anchor: "cleard-run",
    placement: "bottom",
  },
  {
    id: "2.4",
    chapterId: 2,
    chapterTitle: "CLEAR-D Synthesis",
    title: "The attribution panel",
    body: "Unsat core to grammar feature to conflict-prone table. This is what makes CLEAR-D different from random search.",
    anchor: "cleard-dashboard",
    placement: "bottom",
  },
  {
    id: "2.5",
    chapterId: 2,
    chapterTitle: "CLEAR-D Synthesis",
    title: "Generation stats",
    body: "Feasible versus infeasible count per generation. A working loop drives infeasible towards feasible.",
    anchor: "cleard-dashboard",
    placement: "bottom",
  },
  {
    id: "2.6",
    chapterId: 2,
    chapterTitle: "CLEAR-D Synthesis",
    title: "Pareto front as cards",
    body: "Each card is one architecture. The front is the set of non-dominated designs.",
    anchor: "architectures",
    placement: "bottom",
  },
  {
    id: "2.7",
    chapterId: 2,
    chapterTitle: "CLEAR-D Synthesis",
    title: "What moves the needle",
    body: "Elasticity of delivered power to each mission parameter, ranked.",
    anchor: "sensitivity",
    placement: "bottom",
  },
  {
    id: "3.1",
    chapterId: 3,
    chapterTitle: "Two-Tier XAI Core",
    title: "The decision trace",
    body: "Every charge decision is the sum of rule weights. No black box.",
    anchor: "xai-trace",
    placement: "bottom",
  },
  {
    id: "3.2",
    chapterId: 3,
    chapterTitle: "Two-Tier XAI Core",
    title: "Candidates",
    body: "Two UAVs. Each row is one candidate's features.",
    anchor: "xai-trace",
    placement: "bottom",
  },
  {
    id: "3.3",
    chapterId: 3,
    chapterTitle: "Two-Tier XAI Core",
    title: "Trace steps",
    body: "Fidelity means score equals the sum of step weights. This is tested.",
    anchor: "xai-trace",
    placement: "bottom",
  },
  {
    id: "3.4",
    chapterId: 3,
    chapterTitle: "Two-Tier XAI Core",
    title: "Counterfactual",
    body: "Turn a rule off and see whether the decision flips.",
    anchor: "xai-trace",
    placement: "bottom",
  },
  {
    id: "3.5",
    chapterId: 3,
    chapterTitle: "Two-Tier XAI Core",
    title: "The Tier-2 firewall",
    body: "Tier-2 estimates never reach the Tier-1 action interface. A static analyzer enforces this on every commit.",
    anchor: "xai-trace",
    placement: "bottom",
  },
  {
    id: "4.1",
    chapterId: 4,
    chapterTitle: "Trade Space",
    title: "Pareto scatter",
    body: "Points are architectures. Axes are objectives. The front is the non-dominated set.",
    anchor: "tradespace",
    placement: "bottom",
  },
  {
    id: "4.2",
    chapterId: 4,
    chapterTitle: "Trade Space",
    title: "Axis picker",
    body: "Choose which objectives to plot. The front is invariant; the projection is not.",
    anchor: "tradespace",
    placement: "bottom",
  },
  {
    id: "4.3",
    chapterId: 4,
    chapterTitle: "Trade Space",
    title: "Parallel coordinates",
    body: "Six dimensions at once. Drag a slider to filter.",
    anchor: "tradespace",
    placement: "bottom",
  },
  {
    id: "4.4",
    chapterId: 4,
    chapterTitle: "Trade Space",
    title: "Hypervolume",
    body: "One number that ranks a whole front. Monotone in coverage.",
    anchor: "tradespace",
    placement: "bottom",
  },
  {
    id: "5.1",
    chapterId: 5,
    chapterTitle: "Design Studio",
    title: "Satellite designer",
    body: "Parametric SVG of a satellite bus. Drag handles change the geometry.",
    anchor: "design-studio",
    placement: "bottom",
  },
  {
    id: "5.2",
    chapterId: 5,
    chapterTitle: "Design Studio",
    title: "The solar array chain",
    body: "I_AM0, eta_cell, packing, PSE, effective specific power, panel dimensions. Every stage feeds the next.",
    anchor: "design-studio",
    placement: "bottom",
  },
  {
    id: "5.3",
    chapterId: 5,
    chapterTitle: "Design Studio",
    title: "Drone designer",
    body: "Fixed-wing three-view with a NACA inset, multirotor three-view with a motor cross-section.",
    anchor: "design-studio",
    placement: "bottom",
  },
  {
    id: "5.4",
    chapterId: 5,
    chapterTitle: "Design Studio",
    title: "Preset library",
    body: "Anonymous presets. Starting points, not conclusions.",
    anchor: "design-studio",
    placement: "bottom",
  },
  {
    id: "5.5",
    chapterId: 5,
    chapterTitle: "Design Studio",
    title: "Evaluation",
    body: "A feasibility verdict. Not a certification.",
    anchor: "design-studio",
    placement: "bottom",
  },
  {
    id: "6.1",
    chapterId: 6,
    chapterTitle: "Status and About",
    title: "Status",
    body: "Dependency health: Postgres, Redis, HTTP. In the desktop app, Postgres and Redis are expected to be down.",
    anchor: "status-view",
    placement: "bottom",
  },
  {
    id: "6.2",
    chapterId: 6,
    chapterTitle: "Status and About",
    title: "The epistemic hierarchy",
    body: "Seven categories, from physical measurement to hypothetical. Every output carries one.",
    anchor: "app-root",
    placement: "center",
  },
  {
    id: "6.3",
    chapterId: 6,
    chapterTitle: "Status and About",
    title: "About",
    body: "Section 21 in one page.",
    anchor: "app-root",
    placement: "center",
  },
  {
    id: "7.1",
    chapterId: 7,
    chapterTitle: "Export and done",
    title: "Export",
    body: "Download the whole CLEAR-D run as JSON. That is the artifact you keep.",
    anchor: "cleard-run",
    placement: "bottom",
  },
  {
    id: "7.2",
    chapterId: 7,
    chapterTitle: "Export and done",
    title: "You have seen it all",
    body: "Every number is tagged. Every decision is traced. Every claim is in SCIENTIFIC_CLAIMS.md.",
    anchor: "app-root",
    placement: "center",
  },
]

export const ALL_STEPS: TourStep[] = [
  ...WELCOME_STEPS,
  ...CHAPTER_1_STEPS,
  ...REMAINING_STEPS,
]
