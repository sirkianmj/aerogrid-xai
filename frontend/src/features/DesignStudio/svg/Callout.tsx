/**
 * Callout — a leader-line annotation for engineering drawings.
 *
 * A callout points at a specific feature with a leader line and labels
 * it. Two styles:
 *
 *   "leader"   a short straight segment from the anchor point to a
 *              label, with a small arrow at the anchor. Used for
 *              annotations inside a drawing.
 *
 *   "flag"     a horizontal leader from the anchor to a fixed
 *              left-aligned or right-aligned margin, with the label
 *              placed just beyond the leader. Used for stacked
 *              annotations along the edge of a drawing so the labels
 *              line up in a column.
 *
 * The arrow is drawn as a small filled triangle. The leader is a
 * hairline. The label is monospace, matching the frame style.
 */

import type { ReactElement } from "react"

export type CalloutProps = {
  /** Anchor point on the feature. */
  x: number
  y: number
  /** Where the label starts (the far end of the leader). */
  labelX: number
  labelY: number
  /** Label text. */
  label: string
  /** Optional second line under the label (smaller, muted). */
  sublabel?: string
  /** Direction the arrow points; default "left" means it points left to the anchor. */
  arrow?: "left" | "right" | "up" | "down"
  /** Font size in viewBox units. */
  fontSize: number
  /** Stroke width in viewBox units. */
  strokeWidth: number
}

export function Callout({
  x,
  y,
  labelX,
  labelY,
  label,
  sublabel,
  arrow = "left",
  fontSize,
  strokeWidth,
}: CalloutProps): ReactElement {
  // Elbow: the leader goes horizontally from the label, then a short
  // vertical segment to the anchor. This keeps long leader lines from
  // crossing other features.
  const midX = labelX + (arrow === "left" ? -fontSize * 0.9 : fontSize * 0.9)
  const elbowY = y
  const arrowSize = fontSize * 0.35

  // Arrow triangle pointing at the anchor.
  let arrowPts = ""
  switch (arrow) {
    case "left":
      arrowPts = `${x},${y} ${x + arrowSize},${y - arrowSize * 0.6} ${x + arrowSize},${y + arrowSize * 0.6}`
      break
    case "right":
      arrowPts = `${x},${y} ${x - arrowSize},${y - arrowSize * 0.6} ${x - arrowSize},${y + arrowSize * 0.6}`
      break
    case "up":
      arrowPts = `${x},${y} ${x - arrowSize * 0.6},${y + arrowSize} ${x + arrowSize * 0.6},${y + arrowSize}`
      break
    case "down":
      arrowPts = `${x},${y} ${x - arrowSize * 0.6},${y - arrowSize} ${x + arrowSize * 0.6},${y - arrowSize}`
      break
  }

  return (
    <g>
      {/* Leader: horizontal from label to elbow, vertical to anchor */}
      <polyline
        points={`${midX},${labelY + fontSize * 0.35} ${midX},${elbowY} ${x},${elbowY}`}
        fill="none"
        stroke="var(--ink-tertiary)"
        strokeWidth={strokeWidth * 0.6}
      />
      {/* Arrow */}
      <polygon points={arrowPts} fill="var(--ink-tertiary)" />

      {/* Label */}
      <text
        x={labelX}
        y={labelY}
        textAnchor={arrow === "left" ? "end" : "start"}
        fontFamily="ui-monospace, monospace"
        fontSize={fontSize}
        fill="var(--ink-secondary)"
      >
        {label}
      </text>
      {sublabel && (
        <text
          x={labelX}
          y={labelY + fontSize * 1.1}
          textAnchor={arrow === "left" ? "end" : "start"}
          fontFamily="ui-monospace, monospace"
          fontSize={fontSize * 0.8}
          fill="var(--ink-tertiary)"
        >
          {sublabel}
        </text>
      )}
    </g>
  )
}
