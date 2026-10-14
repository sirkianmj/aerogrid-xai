/**
 * MultirotorDetail — planform engineering drawing of a quadrotor.
 *
 * Top-down, scale-correct. Every dimension derived from the wingspan
 * parameter, which for a multirotor is read as the diagonal motor-to-
 * motor distance (the "span" of the drone in the aerospace sense):
 *
 *   span (motor-to-motor across the diagonal)  parameter
 *   arm length (hub to motor)                  0.5 * span / sqrt(2)
 *   arm width                                  0.03 * span
 *   motor housing diameter                     0.09 * span
 *   propeller diameter                         0.35 * span
 *   central hub diameter                       0.16 * span
 *   battery bay (rectangular, on top)          0.5 * hub diameter
 *   gimbal camera diameter                     0.07 * span
 *   landing skid length                        0.4 * span
 *
 * Features: four curved arms, motor housings with visible cooling
 * fins, two-blade propellers with twisted blade shapes, a central hub
 * with a battery bay and antenna, a gimbal camera underneath, two
 * landing skids visible in projection, and a receiver aperture drawn
 * as a circle on the hub crown.
 *
 * Nothing in this file names a real aircraft, manufacturer, or
 * programme. Proportions are generic multirotor conventions.
 */

import { useRef, type ReactElement } from "react"
import { useDragSvg } from "./useDragSvg"
import { ScaleBar } from "./ScaleBar"

export type MultirotorDetailProps = {
  wingspan_m: number
  receiver_aperture_m2: number
  onChange: (patch: { wingspan_m?: number; receiver_aperture_m2?: number }) => void
  highlighted?: boolean
}

export function MultirotorDetail({
  wingspan_m,
  receiver_aperture_m2,
  onChange,
  highlighted = false,
}: MultirotorDetailProps) {
  const svgRef = useRef<SVGSVGElement | null>(null)

  const span = wingspan_m
  const armLen = (0.5 * span) / Math.SQRT2
  const armWidth = 0.03 * span
  const motorDia = 0.09 * span
  const motorR = motorDia / 2
  const propR = 0.175 * span
  const hubR = 0.08 * span
  const gimbalR = 0.035 * span
  const apertureR = Math.sqrt(receiver_aperture_m2 / Math.PI)

  // Arms point at 45 degrees from the axes (X configuration), so the
  // motor-to-motor diagonal is exactly `span`.
  const motorPos = ([1, -1, -1, 1] as const).length // just to satisfy TS
  void motorPos

  const drawW = (span + 2 * propR) * 1.15
  const drawH = drawW
  const vbX = -drawW / 2
  const vbY = -drawH / 2

  const stroke = highlighted ? "var(--ink-primary)" : "var(--ink-secondary)"
  const SW_MAIN = drawW * 0.0018
  const SW_MED = SW_MAIN * 0.7
  const SW_THIN = SW_MAIN * 0.4
  const SW_HAIR = SW_MAIN * 0.25
  const FS = drawW * 0.018
  const DIM_FS = drawW * 0.013

  const armDrag = useDragSvg(svgRef, { w: drawW, h: drawH }, (dx) => {
    const newSpan = Math.max(0.2, span + 2 * dx)
    onChange({ wingspan_m: newSpan })
  })
  const apertureDrag = useDragSvg(svgRef, { w: drawW, h: drawH }, (dx) => {
    const newR = Math.max(0.01, apertureR + dx)
    onChange({ receiver_aperture_m2: Math.PI * newR * newR })
  })

  // Arm positions in X configuration, motors at 45, 135, 225, 315.
  const motors: { x: number; y: number }[] = [
    { x: armLen, y: -armLen },
    { x: armLen, y: armLen },
    { x: -armLen, y: armLen },
    { x: -armLen, y: -armLen },
  ]

  function renderArm(m: { x: number; y: number }, idx: number): ReactElement {
    // Curved arm from hub edge to motor. Quadratic bezier with control
    // point offset perpendicular to the arm axis for a subtle curve.
    const startR = hubR * 0.7
    const sx = (m.x / armLen) * startR
    const sy = (m.y / armLen) * startR
    const ex = m.x
    const ey = m.y
    // Perp direction for the control point.
    const dx = ex - sx
    const dy = ey - sy
    const len = Math.sqrt(dx * dx + dy * dy)
    const px = -dy / len
    const py = dx / len
    const curve = 0.05 * len
    const cx = (sx + ex) / 2 + px * curve
    const cy = (sy + ey) / 2 + py * curve

    // Two offset quadratics to draw the arm as a tapered band.
    const w = armWidth
    const sx1 = sx + px * (w / 2)
    const sy1 = sy + py * (w / 2)
    const sx2 = sx - px * (w / 2)
    const sy2 = sy - py * (w / 2)
    const ex1 = ex + px * (w / 2) * 0.7
    const ey1 = ey + py * (w / 2) * 0.7
    const ex2 = ex - px * (w / 2) * 0.7
    const ey2 = ey - py * (w / 2) * 0.7

    const path = `M ${sx1} ${sy1} Q ${cx + px * (w / 2)} ${cy + py * (w / 2)} ${ex1} ${ey1}
                  L ${ex2} ${ey2}
                  Q ${cx - px * (w / 2)} ${cy - py * (w / 2)} ${sx2} ${sy2} Z`

    return (
      <g key={idx}>
        <path d={path} fill="var(--bg-subtle)" stroke={stroke} strokeWidth={SW_MED} />
        {/* Motor mounting plate: a small rectangle at the arm tip */}
        <rect
          x={ex - motorR * 1.15}
          y={ey - motorR * 1.15}
          width={motorR * 2.3}
          height={motorR * 2.3}
          fill="var(--bg-surface)"
          stroke={stroke}
          strokeWidth={SW_HAIR}
        />
      </g>
    )
  }

  function renderMotor(m: { x: number; y: number }, idx: number): ReactElement {
    return (
      <g key={`motor${idx}`}>
        {/* Motor housing: outer ring with cooling fins */}
        <circle
          cx={m.x}
          cy={m.y}
          r={motorR}
          fill="var(--bg-surface)"
          stroke={stroke}
          strokeWidth={SW_MED}
        />
        {/* Cooling fin lines: short radial segments around the housing */}
        {Array.from({ length: 12 }).map((_, i) => {
          const a = (i * 2 * Math.PI) / 12
          const r1 = motorR * 0.55
          const r2 = motorR * 0.95
          return (
            <line
              key={i}
              x1={m.x + Math.cos(a) * r1}
              y1={m.y + Math.sin(a) * r1}
              x2={m.x + Math.cos(a) * r2}
              y2={m.y + Math.sin(a) * r2}
              stroke={stroke}
              strokeWidth={SW_HAIR}
              opacity={0.7}
            />
          )
        })}
        {/* Inner hub */}
        <circle cx={m.x} cy={m.y} r={motorR * 0.32} fill={stroke} />
      </g>
    )
  }

  function renderProp(m: { x: number; y: number }, idx: number): ReactElement {
    // Two-blade propeller: each blade drawn as a swept path with a
    // bulge for the twisted airfoil, plus a thin tip cap.
    const blades = [0, 180]
    const oneBlade = (angleDeg: number, key: string) => {
      const a = (angleDeg * Math.PI) / 180
      const ca = Math.cos(a)
      const sa = Math.sin(a)
      const bladeW = propR * 0.22
      const perpA = a + Math.PI / 2
      const px = Math.cos(perpA) * bladeW
      const py = Math.sin(perpA) * bladeW
      const tipX = m.x + ca * propR
      const tipY = m.y + sa * propR
      const midX = m.x + ca * propR * 0.55
      const midY = m.y + sa * propR * 0.55
      return (
        <g key={key}>
          {/* Blade path with a slight bow */}
          <path
            d={`M ${m.x} ${m.y}
                Q ${midX + px} ${midY + py} ${tipX} ${tipY}
                Q ${midX - px} ${midY - py} ${m.x} ${m.y} Z`}
            fill="var(--bg-subtle)"
            stroke={stroke}
            strokeWidth={SW_THIN}
            opacity={0.9}
          />
          {/* Tip cap */}
          <line
            x1={tipX + Math.cos(perpA) * bladeW * 0.25}
            y1={tipY + Math.sin(perpA) * bladeW * 0.25}
            x2={tipX - Math.cos(perpA) * bladeW * 0.25}
            y2={tipY - Math.sin(perpA) * bladeW * 0.25}
            stroke={stroke}
            strokeWidth={SW_HAIR}
          />
        </g>
      )
    }
    return (
      <g key={`prop${idx}`} opacity={0.85}>
        {blades.map((b) => oneBlade(b, `b${b}`))}
        <circle cx={m.x} cy={m.y} r={propR * 0.04} fill={stroke} />
      </g>
    )
  }

  return (
    <svg
      ref={svgRef}
      viewBox={`${vbX} ${vbY} ${drawW} ${drawH}`}
      className="w-full"
      style={{ maxHeight: 220, touchAction: "none" }}
      role="img"
      aria-label="Multirotor UAV top view, scale-correct"
      data-testid="drone-top-view"
    >
      {/* 1. Landing skids (drawn under everything) */}
      <g opacity={0.4}>
        <rect
          x={-hubR * 1.1}
          y={-hubR * 0.35}
          width={hubR * 2.2}
          height={hubR * 0.12}
          fill={stroke}
        />
        <rect
          x={-hubR * 1.1}
          y={hubR * 0.23}
          width={hubR * 2.2}
          height={hubR * 0.12}
          fill={stroke}
        />
      </g>

      {/* 2. Arms */}
      {motors.map((m, i) => renderArm(m, i))}

      {/* 3. Propellers */}
      {motors.map((m, i) => renderProp(m, i))}

      {/* 4. Motors (drawn over props so the housing is visible) */}
      {motors.map((m, i) => renderMotor(m, i))}

      {/* 5. Central hub body */}
      <circle
        cx={0}
        cy={0}
        r={hubR}
        fill="var(--bg-surface)"
        stroke={stroke}
        strokeWidth={SW_MAIN}
      />
      {/* Hub panel lines */}
      <circle cx={0} cy={0} r={hubR * 0.65} fill="none" stroke={stroke} strokeWidth={SW_HAIR} />
      <line x1={-hubR * 0.65} y1={0} x2={hubR * 0.65} y2={0} stroke={stroke} strokeWidth={SW_HAIR} />
      <line x1={0} y1={-hubR * 0.65} x2={0} y2={hubR * 0.65} stroke={stroke} strokeWidth={SW_HAIR} />

      {/* 6. Battery bay on top (visible as a rectangle) */}
      <rect
        x={-hubR * 0.55}
        y={-hubR * 0.35}
        width={hubR * 1.1}
        height={hubR * 0.7}
        rx={hubR * 0.08}
        fill="var(--bg-subtle)"
        stroke={stroke}
        strokeWidth={SW_THIN}
      />
      <line
        x1={-hubR * 0.55}
        y1={0}
        x2={hubR * 0.55}
        y2={0}
        stroke={stroke}
        strokeWidth={SW_HAIR}
      />

      {/* 7. Two antenna whips from the hub */}
      <line
        x1={hubR * 0.4}
        y1={-hubR * 0.7}
        x2={hubR * 0.9}
        y2={-hubR * 1.5}
        stroke={stroke}
        strokeWidth={SW_THIN}
      />
      <circle cx={hubR * 0.9} cy={-hubR * 1.5} r={SW_THIN * 1.6} fill={stroke} />
      <line
        x1={-hubR * 0.4}
        y1={-hubR * 0.7}
        x2={-hubR * 0.9}
        y2={-hubR * 1.5}
        stroke={stroke}
        strokeWidth={SW_THIN}
      />
      <circle cx={-hubR * 0.9} cy={-hubR * 1.5} r={SW_THIN * 1.6} fill={stroke} />

      {/* 8. Gimbal camera underneath (drawn as a circle beneath the hub) */}
      <circle
        cx={0}
        cy={0}
        r={gimbalR}
        fill="var(--bg-subtle)"
        stroke={stroke}
        strokeWidth={SW_THIN}
        opacity={0.55}
      />
      <circle cx={0} cy={0} r={gimbalR * 0.5} fill="none" stroke={stroke} strokeWidth={SW_HAIR} opacity={0.55} />

      {/* 9. Receiver aperture on the crown */}
      <circle
        cx={hubR * 0.2}
        cy={0}
        r={apertureR}
        fill="var(--status-green)"
        fillOpacity={0.18}
        stroke="var(--status-green)"
        strokeWidth={SW_MED}
      />
      <circle
        cx={hubR * 0.2 + apertureR}
        cy={0}
        r={drawW * 0.008}
        fill="var(--status-orange)"
        stroke="var(--ink-primary)"
        strokeWidth={SW_THIN}
        style={{ cursor: "ew-resize" }}
        data-testid="aperture-handle"
        {...apertureDrag}
      />

      {/* 10. Arm-end drag handle (motor at 45 degrees, right-front) */}
      <circle
        cx={armLen}
        cy={-armLen}
        r={drawW * 0.009}
        fill="var(--status-green)"
        stroke="var(--ink-primary)"
        strokeWidth={SW_THIN}
        style={{ cursor: "ew-resize" }}
        data-testid="wingtip-handle"
        {...armDrag}
      />

      {/* 11. Dimension callout: motor-to-motor diagonal */}
      <g>
        <line
          x1={armLen + motorR + propR * 1.1}
          y1={-armLen - motorR - propR * 1.1}
          x2={-armLen - motorR - propR * 1.1}
          y2={armLen + motorR + propR * 1.1}
          stroke="var(--ink-tertiary)"
          strokeWidth={SW_HAIR}
          strokeDasharray={`${SW_HAIR * 3} ${SW_HAIR * 3}`}
        />
        <text
          x={0}
          y={-armLen - motorR - propR * 1.3}
          textAnchor="middle"
          fontFamily="ui-monospace, monospace"
          fontSize={DIM_FS}
          fill="var(--ink-tertiary)"
        >
          span {span.toFixed(2)} m (motor-to-motor)
        </text>
      </g>

      {/* 12. Metric scale bar */}
      <ScaleBar
        x={vbX + drawW * 0.05}
        y={vbY + drawH * 0.94}
        widthData={0.15 * drawW}
        label={`${(0.15 * drawW).toFixed(2)} m`}
        fontSize={FS}
      />
    </svg>
  )
}
