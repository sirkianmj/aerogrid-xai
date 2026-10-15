/**
 * OrbitDiagram — a scale-correct top-down view of a Keplerian orbit.
 *
 * The ellipse is drawn with the Earth at the primary focus, at true
 * relative scale. The Earth radius is 6371 km (mean spherical radius,
 * matching the backend constant). For LEO the Earth fills most of the
 * diagram; for GEO it is a small disc inside a large ring; for HEO it
 * sits at one focus of a very elongated ellipse. Those proportions are
 * the physics, not a rendering choice.
 *
 * Two drag handles: periapsis and apoapsis markers. Dragging either
 * changes the semi-major axis and eccentricity together:
 *
 *     rp = a(1 - e)      rp is the periapsis radius from the focus
 *     ra = a(1 + e)      ra is the apoapsis radius from the focus
 *     a = (rp + ra) / 2
 *     e = (ra - rp) / (ra + rp)
 *
 * The other apsis is held fixed during a drag, so the user can imagine
 * "pull this side out" as a linear extension of that radius.
 *
 * A metric scale bar is drawn at the bottom of the diagram. Its length
 * is 10% of the current viewBox width; the label is computed to match.
 */

import { useRef } from "react"
import { useDragSvg } from "./useDragSvg"
import { ScaleBar } from "./ScaleBar"

// Mean spherical Earth radius in km, matching the backend constant
// EARTH_RADIUS_M = 6_371_000.0.
const R_EARTH_KM = 6371.0

export type OrbitDiagramProps = {
  a_km: number
  e: number
  onChange: (patch: { a_km?: number; e?: number }) => void
}

export function OrbitDiagram({ a_km, e, onChange }: OrbitDiagramProps) {
  const svgRef = useRef<SVGSVGElement | null>(null)

  // Derived geometry. The ellipse is centred at the origin; the focus
  // (Earth centre) sits at x = -a*e on the major axis.
  const rp = a_km * (1 - e)
  const ra = a_km * (1 + e)
  const b = a_km * Math.sqrt(Math.max(0, 1 - e * e))
  const focusX = -a_km * e

  // ViewBox bounds include the ellipse and the Earth disc.
  const xMin = Math.min(-a_km, focusX - R_EARTH_KM)
  const xMax = Math.max(a_km, focusX + R_EARTH_KM)
  const yMin = Math.min(-b, -R_EARTH_KM)
  const yMax = Math.max(b, R_EARTH_KM)
  const pad = 0.08 * Math.max(xMax - xMin, yMax - yMin)
  const vbX = xMin - pad
  const vbY = yMin - pad
  const vbW = xMax - xMin + 2 * pad
  const vbH = yMax - yMin + 2 * pad

  // Stroke widths and marker sizes are fractions of the viewBox so they
  // scale consistently at every orbital radius.
  const strokeEllipse = vbW * 0.0016
  const strokeEarth = vbW * 0.0012
  const markerR = vbW * 0.008
  const labelSize = vbW * 0.018

  // Handle drag. Apoapsis drag extends `ra` in the direction of the
  // drag; periapsis drag extends `rp` in the opposite direction, since
  // the periapsis handle is on the left and the focus is to its right.
  function onApoDrag(dx: number) {
    const newRa = Math.max(rp * 1.05, ra + dx)
    const newA = (rp + newRa) / 2
    const newE = (newRa - rp) / (newRa + rp)
    onChange({ a_km: newA, e: Math.max(0, Math.min(0.95, newE)) })
  }
  function onPerDrag(dx: number) {
    const newRp = Math.max(R_EARTH_KM + 150, rp - dx)
    const newA = (newRp + ra) / 2
    const newE = (ra - newRp) / (ra + newRp)
    onChange({ a_km: newA, e: Math.max(0, Math.min(0.95, newE)) })
  }

  const apoDrag = useDragSvg(svgRef, { w: vbW, h: vbH }, onApoDrag)
  const perDrag = useDragSvg(svgRef, { w: vbW, h: vbH }, onPerDrag)

  // Scale bar: a round 10% of the viewBox width, labelled with the
  // corresponding distance in kilometres.
  const barData = 0.10 * vbW
  const barLabel = `${Math.round(barData).toLocaleString()} km`

  return (
    <svg
      ref={svgRef}
      viewBox={`${vbX} ${vbY} ${vbW} ${vbH}`}
      className="w-full"
      style={{ maxHeight: 260, touchAction: "none" }}
      role="img"
      aria-label="Orbit diagram; drag the apsis markers to change the orbit"
      data-testid="orbit-diagram"
    >
      {/* Earth */}
      <circle
        cx={focusX}
        cy={0}
        r={R_EARTH_KM}
        fill="var(--bg-subtle)"
        stroke="var(--ink-tertiary)"
        strokeWidth={strokeEarth}
      />
      {/* Equator tick on the Earth for orientation */}
      <line
        x1={focusX - R_EARTH_KM}
        y1={0}
        x2={focusX + R_EARTH_KM}
        y2={0}
        stroke="var(--ink-tertiary)"
        strokeWidth={strokeEarth * 0.5}
        opacity={0.5}
      />

      {/* Orbit ellipse */}
      <ellipse
        cx={0}
        cy={0}
        rx={a_km}
        ry={b}
        fill="none"
        stroke="var(--ink-secondary)"
        strokeWidth={strokeEllipse}
      />

      {/* Periapsis marker + label */}
      <circle
        cx={-a_km}
        cy={0}
        r={markerR}
        fill="var(--status-green)"
        stroke="var(--ink-primary)"
        strokeWidth={strokeEarth}
        style={{ cursor: "ew-resize" }}
        data-testid="orbit-periapsis-handle"
        {...perDrag}
      />
      <text
        x={-a_km}
        y={markerR + labelSize * 1.2}
        textAnchor="middle"
        fontFamily="ui-monospace, monospace"
        fontSize={labelSize}
        fill="var(--ink-tertiary)"
      >
        rp {Math.round(rp).toLocaleString()} km
      </text>

      {/* Apoapsis marker + label */}
      <circle
        cx={a_km}
        cy={0}
        r={markerR}
        fill="var(--status-orange)"
        stroke="var(--ink-primary)"
        strokeWidth={strokeEarth}
        style={{ cursor: "ew-resize" }}
        data-testid="orbit-apoapsis-handle"
        {...apoDrag}
      />
      <text
        x={a_km}
        y={markerR + labelSize * 1.2}
        textAnchor="middle"
        fontFamily="ui-monospace, monospace"
        fontSize={labelSize}
        fill="var(--ink-tertiary)"
      >
        ra {Math.round(ra).toLocaleString()} km
      </text>

      <ScaleBar
        x={vbX + vbW * 0.06}
        y={vbY + vbH * 0.94}
        widthData={barData}
        label={barLabel}
        fontSize={labelSize}
      />
    </svg>
  )
}
