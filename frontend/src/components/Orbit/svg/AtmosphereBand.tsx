/**
 * AtmosphereBand — the atmospheric attenuation region in a side-view
 * schematic. A gradient fill and two dashed boundary lines. The
 * optical density of the band is proportional to the current
 * atmospheric optical depth.
 */

export type AtmosphereBandProps = {
  x: number
  y: number
  width: number
  height: number
  /** 0..1 optical depth driving the gradient opacity. */
  opticalDepth: number
}

export function AtmosphereBand({ x, y, width, height, opticalDepth }: AtmosphereBandProps) {
  const opacity = Math.min(0.14, Math.max(0.02, opticalDepth * 0.18))
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} fill="var(--ink-primary)" opacity={opacity} />
      <line
        x1={x}
        y1={y}
        x2={x + width}
        y2={y}
        stroke="var(--ink-tertiary)"
        strokeWidth={0.5}
        strokeDasharray="4 3"
      />
      <line
        x1={x}
        y1={y + height}
        x2={x + width}
        y2={y + height}
        stroke="var(--ink-tertiary)"
        strokeWidth={0.5}
        strokeDasharray="4 3"
      />
    </g>
  )
}
