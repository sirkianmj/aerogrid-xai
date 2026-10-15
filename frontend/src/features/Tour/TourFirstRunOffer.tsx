/**
 * TourFirstRunOffer — a modal that offers the tour on first launch.
 *
 * Shows once, when localStorage["aerogrid.tour"] has no record of
 * either a completed first-run tour or a "never show" dismissal.
 * After the user chooses, the offer does not appear again.
 *
 * The full course is always reachable from About, whether or not the
 * offer was dismissed.
 */

import { useState } from "react"
import { useTour } from "./useTour"

export function TourFirstRunOffer() {
  const { progress, start, setNeverShow } = useTour()
  const [dismissed, setDismissed] = useState(false)

  const shouldShow =
    !dismissed && !progress.firstRunDone && !progress.neverShow
  if (!shouldShow) return null

  function takeTour() {
    setDismissed(true)
    start("first-run")
  }

  function notNow() {
    setDismissed(true)
    setNeverShow()
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Welcome"
      className="fixed inset-0 z-[900] flex items-center justify-center bg-[rgba(0,0,0,0.35)]"
      data-testid="tour-first-run-offer"
    >
      <div className="flex w-[420px] flex-col gap-4 rounded-xl border border-[var(--border-hairline)] bg-[var(--bg-surface)] p-6 shadow-[var(--shadow-lg)]">
        <h2 className="text-title-3">Welcome to AeroGrid-XAI</h2>
        <p className="text-footnote text-[var(--ink-secondary)]">
          A software-only research instrument for architecture discovery
          in space-to-air wireless power transfer. Would you like a short
          tour of the workspace?
        </p>
        <div className="mt-2 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={notNow}
            className="apple-btn apple-btn-secondary"
          >
            Not now
          </button>
          <button
            type="button"
            onClick={takeTour}
            className="apple-btn apple-btn-primary"
          >
            Take the tour
          </button>
        </div>
      </div>
    </div>
  )
}
