/**
 * The useTour hook. Split out of TourProvider.tsx so the provider file
 * exports only a component (React Fast Refresh requirement).
 */

import { useContext } from "react"
import { TourContext } from "./TourContext"
import type { TourContextValue } from "./tourTypes"

export function useTour(): TourContextValue {
  const ctx = useContext(TourContext)
  if (!ctx) throw new Error("useTour must be used within <TourProvider>")
  return ctx
}
