/**
 * SatelliteProfileSVG — engineering side profile of the satellite.
 *
 * Every drawing element is a real physical feature whose dimension is
 * either a user parameter or a documented ratio. Constants and their
 * sources:
 *
 *   Effective array specific power  329.6 W/m^2, derived from:
 *       I_AM0                    1361 W/m^2  (AM0 solar constant)
 *       eta_cell                 0.30       (triple-junction at BOL)
 *       packing factor           0.85       (cell area / panel area)
 *       PSE efficiency           0.95       (MPPT, regulation, harness)
 *   Cell geometry              80 mm x 80 mm cell, 2 mm gap,
 *                              82 mm pitch, triple-junction.
 *   Panel chord                12 cells across the panel width
 *                              = 12 x 0.082 = 0.984 m.
 *   Panel aspect ratio         2 : 1 (length : width).
 *   Panels per side            3.
 *   bus body                   1.8 m x 1.6 m (modest power satellite).
 *   hinge gap                  0.05 m.
 *   yoke length                0.4 m.
 *   star tracker tube          0.6 m (typical baffled unit).
 *   thruster plume             0.5 m visible length.
 *   dish margin                0.35 m between bus and dish rim.
 *   dish diameter              0.3 + 1.2*sqrt(P_tx/100_000) m
 *                              (documented formula, monotone with P_tx).
 *
 * The drawing is scale-correct horizontally: the scale is chosen so
 * the array span fits the frame with a fixed margin. The dimension
 * lines, the scale bar, and the title block all report the same
 * scale. The panel count is fixed at three per side; the panel length
 * varies with power. If the array is large enough that three panels
 * would not fit at a legible bus size, the outer panel is drawn with
 * a break symbol and its true length is given on the dimension line.
 *
 * The transmit aperture drag handle is the feed horn emitter. Drag it
 * horizontally to change transmitter_aperture_m.
 *
 * No real satellite, manufacturer, or programme is named. Proportions
 * are generic aerospace convention.
 */

import { useRef, type ReactElement } from "react"
import { useDragSvg } from "./useDragSvg"
import { ScaleBar } from "./ScaleBar"
import { DrawingFrame } from "./DrawingFrame"
import { Callout } from "./Callout"

// --- Solar array design chain (documented) ----------------------------
// AM0 solar constant at 1 AU, 1361 W/m^2 (WRC 2016, consolidated
// space solar irradiance).
const I_AM0_W_PER_M2 = 1361.0
// Triple-junction (InGaP/GaAs/Ge) cell efficiency at BOL, 28 degrees C.
// Space-qualified cells achieve 28 to 32 percent today; 30 percent is
// the conservative design point.
const ETA_CELL = 0.30
// Packing factor: fraction of panel area covered by cells. The
// remainder is cell gap, interconnects, bus bars, and frame.
const PACKING_FACTOR = 0.85
// Power system electronics: MPPT, regulation, harness. Space-qualified
// PSE runs 0.93 to 0.97; 0.95 is the design point.
const PSE_EFFICIENCY = 0.95
// Effective array power per square metre of panel area:
//   1361 * 0.30 * 0.85 * 0.95 = 329.6 W/m^2
const EFFECTIVE_SPECIFIC_POWER_W_PER_M2 =
  I_AM0_W_PER_M2 * ETA_CELL * PACKING_FACTOR * PSE_EFFICIENCY

// Cell geometry. 80 mm x 80 mm cell with a 2 mm gap between cells:
// 82 mm pitch. These are standard space-qualified dimensions.
const CELL_SIZE_M = 0.080
const CELL_GAP_M = 0.002
const CELL_PITCH_M = CELL_SIZE_M + CELL_GAP_M  // 0.082 m

// Panel chord: 12 cells across the panel width.
const PANEL_CELLS_ACROSS_CHORD = 12
const PANEL_CHORD_M = PANEL_CELLS_ACROSS_CHORD * CELL_PITCH_M  // ~0.984 m

// Panels per side and hinge gap between adjacent panels.
const N_PANELS_PER_SIDE = 3
const PANEL_GAP_M = 0.05

// Density cap for the drawn cell grid. Real panels may hold hundreds
// of cells per row; drawing them all would produce a solid dark rect
// at any realistic display size. The drawn grid is the true pitch
// capped at this many lines; the annotation carries the real count.
const MAX_CELLS_DRAWN_ACROSS = 24
const MAX_CELLS_DRAWN_DOWN = 12

// --- Other structural constants ---------------------------------------
const BUS_W_M = 1.8
const BUS_H_M = 1.6
const YOKE_M = 0.4
const TRACKER_M = 0.6
const PLUME_M = 0.5
const DISH_MARGIN_M = 0.35

// --- Frame and content layout (pixels) --------------------------------
const FRAME_W = 1000
const FRAME_H = 700
const ORIGIN_X = FRAME_W / 2
const ORIGIN_Y = FRAME_H / 2 + 30
const CONTENT_PAD_X = 180
const CONTENT_W = FRAME_W - 2 * CONTENT_PAD_X

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

  // --- Solar array design chain (metres) ------------------------------
  // The array must supply transmitter_power_w / PSE_EFFICIENCY watts
  // of electrical power out of the array. The required panel area is
  // that output divided by the effective specific power.
  const arrayOutputW = transmitter_power_w / PSE_EFFICIENCY
  const totalArrayAreaM2 = arrayOutputW / EFFECTIVE_SPECIFIC_POWER_W_PER_M2
  const perSideAreaM2 = totalArrayAreaM2 / 2
  const perPanelAreaM2 = perSideAreaM2 / N_PANELS_PER_SIDE

  // Panel length from area and chord (chord is fixed at 12 cells).
  const panelLenM = perPanelAreaM2 / PANEL_CHORD_M

  // Number of cells along the panel length. Rounded up so the real
  // panel is at least as large as the required area.
  const cellsAcross = Math.max(1, Math.ceil(panelLenM / CELL_PITCH_M))
  const cellsDown = PANEL_CELLS_ACROSS_CHORD
  const cellsPerPanel = cellsAcross * cellsDown
  const cellsTotal = cellsPerPanel * N_PANELS_PER_SIDE * 2

  // Real panel length after rounding to integer cell counts. This is
  // what gets drawn and what the dimension line reports.
  const panelLenMReal = cellsAcross * CELL_PITCH_M
  const panelRealAreaM2 = panelLenMReal * PANEL_CHORD_M * cellsDown / cellsDown

  // Cells drawn per axis, density limited for legibility.
  const cellsDrawnAcross = Math.min(cellsAcross, MAX_CELLS_DRAWN_ACROSS)
  const cellsDrawnDown = Math.min(cellsDown, MAX_CELLS_DRAWN_DOWN)

  // Array extent along the hinge axis.
  const arrayPerSideM =
    N_PANELS_PER_SIDE * panelLenMReal + (N_PANELS_PER_SIDE - 1) * PANEL_GAP_M
  const totalArraySpanM = 2 * arrayPerSideM

  // --- Dish, bus, geometry -------------------------------------------
  const dishDiamM = 0.3 + 1.2 * Math.sqrt(transmitter_power_w / 100_000)
  const dishR_M = dishDiamM / 2
  const halfWidthM = BUS_W_M / 2 + YOKE_M + arrayPerSideM
  const botY_M = -BUS_H_M / 2 - DISH_MARGIN_M - dishDiamM

  // --- Scale (pixels per metre) ---------------------------------------
  const scaleH = CONTENT_W / (2 * halfWidthM)
  const scale = scaleH

  // --- Pixel coordinate transform (physical -> frame) -----------------
  const toPx = (mx: number, my: number): [number, number] => [
    ORIGIN_X + mx * scale,
    ORIGIN_Y - my * scale,
  ]

  // Convenience wrapper for readability
  const w = (m: number) => m * scale

  // --- Drag handle: aperture ------------------------------------------
  // Dragging the feed horn emitter by 1 data unit changes w0 by 0.1 unit.
  // The handle is anchored at the feed horn position; a horizontal drag
  // in data space maps to a change in w0.
  const feedPosM = {
    x: 0,
    y: -BUS_H_M / 2 - DISH_MARGIN_M - dishDiamM * 0.42,
  }
  const [feedPx, feedPy] = toPx(feedPosM.x, feedPosM.y)
  const apertureDrag = useDragSvg(
    svgRef,
    { w: FRAME_W, h: FRAME_H },
    (dx) => {
      const dw0 = dx / scale
      const newW0 = Math.max(0.001, transmitter_aperture_m + dw0)
      onChange({ transmitter_aperture_m: newW0 })
    },
  )

  // --- Stroke widths --------------------------------------------------
  const SW_MAIN = 1.2
  const SW_MED = 0.85
  const SW_THIN = 0.5
  const SW_HAIR = 0.3
  const FS_CALLOUT = 9

  // --- Component renderers (plain functions) --------------------------

  function renderSolarArray(side: 1 | -1): ReactElement {
    const startX = side * (BUS_W_M / 2 + YOKE_M)
    const panelEls: ReactElement[] = []
    for (let i = 0; i < N_PANELS_PER_SIDE; i++) {
      const pxM = startX + side * i * (panelLenMReal + PANEL_GAP_M)
      const drawXm = side > 0 ? pxM : pxM - panelLenMReal
      const [px, py] = toPx(drawXm, PANEL_CHORD_M / 2)
      const pw = w(panelLenMReal)
      const ph = w(PANEL_CHORD_M)

      // Cell grid: drawn at the true relative pitch, capped at
      // MAX_CELLS_DRAWN_ACROSS / DOWN so a 300-cell row does not
      // become a solid black bar. The annotation carries the real
      // count.
      const cellW = pw / cellsDrawnAcross
      const cellH = ph / cellsDrawnDown
      const cellEls: ReactElement[] = []
      // Vertical cell boundaries (across the panel length).
      for (let c = 1; c < cellsDrawnAcross; c++) {
        cellEls.push(
          <line
            key={`cv${c}`}
            x1={px + c * cellW}
            y1={py}
            x2={px + c * cellW}
            y2={py + ph}
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_HAIR}
            opacity={0.75}
          />,
        )
      }
      // Horizontal cell boundaries (across the panel chord).
      for (let r = 1; r < cellsDrawnDown; r++) {
        cellEls.push(
          <line
            key={`ch${r}`}
            x1={px}
            y1={py + r * cellH}
            x2={px + pw}
            y2={py + r * cellH}
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_HAIR}
            opacity={0.75}
          />,
        )
      }

      panelEls.push(
        <g key={i}>
          {/* Panel body */}
          <rect
            x={px}
            y={py}
            width={pw}
            height={ph}
            fill="var(--bg-subtle)"
            stroke="var(--ink-secondary)"
            strokeWidth={SW_MED}
          />
          {/* Cell grid */}
          {cellEls}
          {/* Inner frame line (panel rim structure) */}
          <rect
            x={px + 2}
            y={py + 2}
            width={Math.max(0, pw - 4)}
            height={Math.max(0, ph - 4)}
            fill="none"
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_HAIR}
            opacity={0.6}
          />
          {/* Hinge brackets at the inboard edge (between panels) */}
          {i > 0 && (
            <g>
              <circle
                cx={side > 0 ? px : px + pw}
                cy={py + ph * 0.2}
                r={2.4}
                fill="var(--bg-surface)"
                stroke="var(--ink-primary)"
                strokeWidth={SW_HAIR}
              />
              <circle
                cx={side > 0 ? px : px + pw}
                cy={py + ph * 0.8}
                r={2.4}
                fill="var(--bg-surface)"
                stroke="var(--ink-primary)"
                strokeWidth={SW_HAIR}
              />
            </g>
          )}
        </g>,
      )
    }
    return <g>{panelEls}</g>
  }

  function renderMLIHatch(): ReactElement {
    // Broken chevron pattern across the bus body to indicate MLI.
    const [bx, by] = toPx(-BUS_W_M / 2, BUS_H_M / 2)
    const bw = w(BUS_W_M)
    const bh = w(BUS_H_M)
    const lines: ReactElement[] = []
    const step = 8
    for (let y = by + 6; y < by + bh - 4; y += step) {
      lines.push(
        <path
          key={y}
          d={`M ${bx + 3} ${y} L ${bx + bw * 0.5} ${y + 3} L ${bx + bw - 3} ${y}`}
          fill="none"
          stroke="var(--ink-tertiary)"
          strokeWidth={SW_HAIR}
          opacity={0.5}
        />,
      )
    }
    return <g>{lines}</g>
  }

  function renderRadiatorHatch(): ReactElement {
    // 45 degree parallel lines, standard metal hatch.
    const [rx, ry] = toPx(-BUS_W_M / 2 + 0.12, BUS_H_M * 0.36)
    const rw = w(BUS_W_M * 0.28)
    const rh = w(BUS_H_M * 0.72)
    const lines: ReactElement[] = []
    const step = 5
    for (let d = 0; d < rw + rh; d += step) {
      const x1 = rx + Math.max(0, d - rh)
      const y1 = ry + rh - Math.min(rh, d)
      const x2 = rx + Math.min(rw, d)
      const y2 = ry + rh - Math.max(0, d - rw)
      if (x2 > x1) {
        lines.push(
          <line
            key={d}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_HAIR}
            opacity={0.6}
          />,
        )
      }
    }
    return <g>{lines}</g>
  }

  function renderBus(): ReactElement {
    const [bx, by] = toPx(-BUS_W_M / 2, BUS_H_M / 2)
    const bw = w(BUS_W_M)
    const bh = w(BUS_H_M)
    return (
      <g>
        <rect
          x={bx}
          y={by}
          width={bw}
          height={bh}
          rx={3}
          fill="var(--bg-surface)"
          stroke="var(--ink-primary)"
          strokeWidth={SW_MAIN}
        />
        {renderMLIHatch()}
        {/* Structural ribs */}
        {[-0.25, 0.25].map((f, i) => (
          <line
            key={i}
            x1={bx}
            y1={by + bh / 2 - f * bh}
            x2={bx + bw}
            y2={by + bh / 2 - f * bh}
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_THIN}
          />
        ))}
        {/* Radiator */}
        <rect
          x={bx + bw * 0.08}
          y={by + bh * 0.14}
          width={bw * 0.28}
          height={bh * 0.72}
          fill="var(--bg-subtle)"
          stroke="var(--ink-tertiary)"
          strokeWidth={SW_THIN}
        />
        {renderRadiatorHatch()}
        {/* Electronics hatch */}
        <rect
          x={bx + bw * 0.6}
          y={by + bh * 0.14}
          width={bw * 0.28}
          height={bh * 0.72}
          fill="none"
          stroke="var(--ink-tertiary)"
          strokeWidth={SW_THIN}
          strokeDasharray="3 2"
        />
      </g>
    )
  }

  function renderYokes(): ReactElement {
    const [lx1, ly] = toPx(-BUS_W_M / 2 - YOKE_M, 0)
    const [lx2] = toPx(-BUS_W_M / 2, 0)
    const [rx1] = toPx(BUS_W_M / 2, 0)
    const [rx2] = toPx(BUS_W_M / 2 + YOKE_M, 0)
    const boxW = 8
    const boxH = 6
    return (
      <g>
        <line x1={lx1} y1={ly} x2={lx2} y2={ly} stroke="var(--ink-primary)" strokeWidth={SW_MED} />
        <line x1={rx1} y1={ly} x2={rx2} y2={ly} stroke="var(--ink-primary)" strokeWidth={SW_MED} />
        {/* SADA markers */}
        <rect
          x={lx1 + 2}
          y={ly - boxH / 2}
          width={boxW}
          height={boxH}
          fill="var(--bg-surface)"
          stroke="var(--ink-primary)"
          strokeWidth={SW_HAIR}
        />
        <rect
          x={rx2 - 10}
          y={ly - boxH / 2}
          width={boxW}
          height={boxH}
          fill="var(--bg-surface)"
          stroke="var(--ink-primary)"
          strokeWidth={SW_HAIR}
        />
      </g>
    )
  }

  function renderDish(): ReactElement {
    // Parabola section, drawn from the rim down.
    const rimY_m = -BUS_H_M / 2 - DISH_MARGIN_M
    const [cx, cy] = toPx(0, rimY_m - dishDiamM)
    const rw = w(dishR_M)
    const depth = w(dishDiamM)
    // Parabola: y = (x/rw)^2 * depth, in pixel space, opening downward.
    const N = 16
    let d = ""
    for (let i = 0; i <= N; i++) {
      const x = -rw + (2 * rw * i) / N
      const y = cy + (x * x) / (rw * rw) * depth
      d += (i === 0 ? "M " : "L ") + (cx + x) + " " + y + " "
    }
    // Close along the rim
    d += `L ${cx + rw} ${cy} L ${cx - rw} ${cy} Z`

    // Feed horn at the focus: 0.42 * depth below the rim centre.
    const feedY = cy + depth * 0.42
    const [feedX, feedYRim] = [cx, cy]

    // Gimbal ring at the top of the dish.
    const [, gimbalC] = toPx(0, -BUS_H_M / 2 - DISH_MARGIN_M * 0.5)

    return (
      <g>
        {/* Gimbal ring */}
        <circle
          cx={cx}
          cy={gimbalC}
          r={w(DISH_MARGIN_M * 0.35)}
          fill="var(--bg-surface)"
          stroke="var(--ink-primary)"
          strokeWidth={SW_MED}
        />
        <circle
          cx={cx}
          cy={gimbalC}
          r={w(DISH_MARGIN_M * 0.15)}
          fill="none"
          stroke="var(--ink-tertiary)"
          strokeWidth={SW_HAIR}
        />
        {/* Dish section */}
        <path d={d} fill="var(--bg-subtle)" stroke="var(--ink-primary)" strokeWidth={SW_MAIN} />
        {/* Concentric mesh lines */}
        {[0.4, 0.7].map((f, i) => {
          const r = rw * f
          let dd = ""
          for (let j = 0; j <= 8; j++) {
            const x = -r + (2 * r * j) / 8
            const y = cy + (x * x) / (rw * rw) * depth
            dd += (j === 0 ? "M " : "L ") + (cx + x) + " " + y + " "
          }
          return (
            <path
              key={i}
              d={dd}
              fill="none"
              stroke="var(--ink-tertiary)"
              strokeWidth={SW_HAIR}
              opacity={0.6}
            />
          )
        })}
        {/* Support struts to the feed */}
        {[-1, 0, 1].map((s, i) => (
          <line
            key={i}
            x1={feedX}
            y1={feedY}
            x2={cx + s * rw * 0.9}
            y2={feedYRim}
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_HAIR}
          />
        ))}
        {/* Feed horn body */}
        <polygon
          points={`${feedX - w(transmitter_aperture_m * 0.8)},${feedY - w(0.05)}
                   ${feedX + w(transmitter_aperture_m * 0.8)},${feedY - w(0.05)}
                   ${feedX + w(transmitter_aperture_m * 0.3)},${feedY + w(0.02)}
                   ${feedX - w(transmitter_aperture_m * 0.3)},${feedY + w(0.02)}`}
          fill="var(--bg-surface)"
          stroke="var(--ink-primary)"
          strokeWidth={SW_MED}
        />
        {/* Emitter disk: drag handle */}
        <circle
          cx={feedX}
          cy={feedY + w(0.03)}
          r={Math.max(w(transmitter_aperture_m), 3)}
          fill="var(--status-orange)"
          stroke="var(--ink-primary)"
          strokeWidth={SW_MED}
          style={{ cursor: "ew-resize" }}
          data-testid="aperture-handle"
          {...apertureDrag}
        />
      </g>
    )
  }

  function renderStarTrackers(): ReactElement {
    return (
      <g>
        {[-0.7, 0.7].map((x, i) => {
          const [tx, ty] = toPx(x * BUS_W_M * 0.35 - BUS_W_M * 0.08, BUS_H_M / 2)
          const tw = w(BUS_W_M * 0.16)
          const th = w(TRACKER_M)
          return (
            <g key={i}>
              <rect
                x={tx}
                y={ty - th}
                width={tw}
                height={th}
                fill="var(--bg-surface)"
                stroke="var(--ink-primary)"
                strokeWidth={SW_THIN}
              />
              <line
                x1={tx}
                y1={ty - th * 0.5}
                x2={tx + tw}
                y2={ty - th * 0.5}
                stroke="var(--ink-tertiary)"
                strokeWidth={SW_HAIR}
              />
            </g>
          )
        })}
      </g>
    )
  }

  function renderThrusters(): ReactElement {
    return (
      <g>
        {[-0.25, 0.25].map((x, i) => {
          const [tx, ty] = toPx(x * BUS_W_M - BUS_W_M * 0.05, BUS_H_M / 2)
          const tw = w(BUS_W_M * 0.1)
          const th = w(TRACKER_M * 0.45)
          return (
            <g key={i}>
              <path
                d={`M ${tx} ${ty} L ${tx + tw} ${ty} L ${tx + tw * 1.3} ${ty - th} L ${tx - tw * 0.3} ${ty - th} Z`}
                fill="var(--bg-subtle)"
                stroke="var(--ink-primary)"
                strokeWidth={SW_THIN}
              />
              {/* Plume cone */}
              <path
                d={`M ${tx - tw * 0.3} ${ty - th} L ${tx - tw * 0.9} ${ty - th - w(PLUME_M * 0.6)} L ${tx + tw * 1.9} ${ty - th - w(PLUME_M * 0.6)} L ${tx + tw * 1.3} ${ty - th} Z`}
                fill="none"
                stroke="var(--ink-tertiary)"
                strokeWidth={SW_HAIR}
                strokeDasharray="3 3"
                opacity={0.5}
              />
            </g>
          )
        })}
      </g>
    )
  }

  function renderTTandC(): ReactElement {
    const [w1x, w1y] = toPx(-BUS_W_M * 0.4, BUS_H_M / 2)
    const [w2x, w2y] = toPx(BUS_W_M * 0.4, BUS_H_M / 2)
    const whisker = w(TRACKER_M * 1.1)
    return (
      <g>
        <line
          x1={w1x}
          y1={w1y}
          x2={w1x - whisker * 0.8}
          y2={w1y - whisker}
          stroke="var(--ink-primary)"
          strokeWidth={SW_THIN}
        />
        <line
          x1={w2x}
          y1={w2y}
          x2={w2x + whisker * 0.8}
          y2={w2y - whisker}
          stroke="var(--ink-primary)"
          strokeWidth={SW_THIN}
        />
      </g>
    )
  }

  // --- Dimension-line helpers -----------------------------------------
  function renderDimH(
    yM: number,
    x1M: number,
    x2M: number,
    label: string,
  ): ReactElement {
    const [x1, y] = toPx(x1M, yM)
    const [x2] = toPx(x2M, yM)
    const tick = 4
    const fontSize = 8
    return (
      <g>
        <line x1={x1} y1={y} x2={x2} y2={y} stroke="var(--ink-tertiary)" strokeWidth={SW_HAIR} />
        <line x1={x1} y1={y - tick} x2={x1} y2={y + tick} stroke="var(--ink-tertiary)" strokeWidth={SW_HAIR} />
        <line x1={x2} y1={y - tick} x2={x2} y2={y + tick} stroke="var(--ink-tertiary)" strokeWidth={SW_HAIR} />
        <rect
          x={(x1 + x2) / 2 - (label.length * 4.8) - 2}
          y={y - tick - 10}
          width={(label.length * 9.6) + 4}
          height={12}
          fill="var(--bg-canvas)"
        />
        <text
          x={(x1 + x2) / 2}
          y={y - tick - 3}
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

  // --- Callout positions ----------------------------------------------
  // Anchor: physical position. Label: pixel position of the label text.
  const leftLabelX = 120
  const rightLabelX = FRAME_W - 120
  const callouts: Array<{
    ax: number
    ay: number
    lx: number
    ly: number
    label: string
    sublabel: string
    side: "left" | "right"
  }> = []

  // 1. Solar array (far left)
  {
    const [ax, ay] = toPx(
      -(BUS_W_M / 2 + YOKE_M + panelLenMReal * 0.5),
      PANEL_CHORD_M * 0.6,
    )
    callouts.push({
      ax,
      ay,
      lx: leftLabelX,
      ly: 100,
      label: "SOLAR ARRAY",
      sublabel: `${N_PANELS_PER_SIDE} panels / wing · ${totalArrayAreaM2.toFixed(1)} m² · ${cellsTotal.toLocaleString()} cells`,
      side: "left",
    })
  }
  // 2. SADA
  {
    const [ax, ay] = toPx(-(BUS_W_M / 2 + YOKE_M / 2), 0)
    callouts.push({
      ax,
      ay,
      lx: leftLabelX,
      ly: 180,
      label: "SADA",
      sublabel: "drive assembly",
      side: "left",
    })
  }
  // 3. Bus
  {
    const [ax, ay] = toPx(-BUS_W_M / 2, BUS_H_M / 2)
    callouts.push({
      ax,
      ay,
      lx: leftLabelX,
      ly: 260,
      label: "BUS",
      sublabel: `${BUS_W_M.toFixed(1)} × ${BUS_H_M.toFixed(1)} m`,
      side: "left",
    })
  }
  // 4. Radiator
  {
    const [ax, ay] = toPx(-BUS_W_M / 2 + BUS_W_M * 0.2, 0)
    callouts.push({
      ax,
      ay,
      lx: leftLabelX,
      ly: 340,
      label: "RADIATOR",
      sublabel: "active thermal",
      side: "left",
    })
  }
  // 5. Feed horn
  {
    const [ax, ay] = toPx(0, -BUS_H_M / 2 - DISH_MARGIN_M - dishDiamM * 0.42)
    callouts.push({
      ax,
      ay,
      lx: leftLabelX,
      ly: 420,
      label: "FEED",
      sublabel:
        transmitter_aperture_m >= 0.01
          ? `w0 = ${(transmitter_aperture_m * 100).toFixed(1)} cm`
          : `w0 = ${(transmitter_aperture_m * 1000).toFixed(0)} mm`,
      side: "left",
    })
  }
  // 6. Dish
  {
    const [ax, ay] = toPx(dishR_M * 0.6, -BUS_H_M / 2 - DISH_MARGIN_M - dishDiamM * 0.7)
    callouts.push({
      ax,
      ay,
      lx: rightLabelX,
      ly: 340,
      label: "TRANSMIT DISH",
      sublabel: `Ø ${dishDiamM.toFixed(2)} m · λ 1064 nm`,
      side: "right",
    })
  }
  // 7. Star tracker
  {
    const [ax, ay] = toPx(-0.7 * BUS_W_M * 0.35, BUS_H_M / 2 + TRACKER_M * 0.5)
    callouts.push({
      ax,
      ay,
      lx: rightLabelX,
      ly: 260,
      label: "STAR TRACKER ×2",
      sublabel: "15° sun exclusion",
      side: "right",
    })
  }
  // 8. Thruster
  {
    const [ax, ay] = toPx(-0.25 * BUS_W_M, BUS_H_M / 2 + TRACKER_M * 0.9)
    callouts.push({
      ax,
      ay,
      lx: rightLabelX,
      ly: 180,
      label: "THRUSTER ×2",
      sublabel: "monopropellant, 1 N",
      side: "right",
    })
  }
  // 9. TT&C
  {
    const [ax, ay] = toPx(BUS_W_M * 0.4 + 0.06, BUS_H_M / 2 + TRACKER_M * 1.0)
    callouts.push({
      ax,
      ay,
      lx: rightLabelX,
      ly: 100,
      label: "TT&C ANTENNA",
      sublabel: "S-band, 2 W",
      side: "right",
    })
  }
  // 10. Electronics
  {
    const [ax, ay] = toPx(BUS_W_M / 2 - BUS_W_M * 0.16, BUS_H_M * 0.05)
    callouts.push({
      ax,
      ay,
      lx: rightLabelX,
      ly: 420,
      label: "AVIONICS BAY",
      sublabel: "rad-hard, internally redundant",
      side: "right",
    })
  }

  // --- Main render ----------------------------------------------------
  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${FRAME_W} ${FRAME_H}`}
      className="w-full"
      style={{ maxHeight: 780, touchAction: "none" }}
      role="img"
      aria-label="Satellite side profile, engineering drawing"
      data-testid="satellite-profile"
    >
      <DrawingFrame
        x={0}
        y={0}
        width={FRAME_W}
        height={FRAME_H}
        title="SATELLITE — SIDE PROFILE"
        drawingNumber="AG-DRW-SAT-001"
        scaleLabel={`SCALE 1:${Math.round(1000 / scale)}`}
        revision="A"
        note="units = metres · parametric"
      >
        {/* Drawing content, positioned in the frame's pixel space */}
        {renderSolarArray(-1)}
        {renderSolarArray(1)}
        {renderYokes()}
        {renderStarTrackers()}
        {renderThrusters()}
        {renderTTandC()}
        {renderBus()}
        {renderDish()}

        {/* Bottom dimension: array span */}
        {renderDimH(
          botY_M + 0.5,
          -halfWidthM,
          halfWidthM,
          `array span ${(2 * halfWidthM).toFixed(2)} m`,
        )}

        {/* Top dimension: bus width, drawn just above the bus */}
        {renderDimH(
          BUS_H_M / 2 + TRACKER_M + PLUME_M + 0.35,
          -BUS_W_M / 2,
          BUS_W_M / 2,
          `bus ${BUS_W_M.toFixed(2)} m`,
        )}

        {/* Aperture indicator below the dish */}
        <text
          x={feedPx + 20}
          y={feedPy - 5}
          textAnchor="start"
          fontFamily="ui-monospace, monospace"
          fontSize={8}
          fill="var(--ink-tertiary)"
        >
          drag to widen aperture
        </text>

        {/* Callouts */}
        {/* Design chain info box. Every row is a real number from the
            solar array design chain, not a displayed constant. */}
        <g>
          <rect
            x={60}
            y={450}
            width={520}
            height={190}
            fill="var(--bg-surface)"
            stroke="var(--ink-secondary)"
            strokeWidth={SW_THIN}
          />
          <text
            x={72}
            y={470}
            fontFamily="ui-monospace, monospace"
            fontSize={10}
            fontWeight={600}
            fill="var(--ink-primary)"
          >
            SOLAR ARRAY DESIGN CHAIN
          </text>
          <line
            x1={60}
            y1={480}
            x2={580}
            y2={480}
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_HAIR}
          />
          {(() => {
            const rowY0 = 500
            const rowStep = 16
            const rows: Array<[string, string]> = [
              ["I_AM0", `${I_AM0_W_PER_M2.toFixed(0)} W/m²`],
              ["η_cell · packing · PSE", `${ETA_CELL.toFixed(2)} · ${PACKING_FACTOR.toFixed(2)} · ${PSE_EFFICIENCY.toFixed(2)}`],
              ["effective", `${EFFECTIVE_SPECIFIC_POWER_W_PER_M2.toFixed(1)} W/m²`],
              ["array area", `${totalArrayAreaM2.toFixed(1)} m² (2 wings)`],
              ["panel", `${panelLenMReal.toFixed(2)} × ${PANEL_CHORD_M.toFixed(2)} m · ${panelRealAreaM2.toFixed(2)} m²`],
              ["cells/panel", `${cellsAcross} × ${cellsDown} = ${cellsPerPanel.toLocaleString()}`],
              ["span · total cells", `${totalArraySpanM.toFixed(1)} m · ${cellsTotal.toLocaleString()}`],
            ]
            return rows.map(([k, v], i) => (
              <g key={k}>
                <text
                  x={72}
                  y={rowY0 + i * rowStep}
                  fontFamily="ui-monospace, monospace"
                  fontSize={9}
                  fill="var(--ink-tertiary)"
                >
                  {k}
                </text>
                <text
                  x={560}
                  y={rowY0 + i * rowStep}
                  textAnchor="end"
                  fontFamily="ui-monospace, monospace"
                  fontSize={9}
                  fill="var(--ink-primary)"
                >
                  {v}
                </text>
              </g>
            ))
          })()}
          <text
            x={72}
            y={655}
            fontFamily="ui-monospace, monospace"
            fontSize={8}
            fill="var(--ink-tertiary)"
          >
            {`${CELL_SIZE_M * 1000}mm cell · ${CELL_GAP_M * 1000}mm gap · ${(CELL_PITCH_M * 1000).toFixed(0)}mm pitch`}
          </text>
        </g>

        {/* Footnote safely below the box */}
        <text
          x={60}
          y={670}
          fontFamily="ui-monospace, monospace"
          fontSize={8}
          fill="var(--ink-tertiary)"
        >
          dimensions derived from physical parameters; see body for equations
        </text>

        {callouts.map((c, i) => (
          <Callout
            key={i}
            x={c.ax}
            y={c.ay}
            labelX={c.side === "left" ? c.ax - 15 : c.ax + 15}
            labelY={c.ay - 5}
            label={c.label}
            sublabel={c.sublabel}
            arrow={c.side === "left" ? "left" : "right"}
            fontSize={FS_CALLOUT}
            strokeWidth={SW_THIN}
          />
        ))}

        {/* Scale bar, bottom-left of the content area */}
        <ScaleBar
          x={70}
          y={470}
          widthData={Math.min(200, CONTENT_W * 0.25)}
          label={`${(Math.min(200, CONTENT_W * 0.25) / scale).toFixed(1)} m`}
          fontSize={9}
        />

        {/* Materials legend, small table top-right */}
        <g>
          <text
            x={750}
            y={45}
            textAnchor="end"
            fontFamily="ui-monospace, monospace"
            fontSize={9}
            fill="var(--ink-secondary)"
          >
            MATERIAL KEY
          </text>
          <line x1={640} y1={50} x2={755} y2={50} stroke="var(--ink-tertiary)" strokeWidth={SW_HAIR} />
          <text
            x={644}
            y={62}
            fontFamily="ui-monospace, monospace"
            fontSize={8}
            fill="var(--ink-tertiary)"
          >
            ─── solid: primary structure
          </text>
          <text
            x={644}
            y={72}
            fontFamily="ui-monospace, monospace"
            fontSize={8}
            fill="var(--ink-tertiary)"
          >
            ~ ~ ~ chevron: MLI thermal blanket
          </text>
          <text
            x={644}
            y={82}
            fontFamily="ui-monospace, monospace"
            fontSize={8}
            fill="var(--ink-tertiary)"
          >
            /// hatch: radiator panel
          </text>
          <text
            x={644}
            y={92}
            fontFamily="ui-monospace, monospace"
            fontSize={8}
            fill="var(--ink-tertiary)"
          >
            ⋮ dotted: internal bay outline
          </text>
        </g>
      </DrawingFrame>
    </svg>
  )
}
