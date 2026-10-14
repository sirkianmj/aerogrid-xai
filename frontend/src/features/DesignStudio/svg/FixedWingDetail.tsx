/**
 * FixedWingDetail — planform engineering drawing of a fixed-wing UAV.
 *
 * Top-down, scale-correct. Every dimension derived from the wingspan:
 *
 *   wingspan              parameter
 *   chord (root)          0.15 span
 *   chord (tip)           0.55 of root chord — taper ratio 0.55
 *   quarter-chord sweep   8 degrees
 *   fuselage length       0.6 span
 *   fuselage max width    0.06 span
 *   nose radius           0.03 span
 *   tail span             0.35 span
 *   tail chord            0.06 span
 *   sensor turret radius  0.05 span
 *   propeller radius      0.15 span
 *
 * Receiver aperture is drawn as a circle of radius sqrt(A/pi) at the
 * centre of the fuselage, visible from above.
 *
 * Features: swept tapered wing, ailerons and flaps shown as trailing-
 * edge segments, winglets at the tips, teardrop fuselage with panel
 * lines, tapered nose with a sensor turret and a cockpit window
 * outline, three-blade propeller at the nose, vertical fin, horizontal
 * stabiliser with elevator, three landing-gear fairings (retracted),
 * and a receiver aperture on the fuselage crown.
 *
 * Nothing in this file names a real aircraft, manufacturer, or
 * programme. Proportions are generic aerospace conventions.
 */

import { useRef, type ReactElement } from "react"
import { useDragSvg } from "./useDragSvg"
import { ScaleBar } from "./ScaleBar"

const SWEEP_DEG = 8

export type FixedWingDetailProps = {
  wingspan_m: number
  receiver_aperture_m2: number
  onChange: (patch: { wingspan_m?: number; receiver_aperture_m2?: number }) => void
  highlighted?: boolean
}

export function FixedWingDetail({
  wingspan_m,
  receiver_aperture_m2,
  onChange,
  highlighted = false,
}: FixedWingDetailProps) {
  const svgRef = useRef<SVGSVGElement | null>(null)

  const span = wingspan_m
  const halfSpan = span / 2
  const rootChord = 0.15 * span
  const tipChord = 0.55 * rootChord
  const fusLen = 0.6 * span
  const fusWidth = 0.06 * span
  const noseR = 0.03 * span
  const tailSpan = 0.35 * span
  const tailChord = 0.06 * span
  const turretR = 0.05 * span
  const propR = 0.15 * span
  const apertureR = Math.sqrt(receiver_aperture_m2 / Math.PI)

  const sweepOffset = Math.tan((SWEEP_DEG * Math.PI) / 180) * (halfSpan - fusWidth / 2)

  const drawW = Math.max(span, fusLen, 2 * propR + fusLen) * 1.15
  const drawH = Math.max(fusLen, span * 0.6) * 1.1
  const vbX = -drawW / 2
  const vbY = -drawH / 2

  const stroke = highlighted ? "var(--ink-primary)" : "var(--ink-secondary)"
  const SW_MAIN = drawW * 0.0016
  const SW_MED = SW_MAIN * 0.7
  const SW_THIN = SW_MAIN * 0.4
  const SW_HAIR = SW_MAIN * 0.25
  const FS = drawW * 0.018
  const DIM_FS = drawW * 0.013

  const wingtipDrag = useDragSvg(svgRef, { w: drawW, h: drawH }, (dx) => {
    const newSpan = Math.max(0.2, span + 2 * dx)
    onChange({ wingspan_m: newSpan })
  })
  const apertureDrag = useDragSvg(svgRef, { w: drawW, h: drawH }, (dx) => {
    const newR = Math.max(0.01, apertureR + dx)
    onChange({ receiver_aperture_m2: Math.PI * newR * newR })
  })

  // Nose is +X, tail is -X (aerospace convention: nose forward).
  const noseX = fusLen / 2
  const tailX = -fusLen / 2

  function renderWing(side: 1 | -1): ReactElement {
    const sideSign = side
    // Root LE at the fuselage edge, tip LE swept back.
    const leRootX = -rootChord / 2 + fusWidth * 0.5
    const leRootY = sideSign * (fusWidth * 0.35)
    const leTipX = leRootX - sweepOffset
    const leTipY = sideSign * halfSpan

    const teRootX = rootChord / 2 + fusWidth * 0.5
    const teRootY = sideSign * (fusWidth * 0.35)
    const teTipX = leTipX + tipChord
    const teTipY = sideSign * halfSpan

    const path = `M ${leRootX} ${leRootY} L ${leTipX} ${leTipY} L ${teTipX} ${teTipY} L ${teRootX} ${teRootY} Z`

    // Trailing-edge control surfaces: aileron (outboard) and flap
    // (inboard). Drawn as inset parallelogram ticks along the TE.
    const aileronInboardT = 0.55
    const aileronOutboardT = 0.9
    const controlLine = (t1: number, t2: number, label: string, key: string) => {
      const x1 = teRootX + t1 * (teTipX - teRootX)
      const y1 = teRootY + t1 * (teTipY - teRootY)
      const x2 = teRootX + t2 * (teTipX - teRootX)
      const y2 = teRootY + t2 * (teTipY - teRootY)
      const dxIn = -tipChord * 0.2
      const dyIn = -sideSign * tipChord * 0.15
      const path = `M ${x1} ${y1} L ${x2} ${y2} L ${x2 + dxIn} ${y2 + dyIn} L ${x1 + dxIn} ${y1 + dyIn} Z`
      return (
        <g key={key}>
          <path d={path} fill="var(--bg-subtle)" stroke={stroke} strokeWidth={SW_HAIR} />
          <text
            x={(x1 + x2) / 2 + dxIn}
            y={(y1 + y2) / 2 + dyIn + FS * 0.1}
            textAnchor="middle"
            fontFamily="ui-monospace, monospace"
            fontSize={DIM_FS * 0.85}
            fill="var(--ink-tertiary)"
          >
            {label}
          </text>
        </g>
      )
    }

    return (
      <g>
        <path d={path} fill="var(--bg-subtle)" stroke={stroke} strokeWidth={SW_MED} />
        {/* Panel line along the wing */}
        <line
          x1={leRootX + tipChord * 0.25}
          y1={leRootY + sideSign * fusWidth * 0.1}
          x2={leTipX + tipChord * 0.3}
          y2={leTipY - sideSign * tipChord * 0.2}
          stroke={stroke}
          strokeWidth={SW_HAIR}
          opacity={0.5}
        />
        {/* Winglet at tip */}
        <line
          x1={leTipX}
          y1={leTipY}
          x2={leTipX - tipChord * 0.1}
          y2={leTipY + sideSign * tipChord * 0.6}
          stroke={stroke}
          strokeWidth={SW_MED}
        />
        <line
          x1={teTipX}
          y1={teTipY}
          x2={leTipX - tipChord * 0.1}
          y2={leTipY + sideSign * tipChord * 0.6}
          stroke={stroke}
          strokeWidth={SW_MED}
        />

        {/* Control surfaces */}
        {controlLine(0.1, 0.5, "FLAP", `flap${side}`)}
        {controlLine(aileronInboardT, aileronOutboardT, "AIL", `ail${side}`)}
      </g>
    )
  }

  // Sensor turret (under the nose, visible from top as a faint circle)
  const turretCx = noseX - fusWidth * 0.9

  return (
    <svg
      ref={svgRef}
      viewBox={`${vbX} ${vbY} ${drawW} ${drawH}`}
      className="w-full"
      style={{ maxHeight: 220, touchAction: "none" }}
      role="img"
      aria-label="Fixed-wing UAV top view, scale-correct"
      data-testid="drone-top-view"
    >
      {/* 1. Fuselage: teardrop with tapered nose and tail */}
      <path
        d={(() => {
          const w2 = fusWidth / 2
          return `M ${noseX} 0
                  C ${noseX - noseR * 1.4} ${-w2 * 1.6}, ${noseX - fusLen * 0.15} ${-w2 * 1.15}, ${0} ${-w2}
                  L ${tailX + fusLen * 0.1} ${-w2 * 0.7}
                  C ${tailX - fusLen * 0.05} ${-w2 * 0.6}, ${tailX - fusLen * 0.02} ${-w2 * 0.25}, ${tailX} 0
                  C ${tailX - fusLen * 0.02} ${w2 * 0.25}, ${tailX - fusLen * 0.05} ${w2 * 0.6}, ${tailX + fusLen * 0.1} ${w2 * 0.7}
                  L ${0} ${w2}
                  C ${noseX - fusLen * 0.15} ${w2 * 1.15}, ${noseX - noseR * 1.4} ${w2 * 1.6}, ${noseX} 0 Z`
        })()}
        fill="var(--bg-surface)"
        stroke={stroke}
        strokeWidth={SW_MAIN}
      />

      {/* 2. Cockpit window (nose top) */}
      <path
        d={`M ${noseX - fusLen * 0.02} ${-fusWidth * 0.28}
            C ${noseX - fusLen * 0.06} ${-fusWidth * 0.3}, ${noseX - fusLen * 0.1} ${-fusWidth * 0.22}, ${noseX - fusLen * 0.13} 0
            C ${noseX - fusLen * 0.1} ${fusWidth * 0.22}, ${noseX - fusLen * 0.06} ${fusWidth * 0.3}, ${noseX - fusLen * 0.02} ${fusWidth * 0.28} Z`}
        fill="none"
        stroke={stroke}
        strokeWidth={SW_THIN}
        opacity={0.7}
      />

      {/* 3. Fuselage panel lines */}
      {[-0.15, 0.05, 0.25].map((t, i) => (
        <line
          key={`fl${i}`}
          x1={tailX + t * fusLen}
          y1={-fusWidth * 0.55}
          x2={tailX + t * fusLen}
          y2={fusWidth * 0.55}
          stroke={stroke}
          strokeWidth={SW_HAIR}
          opacity={0.5}
        />
      ))}

      {/* 4. Wings */}
      {renderWing(-1)}
      {renderWing(1)}

      {/* 5. Sensor turret (top view: circle with crosshair) */}
      <g>
        <circle
          cx={turretCx}
          cy={0}
          r={turretR}
          fill="var(--bg-subtle)"
          stroke={stroke}
          strokeWidth={SW_MED}
        />
        <circle cx={turretCx} cy={0} r={turretR * 0.55} fill="none" stroke={stroke} strokeWidth={SW_HAIR} />
        <line
          x1={turretCx - turretR * 0.75}
          y1={0}
          x2={turretCx + turretR * 0.75}
          y2={0}
          stroke={stroke}
          strokeWidth={SW_HAIR}
        />
      </g>

      {/* 6. Propeller at nose: three blades with twist */}
      <g transform={`translate(${noseX + noseR * 0.3}, 0)`}>
        <circle r={propR * 0.12} fill="var(--ink-primary)" />
        {[0, 120, 240].map((deg) => {
          const rad = (deg * Math.PI) / 180
          const bladeLen = propR
          const tipX = Math.cos(rad) * bladeLen
          const tipY = Math.sin(rad) * bladeLen
          const midX = tipX * 0.55
          const midY = tipY * 0.55
          const perp = rad + Math.PI / 2
          const bladeW = bladeLen * 0.18
          const px = Math.cos(perp) * bladeW / 2
          const py = Math.sin(perp) * bladeW / 2
          return (
            <path
              key={deg}
              d={`M 0 0
                  L ${midX + px} ${midY + py}
                  L ${tipX} ${tipY}
                  L ${midX - px} ${midY - py} Z`}
              fill="var(--bg-subtle)"
              stroke={stroke}
              strokeWidth={SW_THIN}
            />
          )
        })}
      </g>

      {/* 7. Vertical fin (viewed from above: line at tail centreline) */}
      <line
        x1={tailX - fusLen * 0.02}
        y1={0}
        x2={tailX + fusLen * 0.08}
        y2={0}
        stroke={stroke}
        strokeWidth={SW_MAIN}
      />

      {/* 8. Horizontal stabiliser with elevator */}
      <g>
        <path
          d={`M ${tailX + fusLen * 0.14} ${-tailSpan / 2}
              L ${tailX - fusLen * 0.02} ${-tailSpan * 0.42}
              L ${tailX - fusLen * 0.02} ${tailSpan * 0.42}
              L ${tailX + fusLen * 0.14} ${tailSpan / 2}
              L ${tailX + fusLen * 0.14 + tailChord * 0.2} ${tailSpan / 2}
              L ${tailX + fusLen * 0.14 + tailChord * 0.2} ${-tailSpan / 2} Z`}
          fill="var(--bg-subtle)"
          stroke={stroke}
          strokeWidth={SW_MED}
        />
        {/* Elevator line */}
        <line
          x1={tailX + fusLen * 0.14 + tailChord * 0.1}
          y1={-tailSpan / 2}
          x2={tailX + fusLen * 0.14 + tailChord * 0.1}
          y2={tailSpan / 2}
          stroke={stroke}
          strokeWidth={SW_HAIR}
        />
      </g>

      {/* 9. Landing gear fairings (retracted, seen as small bumps) */}
      {[
        [noseX - fusLen * 0.35, 0],
        [0, -fusWidth * 0.65],
        [0, fusWidth * 0.65],
      ].map(([cx, cy], i) => (
        <ellipse
          key={`lg${i}`}
          cx={cx}
          cy={cy}
          rx={fusWidth * 0.18}
          ry={fusWidth * 0.1}
          fill="var(--ink-primary)"
          opacity={0.7}
        />
      ))}

      {/* 10. Receiver aperture on the crown (visible from above) */}
      <circle
        cx={-fusLen * 0.12}
        cy={0}
        r={apertureR}
        fill="var(--status-green)"
        fillOpacity={0.18}
        stroke="var(--status-green)"
        strokeWidth={SW_MED}
      />
      <circle
        cx={-fusLen * 0.12 + apertureR}
        cy={0}
        r={drawW * 0.008}
        fill="var(--status-orange)"
        stroke="var(--ink-primary)"
        strokeWidth={SW_THIN}
        style={{ cursor: "ew-resize" }}
        data-testid="aperture-handle"
        {...apertureDrag}
      />

      {/* 11. Wingtip drag handle (right wing only, at the tip) */}
      <circle
        cx={-rootChord / 2 + fusWidth * 0.5 - sweepOffset + tipChord * 0.5}
        cy={halfSpan}
        r={drawW * 0.009}
        fill="var(--status-green)"
        stroke="var(--ink-primary)"
        strokeWidth={SW_THIN}
        style={{ cursor: "ew-resize" }}
        data-testid="wingtip-handle"
        {...wingtipDrag}
      />

      {/* 12. Dimension callout for wingspan */}
      <g>
        <line
          x1={-rootChord / 2 + fusWidth * 0.5 - sweepOffset - tipChord * 1.2}
          y1={-halfSpan}
          x2={-rootChord / 2 + fusWidth * 0.5 - sweepOffset - tipChord * 1.2}
          y2={halfSpan}
          stroke="var(--ink-tertiary)"
          strokeWidth={SW_HAIR}
        />
        <line
          x1={-rootChord / 2 + fusWidth * 0.5 - sweepOffset - tipChord * 1.4}
          y1={-halfSpan}
          x2={-rootChord / 2 + fusWidth * 0.5 - sweepOffset - tipChord * 1.0}
          y2={-halfSpan}
          stroke="var(--ink-tertiary)"
          strokeWidth={SW_HAIR}
        />
        <line
          x1={-rootChord / 2 + fusWidth * 0.5 - sweepOffset - tipChord * 1.4}
          y1={halfSpan}
          x2={-rootChord / 2 + fusWidth * 0.5 - sweepOffset - tipChord * 1.0}
          y2={halfSpan}
          stroke="var(--ink-tertiary)"
          strokeWidth={SW_HAIR}
        />
        <text
          x={-rootChord / 2 + fusWidth * 0.5 - sweepOffset - tipChord * 1.6}
          y={0}
          textAnchor="middle"
          fontFamily="ui-monospace, monospace"
          fontSize={DIM_FS}
          fill="var(--ink-tertiary)"
        >
          span {span.toFixed(2)} m
        </text>
      </g>

      {/* 13. Metric scale bar */}
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
