/**
 * TrajectoryChart — an inline SVG line plot of the two-node thermal
 * transient response.
 *
 * No charting library. The data is a fixed number of samples with two
 * series (PLC and TE temperature); a polyline is the simplest honest
 * rendering. If a chart library becomes necessary later this component
 * is a drop-in replacement site.
 *
 * Axes are linear. The x-axis is time in seconds, the y-axis is
 * temperature in Celsius. Both axes are labelled with their units.
 */

import type { TrajectorySample } from "./digitalTwinApi"

const W = 640
const H = 260

const PAD_LEFT = 56
const PAD_RIGHT = 12
const PAD_TOP = 12
const PAD_BOTTOM = 32

export type TrajectoryChartProps = {
  samples: TrajectorySample[]
  /** Optional title for the aria-label. */
  label?: string
}

export function TrajectoryChart({ samples, label }: TrajectoryChartProps) {
  if (samples.length < 2) {
    return (
      <p className="text-sm opacity-60">
        Fewer than two samples; nothing to plot.
      </p>
    )
  }

  const t_max = samples[samples.length - 1]!.time_s
  const kelvin = samples.flatMap((s) => [s.t_plc_k, s.t_te_k])
  const k_min = Math.min(...kelvin)
  const k_max = Math.max(...kelvin)
  const k_pad = Math.max(1, (k_max - k_min) * 0.05)
  const y_lo_c = k_min - k_pad - 273.15
  const y_hi_c = k_max + k_pad - 273.15

  const xScale = (t: number): number =>
    PAD_LEFT + ((W - PAD_LEFT - PAD_RIGHT) * (t / t_max))
  const yScale = (k: number): number => {
    const c = k - 273.15
    const frac = (y_hi_c - c) / (y_hi_c - y_lo_c)
    return PAD_TOP + frac * (H - PAD_TOP - PAD_BOTTOM)
  }

  const plcPath = samples
    .map((s) => `${xScale(s.time_s).toFixed(2)},${yScale(s.t_plc_k).toFixed(2)}`)
    .join(" ")
  const tePath = samples
    .map((s) => `${xScale(s.time_s).toFixed(2)},${yScale(s.t_te_k).toFixed(2)}`)
    .join(" ")

  // Gridlines at nice y-axis values.
  const yTicks: number[] = []
  const ySpan = y_hi_c - y_lo_c
  const yStep = ySpan > 40 ? 20 : ySpan > 20 ? 10 : ySpan > 10 ? 5 : 1
  const first = Math.ceil(y_lo_c / yStep) * yStep
  for (let v = first; v <= y_hi_c; v += yStep) yTicks.push(v)

  return (
    <svg
      role="img"
      aria-label={label ?? "Digital twin thermal transient response"}
      viewBox={`0 0 ${W} ${H}`}
      className="w-full"
      style={{ maxWidth: W }}
    >
      {/* y grid + labels */}
      {yTicks.map((v) => {
        const y = yScale(v + 273.15)
        return (
          <g key={v}>
            <line
              x1={PAD_LEFT}
              x2={W - PAD_RIGHT}
              y1={y}
              y2={y}
              stroke="currentColor"
              strokeOpacity={0.12}
            />
            <text
              x={PAD_LEFT - 6}
              y={y + 3}
              fontSize="10"
              textAnchor="end"
              fill="currentColor"
              opacity={0.65}
            >
              {v}
            </text>
          </g>
        )
      })}

      {/* axes */}
      <line
        x1={PAD_LEFT}
        x2={W - PAD_RIGHT}
        y1={H - PAD_BOTTOM}
        y2={H - PAD_BOTTOM}
        stroke="currentColor"
        strokeOpacity={0.4}
      />
      <line
        x1={PAD_LEFT}
        x2={PAD_LEFT}
        y1={PAD_TOP}
        y2={H - PAD_BOTTOM}
        stroke="currentColor"
        strokeOpacity={0.4}
      />

      {/* series */}
      <polyline
        points={plcPath}
        fill="none"
        stroke="#f59e0b"
        strokeWidth={2}
      />
      <polyline
        points={tePath}
        fill="none"
        stroke="#14b8a6"
        strokeWidth={2}
      />

      {/* x label */}
      <text
        x={(W + PAD_LEFT - PAD_RIGHT) / 2}
        y={H - 6}
        fontSize="10"
        textAnchor="middle"
        fill="currentColor"
        opacity={0.65}
      >
        time (s)
      </text>

      {/* y label */}
      <text
        x={14}
        y={H / 2}
        fontSize="10"
        textAnchor="middle"
        fill="currentColor"
        opacity={0.65}
        transform={`rotate(-90 14 ${H / 2})`}
      >
        temperature (C)
      </text>

      {/* legend */}
      <g transform={`translate(${W - 130} ${PAD_TOP + 12})`}>
        <rect x={0} y={-8} width={8} height={8} fill="#f59e0b" />
        <text x={12} y={0} fontSize="10" fill="currentColor" opacity={0.85}>
          PLC
        </text>
        <rect x={50} y={-8} width={8} height={8} fill="#14b8a6" />
        <text x={62} y={0} fontSize="10" fill="currentColor" opacity={0.85}>
          TE
        </text>
      </g>
    </svg>
  )
}
