/**
 * ParallelCoordinates — an inline SVG parallel-coordinates plot of the
 * Pareto front.
 *
 * One vertical axis per objective. Each Pareto point is a polyline
 * crossing all axes; the y position on axis i is the objective value
 * normalized to the [min, max] range observed across the front. For
 * objectives that are minimized (the "negative" ones, per the backend's
 * negative_objectives list), the normalization inverts so that
 * "higher on screen" always means "better".
 *
 * No charting library. The plot is simple enough that an inline SVG is
 * more honest than a 200 kB dependency, and it keeps the whole thing in
 * the same render path as the data that produced it. If a charting
 * library becomes necessary later, this is a drop-in replacement site.
 */

import type { ParetoPoint } from "./tradeSpaceApi"

const W = 720
const H = 320

const PAD_LEFT = 56
const PAD_RIGHT = 56
const PAD_TOP = 24
const PAD_BOTTOM = 40

export type ParallelCoordinatesProps = {
  points: ParetoPoint[]
  /** Objective labels in order, e.g. ["C", "R", "E", "N", "T", "U"]. */
  labels: string[]
  /** Indices of objectives that are minimized. All others are maximized. */
  negativeObjectives: number[]
  /** Optional aria-label for the SVG. */
  ariaLabel?: string
}

export function ParallelCoordinates({
  points,
  labels,
  negativeObjectives,
  ariaLabel,
}: ParallelCoordinatesProps) {
  if (points.length === 0 || labels.length === 0) {
    return <p className="text-sm opacity-60">No Pareto points to plot.</p>
  }

  const nAxes = labels.length
  const nPoints = points.length

  // Ensure every point has the expected arity.
  for (const p of points) {
    if (p.objectives.length !== nAxes) {
      return (
        <p className="text-sm" style={{ color: "var(--color-accent-amber)" }}>
          Pareto point has {p.objectives.length} objectives; expected {nAxes}.
        </p>
      )
    }
  }

  // Per-axis min and max.
  const mins: number[] = new Array(nAxes).fill(Number.POSITIVE_INFINITY)
  const maxs: number[] = new Array(nAxes).fill(Number.NEGATIVE_INFINITY)
  for (const p of points) {
    for (let i = 0; i < nAxes; i++) {
      const v = p.objectives[i]!
      if (v < mins[i]!) mins[i] = v
      if (v > maxs[i]!) maxs[i] = v
    }
  }

  const negativeSet = new Set(negativeObjectives)

  const xAt = (i: number): number => {
    if (nAxes === 1) return (W + PAD_LEFT - PAD_RIGHT) / 2
    return PAD_LEFT + ((W - PAD_LEFT - PAD_RIGHT) * i) / (nAxes - 1)
  }

  // Normalize a value in [min, max] to [0, 1] where 1 means "best".
  // For maximized objectives, best is max, so norm = (v - min) / span.
  // For minimized objectives, best is min, so norm = 1 - (v - min) / span.
  const normAt = (i: number, v: number): number => {
    const lo = mins[i]!
    const hi = maxs[i]!
    const span = hi - lo
    const raw = span > 0 ? (v - lo) / span : 0.5
    return negativeSet.has(i) ? 1 - raw : raw
  }

  const yAt = (i: number, v: number): number => {
    const n = normAt(i, v)
    return PAD_TOP + (1 - n) * (H - PAD_TOP - PAD_BOTTOM)
  }

  return (
    <svg
      role="img"
      aria-label={ariaLabel ?? "Pareto front parallel coordinates"}
      viewBox={`0 0 ${W} ${H}`}
      className="w-full"
      style={{ maxWidth: W }}
    >
      {/* Vertical axes */}
      {labels.map((label, i) => {
        const x = xAt(i)
        return (
          <g key={label}>
            <line
              x1={x}
              x2={x}
              y1={PAD_TOP}
              y2={H - PAD_BOTTOM}
              stroke="currentColor"
              strokeOpacity={0.3}
            />
            <text
              x={x}
              y={H - PAD_BOTTOM + 16}
              fontSize="11"
              textAnchor="middle"
              fill="currentColor"
              opacity={0.85}
            >
              {label}
            </text>
            <text
              x={x}
              y={H - PAD_BOTTOM + 30}
              fontSize="9"
              textAnchor="middle"
              fill="currentColor"
              opacity={0.5}
            >
              {negativeSet.has(i) ? "min" : "max"}
            </text>
          </g>
        )
      })}

      {/* Pareto point polylines. A single color for the front; the
          per-line opacity increases slightly for lower-index points so
          overlaps are legible when the front has many members. */}
      {points.map((p, idx) => {
        const pointsStr = labels
          .map((_, i) => `${xAt(i).toFixed(2)},${yAt(i, p.objectives[i]!).toFixed(2)}`)
          .join(" ")
        const opacity = nPoints <= 1 ? 0.9 : 0.35 + 0.5 * (1 - idx / nPoints)
        return (
          <polyline
            key={`pareto-${idx}`}
            points={pointsStr}
            fill="none"
            stroke="#14b8a6"
            strokeOpacity={opacity}
            strokeWidth={1.5}
          />
        )
      })}

      {/* Legend */}
      <text
        x={PAD_LEFT}
        y={PAD_TOP - 8}
        fontSize="10"
        fill="currentColor"
        opacity={0.65}
      >
        {nPoints} Pareto point{nPoints === 1 ? "" : "s"} (higher = better on every axis)
      </text>
    </svg>
  )
}
