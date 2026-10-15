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

/** Every step in the tour, in order. */
export const ALL_STEPS: TourStep[] = [...WELCOME_STEPS]
