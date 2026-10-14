/**
 * ScaleBar — a metric scale reference drawn inside an SVG. Caller
 * supplies the position in data units, the length in data units, and
 * the label text (a human-readable metric figure that matches the
 * length). The bar is drawn with end ticks and a centred label.
 */

export type ScaleBarProps = {
  x: number
  y: number
  widthData: number
  label: string
  fontSize?: number
}

export function ScaleBar({ x, y, widthData, label, fontSize = 6 }: ScaleBarProps) {
  const tick = fontSize * 0.5
  return (
    <g>
      <line
        x1={x}
        y1={y}
        x2={x + widthData}
        y2={y}
        stroke="var(--ink-tertiary)"
        strokeWidth={0.5}
      />
      <line
        x1={x}
        y1={y - tick}
        x2={x}
        y2={y + tick}
        stroke="var(--ink-tertiary)"
        strokeWidth={0.5}
      />
      <line
        x1={x + widthData}
        y1={y - tick}
        x2={x + widthData}
        y2={y + tick}
        stroke="var(--ink-tertiary)"
        strokeWidth={0.5}
      />
      <text
        x={x + widthData / 2}
        y={y - tick - 2}
        textAnchor="middle"
        fontFamily="ui-monospace, monospace"
        fontSize={fontSize}
        fill="var(--ink-tertiary)"
      >
        {label}
      </text>
    </g>
  )
}
