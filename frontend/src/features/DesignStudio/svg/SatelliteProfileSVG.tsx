/**
 * SatelliteProfileSVG — full engineering side profile of the satellite.
 *
 * This is a scale-correct spacecraft drawing, not a schematic. Every
 * dimension comes from the physical parameters:
 *
 *   Solar array span   from P_tx / (408 W/m^2 triple-junction cell at
 *                      AM0). Panels shown edge-on: the drawing's
 *                      vertical extent per panel is the array chord,
 *                      the horizontal extent is the panel length.
 *
 *   Dish diameter      scales modestly with P_tx so the drawing is
 *                      legible at all power levels. Documented
 *                      formula: dish_diam_m = 0.3 + 1.2 *
 *                      sqrt(P_tx / 100_000).
 *
 *   Beam waist         the transmitter aperture w0 is what the drag
 *                      handle changes. It is drawn as a small emitter
 *                      at the dish focus.
 *
 * Drawing anatomy, in the order features are rendered:
 *
 *   1. Solar arrays (left and right), each with N panels, hinge
 *      gaps between them, and visible cell division lines.
 *   2. Yoke arms connecting each array to the spacecraft bus.
 *   3. Central bus with structural ribs, MLI cross-hatch, a radiator
 *      panel, and a small electronics hatch.
 *   4. Parabolic transmit dish on the nadir face with a feed horn,
 *      support struts, and a two-axis gimbal.
 *   5. Star tracker baffle tubes on the zenith face.
 *   6. Thruster cluster on the zenith face.
 *   7. TT&C antenna whips.
 *   8. Dimensional callouts (array span, bus dimensions, dish
 *      diameter) with proper arrowheads and datum lines.
 *   9. Metric scale bar at the bottom of the drawing.
 *
 * Nothing in this file names a real satellite, programme, or
 * manufacturer. Proportions are generic aerospace convention.
 */

import { useRef, type ReactElement } from "react"
import { useDragSvg } from "./useDragSvg"
import { ScaleBar } from "./ScaleBar"

// Triple-junction solar cell specific power at AM0 (1 AU, 1361 W/m^2),
// 30 percent cell efficiency. Documented figure; real values vary by
// manufacturer and by temperature.
const W_PER_M2 = 408.0

// Geometry constants. Kept modestly abstract; the drawing scales with
// the physical parameters above.
const N_PANELS_PER_SIDE = 3
const PANEL_CHORD_M = 1.0          // vertical extent of one array panel
const PANEL_GAP_M = 0.05           // hinge gap between adjacent panels
const BUS_W_M = 1.8                // bus width (horizontal)
const BUS_H_M = 1.6                // bus height (vertical)
const YOKE_L_M = 0.4               // length of the array-to-bus yoke
const DISH_MARGIN_M = 0.35         // distance from bus bottom to dish top

export type SatelliteProfileSVGProps = {
  transmitter_power_w: number
  transmitter_aperture_m: number
  onChange: (patch: { transmitter_aperture_m?: number }) => void
}

export function SatelliteProfileSVG({
  transmitter_power_w,
  transmitter_aperture_m,
  onChange,
}: SatelliteProfileSVGProps) {
  const svgRef = useRef<SVGSVGElement | null>(null)

  // --- Derived dimensions (all in metres) ----------------------------
  const totalArrayAreaM2 = transmitter_power_w / W_PER_M2
  const perSideAreaM2 = totalArrayAreaM2 / 2
  const panelLengthM = perSideAreaM2 / N_PANELS_PER_SIDE / PANEL_CHORD_M
  const arrayLenPerSideM =
    N_PANELS_PER_SIDE * panelLengthM +
    (N_PANELS_PER_SIDE - 1) * PANEL_GAP_M

  const dishDiamM = 0.3 + 1.2 * Math.sqrt(transmitter_power_w / 100_000)
  const dishRadiusM = dishDiamM / 2

  // Full horizontal extent: bus half + yoke + array span, both sides.
  const totalHalfWidth =
    BUS_W_M / 2 + YOKE_L_M + arrayLenPerSideM
  const margin = 0.08 * totalHalfWidth

  // Full vertical extent: star tracker tubes on top, then bus, then
  // margin, then dish below. Dish sits below the bus with a gimbal.
  const starTrackerLenM = 0.6
  const dishTopY = -BUS_H_M / 2 - DISH_MARGIN_M
  const dishBottomY = dishTopY - dishDiamM
  const topY = BUS_H_M / 2 + starTrackerLenM
  const botY = dishBottomY
  const viewH = topY - botY

  const vbX = -totalHalfWidth - margin
  const vbY = botY - margin
  const vbW = 2 * (totalHalfWidth + margin)
  const vbH = viewH + 2 * margin

  // Stroke widths and font sizes scale with the viewBox width so the
  // drawing is legible at every array size.
  const SW_MAIN = vbW * 0.0009
  const SW_MED = SW_MAIN * 0.7
  const SW_THIN = SW_MAIN * 0.45
  const SW_HAIR = SW_MAIN * 0.28
  const FS = vbW * 0.016
  const DIM_FS = vbW * 0.012

  // --- Drag handle for the aperture ----------------------------------
  // The feed horn emitter is drawn at the focus of the dish. Dragging
  // it left or right horizontally changes w0. dx is in data units (m).
  const handleDrag = useDragSvg(
    svgRef,
    { w: vbW, h: vbH },
    (dx) => {
      const newW0 = Math.max(0.001, transmitter_aperture_m + dx * 0.1)
      onChange({ transmitter_aperture_m: newW0 })
    },
  )

  // --- Dimension-line helper (plain function, not a component) -------
  function renderDimH(x1: number, x2: number, y: number, label: string): ReactElement {
    const tick = FS * 0.4
    return (
      <g>
        <line x1={x1} y1={y} x2={x2} y2={y} stroke="var(--ink-tertiary)" strokeWidth={SW_HAIR} />
        <line x1={x1} y1={y - tick} x2={x1} y2={y + tick} stroke="var(--ink-tertiary)" strokeWidth={SW_HAIR} />
        <line x1={x2} y1={y - tick} x2={x2} y2={y + tick} stroke="var(--ink-tertiary)" strokeWidth={SW_HAIR} />
        <text
          x={(x1 + x2) / 2}
          y={y - tick - FS * 0.2}
          textAnchor="middle"
          fontFamily="ui-monospace, monospace"
          fontSize={DIM_FS}
          fill="var(--ink-tertiary)"
        >
          {label}
        </text>
      </g>
    )
  }

  function renderDimV(x: number, y1: number, y2: number, label: string): ReactElement {
    const tick = FS * 0.4
    return (
      <g>
        <line x1={x} y1={y1} x2={x} y2={y2} stroke="var(--ink-tertiary)" strokeWidth={SW_HAIR} />
        <line x1={x - tick} y1={y1} x2={x + tick} y2={y1} stroke="var(--ink-tertiary)" strokeWidth={SW_HAIR} />
        <line x1={x - tick} y1={y2} x2={x + tick} y2={y2} stroke="var(--ink-tertiary)" strokeWidth={SW_HAIR} />
        <text
          x={x + tick + DIM_FS * 0.3}
          y={(y1 + y2) / 2}
          textAnchor="start"
          dominantBaseline="middle"
          fontFamily="ui-monospace, monospace"
          fontSize={DIM_FS}
          fill="var(--ink-tertiary)"
        >
          {label}
        </text>
      </g>
    )
  }

  // --- Solar-array renderer (one side) --------------------------------
  // Plain function (not a component), called inline to avoid the
  // "component created during render" anti-pattern. It uses no hooks
  // and no state.
  function renderSolarArray(side: 1 | -1): ReactElement {
    const startX = side * (BUS_W_M / 2 + YOKE_L_M)
    const panelEls: ReactElement[] = []
    for (let i = 0; i < N_PANELS_PER_SIDE; i++) {
      const px = startX + side * i * (panelLengthM + PANEL_GAP_M)
      const drawX = side > 0 ? px : px - panelLengthM
      panelEls.push(
        <g key={i}>
          {/* Panel body */}
          <rect
            x={drawX}
            y={-PANEL_CHORD_M / 2}
            width={panelLengthM}
            height={PANEL_CHORD_M}
            fill="var(--bg-subtle)"
            stroke="var(--ink-secondary)"
            strokeWidth={SW_MED}
          />
          {/* Cell division grid: 4x2 = 8 cells */}
          {Array.from({ length: 3 }).map((_, k) => {
            const cx = drawX + ((k + 1) * panelLengthM) / 4
            return (
              <line
                key={`cv${k}`}
                x1={cx}
                y1={-PANEL_CHORD_M / 2}
                x2={cx}
                y2={PANEL_CHORD_M / 2}
                stroke="var(--ink-tertiary)"
                strokeWidth={SW_HAIR}
              />
            )
          })}
          <line
            x1={drawX}
            y1={0}
            x2={drawX + panelLengthM}
            y2={0}
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_HAIR}
          />
          {/* Hinge brackets between panels */}
          {i < N_PANELS_PER_SIDE - 1 && (
            <g>
              <circle
                cx={drawX + side * panelLengthM}
                cy={-PANEL_CHORD_M * 0.35}
                r={SW_MED * 2}
                fill="var(--bg-surface)"
                stroke="var(--ink-primary)"
                strokeWidth={SW_HAIR}
              />
              <circle
                cx={drawX + side * panelLengthM}
                cy={PANEL_CHORD_M * 0.35}
                r={SW_MED * 2}
                fill="var(--bg-surface)"
                stroke="var(--ink-primary)"
                strokeWidth={SW_HAIR}
              />
            </g>
          )}
        </g>
      )
    }
    return <g>{panelEls}</g>
  }

  // --- Main render ----------------------------------------------------
  return (
    <svg
      ref={svgRef}
      viewBox={`${vbX} ${vbY} ${vbW} ${vbH}`}
      className="w-full"
      style={{ maxHeight: 340, touchAction: "none" }}
      role="img"
      aria-label="Satellite side profile, scale-correct"
      data-testid="satellite-profile"
    >
      {/* 1. Solar arrays */}
      {renderSolarArray(-1)}
      {renderSolarArray(1)}

      {/* 2. Yokes */}
      <line
        x1={-BUS_W_M / 2}
        y1={0}
        x2={-BUS_W_M / 2 - YOKE_L_M}
        y2={0}
        stroke="var(--ink-primary)"
        strokeWidth={SW_MED}
      />
      <line
        x1={BUS_W_M / 2}
        y1={0}
        x2={BUS_W_M / 2 + YOKE_L_M}
        y2={0}
        stroke="var(--ink-primary)"
        strokeWidth={SW_MED}
      />
      {/* Solar array drive assembly (SADA) markers */}
      <rect
        x={-BUS_W_M / 2 - YOKE_L_M * 0.6}
        y={-PANEL_CHORD_M * 0.15}
        width={YOKE_L_M * 0.4}
        height={PANEL_CHORD_M * 0.3}
        fill="var(--bg-surface)"
        stroke="var(--ink-primary)"
        strokeWidth={SW_HAIR}
      />
      <rect
        x={BUS_W_M / 2 + YOKE_L_M * 0.2}
        y={-PANEL_CHORD_M * 0.15}
        width={YOKE_L_M * 0.4}
        height={PANEL_CHORD_M * 0.3}
        fill="var(--bg-surface)"
        stroke="var(--ink-primary)"
        strokeWidth={SW_HAIR}
      />

      {/* 3. Bus body */}
      <rect
        x={-BUS_W_M / 2}
        y={-BUS_H_M / 2}
        width={BUS_W_M}
        height={BUS_H_M}
        rx={SW_MED}
        fill="var(--bg-surface)"
        stroke="var(--ink-primary)"
        strokeWidth={SW_MAIN}
      />

      {/* MLI cross-hatch texture on the bus (subtle) */}
      <g opacity={0.35}>
        {Array.from({ length: 10 }).map((_, i) => {
          const y = -BUS_H_M / 2 + ((i + 1) * BUS_H_M) / 11
          return (
            <line
              key={`mli${i}`}
              x1={-BUS_W_M / 2 + SW_THIN}
              y1={y}
              x2={BUS_W_M / 2 - SW_THIN}
              y2={y}
              stroke="var(--ink-tertiary)"
              strokeWidth={SW_HAIR}
              strokeDasharray={`${SW_HAIR * 4} ${SW_HAIR * 4}`}
            />
          )
        })}
      </g>

      {/* Structural ribs */}
      {[-0.25, 0.25].map((frac, i) => (
        <line
          key={`rib${i}`}
          x1={-BUS_W_M / 2}
          y1={frac * BUS_H_M}
          x2={BUS_W_M / 2}
          y2={frac * BUS_H_M}
          stroke="var(--ink-tertiary)"
          strokeWidth={SW_THIN}
        />
      ))}

      {/* Radiator panel on the side */}
      <rect
        x={-BUS_W_M / 2 + BUS_W_M * 0.08}
        y={-BUS_H_M * 0.32}
        width={BUS_W_M * 0.32}
        height={BUS_H_M * 0.64}
        fill="var(--bg-subtle)"
        stroke="var(--ink-tertiary)"
        strokeWidth={SW_THIN}
      />
      <line
        x1={-BUS_W_M / 2 + BUS_W_M * 0.12}
        y1={-BUS_H_M * 0.28}
        x2={-BUS_W_M / 2 + BUS_W_M * 0.36}
        y2={-BUS_H_M * 0.28}
        stroke="var(--ink-tertiary)"
        strokeWidth={SW_HAIR}
      />
      <line
        x1={-BUS_W_M / 2 + BUS_W_M * 0.12}
        y1={-BUS_H_M * 0.28 + 0.05}
        x2={-BUS_W_M / 2 + BUS_W_M * 0.36}
        y2={-BUS_H_M * 0.28 + 0.05}
        stroke="var(--ink-tertiary)"
        strokeWidth={SW_HAIR}
      />
      <line
        x1={-BUS_W_M / 2 + BUS_W_M * 0.12}
        y1={-BUS_H_M * 0.28 + 0.1}
        x2={-BUS_W_M / 2 + BUS_W_M * 0.36}
        y2={-BUS_H_M * 0.28 + 0.1}
        stroke="var(--ink-tertiary)"
        strokeWidth={SW_HAIR}
      />

      {/* Electronics hatch on the other side */}
      <rect
        x={BUS_W_M / 2 - BUS_W_M * 0.4}
        y={-BUS_H_M * 0.3}
        width={BUS_W_M * 0.32}
        height={BUS_H_M * 0.6}
        fill="none"
        stroke="var(--ink-tertiary)"
        strokeWidth={SW_THIN}
      />

      {/* 4. Transmit dish on nadir (-Y) face */}
      <g>
        {/* Gimbal ring */}
        <circle
          cx={0}
          cy={-BUS_H_M / 2 - DISH_MARGIN_M * 0.5}
          r={DISH_MARGIN_M * 0.35}
          fill="var(--bg-surface)"
          stroke="var(--ink-primary)"
          strokeWidth={SW_MED}
        />
        <circle
          cx={0}
          cy={-BUS_H_M / 2 - DISH_MARGIN_M * 0.5}
          r={DISH_MARGIN_M * 0.15}
          fill="none"
          stroke="var(--ink-tertiary)"
          strokeWidth={SW_HAIR}
        />

        {/* Parabolic dish: an arc drawn as an SVG path, then closed by a
            chord to give it a section view. Interior has subtle mesh
            lines (concentric arcs) to suggest a wire-mesh reflector. */}
        <path
          d={(() => {
            // Parabola approximation: y = k x^2, k = 1 / (4 f), where f
            // is the focal length. Use f = 0.35 * diameter (typical for
            // short-focal dishes). Points from -r to +r on x.
            const r = dishRadiusM
            const f = 0.35 * dishDiamM
            const k = 1 / (4 * f)
            const y0 = -BUS_H_M / 2 - DISH_MARGIN_M
            // Approximate the parabola with 12 line segments.
            const N = 12
            let d = ""
            for (let i = 0; i <= N; i++) {
              const x = -r + (2 * r * i) / N
              const y = y0 - k * x * x
              d += (i === 0 ? "M " : "L ") + x + " " + y + " "
            }
            // Close along the chord at the rim.
            d += `L ${r} ${y0} L ${-r} ${y0} Z`
            return d
          })()}
          fill="var(--bg-subtle)"
          stroke="var(--ink-primary)"
          strokeWidth={SW_MAIN}
        />
        {/* Mesh lines (concentric arcs) */}
        {[0.4, 0.7].map((frac, i) => {
          const r = dishRadiusM * frac
          const f = 0.35 * dishDiamM
          const k = 1 / (4 * f)
          const y0 = -BUS_H_M / 2 - DISH_MARGIN_M
          const N = 8
          let d = ""
          for (let j = 0; j <= N; j++) {
            const x = -r + (2 * r * j) / N
            const y = y0 - k * x * x
            d += (j === 0 ? "M " : "L ") + x + " " + y + " "
          }
          return (
            <path
              key={`mesh${i}`}
              d={d}
              fill="none"
              stroke="var(--ink-tertiary)"
              strokeWidth={SW_HAIR}
              opacity={0.6}
            />
          )
        })}

        {/* Feed horn at the focus. This is what the drag handle adjusts. */}
        <g>
          {/* Support struts from feed to dish rim (3) */}
          {[-1, 0, 1].map((s, i) => {
            const rimX = s * dishRadiusM * 0.9
            const rimY = -BUS_H_M / 2 - DISH_MARGIN_M
            const feedX = 0
            const feedY = rimY - dishDiamM * 0.35
            return (
              <line
                key={`strut${i}`}
                x1={feedX}
                y1={feedY}
                x2={rimX}
                y2={rimY}
                stroke="var(--ink-tertiary)"
                strokeWidth={SW_HAIR}
              />
            )
          })}
          {/* Feed horn body */}
          <polygon
            points={`${-transmitter_aperture_m * 0.8},${-BUS_H_M / 2 - DISH_MARGIN_M - dishDiamM * 0.4}
                     ${transmitter_aperture_m * 0.8},${-BUS_H_M / 2 - DISH_MARGIN_M - dishDiamM * 0.4}
                     ${transmitter_aperture_m * 0.3},${-BUS_H_M / 2 - DISH_MARGIN_M - dishDiamM * 0.3}
                     ${-transmitter_aperture_m * 0.3},${-BUS_H_M / 2 - DISH_MARGIN_M - dishDiamM * 0.3}`}
            fill="var(--bg-surface)"
            stroke="var(--ink-primary)"
            strokeWidth={SW_MED}
          />
          {/* The emitter disk; drag handle */}
          <circle
            cx={0}
            cy={-BUS_H_M / 2 - DISH_MARGIN_M - dishDiamM * 0.3}
            r={Math.max(transmitter_aperture_m, vbW * 0.004)}
            fill="var(--status-orange)"
            stroke="var(--ink-primary)"
            strokeWidth={SW_MED}
            style={{ cursor: "ew-resize" }}
            data-testid="aperture-handle"
            {...handleDrag}
          />
          {/* Label */}
          <text
            x={0}
            y={-BUS_H_M / 2 - DISH_MARGIN_M - dishDiamM * 0.3 - Math.max(transmitter_aperture_m, vbW * 0.004) - FS * 0.3}
            textAnchor="middle"
            fontFamily="ui-monospace, monospace"
            fontSize={DIM_FS}
            fill="var(--ink-tertiary)"
          >
            w0 {transmitter_aperture_m >= 0.01
              ? `${(transmitter_aperture_m * 100).toFixed(1)} cm`
              : `${(transmitter_aperture_m * 1000).toFixed(1)} mm`}
          </text>
        </g>
      </g>

      {/* 5. Star tracker baffle tubes on zenith (+Y) face */}
      {[-0.7, 0.7].map((x, i) => (
        <g key={`st${i}`}>
          <rect
            x={x * BUS_W_M * 0.35 - BUS_W_M * 0.08}
            y={BUS_H_M / 2}
            width={BUS_W_M * 0.16}
            height={starTrackerLenM}
            fill="var(--bg-surface)"
            stroke="var(--ink-primary)"
            strokeWidth={SW_THIN}
          />
          <line
            x1={x * BUS_W_M * 0.35 - BUS_W_M * 0.08}
            y1={BUS_H_M / 2 + starTrackerLenM * 0.5}
            x2={x * BUS_W_M * 0.35 + BUS_W_M * 0.08}
            y2={BUS_H_M / 2 + starTrackerLenM * 0.5}
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_HAIR}
          />
        </g>
      ))}

      {/* 6. Thruster cluster on zenith face */}
      {[-0.25, 0.25].map((x, i) => (
        <g key={`th${i}`}>
          {/* Nozzle body */}
          <path
            d={`M ${x * BUS_W_M - BUS_W_M * 0.05} ${BUS_H_M / 2}
                L ${x * BUS_W_M + BUS_W_M * 0.05} ${BUS_H_M / 2}
                L ${x * BUS_W_M + BUS_W_M * 0.08} ${BUS_H_M / 2 + starTrackerLenM * 0.45}
                L ${x * BUS_W_M - BUS_W_M * 0.08} ${BUS_H_M / 2 + starTrackerLenM * 0.45} Z`}
            fill="var(--bg-subtle)"
            stroke="var(--ink-primary)"
            strokeWidth={SW_THIN}
          />
          {/* Plume cone (dashed) */}
          <path
            d={`M ${x * BUS_W_M - BUS_W_M * 0.08} ${BUS_H_M / 2 + starTrackerLenM * 0.45}
                L ${x * BUS_W_M - BUS_W_M * 0.16} ${BUS_H_M / 2 + starTrackerLenM * 1.05}
                L ${x * BUS_W_M + BUS_W_M * 0.16} ${BUS_H_M / 2 + starTrackerLenM * 1.05}
                L ${x * BUS_W_M + BUS_W_M * 0.08} ${BUS_H_M / 2 + starTrackerLenM * 0.45} Z`}
            fill="none"
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_HAIR}
            strokeDasharray={`${SW_HAIR * 5} ${SW_HAIR * 4}`}
            opacity={0.5}
          />
        </g>
      ))}

      {/* 7. TT&C antenna whips */}
      <line
        x1={-BUS_W_M / 2 + BUS_W_M * 0.05}
        y1={BUS_H_M / 2}
        x2={-BUS_W_M / 2 + BUS_W_M * 0.05 - starTrackerLenM * 0.8}
        y2={BUS_H_M / 2 + starTrackerLenM * 1.3}
        stroke="var(--ink-primary)"
        strokeWidth={SW_THIN}
      />
      <line
        x1={BUS_W_M / 2 - BUS_W_M * 0.05}
        y1={BUS_H_M / 2}
        x2={BUS_W_M / 2 - BUS_W_M * 0.05 + starTrackerLenM * 0.8}
        y2={BUS_H_M / 2 + starTrackerLenM * 1.3}
        stroke="var(--ink-primary)"
        strokeWidth={SW_THIN}
      />

      {/* 8. Dimension callouts */}
      {/* Total array span, bottom of the drawing */}
      {renderDimH(
        -(BUS_W_M / 2 + YOKE_L_M + arrayLenPerSideM),
        BUS_W_M / 2 + YOKE_L_M + arrayLenPerSideM,
        botY - margin * 0.35,
        `array span ${(2 * (BUS_W_M / 2 + YOKE_L_M + arrayLenPerSideM)).toFixed(1)} m`,
      )}
      {/* Bus width, just above bus */}
      {renderDimH(
        -BUS_W_M / 2,
        BUS_W_M / 2,
        BUS_H_M / 2 + starTrackerLenM * 1.4 + FS * 1.0,
        `bus ${BUS_W_M.toFixed(1)} m`,
      )}
      {/* Dish diameter, vertical to the left of the dish */}
      {renderDimV(
        -totalHalfWidth - margin * 0.35,
        -BUS_H_M / 2 - DISH_MARGIN_M,
        -BUS_H_M / 2 - DISH_MARGIN_M - dishDiamM,
        `Ø ${dishDiamM.toFixed(2)} m`,
      )}

      {/* 9. Scale bar */}
      <ScaleBar
        x={vbX + vbW * 0.05}
        y={vbY + vbH * 0.96}
        widthData={0.1 * vbW}
        label={`${Math.round(0.1 * vbW * 10) / 10} m`}
        fontSize={FS}
      />
    </svg>
  )
}
