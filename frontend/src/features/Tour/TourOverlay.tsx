/**
 * TourOverlay — the dimming layer, the highlight, and the card.
 *
 * Positioning:
 *
 *   1. Measure the anchor element's bounding box.
 *   2. Measure the card's own bounding box after it renders.
 *   3. Choose a position from the step's preferred placement.
 *   4. Clamp that position into the viewport with a fixed padding.
 *
 * Without step 4 the card runs off the right edge when the anchor is
 * near it (globe, dashboard panels). Without step 2 there is nothing
 * to clamp against. Both are done on every step change and on every
 * resize or scroll.
 */

import { useEffect, useLayoutEffect, useRef, useState } from "react"
import { TourCard } from "./TourCard"
import { useTour } from "./useTour"
import type { TourPlacement } from "./tourDefinitions"

type Box = { top: number; left: number; width: number; height: number }

const PAD = 16
const GAP = 14

function useElementBox(
  anchorId: string | undefined,
  stepId: string | undefined,
): Box | null {
  const [box, setBox] = useState<Box | null>(null)

  useLayoutEffect(() => {
    if (!anchorId) return
    const el = document.querySelector<HTMLElement>(
      `[data-tour-id="${anchorId}"]`,
    )
    // If the anchor is missing, leave the previous box in state. The
    // anchor test guarantees every anchor exists, so this branch is a
    // bug path, not a steady-state one. Clearing here would call
    // setState synchronously inside the effect and cascade a render.
    if (!el) return

    // Scroll the target into view first. Without this the card can
    // appear while the anchor is still below the fold and the user
    // has to hunt for what the step is talking about.
    el.scrollIntoView({ block: "center", inline: "nearest", behavior: "auto" })

    function measure() {
      const rect = el!.getBoundingClientRect()
      setBox({
        top: rect.top,
        left: rect.left,
        width: rect.width,
        height: rect.height,
      })
    }

    // Measure immediately, then again after the browser settles
    // layout and again after any smooth-scroll animation completes.
    measure()
    const raf = requestAnimationFrame(measure)
    const t1 = window.setTimeout(measure, 80)
    const t2 = window.setTimeout(measure, 260)

    const ro = new ResizeObserver(measure)
    ro.observe(document.body)
    window.addEventListener("resize", measure)
    window.addEventListener("scroll", measure, true)
    return () => {
      cancelAnimationFrame(raf)
      window.clearTimeout(t1)
      window.clearTimeout(t2)
      ro.disconnect()
      window.removeEventListener("resize", measure)
      window.removeEventListener("scroll", measure, true)
    }
    // `stepId` in the deps ensures a re-measure happens even when two
    // consecutive steps share the same anchor.
  }, [anchorId, stepId])

  return anchorId ? box : null
}

function placeCard(
  anchor: Box,
  card: { width: number; height: number },
  preferred: TourPlacement | undefined,
): { top: number; left: number } {
  const vw = window.innerWidth
  const vh = window.innerHeight

  let top = 0
  let left = 0

  const anchorCenterX = anchor.left + anchor.width / 2
  const anchorCenterY = anchor.top + anchor.height / 2

  // Try the preferred placement first; fall back to centered.
  const placement = preferred ?? "center"

  switch (placement) {
    case "right":
      top = anchorCenterY - card.height / 2
      left = anchor.left + anchor.width + GAP
      break
    case "left":
      top = anchorCenterY - card.height / 2
      left = anchor.left - card.width - GAP
      break
    case "bottom":
      top = anchor.top + anchor.height + GAP
      left = anchorCenterX - card.width / 2
      break
    case "top":
      top = anchor.top - card.height - GAP
      left = anchorCenterX - card.width / 2
      break
    case "center":
    default:
      top = vh / 2 - card.height / 2
      left = vw / 2 - card.width / 2
      break
  }

  // If a directional placement ran off the viewport, fall back to
  // centering rather than clipping a card against the edge.
  const offRight = left + card.width > vw - PAD
  const offLeft = left < PAD
  const offBottom = top + card.height > vh - PAD
  const offTop = top < PAD
  if (
    placement !== "center" &&
    (offRight || offLeft || offBottom || offTop)
  ) {
    top = vh / 2 - card.height / 2
    left = vw / 2 - card.width / 2
  }

  // Final clamp: never let the card leave the viewport.
  left = Math.min(Math.max(left, PAD), vw - card.width - PAD)
  top = Math.min(Math.max(top, PAD), vh - card.height - PAD)

  return { top, left }
}

export function TourOverlay() {
  const { isOpen, activeStep, stepIndex, totalSteps, next, back, skip } =
    useTour()
  const anchorBox = useElementBox(activeStep?.anchor, activeStep?.id)
  const cardRef = useRef<HTMLDivElement>(null)
  const [position, setPosition] = useState<{ top: number; left: number } | null>(
    null,
  )

  useLayoutEffect(() => {
    // When the tour is closed the component returns null below, so
    // there is nothing to reset here. The stale `position` is only
    // read when isOpen is true.
    if (!isOpen || !activeStep) return
    const placement = activeStep.placement
    function compute() {
      const cardEl = cardRef.current
      if (!cardEl) return
      const cardRect = cardEl.getBoundingClientRect()
      const cardSize = { width: cardRect.width, height: cardRect.height }
      if (anchorBox) {
        setPosition(placeCard(anchorBox, cardSize, placement))
      } else {
        setPosition({
          top: window.innerHeight / 2 - cardSize.height / 2,
          left: window.innerWidth / 2 - cardSize.width / 2,
        })
      }
    }
    compute()
    window.addEventListener("resize", compute)
    window.addEventListener("scroll", compute, true)
    return () => {
      window.removeEventListener("resize", compute)
      window.removeEventListener("scroll", compute, true)
    }
  }, [isOpen, activeStep, anchorBox])

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

  // Hide the card until we have measured it once; otherwise it flashes
  // at 0,0 for a frame before the layout effect runs.
  const cardStyle: React.CSSProperties = position
    ? { top: position.top, left: position.left, position: "fixed" }
    : { top: 0, left: 0, position: "fixed", visibility: "hidden" }

  const highlight = anchorBox
    ? {
        top: anchorBox.top - 4,
        left: anchorBox.left - 4,
        width: anchorBox.width + 8,
        height: anchorBox.height + 8,
      }
    : null

  return (
    <div
      data-testid="tour-overlay"
      className="pointer-events-none fixed inset-0 z-[1000]"
    >
      {highlight ? (
        <div
          aria-hidden="true"
          className="absolute rounded-lg transition-all duration-200"
          style={{
            ...highlight,
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
        ref={cardRef}
        className="pointer-events-auto"
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
