/**
 * SatelliteBusDiagram — engineering profile of the satellite.
 *
 * Two stacked views:
 *
 *   1. Bus and solar arrays to scale, in metres. Array area is derived
 *      from transmitter power with a specific power figure of
 *      408 W/m^2 (triple-junction cell at AM0, 30% efficient), and a
 *      chord of 0.5 m. The span shown is the total of both arrays.
 *
 *   2. Aperture detail to scale, in metres (usually centimetres). The
 *      beam waist radius w0 is drawn as a circle with a drag handle on
 *      its edge; dragging widens or narrows the aperture.
 *
 * The bus itself is drawn at a fixed physical size (2 m x 2 m,
 * documented as a rough figure for a modest power satellite), so the
 * array span is the variable that grows with power.
 */

import { useRef } from "react"
import { useDragSvg } from "./useDragSvg"
import { ScaleBar } from "./ScaleBar"

// Triple-junction solar cell specific power at AM0.
const W_PER_M2 = 408.0
// Assumed panel chord. Documented; a real design would use the
// manufacturer's panel aspect ratio.
const CHORD_M = 0.5
// Assumed bus body size. Small satellite bus.
const BUS_SIZE_M = 2.0

export type SatelliteBusDiagramProps = {
  transmitter_power_w: number
  transmitter_aperture_m: number
  onChange: (patch: { transmitter_aperture_m?: number }) => void
}

export function SatelliteBusDiagram({
  transmitter_power_w,
  transmitter_aperture_m,
  onChange,
}: SatelliteBusDiagramProps) {
  const svgRef = useRef<SVGSVGElement | null>(null)
  const apertureRef = useRef<SVGSVGElement | null>(null)

  // Array sizing. Total area needed (both arrays together) is
  // P / W_per_m2. Per-side span = area / 2 / chord.
  const arrayAreaM2 = transmitter_power_w / W_PER_M2
  const spanPerSideM = arrayAreaM2 / 2 / CHORD_M
  const halfWidth = Math.max(BUS_SIZE_M / 2 + spanPerSideM, BUS_SIZE_M)

  // Bus view viewBox. Half-width = bus + array span + 5% pad.
  const padM = 0.05 * halfWidth
  const busVbW = 2 * (halfWidth + padM)
  const busVbH = 2 * (BUS_SIZE_M * 0.75 + padM)
  const busVbX = -busVbW / 2
  const busVbY = -busVbH / 2
  const busScale = busVbW * 0.003  // stroke width

  const busBarData = 0.1 * busVbW
  const busBarLabel = `${Math.round(busBarData * 10) / 10} m`

  // Aperture detail view. Aperture diameter is 2 * w0.
  // Viewbox: 2.5 * diameter to leave room for the handle.
  const apDiamM = 2 * transmitter_aperture_m
  const apVbSide = Math.max(apDiamM * 3, 0.05)
  const apVbX = -apVbSide / 2
  const apVbY = -apVbSide / 2
  const apScale = apVbSide * 0.005

  // Aperture drag: horizontal drag on the handle changes w0.
  // The handle is placed at (w0, 0); dragging right widens it.
  const apertureDrag = useDragSvg(
    apertureRef,
    { w: apVbSide, h: apVbSide },
    (dx) => {
      const newW0 = Math.max(0.001, transmitter_aperture_m + dx)
      onChange({ transmitter_aperture_m: newW0 })
    },
  )

  const apBarData = apDiamM
  const apBarLabel =
    apDiamM >= 1
      ? `${Math.round(apDiamM * 100) / 100} m`
      : `${Math.round(apDiamM * 1000)} mm`

  return (
    <div className="space-y-2">
      {/* Bus + arrays view */}
      <svg
        ref={svgRef}
        viewBox={`${busVbX} ${busVbY} ${busVbW} ${busVbH}`}
        className="w-full"
        style={{ maxHeight: 140 }}
        role="img"
        aria-label="Satellite bus and solar arrays to scale"
        data-testid="satellite-bus-diagram"
      >
        {/* Solar array — left */}
        <rect
          x={-BUS_SIZE_M / 2 - spanPerSideM}
          y={-CHORD_M / 2}
          width={spanPerSideM}
          height={CHORD_M}
          fill="var(--bg-subtle)"
          stroke="var(--ink-secondary)"
          strokeWidth={busScale * 0.8}
        />
        {/* Array cell divisions (visual) */}
        {Array.from({ length: 4 }).map((_, i) => {
          const x = -BUS_SIZE_M / 2 - spanPerSideM + ((i + 1) * spanPerSideM) / 5
          return (
            <line
              key={`lc${i}`}
              x1={x}
              y1={-CHORD_M / 2}
              x2={x}
              y2={CHORD_M / 2}
              stroke="var(--ink-tertiary)"
              strokeWidth={busScale * 0.4}
            />
          )
        })}

        {/* Solar array — right */}
        <rect
          x={BUS_SIZE_M / 2}
          y={-CHORD_M / 2}
          width={spanPerSideM}
          height={CHORD_M}
          fill="var(--bg-subtle)"
          stroke="var(--ink-secondary)"
          strokeWidth={busScale * 0.8}
        />
        {Array.from({ length: 4 }).map((_, i) => {
          const x = BUS_SIZE_M / 2 + ((i + 1) * spanPerSideM) / 5
          return (
            <line
              key={`rc${i}`}
              x1={x}
              y1={-CHORD_M / 2}
              x2={x}
              y2={CHORD_M / 2}
              stroke="var(--ink-tertiary)"
              strokeWidth={busScale * 0.4}
            />
          )
        })}

        {/* Bus body */}
        <rect
          x={-BUS_SIZE_M / 2}
          y={-BUS_SIZE_M / 2}
          width={BUS_SIZE_M}
          height={BUS_SIZE_M}
          rx={BUS_SIZE_M * 0.06}
          fill="var(--bg-surface)"
          stroke="var(--ink-primary)"
          strokeWidth={busScale}
        />
        {/* Bus interior lines to suggest structure */}
        <line
          x1={-BUS_SIZE_M / 2}
          y1={-BUS_SIZE_M / 6}
          x2={BUS_SIZE_M / 2}
          y2={-BUS_SIZE_M / 6}
          stroke="var(--ink-tertiary)"
          strokeWidth={busScale * 0.4}
        />
        <line
          x1={-BUS_SIZE_M / 2}
          y1={BUS_SIZE_M / 6}
          x2={BUS_SIZE_M / 2}
          y2={BUS_SIZE_M / 6}
          stroke="var(--ink-tertiary)"
          strokeWidth={busScale * 0.4}
        />

        <ScaleBar
          x={busVbX + busVbW * 0.06}
          y={busVbY + busVbH * 0.94}
          widthData={busBarData}
          label={busBarLabel}
          fontSize={busVbW * 0.02}
        />
      </svg>

      {/* Aperture detail view */}
      <svg
        ref={apertureRef}
        viewBox={`${apVbX} ${apVbY} ${apVbSide} ${apVbSide}`}
        className="w-full"
        style={{ maxHeight: 90, touchAction: "none" }}
        role="img"
        aria-label="Transmitter aperture detail; drag the edge to change the beam waist"
        data-testid="satellite-aperture-diagram"
      >
        <circle
          cx={0}
          cy={0}
          r={transmitter_aperture_m}
          fill="var(--bg-subtle)"
          stroke="var(--ink-primary)"
          strokeWidth={apScale}
        />
        <line
          x1={-transmitter_aperture_m}
          y1={0}
          x2={transmitter_aperture_m}
          y2={0}
          stroke="var(--ink-tertiary)"
          strokeWidth={apScale * 0.5}
          strokeDasharray="2 2"
        />
        <circle
          cx={transmitter_aperture_m}
          cy={0}
          r={apVbSide * 0.02}
          fill="var(--status-orange)"
          stroke="var(--ink-primary)"
          strokeWidth={apScale * 0.6}
          style={{ cursor: "ew-resize" }}
          data-testid="aperture-handle"
          {...apertureDrag}
        />
        <text
          x={0}
          y={-apVbSide * 0.35}
          textAnchor="middle"
          fontFamily="ui-monospace, monospace"
          fontSize={apVbSide * 0.055}
          fill="var(--ink-tertiary)"
        >
          w0 ={" "}
          {transmitter_aperture_m >= 1
            ? `${transmitter_aperture_m.toFixed(2)} m`
            : `${(transmitter_aperture_m * 100).toFixed(1)} cm`}
        </text>
        <ScaleBar
          x={apVbX + apVbSide * 0.1}
          y={apVbY + apVbSide * 0.9}
          widthData={apBarData}
          label={apBarLabel}
          fontSize={apVbSide * 0.05}
        />
      </svg>
    </div>
  )
}
