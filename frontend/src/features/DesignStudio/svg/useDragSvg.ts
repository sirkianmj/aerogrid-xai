/**
 * Pointer-drag hook for SVG elements. Translates screen-space pointer
 * deltas into the SVG's viewBox data-space, using the element's live
 * pixel size at pointerdown. That means the hook works regardless of
 * how the SVG is scaled by its container.
 *
 * Returned handlers are spread onto the draggable SVG element. The
 * element receives pointer capture so the drag continues even if the
 * cursor leaves its bounds.
 */

import { useRef, type RefObject } from "react"

export type DragHandlers = {
  onPointerDown: (e: React.PointerEvent) => void
  onPointerMove: (e: React.PointerEvent) => void
  onPointerUp: (e: React.PointerEvent) => void
  onPointerCancel: (e: React.PointerEvent) => void
}

export function useDragSvg(
  svgRef: RefObject<SVGSVGElement | null>,
  viewBox: { w: number; h: number },
  onMove: (dxData: number, dyData: number) => void,
): DragHandlers {
  const state = useRef<{ x: number; y: number; sx: number; sy: number } | null>(null)

  function release(e: React.PointerEvent) {
    try {
      ;(e.currentTarget as Element).releasePointerCapture(e.pointerId)
    } catch {
      // pointer may already be released
    }
    state.current = null
  }

  return {
    onPointerDown: (e) => {
      const rect = svgRef.current?.getBoundingClientRect()
      if (!rect) return
      state.current = {
        x: e.clientX,
        y: e.clientY,
        sx: viewBox.w / rect.width,
        sy: viewBox.h / rect.height,
      }
      ;(e.currentTarget as Element).setPointerCapture(e.pointerId)
      e.preventDefault()
    },
    onPointerMove: (e) => {
      const s = state.current
      if (!s) return
      const dx = (e.clientX - s.x) * s.sx
      const dy = (e.clientY - s.y) * s.sy
      state.current = { x: e.clientX, y: e.clientY, sx: s.sx, sy: s.sy }
      onMove(dx, dy)
    },
    onPointerUp: release,
    onPointerCancel: release,
  }
}
