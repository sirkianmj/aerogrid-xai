/**
 * Callout — a leader-line annotation for engineering drawings.
 *
 * Uses a straight diagonal leader line from the label to the anchor
 * point, terminating in a small dot. This is standard aerospace
 * convention and prevents leader lines from crossing the entire
 * drawing.
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
  /** Direction the arrow points; determines text alignment. */
  arrow?: "left" | "right"
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
  // If arrow is left, the label is on the left, so text is right-aligned
  const isLeft = arrow === "left"
  const textAnchor = isLeft ? "end" : "start"
  // The leader starts just outside the text and goes to the anchor.
  const startX = labelX + (isLeft ? fontSize * 0.5 : -fontSize * 0.5)
  const startY = labelY - fontSize * 0.3

  return (
    <g>
      {/* Leader: straight diagonal line */}
      <line
        x1={startX}
        y1={startY}
        x2={x}
        y2={y}
        stroke="var(--ink-tertiary)"
        strokeWidth={strokeWidth * 0.6}
      />
      {/* Anchor dot */}
      <circle cx={x} cy={y} r={fontSize * 0.25} fill="var(--ink-tertiary)" />

      {/* Label */}
      <text
        x={labelX}
        y={labelY}
        textAnchor={textAnchor}
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
          textAnchor={textAnchor}
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
