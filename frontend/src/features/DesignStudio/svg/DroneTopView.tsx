/**
 * DroneTopView — top-down, scale-correct drawing of one drone.
 *
 * Two airframe classes:
 *
 *   fixed_wing   fuselage + wing + tail. Fuselage length and tail
 *                dimensions are documented ratios of the wingspan
 *                (fuselage 0.6 span, tail 0.35 span, tail chord
 *                0.06 span).
 *
 *   multirotor   four arms in X, rotor discs at the ends. Arm length
 *                is half the span (rotor-to-rotor), rotor diameter
 *                0.35 span.
 *
 * Wing chord for the fixed-wing is 0.15 span, documented as a rough
 * aspect ratio for a small UAV. The receiver aperture is drawn as a
 * circle whose radius is sqrt(A / pi), to scale with the airframe.
 *
 * Two drag handles:
 *
 *   wingtip / arm end   horizontal drag changes wingspan.
 *   aperture edge       horizontal drag changes receiver area.
 */

import { useRef } from "react"
import { useDragSvg } from "./useDragSvg"
import { ScaleBar } from "./ScaleBar"

export type DroneTopViewProps = {
  wingspan_m: number
  receiver_aperture_m2: number
  airframe: "fixed_wing" | "multirotor"
  onChange: (patch: { wingspan_m?: number; receiver_aperture_m2?: number }) => void
  /** Highlight this drawing (used by the fleet overview). */
  highlighted?: boolean
}

export function DroneTopView({
  wingspan_m,
  receiver_aperture_m2,
  airframe,
  onChange,
  highlighted = false,
}: DroneTopViewProps) {
  const svgRef = useRef<SVGSVGElement | null>(null)

  const apertureRadius = Math.sqrt(receiver_aperture_m2 / Math.PI)

  // Fixed aspect: 2:1 (width : height). The drawing occupies 80% of
  // the viewBox width; the remaining space holds the scale bar and
  // dimensions. All units metres.
  const drawWidth = Math.max(wingspan_m, apertureRadius * 2) / 0.8
  const drawHeight = drawWidth / 2
  const vbX = -drawWidth / 2
  const vbY = -drawHeight / 2

  const stroke = highlighted ? "var(--ink-primary)" : "var(--ink-secondary)"
  const strokeW = drawWidth * 0.004

  // Chord (fixed-wing) and rotor diameter, documented ratios.
  const chord = airframe === "fixed_wing" ? 0.15 * wingspan_m : 0
  const fuselageLength = airframe === "fixed_wing" ? 0.6 * wingspan_m : 0
  const tailSpan = airframe === "fixed_wing" ? 0.35 * wingspan_m : 0
  const tailChord = airframe === "fixed_wing" ? 0.06 * wingspan_m : 0

  // Drag: change wingspan keeping it proportional. Dragging the right
  // wingtip outward increases span.
  const halfSpan = wingspan_m / 2
  const wingtipDrag = useDragSvg(svgRef, { w: drawWidth, h: drawHeight }, (dx) => {
    const newSpan = Math.max(0.05, wingspan_m + 2 * dx)
    onChange({ wingspan_m: newSpan })
  })

  const apertureDrag = useDragSvg(svgRef, { w: drawWidth, h: drawHeight }, (dx) => {
    const newR = Math.max(0.01, apertureRadius + dx)
    onChange({ receiver_aperture_m2: Math.PI * newR * newR })
  })

  const barData = 0.1 * drawWidth
  const barLabel =
    barData >= 1
      ? `${Math.round(barData * 10) / 10} m`
      : `${Math.round(barData * 100)} cm`

  return (
    <svg
      ref={svgRef}
      viewBox={`${vbX} ${vbY} ${drawWidth} ${drawHeight}`}
      className="w-full"
      style={{ maxHeight: 140, touchAction: "none" }}
      role="img"
      aria-label="Drone top view; drag wingtips to change span, aperture to change receiver"
      data-testid="drone-top-view"
    >
      {airframe === "fixed_wing" ? (
        <g>
          {/* Fuselage */}
          <ellipse
            cx={0}
            cy={0}
            rx={fuselageLength / 2}
            ry={chord * 0.5}
            fill="var(--bg-surface)"
            stroke={stroke}
            strokeWidth={strokeW}
          />
          {/* Wing (rectangular planform, aspect documented above) */}
          <rect
            x={-halfSpan}
            y={-chord / 2}
            width={wingspan_m}
            height={chord}
            fill="var(--bg-subtle)"
            stroke={stroke}
            strokeWidth={strokeW}
          />
          {/* Tail plane */}
          <rect
            x={fuselageLength / 2 - tailChord}
            y={-tailSpan / 2}
            width={tailChord}
            height={tailSpan}
            fill="var(--bg-subtle)"
            stroke={stroke}
            strokeWidth={strokeW * 0.8}
          />
          {/* Receiver aperture on the fuselage centre */}
          <circle
            cx={0}
            cy={0}
            r={apertureRadius}
            fill="var(--status-green)"
            fillOpacity={0.15}
            stroke="var(--status-green)"
            strokeWidth={strokeW}
          />
          {/* Aperture edge drag handle */}
          <circle
            cx={apertureRadius}
            cy={0}
            r={drawWidth * 0.008}
            fill="var(--status-orange)"
            stroke="var(--ink-primary)"
            strokeWidth={strokeW * 0.6}
            style={{ cursor: "ew-resize" }}
            data-testid="aperture-handle"
            {...apertureDrag}
          />
          {/* Right wingtip drag handle */}
          <circle
            cx={halfSpan}
            cy={0}
            r={drawWidth * 0.008}
            fill="var(--status-green)"
            stroke="var(--ink-primary)"
            strokeWidth={strokeW * 0.6}
            style={{ cursor: "ew-resize" }}
            data-testid="wingtip-handle"
            {...wingtipDrag}
          />
        </g>
      ) : (
        <g>
          {/* Four arms in X */}
          {(
            [
              [-1, -1],
              [1, -1],
              [-1, 1],
              [1, 1],
            ] as const
          ).map(([sx, sy], i) => {
            const arm = halfSpan
            const ex = sx * arm * Math.cos(Math.PI / 4)
            const ey = sy * arm * Math.sin(Math.PI / 4)
            const rotorR = 0.175 * wingspan_m
            return (
              <g key={i}>
                <line
                  x1={0}
                  y1={0}
                  x2={ex}
                  y2={ey}
                  stroke={stroke}
                  strokeWidth={strokeW}
                />
                <circle
                  cx={ex}
                  cy={ey}
                  r={rotorR}
                  fill="none"
                  stroke={stroke}
                  strokeWidth={strokeW * 0.7}
                />
                <circle cx={ex} cy={ey} r={strokeW * 1.2} fill={stroke} />
              </g>
            )
          })}
          {/* Central hub */}
          <circle
            cx={0}
            cy={0}
            r={0.12 * wingspan_m}
            fill="var(--bg-surface)"
            stroke={stroke}
            strokeWidth={strokeW}
          />
          {/* Receiver aperture */}
          <circle
            cx={0}
            cy={0}
            r={apertureRadius}
            fill="var(--status-green)"
            fillOpacity={0.15}
            stroke="var(--status-green)"
            strokeWidth={strokeW}
          />
          <circle
            cx={apertureRadius}
            cy={0}
            r={drawWidth * 0.008}
            fill="var(--status-orange)"
            stroke="var(--ink-primary)"
            strokeWidth={strokeW * 0.6}
            style={{ cursor: "ew-resize" }}
            data-testid="aperture-handle"
            {...apertureDrag}
          />
          {/* Right arm-end drag handle */}
          <circle
            cx={halfSpan * Math.cos(Math.PI / 4)}
            cy={-halfSpan * Math.sin(Math.PI / 4)}
            r={drawWidth * 0.008}
            fill="var(--status-green)"
            stroke="var(--ink-primary)"
            strokeWidth={strokeW * 0.6}
            style={{ cursor: "ew-resize" }}
            data-testid="wingtip-handle"
            {...wingtipDrag}
          />
        </g>
      )}

      {/* Metric labels */}
      <text
        x={0}
        y={vbY + drawHeight * 0.08}
        textAnchor="middle"
        fontFamily="ui-monospace, monospace"
        fontSize={drawWidth * 0.025}
        fill="var(--ink-tertiary)"
      >
        span {wingspan_m.toFixed(2)} m · aperture {receiver_aperture_m2.toFixed(3)} m² ·{" "}
        {airframe === "fixed_wing" ? "fixed-wing" : "multirotor"}
      </text>

      <ScaleBar
        x={vbX + drawWidth * 0.06}
        y={vbY + drawHeight * 0.9}
        widthData={barData}
        label={barLabel}
        fontSize={drawWidth * 0.022}
      />
    </svg>
  )
}
