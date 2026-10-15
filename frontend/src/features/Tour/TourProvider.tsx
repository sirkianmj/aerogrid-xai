/**
 * TourProvider — context that owns the currently-open tour.
 *
 * The provider tracks which step is showing (or none). It does not
 * render anything itself; TourOverlay reads the context and renders
 * the dim layer + card. This split keeps the App tree free of any
 * DOM-altering code except the overlay.
 */

import { useCallback, useMemo, useState, type ReactNode } from "react"
import { ALL_STEPS } from "./tourDefinitions"
import { TourContext } from "./TourContext"
import type { TourContextValue, TourMode } from "./tourTypes"
import { useTourProgress } from "./useTourProgress"

export function TourProvider({ children }: { children: ReactNode }) {
  const progressApi = useTourProgress()
  const [mode, setMode] = useState<TourMode | null>(null)
  const [stepIndex, setStepIndex] = useState(0)

  const start = useCallback(
    (m: TourMode, fromStepId?: string) => {
      setMode(m)
      if (fromStepId) {
        const idx = ALL_STEPS.findIndex((s) => s.id === fromStepId)
        setStepIndex(idx >= 0 ? idx : 0)
      } else {
        setStepIndex(0)
      }
    },
    [],
  )

  const next = useCallback(() => {
    setStepIndex((i) => {
      const last = ALL_STEPS.length - 1
      if (i >= last) {
        // Tour finished.
        const finishedChapter = ALL_STEPS[last].chapterId
        progressApi.markChapterComplete(finishedChapter)
        progressApi.markFirstRunDone()
        setMode(null)
        return 0
      }
      const nextIdx = i + 1
      if (ALL_STEPS[nextIdx].chapterId !== ALL_STEPS[i].chapterId) {
        progressApi.markChapterComplete(ALL_STEPS[i].chapterId)
      }
      return nextIdx
    })
  }, [progressApi])

  const back = useCallback(() => {
    setStepIndex((i) => Math.max(0, i - 1))
  }, [])

  const skip = useCallback(() => {
    setMode(null)
    progressApi.markFirstRunDone()
  }, [progressApi])

  const value = useMemo<TourContextValue>(
    () => ({
      activeStep: mode === null ? null : ALL_STEPS[stepIndex] ?? null,
      stepIndex,
      totalSteps: ALL_STEPS.length,
      mode,
      isOpen: mode !== null,
      start,
      next,
      back,
      skip,
      progress: progressApi.progress,
      setNeverShow: progressApi.setNeverShow,
      reset: progressApi.reset,
    }),
    [mode, stepIndex, start, next, back, skip, progressApi],
  )

  return <TourContext.Provider value={value}>{children}</TourContext.Provider>
}
