import type { ReactElement } from "react"

export type CalloutProps = {
  x: number
  y: number
  labelX: number
  labelY: number
  label: string
  sublabel?: string
  arrow?: "left" | "right"
  fontSize: number
  strokeWidth: number
}

export function Callout({
  x, y, labelX, labelY, label, sublabel, arrow = "left", fontSize, strokeWidth,
}: CalloutProps): ReactElement {
  const isLeft = arrow === "left"
  const textAnchor = isLeft ? "end" : "start"
  const textX = isLeft ? labelX + 4 : labelX - 4
  // Draw a horizontal shoulder from the text, then a straight line to the anchor
  const shoulderX = isLeft ? labelX + fontSize * 1.5 : labelX - fontSize * 1.5
  const shoulderY = labelY - fontSize * 0.3

  return (
    <g>
      <polyline
        points={`${labelX},${shoulderY} ${shoulderX},${shoulderY} ${x},${y}`}
        fill="none"
        stroke="var(--ink-tertiary)"
        strokeWidth={strokeWidth * 0.6}
      />
      <circle cx={x} cy={y} r={fontSize * 0.25} fill="var(--ink-tertiary)" />
      <text x={textX} y={labelY} textAnchor={textAnchor} fontFamily="ui-monospace, monospace" fontSize={fontSize} fill="var(--ink-secondary)">
        {label}
      </text>
      {sublabel && (
        <text x={textX} y={labelY + fontSize * 1.1} textAnchor={textAnchor} fontFamily="ui-monospace, monospace" fontSize={fontSize * 0.8} fill="var(--ink-tertiary)">
          {sublabel}
        </text>
      )}
    </g>
  )
}
