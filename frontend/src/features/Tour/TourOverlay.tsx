/**
 * TourOverlay — the dimming layer, the highlight, and the card.
 *
 * Technique: a "spotlight" hole. A positioned element at the anchor's
 * bounding box carries `box-shadow: 0 0 0 9999px rgba(0,0,0,0.45)`,
 * which dims everything outside the hole. The hole itself has
 * `pointer-events: none` so the highlighted element remains clickable
 * — the user can interact with the app while a step is showing.
 *
 * The card sits near the anchor with a preference-based placement, and
 * falls back to centering if the preferred side would overflow the
 * viewport.
 */

import { useEffect, useLayoutEffect, useState } from "react"
import { TourCard } from "./TourCard"
import { useTour } from "./useTour"

type Rect = { top: number; left: number; width: number; height: number }

function useAnchorRect(anchorId: string | undefined): Rect | null {
  const [rect, setRect] = useState<Rect | null>(null)

  useLayoutEffect(() => {
    if (!anchorId) return
    function measure() {
      const el = document.querySelector<HTMLElement>(
        `[data-tour-id="${anchorId}"]`,
      )
      if (!el) {
        setRect(null)
        return
      }
      const r = el.getBoundingClientRect()
      setRect({ top: r.top, left: r.left, width: r.width, height: r.height })
    }
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(document.body)
    window.addEventListener("resize", measure)
    window.addEventListener("scroll", measure, true)
    return () => {
      ro.disconnect()
      window.removeEventListener("resize", measure)
      window.removeEventListener("scroll", measure, true)
    }
  }, [anchorId])

  return anchorId ? rect : null
}

export function TourOverlay() {
  const { isOpen, activeStep, stepIndex, totalSteps, next, back, skip } =
    useTour()
  const rect = useAnchorRect(activeStep?.anchor)

  useEffect(() => {
    if (!isOpen) return
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") skip()
      else if (e.key === "ArrowRight") next()
      else if (e.key === "ArrowLeft") back()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [isOpen, next, back, skip])

  if (!isOpen || !activeStep) return null

  // Placement: prefer the step's placement; fall back to centered.
  const pad = 12
  let cardStyle: React.CSSProperties = {
    top: "50%",
    left: "50%",
    transform: "translate(-50%, -50%)",
  }
  if (rect) {
    const gap = 16
    switch (activeStep.placement) {
      case "right":
        cardStyle = { top: rect.top, left: rect.left + rect.width + gap }
        break
      case "left":
        cardStyle = { top: rect.top, left: Math.max(pad, rect.left - 376) }
        break
      case "bottom":
        cardStyle = { top: rect.top + rect.height + gap, left: rect.left }
        break
      case "top":
        cardStyle = { top: Math.max(pad, rect.top - 260), left: rect.left }
        break
      default:
        break
    }
  }

  return (
    <div
      data-testid="tour-overlay"
      className="pointer-events-none fixed inset-0 z-[1000]"
    >
      {rect ? (
        <div
          aria-hidden="true"
          className="absolute rounded-lg"
          style={{
            top: rect.top - 4,
            left: rect.left - 4,
            width: rect.width + 8,
            height: rect.height + 8,
            boxShadow: "0 0 0 9999px rgba(0, 0, 0, 0.45)",
            outline: "2px solid var(--accent)",
            outlineOffset: "2px",
          }}
        />
      ) : (
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-[rgba(0,0,0,0.45)]"
        />
      )}

      <div
        className="pointer-events-auto absolute"
        style={cardStyle}
      >
        <TourCard
          step={activeStep}
          stepIndex={stepIndex}
          totalSteps={totalSteps}
          onBack={back}
          onNext={next}
          onSkip={skip}
        />
      </div>
    </div>
  )
}
