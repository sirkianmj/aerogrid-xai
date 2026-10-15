/**
 * Persistence for the tutorial tour.
 *
 * State lives in localStorage under "aerogrid.tour". The hook returns
 * the current state plus setters that persist and notify subscribers
 * in the same tab (localStorage does not fire its own "storage"
 * event to the tab that wrote it).
 *
 * Shape:
 *
 *   {
 *     firstRunDone: boolean,     // first-run offer has been shown
 *     neverShow: boolean,        // user dismissed permanently
 *     completedChapters: number[],
 *     lastStepId: string | null,
 *   }
 */

import { useCallback, useEffect, useState } from "react"

export const TOUR_KEY = "aerogrid.tour"

export type TourProgress = {
  firstRunDone: boolean
  neverShow: boolean
  completedChapters: number[]
  lastStepId: string | null
}

const EMPTY: TourProgress = {
  firstRunDone: false,
  neverShow: false,
  completedChapters: [],
  lastStepId: null,
}

function read(): TourProgress {
  if (typeof window === "undefined") return EMPTY
  try {
    const raw = window.localStorage.getItem(TOUR_KEY)
    if (!raw) return EMPTY
    const parsed = JSON.parse(raw) as Partial<TourProgress>
    return {
      firstRunDone: Boolean(parsed.firstRunDone),
      neverShow: Boolean(parsed.neverShow),
      completedChapters: Array.isArray(parsed.completedChapters)
        ? parsed.completedChapters.filter((n) => typeof n === "number")
        : [],
      lastStepId: typeof parsed.lastStepId === "string" ? parsed.lastStepId : null,
    }
  } catch {
    return EMPTY
  }
}

function write(state: TourProgress): void {
  if (typeof window === "undefined") return
  window.localStorage.setItem(TOUR_KEY, JSON.stringify(state))
  window.dispatchEvent(new Event("aerogrid:tour-change"))
}

export function useTourProgress(): {
  progress: TourProgress
  markFirstRunDone: () => void
  setNeverShow: () => void
  markChapterComplete: (chapterId: number) => void
  setLastStep: (stepId: string) => void
  reset: () => void
} {
  const [progress, setProgress] = useState<TourProgress>(() => read())

  useEffect(() => {
    const onChange = () => setProgress(read())
    window.addEventListener("aerogrid:tour-change", onChange)
    return () => window.removeEventListener("aerogrid:tour-change", onChange)
  }, [])

  const markFirstRunDone = useCallback(() => {
    const next = { ...read(), firstRunDone: true }
    write(next)
  }, [])

  const setNeverShow = useCallback(() => {
    const next = { ...read(), neverShow: true, firstRunDone: true }
    write(next)
  }, [])

  const markChapterComplete = useCallback((chapterId: number) => {
    const cur = read()
    const completed = cur.completedChapters.includes(chapterId)
      ? cur.completedChapters
      : [...cur.completedChapters, chapterId]
    write({ ...cur, completedChapters: completed })
  }, [])

  const setLastStep = useCallback((stepId: string) => {
    const cur = read()
    write({ ...cur, lastStepId: stepId })
  }, [])

  const reset = useCallback(() => {
    write(EMPTY)
  }, [])

  return {
    progress,
    markFirstRunDone,
    setNeverShow,
    markChapterComplete,
    setLastStep,
    reset,
  }
}
