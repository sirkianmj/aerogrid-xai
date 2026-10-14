/**
 * FixedWingDetail — three-view engineering drawing of a fixed-wing UAV.
 *
 * Three orthographic views plus a section inset, on one titled frame:
 *
 *   PLAN     (top-down, upper-left)
 *   PROFILE  (side, lower-left)
 *   FRONT    (forward-looking, lower-right)
 *   SECTION  (airfoil inset, upper-right)
 *
 * Every dimension derives from the wingspan parameter. Documented
 * ratios (generic small-UAV conventions, no specific airframe):
 *
 *   chord (root)          0.15 span
 *   chord (tip)           0.55 of root  (taper ratio 0.55)
 *   quarter-chord sweep   8 degrees
 *   fuselage length       0.60 span
 *   fuselage width        0.06 span
 *   nose radius           0.03 span
 *   tail span             0.35 span
 *   tail chord            0.06 span
 *   fin height            0.15 span
 *   propeller radius      0.15 span
 *   sensor turret radius  0.05 span
 *   landing gear track    0.25 span
 *   dihedral              3 degrees (front view)
 *   airfoil thickness     12% of chord (symmetric placeholder)
 *
 * Receiver aperture is drawn as a circle of radius sqrt(A/pi) on the
 * fuselage crown, at the drawing's true scale.
 *
 * Drag handles:
 *   wingtip  (plan view, right wingtip)   changes wingspan_m
 *   aperture (plan view, on the crown)    changes receiver_aperture_m2
 *
 * No real aircraft, manufacturer, or programme is named. Constants
 * are generic aerospace conventions, each documented at the point of
 * use.
 */

import { useRef, type ReactElement } from "react"
import { useDragSvg } from "./useDragSvg"
import { ScaleBar } from "./ScaleBar"
import { DrawingFrame } from "./DrawingFrame"
import { Callout } from "./Callout"

// --- Drawing frame and view regions (pixels) --------------------------
const FRAME_W = 820
const FRAME_H = 520

// Plan view: upper-left, biggest region.
const PLAN = { x: 30, y: 35, w: 580, h: 185 }
// Profile view: lower-left, sized so it shares the bottom row with FRONT.
const PROFILE = { x: 30, y: 235, w: 320, h: 185 }
// Front view: lower-right, enlarged to accommodate the silhouette.
const FRONT = { x: 365, y: 235, w: 425, h: 185 }
// Airfoil section inset: upper-right corner of the frame.
const SECTION = { x: 620, y: 35, w: 170, h: 185 }

// --- Documented physical ratios (see header) --------------------------
const RATIO = {
  chordRoot: 0.15,
  taperRatio: 0.55,
  sweepDeg: 8,
  fusLen: 0.60,
  fusWidth: 0.06,
  noseR: 0.03,
  tailSpan: 0.35,
  tailChord: 0.06,
  finHeight: 0.15,
  propR: 0.15,
  turretR: 0.05,
  gearTrack: 0.25,
  dihedralDeg: 3,
  airfoilThickness: 0.12,
} as const

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

  // --- Derived physical dimensions (metres) ---------------------------
  const span = wingspan_m
  const halfSpan = span / 2
  const chordRoot = RATIO.chordRoot * span
  const chordTip = RATIO.taperRatio * chordRoot
  const fusLen = RATIO.fusLen * span
  const fusWidth = RATIO.fusWidth * span
  const noseR = RATIO.noseR * span
  const tailSpan = RATIO.tailSpan * span
  const tailChord = RATIO.tailChord * span
  const finHeight = RATIO.finHeight * span
  const propR = RATIO.propR * span
  const turretR = RATIO.turretR * span
  const gearTrack = RATIO.gearTrack * span
  const apertureR = Math.sqrt(receiver_aperture_m2 / Math.PI)
  const sweepOffset =
    Math.tan((RATIO.sweepDeg * Math.PI) / 180) * (halfSpan - fusWidth / 2)

  // --- Common scale across all views (pixels per metre) ---------------
  // Constrain by plan width, plan height, profile length, and front width.
  const planUsableW = PLAN.w * 0.85
  const planUsableH = PLAN.h * 0.85
  const profileUsableW = PROFILE.w * 0.85
  const frontUsableW = FRONT.w * 0.85
  const scale = Math.min(
    planUsableW / (span + 2 * propR),
    planUsableH / (fusLen * 1.15),
    profileUsableW / (fusLen + propR + noseR),
    frontUsableW / span,
  )

  // --- Per-view transform: metres -> pixels in that region ------------
  type Region = { x: number; y: number; w: number; h: number }
  function makeTransform(region: Region) {
    const cx = region.x + region.w / 2
    const cy = region.y + region.h / 2
    return (mx: number, my: number): [number, number] => [
      cx + mx * scale,
      cy - my * scale,  // +Y is up in metres, down in pixels
    ]
  }
  const planT = makeTransform(PLAN)
  const profileT = makeTransform(PROFILE)
  const frontT = makeTransform(FRONT)

  // --- Stroke widths and font sizes -----------------------------------
  const SW_MAIN = highlighted ? 1.6 : 1.2
  const SW_MED = 0.85
  const SW_THIN = 0.5
  const SW_HAIR = 0.3
  const FS_CALLOUT = 9
  const FS_LABEL = 8

  // --- Drag handles ---------------------------------------------------
  // Plan-view LE tip X, needed for the wingtip drag handle which sits
  // outside the wing() scope.
  const planLERootX = -chordRoot / 2 + fusWidth * 0.5
  const planLETipX = planLERootX - sweepOffset

  const apertureDrag = useDragSvg(svgRef, { w: FRAME_W, h: FRAME_H }, (dx) => {
    const newR = Math.max(0.01, apertureR + dx / scale)
    onChange({ receiver_aperture_m2: Math.PI * newR * newR })
  })
  const wingtipDrag = useDragSvg(svgRef, { w: FRAME_W, h: FRAME_H }, (dx) => {
    // Dragging the right wingtip horizontally by dx pixels changes span
    // by 2*dx in pixels, so 2*dx/scale in metres.
    const newSpan = Math.max(0.2, span + (2 * dx) / scale)
    onChange({ wingspan_m: newSpan })
  })

  // --- View helpers ---------------------------------------------------

  function P(t: (mx: number, my: number) => [number, number], mx: number, my: number): string {
    const [x, y] = t(mx, my)
    return `${x} ${y}`
  }

  // -------- Plan view (top-down) ---------------------------------------
  function renderPlan(): ReactElement {
    const noseX = fusLen / 2
    const tailX = -fusLen / 2
    const w2 = fusWidth / 2

    // Fuselage path (teardrop, nose forward).
    const fusPath =
      `M ${P(planT, noseX, 0)} ` +
      `C ${P(planT, noseX - noseR * 1.4, -w2 * 1.6)}, ` +
      `${P(planT, noseX - fusLen * 0.15, -w2 * 1.15)}, ` +
      `${P(planT, 0, -w2)} ` +
      `L ${P(planT, tailX + fusLen * 0.1, -w2 * 0.7)} ` +
      `C ${P(planT, tailX - fusLen * 0.05, -w2 * 0.6)}, ` +
      `${P(planT, tailX - fusLen * 0.02, -w2 * 0.25)}, ` +
      `${P(planT, tailX, 0)} ` +
      `C ${P(planT, tailX - fusLen * 0.02, w2 * 0.25)}, ` +
      `${P(planT, tailX - fusLen * 0.05, w2 * 0.6)}, ` +
      `${P(planT, tailX + fusLen * 0.1, w2 * 0.7)} ` +
      `L ${P(planT, 0, w2)} ` +
      `C ${P(planT, noseX - fusLen * 0.15, w2 * 1.15)}, ` +
      `${P(planT, noseX - noseR * 1.4, w2 * 1.6)}, ` +
      `${P(planT, noseX, 0)} Z`

    // Wing (one side): quadrilateral from root LE to tip LE, tip TE, root TE.
    function wing(side: 1 | -1): ReactElement {
      const leRootX = -chordRoot / 2 + fusWidth * 0.5
      const leRootY = side * fusWidth * 0.35
      const leTipX = leRootX - sweepOffset
      const leTipY = side * halfSpan
      const teRootX = chordRoot / 2 + fusWidth * 0.5
      const teRootY = side * fusWidth * 0.35
      const teTipX = leTipX + chordTip
      const teTipY = side * halfSpan

      const wingPath =
        `M ${P(planT, leRootX, leRootY)} ` +
        `L ${P(planT, leTipX, leTipY)} ` +
        `L ${P(planT, teTipX, teTipY)} ` +
        `L ${P(planT, teRootX, teRootY)} Z`

      // Aileron (outboard 55-90% of TE) and flap (inboard 10-50%).
      function control(t1: number, t2: number, label: string, key: string): ReactElement {
        const x1 = teRootX + t1 * (teTipX - teRootX)
        const y1 = teRootY + t1 * (teTipY - teRootY)
        const x2 = teRootX + t2 * (teTipX - teRootX)
        const y2 = teRootY + t2 * (teTipY - teRootY)
        const inset = chordTip * 0.28
        const dxIn = -inset * 0.8
        const dyIn = -side * inset * 0.6
        const path =
          `M ${P(planT, x1, y1)} ` +
          `L ${P(planT, x2, y2)} ` +
          `L ${P(planT, x2 + dxIn, y2 + dyIn)} ` +
          `L ${P(planT, x1 + dxIn, y1 + dyIn)} Z`
        const [lx, ly] = planT((x1 + x2) / 2 + dxIn, (y1 + y2) / 2 + dyIn)
        return (
          <g key={key}>
            <path d={path} fill="var(--bg-subtle)" stroke="var(--ink-secondary)" strokeWidth={SW_HAIR} />
            <text
              x={lx}
              y={ly + FS_LABEL * 0.3}
              textAnchor="middle"
              fontFamily="ui-monospace, monospace"
              fontSize={FS_LABEL * 0.85}
              fill="var(--ink-tertiary)"
            >
              {label}
            </text>
          </g>
        )
      }

      return (
        <g key={side}>
          <path d={wingPath} fill="var(--bg-subtle)" stroke="var(--ink-secondary)" strokeWidth={SW_MED} />
          {/* Panel line along the wing, at mid-span */}
          <line
            x1={planT(leRootX + (leTipX - leRootX) * 0.5, leRootY + (leTipY - leRootY) * 0.5)[0]}
            y1={planT(leRootX + (leTipX - leRootX) * 0.5, leRootY + (leTipY - leRootY) * 0.5)[1]}
            x2={planT(teRootX + (teTipX - teRootX) * 0.5, teRootY + (teTipY - teRootY) * 0.5)[0]}
            y2={planT(teRootX + (teTipX - teRootX) * 0.5, teRootY + (teTipY - teRootY) * 0.5)[1]}
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_HAIR}
            opacity={0.5}
          />
          {/* Winglet at tip, drawn as a small forward-swept cap */}
          <line
            x1={planT(leTipX, leTipY)[0]}
            y1={planT(leTipX, leTipY)[1]}
            x2={planT(leTipX - chordTip * 0.15, leTipY + side * chordTip * 0.55)[0]}
            y2={planT(leTipX - chordTip * 0.15, leTipY + side * chordTip * 0.55)[1]}
            stroke="var(--ink-primary)"
            strokeWidth={SW_MED}
          />
          <line
            x1={planT(teTipX, teTipY)[0]}
            y1={planT(teTipX, teTipY)[1]}
            x2={planT(leTipX - chordTip * 0.15, leTipY + side * chordTip * 0.55)[0]}
            y2={planT(leTipX - chordTip * 0.15, leTipY + side * chordTip * 0.55)[1]}
            stroke="var(--ink-primary)"
            strokeWidth={SW_MED}
          />
          {/* Control surfaces */}
          {control(0.10, 0.50, "FLAP", `flap${side}`)}
          {control(0.55, 0.90, "AIL", `ail${side}`)}
        </g>
      )
    }

    // Horizontal stabiliser with elevator.
    const hsLE = tailX + fusLen * 0.14
    const hsTE = tailX - fusLen * 0.02
    const hsPath =
      `M ${P(planT, hsLE, -tailSpan / 2)} ` +
      `L ${P(planT, hsTE, -tailSpan * 0.42)} ` +
      `L ${P(planT, hsTE, tailSpan * 0.42)} ` +
      `L ${P(planT, hsLE, tailSpan / 2)} Z`

    // Propeller: three blades, each a swept path with a bow.
    const propCx = noseX + noseR * 0.3
    const propBlades = [0, 120, 240]

    const turretCx = noseX - fusWidth * 0.9
    const apertureCx = -fusLen * 0.12

    return (
      <g>
        {/* Fuselage */}
        <path d={fusPath} fill="var(--bg-surface)" stroke="var(--ink-secondary)" strokeWidth={SW_MAIN} />
        {/* Panel-line stations */}
        {[-0.15, 0.05, 0.25].map((t, i) => {
          const [x1, y1] = planT(tailX + t * fusLen, -fusWidth * 0.55)
          const [x2, y2] = planT(tailX + t * fusLen, fusWidth * 0.55)
          return (
            <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--ink-tertiary)" strokeWidth={SW_HAIR} opacity={0.5} />
          )
        })}
        {/* Cockpit window */}
        <path
          d={
            `M ${P(planT, noseX - fusLen * 0.02, -fusWidth * 0.28)} ` +
            `C ${P(planT, noseX - fusLen * 0.06, -fusWidth * 0.30)}, ` +
            `${P(planT, noseX - fusLen * 0.10, -fusWidth * 0.22)}, ` +
            `${P(planT, noseX - fusLen * 0.13, 0)} ` +
            `C ${P(planT, noseX - fusLen * 0.10, fusWidth * 0.22)}, ` +
            `${P(planT, noseX - fusLen * 0.06, fusWidth * 0.30)}, ` +
            `${P(planT, noseX - fusLen * 0.02, fusWidth * 0.28)} Z`
          }
          fill="none"
          stroke="var(--ink-tertiary)"
          strokeWidth={SW_THIN}
          opacity={0.7}
        />

        {/* Sensor turret */}
        <circle
          cx={planT(turretCx, 0)[0]}
          cy={planT(turretCx, 0)[1]}
          r={turretR * scale}
          fill="var(--bg-subtle)"
          stroke="var(--ink-secondary)"
          strokeWidth={SW_THIN}
        />
        <circle
          cx={planT(turretCx, 0)[0]}
          cy={planT(turretCx, 0)[1]}
          r={turretR * scale * 0.55}
          fill="none"
          stroke="var(--ink-tertiary)"
          strokeWidth={SW_HAIR}
        />

        {/* Propeller */}
        <g>
          <circle
            cx={planT(propCx, 0)[0]}
            cy={planT(propCx, 0)[1]}
            r={propR * 0.12 * scale}
            fill="var(--ink-primary)"
          />
          {propBlades.map((deg) => {
            const rad = (deg * Math.PI) / 180
            const bx = propCx + Math.cos(rad) * propR
            const by = Math.sin(rad) * propR
            const mx = propCx + Math.cos(rad) * propR * 0.55
            const my = Math.sin(rad) * propR * 0.55
            const perp = rad + Math.PI / 2
            const bw = propR * 0.18
            const px = Math.cos(perp) * bw * 0.5
            const py = Math.sin(perp) * bw * 0.5
            const path =
              `M ${P(planT, propCx, 0)} ` +
              `Q ${P(planT, mx + px, my + py)} ${P(planT, bx, by)} ` +
              `Q ${P(planT, mx - px, my - py)} ${P(planT, propCx, 0)} Z`
            return <path key={deg} d={path} fill="var(--bg-subtle)" stroke="var(--ink-secondary)" strokeWidth={SW_THIN} />
          })}
        </g>

        {/* Wings (drawn after fuselage so they overlap the join cleanly) */}
        {wing(-1)}
        {wing(1)}

        {/* Vertical fin (thin edge line at the centreline) */}
        <line
          x1={planT(tailX - fusLen * 0.02, 0)[0]}
          y1={planT(tailX - fusLen * 0.02, 0)[1]}
          x2={planT(tailX + fusLen * 0.08, 0)[0]}
          y2={planT(tailX + fusLen * 0.08, 0)[1]}
          stroke="var(--ink-primary)"
          strokeWidth={SW_MAIN}
        />

        {/* Horizontal stabiliser with elevator */}
        <path d={hsPath} fill="var(--bg-subtle)" stroke="var(--ink-secondary)" strokeWidth={SW_MED} />
        <line
          x1={planT(hsLE + (hsTE - hsLE) * 0.55, -tailSpan / 2)[0]}
          y1={planT(hsLE + (hsTE - hsLE) * 0.55, -tailSpan / 2)[1]}
          x2={planT(hsLE + (hsTE - hsLE) * 0.55, tailSpan / 2)[0]}
          y2={planT(hsLE + (hsTE - hsLE) * 0.55, tailSpan / 2)[1]}
          stroke="var(--ink-tertiary)"
          strokeWidth={SW_HAIR}
        />

        {/* Landing gear fairings */}
        {[
          [noseX - fusLen * 0.35, 0],
          [0, -fusWidth * 0.65],
          [0, fusWidth * 0.65],
        ].map(([cx, cy], i) => (
          <ellipse
            key={i}
            cx={planT(cx, cy)[0]}
            cy={planT(cx, cy)[1]}
            rx={fusWidth * 0.18 * scale}
            ry={fusWidth * 0.10 * scale}
            fill="var(--ink-primary)"
            opacity={0.75}
          />
        ))}

        {/* Receiver aperture on the crown */}
        <circle
          cx={planT(apertureCx, 0)[0]}
          cy={planT(apertureCx, 0)[1]}
          r={apertureR * scale}
          fill="var(--status-green)"
          fillOpacity={0.18}
          stroke="var(--status-green)"
          strokeWidth={SW_MED}
        />
        {/* Aperture drag handle at the eastern edge of the aperture */}
        <circle
          cx={planT(apertureCx + apertureR, 0)[0]}
          cy={planT(apertureCx + apertureR, 0)[1]}
          r={5}
          fill="var(--status-orange)"
          stroke="var(--ink-primary)"
          strokeWidth={SW_MED}
          style={{ cursor: "ew-resize" }}
          data-testid="aperture-handle"
          {...apertureDrag}
        />

        {/* Wingtip drag handle on the right wing tip */}
        <circle
          cx={planT(planLETipX + chordTip * 0.5, halfSpan)[0]}
          cy={planT(planLETipX + chordTip * 0.5, halfSpan)[1]}
          r={5}
          fill="var(--status-green)"
          stroke="var(--ink-primary)"
          strokeWidth={SW_MED}
          style={{ cursor: "ew-resize" }}
          data-testid="wingtip-handle"
          {...wingtipDrag}
        />

        {/* Dimension line for wingspan, drawn above the fuselage in the plan view */}
        <g>
          <line
            x1={planT(-chordRoot / 2 + fusWidth * 0.5 - sweepOffset - chordTip * 1.4, halfSpan)[0]}
            y1={planT(-chordRoot / 2 + fusWidth * 0.5 - sweepOffset - chordTip * 1.4, halfSpan)[1]}
            x2={planT(-chordRoot / 2 + fusWidth * 0.5 - sweepOffset - chordTip * 1.4, -halfSpan)[0]}
            y2={planT(-chordRoot / 2 + fusWidth * 0.5 - sweepOffset - chordTip * 1.4, -halfSpan)[1]}
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_HAIR}
          />
          <text
            x={planT(-chordRoot / 2 + fusWidth * 0.5 - sweepOffset - chordTip * 1.7, 0)[0]}
            y={planT(-chordRoot / 2 + fusWidth * 0.5 - sweepOffset - chordTip * 1.7, 0)[1]}
            textAnchor="middle"
            fontFamily="ui-monospace, monospace"
            fontSize={FS_LABEL}
            fill="var(--ink-tertiary)"
          >
            span {span.toFixed(2)} m
          </text>
        </g>

        {/* View label */}
        <text
          x={PLAN.x + PLAN.w * 0.02}
          y={PLAN.y + PLAN.h * 0.06}
          fontFamily="ui-monospace, monospace"
          fontSize={FS_LABEL * 1.1}
          fill="var(--ink-secondary)"
        >
          PLAN
        </text>
      </g>
    )
  }

  // -------- Profile view (side) ----------------------------------------
  function renderProfile(): ReactElement {
    const noseX = fusLen / 2
    const tailX = -fusLen / 2
    const h2 = fusWidth / 2

    // Fuselage silhouette: a long, thin body with a nose taper and a
    // raised tail (to support the fin). The bottom has a modest belly
    // bulge for the sensor turret.
    const fusPath =
      `M ${P(profileT, noseX, -h2 * 0.4)} ` +
      `C ${P(profileT, noseX - noseR * 1.6, -h2 * 1.3)}, ` +
      `${P(profileT, noseX - fusLen * 0.12, -h2 * 1.1)}, ` +
      `${P(profileT, -fusLen * 0.05, -h2)} ` +
      `L ${P(profileT, tailX + fusLen * 0.14, -h2 * 1.1)} ` +
      `C ${P(profileT, tailX + fusLen * 0.06, -h2 * 1.2)}, ` +
      `${P(profileT, tailX - fusLen * 0.02, -h2 * 1.1)}, ` +
      `${P(profileT, tailX, -h2 * 0.9)} ` +
      `L ${P(profileT, tailX, h2 * 0.9)} ` +
      `C ${P(profileT, tailX - fusLen * 0.02, h2 * 1.0)}, ` +
      `${P(profileT, tailX + fusLen * 0.06, h2 * 1.1)}, ` +
      `${P(profileT, tailX + fusLen * 0.14, h2 * 1.0)} ` +
      `L ${P(profileT, -fusLen * 0.05, h2 * 0.9)} ` +
      `C ${P(profileT, noseX - fusLen * 0.12, h2 * 1.0)}, ` +
      `${P(profileT, noseX - noseR * 1.6, h2 * 0.6)}, ` +
      `${P(profileT, noseX, -h2 * 0.4)} Z`

    // Sensor turret below the nose (a small half-cylinder).
    const turretCxProfile = noseX - fusWidth * 0.9

    // Landing gear: main wheel under the wing, nose wheel forward.
    const mainGearX = 0
    const noseGearX = noseX - fusLen * 0.35
    const gearLen = finHeight * 0.55  // how far down the gear extends
    const wheelR = finHeight * 0.15

    return (
      <g>
        {/* Fuselage */}
        <path d={fusPath} fill="var(--bg-surface)" stroke="var(--ink-secondary)" strokeWidth={SW_MAIN} />

        {/* Canopy (a subtle hatch along the top-front) */}
        <path
          d={
            `M ${P(profileT, noseX - fusLen * 0.03, -h2 * 0.5)} ` +
            `L ${P(profileT, noseX - fusLen * 0.2, -h2 * 1.1)} ` +
            `L ${P(profileT, noseX - fusLen * 0.3, -h2 * 1.05)} Z`
          }
          fill="none"
          stroke="var(--ink-tertiary)"
          strokeWidth={SW_THIN}
          opacity={0.75}
        />

        {/* Wing edge-on (a thin horizontal bar at mid-height) */}
        <rect
          x={profileT(-chordRoot * 0.5, 0)[0]}
          y={profileT(0, -h2 * 0.15)[1]}
          width={chordRoot * scale}
          height={Math.max(2, h2 * 0.3 * scale)}
          fill="var(--bg-subtle)"
          stroke="var(--ink-secondary)"
          strokeWidth={SW_THIN}
        />

        {/* Horizontal stabiliser edge-on */}
        <rect
          x={profileT(tailX - fusLen * 0.02, 0)[0]}
          y={profileT(0, -h2 * 0.1)[1]}
          width={tailChord * scale}
          height={Math.max(2, h2 * 0.2 * scale)}
          fill="var(--bg-subtle)"
          stroke="var(--ink-secondary)"
          strokeWidth={SW_THIN}
        />

        {/* Vertical fin profile */}
        <path
          d={
            `M ${P(profileT, tailX + fusLen * 0.12, 0)} ` +
            `L ${P(profileT, tailX + fusLen * 0.14, 0)} ` +
            `L ${P(profileT, tailX + fusLen * 0.06, finHeight)} ` +
            `L ${P(profileT, tailX - fusLen * 0.02, finHeight * 0.85)} ` +
            `L ${P(profileT, tailX - fusLen * 0.02, 0)} Z`
          }
          fill="var(--bg-subtle)"
          stroke="var(--ink-secondary)"
          strokeWidth={SW_MED}
        />

        {/* Nose landing gear */}
        <line
          x1={profileT(noseGearX, -h2 * 0.9)[0]}
          y1={profileT(noseGearX, -h2 * 0.9)[1]}
          x2={profileT(noseGearX, -h2 * 0.9 - gearLen)[0]}
          y2={profileT(noseGearX, -h2 * 0.9 - gearLen)[1]}
          stroke="var(--ink-primary)"
          strokeWidth={SW_THIN}
        />
        <circle
          cx={profileT(noseGearX, -h2 * 0.9 - gearLen)[0]}
          cy={profileT(noseGearX, -h2 * 0.9 - gearLen)[1]}
          r={wheelR * scale}
          fill="var(--bg-surface)"
          stroke="var(--ink-primary)"
          strokeWidth={SW_THIN}
        />

        {/* Main landing gear */}
        <line
          x1={profileT(mainGearX, -h2)[0]}
          y1={profileT(mainGearX, -h2)[1]}
          x2={profileT(mainGearX, -h2 - gearLen)[0]}
          y2={profileT(mainGearX, -h2 - gearLen)[1]}
          stroke="var(--ink-primary)"
          strokeWidth={SW_THIN}
        />
        <circle
          cx={profileT(mainGearX, -h2 - gearLen)[0]}
          cy={profileT(mainGearX, -h2 - gearLen)[1]}
          r={wheelR * scale}
          fill="var(--bg-surface)"
          stroke="var(--ink-primary)"
          strokeWidth={SW_THIN}
        />

        {/* Propeller disk, edge-on (a vertical line at the nose) */}
        <line
          x1={profileT(noseX + noseR * 0.4, propR)[0]}
          y1={profileT(noseX + noseR * 0.4, propR)[1]}
          x2={profileT(noseX + noseR * 0.4, -propR)[0]}
          y2={profileT(noseX + noseR * 0.4, -propR)[1]}
          stroke="var(--ink-primary)"
          strokeWidth={SW_MED}
        />
        <circle
          cx={profileT(noseX + noseR * 0.4, 0)[0]}
          cy={profileT(noseX + noseR * 0.4, 0)[1]}
          r={3}
          fill="var(--ink-primary)"
        />

        {/* Sensor turret under the nose */}
        <path
          d={
            `M ${P(profileT, turretCxProfile - turretR, -h2 * 0.9)} ` +
            `A ${turretR * scale} ${turretR * scale} 0 0 0 ${profileT(turretCxProfile + turretR, -h2 * 0.9)[0]} ${profileT(turretCxProfile + turretR, -h2 * 0.9)[1]} ` +
            `L ${profileT(turretCxProfile + turretR * 0.7, -h2 * 0.9)[0]} ${profileT(turretCxProfile + turretR * 0.7, -h2 * 0.9)[1]} ` +
            `A ${turretR * 0.7 * scale} ${turretR * 0.7 * scale} 0 0 1 ${profileT(turretCxProfile - turretR * 0.7, -h2 * 0.9)[0]} ${profileT(turretCxProfile - turretR * 0.7, -h2 * 0.9)[1]} Z`
          }
          fill="var(--bg-subtle)"
          stroke="var(--ink-secondary)"
          strokeWidth={SW_THIN}
        />

        {/* View label */}
        <text
          x={PROFILE.x + PROFILE.w * 0.02}
          y={PROFILE.y + PROFILE.h * 0.08}
          fontFamily="ui-monospace, monospace"
          fontSize={FS_LABEL * 1.1}
          fill="var(--ink-secondary)"
        >
          PROFILE
        </text>
      </g>
    )
  }

  // -------- Front view -------------------------------------------------
  // -------- FRONT view (looking at the aircraft nose-on) ---------------
  //
  // Layer order, farthest from camera first:
  //   1. Nose landing gear (drawn dashed, behind the fuselage)
  //   2. Tail: fin triangle and h-stab slab
  //   3. Main landing gear (struts and wheels below the wing)
  //   4. Wings with dihedral and winglets
  //   5. Fuselage cross-section (rounded oval)
  //   6. Canopy bubble on top of the fuselage
  //   7. Propeller disk with blades and spinner (front of the aircraft)
  //
  // Airfoil thickness in this view is EXAGGERATED 3x for legibility.
  // At true scale, a 12% chord on a 0.45 m chord is a 5 cm slab, which
  // renders as a line. The SECTION A-A inset draws the same airfoil at
  // true relative thickness.
  function renderFront(): ReactElement {
    const h2 = fusWidth / 2
    const dihedralRad = (RATIO.dihedralDeg * Math.PI) / 180
    const tipLift = halfSpan * Math.tan(dihedralRad)

    // Exaggerated airfoil thickness in the front view (3x reality).
    const tRoot = 3 * RATIO.airfoilThickness * chordRoot
    const tTip = 3 * RATIO.airfoilThickness * chordTip

    // Common vertical dimensions for gear.
    const strutLen = finHeight * 0.55
    const mainWheelR = finHeight * 0.16
    const noseWheelR = finHeight * 0.13

    // --- 1. Nose gear (behind fuselage, dashed) ---
    function renderNoseGear(): ReactElement {
      return (
        <g opacity={0.7}>
          <line
            x1={frontT(0, -h2 * 0.9)[0]}
            y1={frontT(0, -h2 * 0.9)[1]}
            x2={frontT(0, -h2 * 0.9 - strutLen * 0.85)[0]}
            y2={frontT(0, -h2 * 0.9 - strutLen * 0.85)[1]}
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_THIN}
            strokeDasharray="3 2"
          />
          <circle
            cx={frontT(0, -h2 * 0.9 - strutLen * 0.85 - noseWheelR)[0]}
            cy={frontT(0, -h2 * 0.9 - strutLen * 0.85 - noseWheelR)[1]}
            r={noseWheelR * scale}
            fill="var(--bg-surface)"
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_THIN}
            strokeDasharray="3 2"
          />
        </g>
      )
    }

    // --- 2. Tail surfaces ---
    function renderTail(): ReactElement {
      // Vertical fin: triangle from the aft fuselage top.
      const finBaseW = finHeight * 0.55
      const finPath =
        `M ${P(frontT, -finBaseW, h2 * 0.4)} ` +
        `L ${P(frontT, 0, h2 * 0.4)} ` +
        `L ${P(frontT, 0, h2 * 0.4 + finHeight)} ` +
        `L ${P(frontT, -finBaseW * 0.6, h2 * 0.4 + finHeight * 0.7)} Z`

      // Horizontal stabiliser edge-on: a thin slab at the tail height.
      const hsW = tailSpan / 2
      const hsT = tTip * 0.8
      const hsPath =
        `M ${P(frontT, -hsW, h2 * 0.1)} ` +
        `L ${P(frontT, -hsW, h2 * 0.1 - hsT)} ` +
        `L ${P(frontT, hsW, h2 * 0.1 - hsT)} ` +
        `L ${P(frontT, hsW, h2 * 0.1)} Z`

      return (
        <g>
          <path d={hsPath} fill="var(--bg-subtle)" stroke="var(--ink-secondary)" strokeWidth={SW_MED} />
          <line
            x1={frontT(-hsW, h2 * 0.1)[0]}
            y1={frontT(-hsW, h2 * 0.1)[1]}
            x2={frontT(-hsW, h2 * 0.1 - hsT)[0]}
            y2={frontT(-hsW, h2 * 0.1 - hsT)[1]}
            stroke="var(--ink-primary)"
            strokeWidth={SW_MED}
          />
          <line
            x1={frontT(hsW, h2 * 0.1)[0]}
            y1={frontT(hsW, h2 * 0.1)[1]}
            x2={frontT(hsW, h2 * 0.1 - hsT)[0]}
            y2={frontT(hsW, h2 * 0.1 - hsT)[1]}
            stroke="var(--ink-primary)"
            strokeWidth={SW_MED}
          />
          <path d={finPath} fill="var(--bg-subtle)" stroke="var(--ink-secondary)" strokeWidth={SW_MED} />
          <line
            x1={frontT(-finBaseW * 0.35, h2 * 0.4 + finHeight * 0.8)[0]}
            y1={frontT(-finBaseW * 0.35, h2 * 0.4 + finHeight * 0.8)[1]}
            x2={frontT(-finBaseW * 0.35, h2 * 0.4 + finHeight * 0.25)[0]}
            y2={frontT(-finBaseW * 0.35, h2 * 0.4 + finHeight * 0.25)[1]}
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_HAIR}
          />
        </g>
      )
    }

    // --- 3. Main landing gear (in front of the tail, behind the wing) ---
    function renderMainGear(): ReactElement {
      return (
        <g>
          {[-1, 1].map((side) => {
            const gearX = side * gearTrack * 0.5
            return (
              <g key={side}>
                <line
                  x1={frontT(gearX, -h2 * 0.9)[0]}
                  y1={frontT(gearX, -h2 * 0.9)[1]}
                  x2={frontT(gearX, -h2 * 0.9 - strutLen)[0]}
                  y2={frontT(gearX, -h2 * 0.9 - strutLen)[1]}
                  stroke="var(--ink-primary)"
                  strokeWidth={SW_MAIN}
                />
                <rect
                  x={frontT(gearX - fusWidth * 0.06, -h2 * 0.9)[0]}
                  y={frontT(gearX - fusWidth * 0.06, -h2 * 0.9)[1]}
                  width={fusWidth * 0.12 * scale}
                  height={strutLen * 0.4 * scale}
                  fill="var(--bg-subtle)"
                  stroke="var(--ink-secondary)"
                  strokeWidth={SW_THIN}
                />
                <circle
                  cx={frontT(gearX, -h2 * 0.9 - strutLen - mainWheelR)[0]}
                  cy={frontT(gearX, -h2 * 0.9 - strutLen - mainWheelR)[1]}
                  r={mainWheelR * scale}
                  fill="var(--bg-surface)"
                  stroke="var(--ink-primary)"
                  strokeWidth={SW_MAIN}
                />
                <circle
                  cx={frontT(gearX, -h2 * 0.9 - strutLen - mainWheelR)[0]}
                  cy={frontT(gearX, -h2 * 0.9 - strutLen - mainWheelR)[1]}
                  r={mainWheelR * 0.35 * scale}
                  fill="var(--ink-primary)"
                />
                <circle
                  cx={frontT(gearX, -h2 * 0.9 - strutLen - mainWheelR)[0]}
                  cy={frontT(gearX, -h2 * 0.9 - strutLen - mainWheelR)[1]}
                  r={mainWheelR * 0.6 * scale}
                  fill="none"
                  stroke="var(--ink-tertiary)"
                  strokeWidth={SW_HAIR}
                />
              </g>
            )
          })}
        </g>
      )
    }

    // --- 4. Wings ---
    function renderWingFront(side: 1 | -1): ReactElement {
      const tipX = side * halfSpan
      const rootY = 0
      const tipY = tipLift
      const wingPath =
        `M ${P(frontT, 0, rootY + tRoot / 2)} ` +
        `L ${P(frontT, tipX, tipY + tTip / 2)} ` +
        `L ${P(frontT, tipX, tipY - tTip / 2)} ` +
        `L ${P(frontT, 0, rootY - tRoot / 2)} Z`

      const wingletH = tTip * 1.6
      const wingletPath =
        `M ${P(frontT, tipX, tipY + tTip / 2)} ` +
        `L ${P(frontT, tipX + side * wingletH * 0.3, tipY + tTip / 2 + wingletH)} ` +
        `L ${P(frontT, tipX + side * wingletH * 0.3, tipY - tTip / 2 + wingletH)} ` +
        `L ${P(frontT, tipX, tipY - tTip / 2)} Z`

      return (
        <g key={side}>
          <path d={wingPath} fill="var(--bg-subtle)" stroke="var(--ink-secondary)" strokeWidth={SW_MED} />
          <path d={wingletPath} fill="var(--bg-subtle)" stroke="var(--ink-primary)" strokeWidth={SW_MED} />
          {/* Leading edge highlight */}
          <line
            x1={frontT(0, rootY + tRoot / 2)[0]}
            y1={frontT(0, rootY + tRoot / 2)[1]}
            x2={frontT(tipX, tipY + tTip / 2)[0]}
            y2={frontT(tipX, tipY + tTip / 2)[1]}
            stroke="var(--ink-primary)"
            strokeWidth={SW_MAIN * 0.8}
          />
          {/* Aileron outline dashed on the outboard trailing edge */}
          <line
            x1={frontT(side * halfSpan * 0.6, tipY * 0.6 - tTip / 2)[0]}
            y1={frontT(side * halfSpan * 0.6, tipY * 0.6 - tTip / 2)[1]}
            x2={frontT(tipX, tipY - tTip / 2)[0]}
            y2={frontT(tipX, tipY - tTip / 2)[1]}
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_HAIR}
            strokeDasharray="2 2"
          />
        </g>
      )
    }

    // --- 5. Fuselage cross-section ---
    function renderFuselage(): ReactElement {
      const fusH = fusWidth * 1.15
      const cx = frontT(0, 0)[0]
      const cy = frontT(0, 0)[1]
      return (
        <g>
          <ellipse
            cx={cx}
            cy={cy}
            rx={h2 * scale}
            ry={(fusH / 2) * scale}
            fill="var(--bg-surface)"
            stroke="var(--ink-primary)"
            strokeWidth={SW_MAIN}
          />
          <line
            x1={cx - h2 * scale}
            y1={cy}
            x2={cx + h2 * scale}
            y2={cy}
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_HAIR}
          />
          <line
            x1={cx}
            y1={cy - (fusH / 2) * scale}
            x2={cx}
            y2={cy + (fusH / 2) * scale}
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_HAIR}
            opacity={0.6}
          />
          {/* Exhaust ports on each side */}
          {[-1, 1].map((side) => (
            <rect
              key={side}
              x={frontT(side * h2 * 0.85, -h2 * 0.3)[0]}
              y={frontT(side * h2 * 0.85, -h2 * 0.3)[1]}
              width={3}
              height={5}
              fill="var(--ink-secondary)"
            />
          ))}
          {/* Static ports */}
          {[-1, 1].map((side) => (
            <circle
              key={side}
              cx={frontT(side * h2 * 0.7, h2 * 0.15)[0]}
              cy={frontT(side * h2 * 0.7, h2 * 0.15)[1]}
              r={1.2}
              fill="var(--ink-tertiary)"
            />
          ))}
        </g>
      )
    }

    // --- 6. Canopy ---
    function renderCanopy(): ReactElement {
      const canopyW = fusWidth * 0.9
      const canopyH = fusWidth * 0.5
      const canopyPath =
        `M ${P(frontT, -canopyW / 2, h2 * 0.85)} ` +
        `Q ${P(frontT, -canopyW * 0.55, h2 * 0.85 + canopyH)} ${P(frontT, 0, h2 * 0.85 + canopyH)} ` +
        `Q ${P(frontT, canopyW * 0.55, h2 * 0.85 + canopyH)} ${P(frontT, canopyW / 2, h2 * 0.85)} Z`
      return (
        <g>
          <path d={canopyPath} fill="var(--bg-subtle)" stroke="var(--ink-primary)" strokeWidth={SW_MED} />
          <line
            x1={frontT(0, h2 * 0.85)[0]}
            y1={frontT(0, h2 * 0.85)[1]}
            x2={frontT(0, h2 * 0.85 + canopyH)[0]}
            y2={frontT(0, h2 * 0.85 + canopyH)[1]}
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_HAIR}
          />
          <line
            x1={frontT(-canopyW * 0.3, h2 * 0.85)[0]}
            y1={frontT(-canopyW * 0.3, h2 * 0.85)[1]}
            x2={frontT(-canopyW * 0.2, h2 * 0.85 + canopyH * 0.7)[0]}
            y2={frontT(-canopyW * 0.2, h2 * 0.85 + canopyH * 0.7)[1]}
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_HAIR}
          />
          <line
            x1={frontT(canopyW * 0.3, h2 * 0.85)[0]}
            y1={frontT(canopyW * 0.3, h2 * 0.85)[1]}
            x2={frontT(canopyW * 0.2, h2 * 0.85 + canopyH * 0.7)[0]}
            y2={frontT(canopyW * 0.2, h2 * 0.85 + canopyH * 0.7)[1]}
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_HAIR}
          />
        </g>
      )
    }

    // --- 7. Propeller ---
    function renderProp(): ReactElement {
      const cx = frontT(0, 0)[0]
      const cy = frontT(0, 0)[1]
      return (
        <g>
          <circle
            cx={cx}
            cy={cy}
            r={propR * scale}
            fill="none"
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_HAIR}
            strokeDasharray="4 3"
            opacity={0.55}
          />
          {[0, 120, 240].map((deg) => {
            const rad = ((deg - 90) * Math.PI) / 180
            const bx = Math.cos(rad)
            const by = Math.sin(rad)
            const tipX = cx + bx * propR * scale
            const tipY = cy + by * propR * scale
            const midX = cx + bx * propR * scale * 0.55
            const midY = cy + by * propR * scale * 0.55
            const perpX = -by
            const perpY = bx
            const bw = propR * scale * 0.15
            const path =
              `M ${cx} ${cy} ` +
              `Q ${midX + perpX * bw} ${midY + perpY * bw} ${tipX} ${tipY} ` +
              `Q ${midX - perpX * bw} ${midY - perpY * bw} ${cx} ${cy} Z`
            return (
              <path
                key={deg}
                d={path}
                fill="var(--bg-surface)"
                stroke="var(--ink-primary)"
                strokeWidth={SW_MED}
              />
            )
          })}
          <circle cx={cx} cy={cy} r={propR * scale * 0.14} fill="var(--ink-primary)" />
          <circle cx={cx} cy={cy} r={propR * scale * 0.07} fill="var(--bg-surface)" />
        </g>
      )
    }

    return (
      <g>
        {renderNoseGear()}
        {renderTail()}
        {renderMainGear()}
        {renderWingFront(-1)}
        {renderWingFront(1)}
        {renderFuselage()}
        {renderCanopy()}
        {renderProp()}

        {/* Span dimension line above the wings */}
        <g>
          <line
            x1={frontT(-halfSpan, tipLift + tTip + finHeight * 0.4)[0]}
            y1={frontT(-halfSpan, tipLift + tTip + finHeight * 0.4)[1]}
            x2={frontT(halfSpan, tipLift + tTip + finHeight * 0.4)[0]}
            y2={frontT(halfSpan, tipLift + tTip + finHeight * 0.4)[1]}
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_HAIR}
          />
          <line
            x1={frontT(-halfSpan, tipLift + tTip + finHeight * 0.4 - 3)[0]}
            y1={frontT(-halfSpan, tipLift + tTip + finHeight * 0.4 - 3)[1]}
            x2={frontT(-halfSpan, tipLift + tTip + finHeight * 0.4 + 3)[0]}
            y2={frontT(-halfSpan, tipLift + tTip + finHeight * 0.4 + 3)[1]}
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_HAIR}
          />
          <line
            x1={frontT(halfSpan, tipLift + tTip + finHeight * 0.4 - 3)[0]}
            y1={frontT(halfSpan, tipLift + tTip + finHeight * 0.4 - 3)[1]}
            x2={frontT(halfSpan, tipLift + tTip + finHeight * 0.4 + 3)[0]}
            y2={frontT(halfSpan, tipLift + tTip + finHeight * 0.4 + 3)[1]}
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_HAIR}
          />
          <text
            x={frontT(0, tipLift + tTip + finHeight * 0.55)[0]}
            y={frontT(0, tipLift + tTip + finHeight * 0.55)[1]}
            textAnchor="middle"
            fontFamily="ui-monospace, monospace"
            fontSize={FS_LABEL}
            fill="var(--ink-tertiary)"
          >
            span {span.toFixed(2)} m · dihedral {RATIO.dihedralDeg}°
          </text>
        </g>

        {/* Exaggeration note */}
        <text
          x={FRONT.x + FRONT.w * 0.02}
          y={FRONT.y + FRONT.h - 4}
          fontFamily="ui-monospace, monospace"
          fontSize={FS_LABEL * 0.85}
          fill="var(--ink-tertiary)"
        >
          airfoil thickness exaggerated 3× for legibility
        </text>

        <text
          x={FRONT.x + FRONT.w * 0.02}
          y={FRONT.y + FRONT.h * 0.09}
          fontFamily="ui-monospace, monospace"
          fontSize={FS_LABEL * 1.1}
          fill="var(--ink-secondary)"
        >
          FRONT
        </text>
      </g>
    )
  }

  // -------- Airfoil section inset --------------------------------------
  function renderAirfoil(): ReactElement {
    // Symmetric airfoil, thickness 12% chord, drawn at a fixed size
    // inside the SECTION region.
    const inset = SECTION
    const insetCx = inset.x + inset.w / 2
    const insetCy = inset.y + inset.h / 2 + 10
    const airfoilChordPx = inset.w * 0.7
    const airfoilThicknessPx = airfoilChordPx * RATIO.airfoilThickness

    // NACA-like symmetric profile: y = 5 t (0.2969 sqrt(x)
    //     - 0.1260 x - 0.3516 x^2 + 0.2843 x^3 - 0.1015 x^4)
    // with x in [0, 1] chord fraction, t = thickness/chord.
    const t = RATIO.airfoilThickness
    function nacaY(xFrac: number): number {
      return (
        5 *
        t *
        (0.2969 * Math.sqrt(xFrac) -
          0.1260 * xFrac -
          0.3516 * xFrac * xFrac +
          0.2843 * xFrac * xFrac * xFrac -
          0.1015 * xFrac * xFrac * xFrac * xFrac)
      )
    }

    // Build closed path: top curve from LE (0) to TE (1), then back
    // along the bottom curve.
    const N = 40
    let topPath = ""
    let botPath = ""
    for (let i = 0; i <= N; i++) {
      const xFrac = i / N
      const yFrac = nacaY(xFrac)
      const px = insetCx - airfoilChordPx / 2 + xFrac * airfoilChordPx
      const pyTop = insetCy - yFrac * airfoilChordPx
      const pyBot = insetCy + yFrac * airfoilChordPx
      topPath += (i === 0 ? "M " : "L ") + px + " " + pyTop + " "
      botPath = "L " + px + " " + pyBot + " " + botPath
    }
    const closedPath = topPath + botPath + "Z"

    // Chord line
    const chordX1 = insetCx - airfoilChordPx / 2
    const chordX2 = insetCx + airfoilChordPx / 2

    return (
      <g>
        {/* Section box */}
        <rect
          x={inset.x}
          y={inset.y}
          width={inset.w}
          height={inset.h}
          fill="none"
          stroke="var(--ink-secondary)"
          strokeWidth={SW_THIN}
        />
        <text
          x={inset.x + inset.w * 0.03}
          y={inset.y + inset.h * 0.09}
          fontFamily="ui-monospace, monospace"
          fontSize={FS_LABEL * 1.05}
          fill="var(--ink-secondary)"
        >
          SECTION A-A
        </text>
        <text
          x={inset.x + inset.w * 0.03}
          y={inset.y + inset.h * 0.09 + FS_LABEL * 1.1}
          fontFamily="ui-monospace, monospace"
          fontSize={FS_LABEL * 0.9}
          fill="var(--ink-tertiary)"
        >
          airfoil · t/c = {Math.round(RATIO.airfoilThickness * 100)} %
        </text>

        {/* Airfoil body */}
        <path
          d={closedPath}
          fill="var(--bg-subtle)"
          stroke="var(--ink-primary)"
          strokeWidth={SW_MED}
        />

        {/* Chord line */}
        <line
          x1={chordX1}
          y1={insetCy}
          x2={chordX2}
          y2={insetCy}
          stroke="var(--ink-tertiary)"
          strokeWidth={SW_HAIR}
          strokeDasharray="2 2"
        />
        {/* Chord dimension label */}
        <text
          x={insetCx}
          y={insetCy + airfoilThicknessPx * 3.5}
          textAnchor="middle"
          fontFamily="ui-monospace, monospace"
          fontSize={FS_LABEL * 0.9}
          fill="var(--ink-tertiary)"
        >
          c = {chordRoot.toFixed(3)} m
        </text>
        <text
          x={inset.x + inset.w * 0.03}
          y={inset.y + inset.h * 0.92}
          fontFamily="ui-monospace, monospace"
          fontSize={FS_LABEL * 0.85}
          fill="var(--ink-tertiary)"
        >
          symmetric · placeholder
        </text>
      </g>
    )
  }

  // --- Callouts -------------------------------------------------------
  const callouts: Array<{
    ax: number
    ay: number
    lx: number
    ly: number
    label: string
    sublabel: string
    side: "left" | "right"
  }> = []

  {
    const noseX = fusLen / 2
    const tailX = -fusLen / 2
    const planNose = planT(noseX - noseR * 0.5, 0)
    const planTail = planT(tailX + fusLen * 0.14, 0)
    const planWing = planT(-chordRoot / 2 + fusWidth * 0.5 - sweepOffset * 0.5, -halfSpan * 0.5)
    const planAil = planT(chordRoot / 2 + fusWidth * 0.5 - sweepOffset * 0.7, -halfSpan * 0.72)
    const planFlap = planT(chordRoot / 2 + fusWidth * 0.5 - sweepOffset * 0.3, -halfSpan * 0.3)
    const planTurret = planT(noseX - fusWidth * 0.9, 0)
    const planProp = planT(noseX + noseR * 0.3, 0)

    callouts.push(
      {
        ax: planWing[0],
        ay: planWing[1],
        lx: 200,
        ly: 100,
        label: "WING",
        sublabel: `aspect ratio ${(span / chordRoot).toFixed(1)} · taper ${RATIO.taperRatio}`,
        side: "left",
      },
      {
        ax: planAil[0],
        ay: planAil[1],
        lx: 200,
        ly: 130,
        label: "AILERON",
        sublabel: "outboard 55–90 % TE",
        side: "left",
      },
      {
        ax: planFlap[0],
        ay: planFlap[1],
        lx: 200,
        ly: 160,
        label: "FLAP",
        sublabel: "inboard 10–50 % TE",
        side: "left",
      },
      {
        ax: planNose[0],
        ay: planNose[1],
        lx: 520,
        ly: 100,
        label: "PROPELLER",
        sublabel: `3-blade · r ${propR.toFixed(3)} m`,
        side: "right",
      },
      {
        ax: planTurret[0],
        ay: planTurret[1],
        lx: 520,
        ly: 130,
        label: "SENSOR TURRET",
        sublabel: `Ø ${(2 * turretR).toFixed(3)} m`,
        side: "right",
      },
      {
        ax: planTail[0],
        ay: planTail[1],
        lx: 520,
        ly: 160,
        label: "H-STAB + ELEVATOR",
        sublabel: `span ${tailSpan.toFixed(2)} m`,
        side: "right",
      },
      {
        ax: planProp[0],
        ay: planProp[1],
        lx: 520,
        ly: 190,
        label: "FUSELAGE",
        sublabel: `length ${fusLen.toFixed(2)} m · width ${fusWidth.toFixed(3)} m`,
        side: "right",
      },
    )
  }

  // --- Main render ----------------------------------------------------
  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${FRAME_W} ${FRAME_H}`}
      className="w-full"
      style={{ maxHeight: 560, touchAction: "none" }}
      role="img"
      aria-label="Fixed-wing UAV engineering drawing, three views and section"
      data-testid="drone-top-view"
    >
      <DrawingFrame
        x={0}
        y={0}
        width={FRAME_W}
        height={FRAME_H}
        title="UAV — FIXED WING — 3 VIEWS"
        drawingNumber="AG-DRW-UAV-FW-001"
        scaleLabel={`SCALE 1:${Math.round(1000 / scale)}`}
        revision="A"
        note="units = metres · parametric"
        footnote="plan, profile, front views share one scale; section at 4×"
      >
        {renderPlan()}
        {renderProfile()}
        {renderFront()}
        {renderAirfoil()}

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

        <ScaleBar
          x={PROFILE.x + 4}
          y={PROFILE.y + PROFILE.h + 20}
          widthData={Math.min(200, PROFILE.w * 0.3)}
          label={`${(Math.min(200, PROFILE.w * 0.3) / scale).toFixed(2)} m`}
          fontSize={9}
        />

        {/* Materials key, drawn in the top-right corner above the section box */}
        <g>
          <text
            x={FRAME_W - 30}
            y={18}
            textAnchor="end"
            fontFamily="ui-monospace, monospace"
            fontSize={9}
            fill="var(--ink-secondary)"
          >
            MATERIAL KEY
          </text>
          <text
            x={FRAME_W - 30}
            y={28}
            textAnchor="end"
            fontFamily="ui-monospace, monospace"
            fontSize={8}
            fill="var(--ink-tertiary)"
          >
            ─── composite · ~ ~ ~ foam core · /// metal
          </text>
        </g>
      </DrawingFrame>
    </svg>
  )
}
