/**
 * SatelliteProfileSVG — engineering side profile of the satellite.
 *
 * Every drawing element is a real physical feature whose dimension is
 * either a user parameter or a documented ratio. Constants and their
 * sources:
 *
 *   solar cell specific power  408 W/m^2 (triple-junction at AM0,
 *                              30 % cell efficiency; see beam.py for
 *                              the transmitter wall-plug figure).
 *   bus body                   1.8 m x 1.6 m (modest power satellite).
 *   panel chord                1.0 m.
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

// --- Physical constants -----------------------------------------------
const W_PER_M2 = 408.0
const N_PANELS_PER_SIDE = 3
const PANEL_CHORD_M = 1.0
const PANEL_GAP_M = 0.05
const BUS_W_M = 1.8
const BUS_H_M = 1.6
const YOKE_M = 0.4
const TRACKER_M = 0.6
const PLUME_M = 0.5
const DISH_MARGIN_M = 0.35

// --- Frame and content layout (pixels) --------------------------------
const FRAME_W = 820
const FRAME_H = 520
const ORIGIN_X = FRAME_W / 2
const ORIGIN_Y = FRAME_H / 2 + 30
const CONTENT_PAD_X = 60
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

  // --- Derived physical dimensions (metres) ---------------------------
  const totalAreaM2 = transmitter_power_w / W_PER_M2
  const perSideAreaM2 = totalAreaM2 / 2
  const panelLenM = perSideAreaM2 / N_PANELS_PER_SIDE / PANEL_CHORD_M
  const arrayPerSideM =
    N_PANELS_PER_SIDE * panelLenM + (N_PANELS_PER_SIDE - 1) * PANEL_GAP_M
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
      const pxM = startX + side * i * (panelLenM + PANEL_GAP_M)
      const drawXm = side > 0 ? pxM : pxM - panelLenM
      const [px, py] = toPx(drawXm, PANEL_CHORD_M / 2)
      const pw = w(panelLenM)
      const ph = w(PANEL_CHORD_M)
      panelEls.push(
        <g key={i}>
          <rect
            x={px}
            y={py}
            width={pw}
            height={ph}
            fill="var(--bg-subtle)"
            stroke="var(--ink-secondary)"
            strokeWidth={SW_MED}
          />
          {/* Cell divisions: 6 columns */}
          {Array.from({ length: 5 }).map((_, k) => {
            const cx = px + ((k + 1) * pw) / 6
            return (
              <line
                key={k}
                x1={cx}
                y1={py}
                x2={cx}
                y2={py + ph}
                stroke="var(--ink-tertiary)"
                strokeWidth={SW_HAIR}
              />
            )
          })}
          {/* Midline */}
          <line
            x1={px}
            y1={py + ph / 2}
            x2={px + pw}
            y2={py + ph / 2}
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_HAIR}
          />
          {/* Hinge brackets at the inner edge */}
          {i > 0 && (
            <g>
              <circle
                cx={side > 0 ? px : px + pw}
                cy={py + ph * 0.22}
                r={2.4}
                fill="var(--bg-surface)"
                stroke="var(--ink-primary)"
                strokeWidth={SW_HAIR}
              />
              <circle
                cx={side > 0 ? px : px + pw}
                cy={py + ph * 0.78}
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
    return (
      <g>
        <line x1={x1} y1={y} x2={x2} y2={y} stroke="var(--ink-tertiary)" strokeWidth={SW_HAIR} />
        <line x1={x1} y1={y - tick} x2={x1} y2={y + tick} stroke="var(--ink-tertiary)" strokeWidth={SW_HAIR} />
        <line x1={x2} y1={y - tick} x2={x2} y2={y + tick} stroke="var(--ink-tertiary)" strokeWidth={SW_HAIR} />
        <text
          x={(x1 + x2) / 2}
          y={y - tick - 3}
          textAnchor="middle"
          fontFamily="ui-monospace, monospace"
          fontSize={8}
          fill="var(--ink-tertiary)"
        >
          {label}
        </text>
      </g>
    )
  }

  // --- Callout positions ----------------------------------------------
  // Anchor: physical position. Label: pixel position of the label text.
  const leftLabelX = 70
  const rightLabelX = 750
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
    const [ax, ay] = toPx(-(BUS_W_M / 2 + YOKE_M + panelLenM * 0.5), PANEL_CHORD_M * 0.6)
    callouts.push({
      ax,
      ay,
      lx: leftLabelX,
      ly: 100,
      label: "SOLAR ARRAY",
      sublabel: `3 panels / wing · ${totalAreaM2.toFixed(1)} m² total`,
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
      ly: 175,
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
      ly: 220,
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
      ly: 260,
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
      ly: 320,
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
      ly: 320,
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
      ly: 220,
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
      ly: 175,
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
      ly: 130,
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
      ly: 100,
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
      style={{ maxHeight: 560, touchAction: "none" }}
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
        footnote="dimensions derived from physical parameters; see body for equations"
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
          botY_M - 0.4,
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
          x={feedPx}
          y={feedPy + 30}
          textAnchor="middle"
          fontFamily="ui-monospace, monospace"
          fontSize={8}
          fill="var(--ink-tertiary)"
        >
          drag to widen aperture
        </text>

        {/* Callouts */}
        {callouts.map((c, i) => (
          <Callout
            key={i}
            x={c.ax}
            y={c.ay}
            labelX={c.lx}
            labelY={c.ly}
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
