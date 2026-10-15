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

/** Every step in the tour, in order. */
export const ALL_STEPS: TourStep[] = [...WELCOME_STEPS, ...CHAPTER_1_STEPS]
