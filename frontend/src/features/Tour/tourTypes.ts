/**
 * Shared types for the tour feature. Split out so both the context
 * file and the provider file can import them without a cycle.
 */

import type { TourStep } from "./tourDefinitions"

export type TourMode = "first-run" | "full"

export type TourProgressPublic = {
  firstRunDone: boolean
  neverShow: boolean
  completedChapters: number[]
  lastStepId: string | null
}

export type TourContextValue = {
  activeStep: TourStep | null
  stepIndex: number
  totalSteps: number
  mode: TourMode | null
  isOpen: boolean
  start: (mode: TourMode, fromStepId?: string) => void
  next: () => void
  back: () => void
  skip: () => void
  progress: TourProgressPublic
  setNeverShow: () => void
  reset: () => void
  onRequestView: ((view: string) => void) | null
}
