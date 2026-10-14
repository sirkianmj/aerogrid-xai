/**
 * MultirotorDetail — three-view engineering drawing of a quadrotor UAV.
 *
 * Three orthographic views plus a section inset, on one titled frame:
 *
 *   PLAN     (top-down, upper-left)
 *   PROFILE  (side, lower-left)
 *   FRONT    (forward-looking, lower-right)
 *   SECTION  (motor cross-section, upper-right)
 *
 * Every dimension derives from the wingspan parameter, which for a
 * multirotor is read as the diagonal motor-to-motor distance. All
 * other dimensions are documented ratios of that span (generic
 * multirotor conventions, no specific airframe):
 *
 *   arm length (hub to motor)   0.5 span / sqrt(2)
 *   arm width                   0.03 span
 *   motor housing diameter      0.09 span
 *   propeller diameter          0.35 span
 *   central hub diameter        0.16 span
 *   battery bay (rect, on top)  0.5 hub diameter
 *   gimbal camera diameter      0.07 span
 *   landing skid length         0.40 span
 *   antenna length (whisker)    0.15 span
 *   motor stator teeth          12
 *
 * Receiver aperture is drawn as a circle of radius sqrt(A/pi) on the
 * hub crown, at the drawing's true scale.
 *
 * Drag handles:
 *   arm end (plan view, front-right motor)   changes wingspan_m
 *   aperture (plan view, hub crown)          changes receiver_aperture_m2
 *
 * No real aircraft, manufacturer, or programme is named. Constants
 * are generic multirotor conventions, documented at the point of use.
 */

import { useRef, type ReactElement } from "react"
import { useDragSvg } from "./useDragSvg"
import { ScaleBar } from "./ScaleBar"
import { DrawingFrame } from "./DrawingFrame"
import { Callout } from "./Callout"

// --- Drawing frame and view regions (pixels) --------------------------
const FRAME_W = 820
const FRAME_H = 520

const PLAN = { x: 30, y: 35, w: 480, h: 200 }
// Front view: lower-left, directly below the plan view (third-angle).
const FRONT = { x: 30, y: 250, w: 400, h: 150 }
// Profile view: lower-right, beside the front view (third-angle).
const PROFILE = { x: 445, y: 250, w: 340, h: 150 }
const SECTION = { x: 530, y: 35, w: 260, h: 200 }

// --- Documented physical ratios (see header) --------------------------
const RATIO = {
  armLen: 0.5 / Math.SQRT2,
  armWidth: 0.03,
  motorDia: 0.09,
  propDia: 0.35,
  hubDia: 0.16,
  gimbalDia: 0.07,
  skidLen: 0.40,
  antennaLen: 0.15,
  statorTeeth: 12,
} as const

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

  // --- Derived physical dimensions (metres) ---------------------------
  const span = wingspan_m
  const armLen = RATIO.armLen * span
  const armWidth = RATIO.armWidth * span
  const motorDia = RATIO.motorDia * span
  const motorR = motorDia / 2
  const propDia = RATIO.propDia * span
  const propR = propDia / 2
  const hubDia = RATIO.hubDia * span
  const hubR = hubDia / 2
  const gimbalR = (RATIO.gimbalDia * span) / 2
  const skidLen = RATIO.skidLen * span
  const antennaLen = RATIO.antennaLen * span
  const apertureR = Math.sqrt(receiver_aperture_m2 / Math.PI)

  // --- Common scale across all views (pixels per metre) ---------------
  const planUsableW = PLAN.w * 0.9
  const planUsableH = PLAN.h * 0.9
  const profileUsableW = PROFILE.w * 0.9
  const profileUsableH = PROFILE.h * 0.85
  const frontUsableW = FRONT.w * 0.9
  const frontUsableH = FRONT.h * 0.85

  // Plan: diagonal span + prop radius on each side.
  const planExtent = span + 2 * propR
  // Profile: span across the width (arms project), motor height top
  // and bottom, gimbal below, skid below that.
  const profileHeight = motorR * 2 + gimbalR * 2 + armWidth * 2

  const scale = Math.min(
    planUsableW / planExtent,
    planUsableH / planExtent,
    profileUsableW / (skidLen + armWidth * 2),
    profileUsableH / profileHeight,
    frontUsableW / (span + 2 * propR),
    frontUsableH / profileHeight,
  )

  // --- Per-view transform: metres -> pixels in that region ------------
  type Region = { x: number; y: number; w: number; h: number }
  function makeTransform(region: Region) {
    const cx = region.x + region.w / 2
    const cy = region.y + region.h / 2
    return (mx: number, my: number): [number, number] => [
      cx + mx * scale,
      cy - my * scale,
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
  const apertureDrag = useDragSvg(svgRef, { w: FRAME_W, h: FRAME_H }, (dx) => {
    const newR = Math.max(0.01, apertureR + dx / scale)
    onChange({ receiver_aperture_m2: Math.PI * newR * newR })
  })
  const armDrag = useDragSvg(svgRef, { w: FRAME_W, h: FRAME_H }, (dx) => {
    const newSpan = Math.max(0.2, span + (2 * dx) / scale)
    onChange({ wingspan_m: newSpan })
  })

  // Motor positions in the PLAN view (X-config, 45/135/225/315 degrees).
  const motorAngles = [45, 135, 225, 315] as const
  const motors = motorAngles.map((deg) => {
    const rad = (deg * Math.PI) / 180
    return { x: armLen * Math.cos(rad), y: armLen * Math.sin(rad), deg }
  })
  // Front-right motor, used for the arm-end drag handle.
  const armHandleMotor = motors[3]

  // --- View helpers ---------------------------------------------------

  function P(t: (mx: number, my: number) => [number, number], mx: number, my: number): string {
    const [x, y] = t(mx, my)
    return `${x} ${y}`
  }

  // -------- PLAN view (top-down) ---------------------------------------
  function renderPlan(): ReactElement {
    // Arms: tapered bands drawn as quads from hub edge to motor centre.
    function renderArm(m: { x: number; y: number }, idx: number): ReactElement {
      const ex = m.x
      const ey = m.y
      const len = Math.sqrt(ex * ex + ey * ey)
      const ux = ex / len
      const uy = ey / len
      const px = -uy
      const py = ux
      const hw = armWidth / 2
      const startR = hubR * 0.75
      // Four corners: hub left, hub right, tip right, tip left.
      const hxL = ux * startR + px * hw
      const hyL = uy * startR + py * hw
      const hxR = ux * startR - px * hw
      const hyR = uy * startR - py * hw
      const txR = ex - px * hw * 0.6
      const tyR = ey - py * hw * 0.6
      const txL = ex + px * hw * 0.6
      const tyL = ey + py * hw * 0.6
      const path =
        `M ${P(planT, hxL, hyL)} ` +
        `L ${P(planT, txL, tyL)} ` +
        `L ${P(planT, txR, tyR)} ` +
        `L ${P(planT, hxR, hyR)} Z`

      return (
        <g key={idx}>
          <path d={path} fill="var(--bg-subtle)" stroke="var(--ink-secondary)" strokeWidth={SW_MED} />
          {/* Motor mounting plate under the motor (small rect) */}
          <rect
            x={planT(ex - motorR * 1.2, ey + motorR * 1.2)[0]}
            y={planT(ex - motorR * 1.2, ey + motorR * 1.2)[1]}
            width={motorR * 2.4 * scale}
            height={motorR * 2.4 * scale}
            fill="none"
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_HAIR}
            strokeDasharray="2 2"
          />
        </g>
      )
    }

    function renderMotorTop(m: { x: number; y: number }, idx: number): ReactElement {
      return (
        <g key={`motor${idx}`}>
          {/* Motor housing, outer ring */}
          <circle
            cx={planT(m.x, m.y)[0]}
            cy={planT(m.x, m.y)[1]}
            r={motorR * scale}
            fill="var(--bg-surface)"
            stroke="var(--ink-primary)"
            strokeWidth={SW_MED}
          />
          {/* Cooling fins: 12 radial lines */}
          {Array.from({ length: 12 }).map((_, i) => {
            const a = (i * 2 * Math.PI) / 12
            const r1 = motorR * 0.55
            const r2 = motorR * 0.95
            return (
              <line
                key={i}
                x1={planT(m.x + Math.cos(a) * r1, m.y + Math.sin(a) * r1)[0]}
                y1={planT(m.x + Math.cos(a) * r1, m.y + Math.sin(a) * r1)[1]}
                x2={planT(m.x + Math.cos(a) * r2, m.y + Math.sin(a) * r2)[0]}
                y2={planT(m.x + Math.cos(a) * r2, m.y + Math.sin(a) * r2)[1]}
                stroke="var(--ink-tertiary)"
                strokeWidth={SW_HAIR}
                opacity={0.7}
              />
            )
          })}
          {/* Inner hub */}
          <circle
            cx={planT(m.x, m.y)[0]}
            cy={planT(m.x, m.y)[1]}
            r={motorR * 0.32 * scale}
            fill="var(--ink-primary)"
          />
        </g>
      )
    }

    function renderPropTop(m: { x: number; y: number; deg: number }, idx: number): ReactElement {
      const blades = [0, 180]
      return (
        <g key={`prop${idx}`} opacity={0.85}>
          {blades.map((deg) => {
            const a = ((deg + m.deg) * Math.PI) / 180
            const ca = Math.cos(a)
            const sa = Math.sin(a)
            const bw = propR * 0.22
            const px = -sa * bw
            const py = ca * bw
            const tipX = m.x + ca * propR
            const tipY = m.y + sa * propR
            const midX = m.x + ca * propR * 0.55
            const midY = m.y + sa * propR * 0.55
            const path =
              `M ${P(planT, m.x, m.y)} ` +
              `Q ${P(planT, midX + px, midY + py)} ${P(planT, tipX, tipY)} ` +
              `Q ${P(planT, midX - px, midY - py)} ${P(planT, m.x, m.y)} Z`
            return (
              <g key={deg}>
                <path d={path} fill="var(--bg-subtle)" stroke="var(--ink-secondary)" strokeWidth={SW_THIN} />
                <line
                  x1={planT(tipX + px * 0.25, tipY + py * 0.25)[0]}
                  y1={planT(tipX + px * 0.25, tipY + py * 0.25)[1]}
                  x2={planT(tipX - px * 0.25, tipY - py * 0.25)[0]}
                  y2={planT(tipX - px * 0.25, tipY - py * 0.25)[1]}
                  stroke="var(--ink-tertiary)"
                  strokeWidth={SW_HAIR}
                />
              </g>
            )
          })}
        </g>
      )
    }

    return (
      <g>
        {/* Skids, drawn as two parallel rectangles under the hub */}
        <rect
          x={planT(-hubR * 1.15, -hubR * 0.35)[0]}
          y={planT(-hubR * 1.15, -hubR * 0.35)[1]}
          width={hubR * 2.3 * scale}
          height={hubR * 0.12 * scale}
          fill="var(--ink-tertiary)"
          opacity={0.4}
        />
        <rect
          x={planT(-hubR * 1.15, hubR * 0.23)[0]}
          y={planT(-hubR * 1.15, hubR * 0.23)[1]}
          width={hubR * 2.3 * scale}
          height={hubR * 0.12 * scale}
          fill="var(--ink-tertiary)"
          opacity={0.4}
        />

        {/* Arms first (under the props and motors) */}
        {motors.map((m, i) => renderArm(m, i))}
        {/* Props */}
        {motors.map((m, i) => renderPropTop(m, i))}
        {/* Motors on top of props */}
        {motors.map((m, i) => renderMotorTop(m, i))}

        {/* Central hub body */}
        <circle
          cx={planT(0, 0)[0]}
          cy={planT(0, 0)[1]}
          r={hubR * scale}
          fill="var(--bg-surface)"
          stroke="var(--ink-primary)"
          strokeWidth={SW_MAIN}
        />
        {/* Hub panel lines */}
        <circle
          cx={planT(0, 0)[0]}
          cy={planT(0, 0)[1]}
          r={hubR * 0.65 * scale}
          fill="none"
          stroke="var(--ink-tertiary)"
          strokeWidth={SW_HAIR}
        />
        <line
          x1={planT(-hubR * 0.65, 0)[0]}
          y1={planT(-hubR * 0.65, 0)[1]}
          x2={planT(hubR * 0.65, 0)[0]}
          y2={planT(hubR * 0.65, 0)[1]}
          stroke="var(--ink-tertiary)"
          strokeWidth={SW_HAIR}
        />
        <line
          x1={planT(0, -hubR * 0.65)[0]}
          y1={planT(0, -hubR * 0.65)[1]}
          x2={planT(0, hubR * 0.65)[0]}
          y2={planT(0, hubR * 0.65)[1]}
          stroke="var(--ink-tertiary)"
          strokeWidth={SW_HAIR}
        />

        {/* Battery bay on top */}
        <rect
          x={planT(-hubR * 0.55, -hubR * 0.35)[0]}
          y={planT(-hubR * 0.55, -hubR * 0.35)[1]}
          width={hubR * 1.1 * scale}
          height={hubR * 0.7 * scale}
          rx={hubR * 0.08 * scale}
          fill="var(--bg-subtle)"
          stroke="var(--ink-secondary)"
          strokeWidth={SW_THIN}
        />
        <line
          x1={planT(-hubR * 0.55, 0)[0]}
          y1={planT(-hubR * 0.55, 0)[1]}
          x2={planT(hubR * 0.55, 0)[0]}
          y2={planT(hubR * 0.55, 0)[1]}
          stroke="var(--ink-tertiary)"
          strokeWidth={SW_HAIR}
        />

        {/* Two antenna whips */}
        <line
          x1={planT(hubR * 0.4, -hubR * 0.7)[0]}
          y1={planT(hubR * 0.4, -hubR * 0.7)[1]}
          x2={planT(hubR * 0.9, -hubR * 1.5)[0]}
          y2={planT(hubR * 0.9, -hubR * 1.5)[1]}
          stroke="var(--ink-primary)"
          strokeWidth={SW_THIN}
        />
        <circle
          cx={planT(hubR * 0.9, -hubR * 1.5)[0]}
          cy={planT(hubR * 0.9, -hubR * 1.5)[1]}
          r={2}
          fill="var(--ink-primary)"
        />
        <line
          x1={planT(-hubR * 0.4, -hubR * 0.7)[0]}
          y1={planT(-hubR * 0.4, -hubR * 0.7)[1]}
          x2={planT(-hubR * 0.9, -hubR * 1.5)[0]}
          y2={planT(-hubR * 0.9, -hubR * 1.5)[1]}
          stroke="var(--ink-primary)"
          strokeWidth={SW_THIN}
        />
        <circle
          cx={planT(-hubR * 0.9, -hubR * 1.5)[0]}
          cy={planT(-hubR * 0.9, -hubR * 1.5)[1]}
          r={2}
          fill="var(--ink-primary)"
        />

        {/* Gimbal camera, beneath the hub (drawn as a faint circle) */}
        <circle
          cx={planT(0, 0)[0]}
          cy={planT(0, 0)[1]}
          r={gimbalR * scale}
          fill="var(--bg-subtle)"
          stroke="var(--ink-tertiary)"
          strokeWidth={SW_THIN}
          opacity={0.55}
        />
        <circle
          cx={planT(0, 0)[0]}
          cy={planT(0, 0)[1]}
          r={gimbalR * 0.5 * scale}
          fill="none"
          stroke="var(--ink-tertiary)"
          strokeWidth={SW_HAIR}
          opacity={0.55}
        />

        {/* Receiver aperture on the crown */}
        <circle
          cx={planT(hubR * 0.2, 0)[0]}
          cy={planT(hubR * 0.2, 0)[1]}
          r={apertureR * scale}
          fill="var(--status-green)"
          fillOpacity={0.18}
          stroke="var(--status-green)"
          strokeWidth={SW_MED}
        />
        <circle
          cx={planT(hubR * 0.2 + apertureR, 0)[0]}
          cy={planT(hubR * 0.2 + apertureR, 0)[1]}
          r={5}
          fill="var(--status-orange)"
          stroke="var(--ink-primary)"
          strokeWidth={SW_MED}
          style={{ cursor: "ew-resize" }}
          data-testid="aperture-handle"
          {...apertureDrag}
        />

        {/* Arm-end drag handle on the front-right motor */}
        <circle
          cx={planT(armHandleMotor.x, armHandleMotor.y)[0]}
          cy={planT(armHandleMotor.x, armHandleMotor.y)[1]}
          r={5}
          fill="var(--status-green)"
          stroke="var(--ink-primary)"
          strokeWidth={SW_MED}
          style={{ cursor: "ew-resize" }}
          data-testid="wingtip-handle"
          {...armDrag}
        />

        {/* Diagonal span dimension callout */}
        <g>
          <line
            x1={planT(-armLen * 0.9, -armLen * 0.9)[0]}
            y1={planT(-armLen * 0.9, -armLen * 0.9)[1]}
            x2={planT(armLen * 0.9, armLen * 0.9)[0]}
            y2={planT(armLen * 0.9, armLen * 0.9)[1]}
            stroke="var(--ink-tertiary)"
            strokeWidth={SW_HAIR}
            strokeDasharray="3 3"
          />
          <text
            x={planT(0, armLen * 1.4)[0]}
            y={planT(0, armLen * 1.4)[1]}
            textAnchor="middle"
            fontFamily="ui-monospace, monospace"
            fontSize={FS_LABEL}
            fill="var(--ink-tertiary)"
          >
            span {span.toFixed(2)} m (motor-to-motor)
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

  // -------- PROFILE view (side, from the +Y side) ----------------------
  function renderProfile(): ReactElement {
    // In this view, the aircraft is viewed from the side. The four
    // motors appear as two rows (near pair and far pair), the arms
    // project horizontally, the hub sits in the middle.
    // Horizontal axis in this view = arm axis in-plane with the viewer.
    // We draw the aircraft "facing right" with the plane of the arms
    // in the horizontal.

    const armLenPx = armLen

    // Arms seen edge-on: two horizontal bars at ±armLen from centre.
    return (
      <g>
        {/* Skids, drawn as long bars below */}
        <rect
          x={profileT(-skidLen / 2, -hubR - armWidth * 0.5 - gimbalR - motorR)[0]}
          y={profileT(-skidLen / 2, -hubR - armWidth * 0.5 - gimbalR - motorR)[1]}
          width={skidLen * scale}
          height={armWidth * 0.6 * scale}
          fill="var(--ink-primary)"
          opacity={0.65}
        />

        {/* Hub body (as a rounded rectangle when seen from the side) */}
        <rect
          x={profileT(-hubR, hubR)[0]}
          y={profileT(-hubR, hubR)[1]}
          width={hubR * 2 * scale}
          height={hubR * 2 * scale}
          rx={hubR * 0.15 * scale}
          fill="var(--bg-surface)"
          stroke="var(--ink-primary)"
          strokeWidth={SW_MAIN}
        />
        {/* Battery bay top cap */}
        <rect
          x={profileT(-hubR * 0.55, hubR + armWidth * 0.5)[0]}
          y={profileT(-hubR * 0.55, hubR + armWidth * 0.5)[1]}
          width={hubR * 1.1 * scale}
          height={armWidth * 1.1 * scale}
          fill="var(--bg-subtle)"
          stroke="var(--ink-secondary)"
          strokeWidth={SW_THIN}
        />

        {/* Arms in profile: two arms project forward and two back.
            Their projection in this view is a horizontal segment to
            each side at the hub's mid-height. */}
        <rect
          x={profileT(-armLenPx - motorR, 0)[0]}
          y={profileT(-armLenPx - motorR, 0)[1]}
          width={(armLenPx + motorR) * 2 * scale}
          height={armWidth * scale}
          fill="var(--bg-subtle)"
          stroke="var(--ink-secondary)"
          strokeWidth={SW_THIN}
        />

        {/* Motor housings at each end of the arm */}
        <circle
          cx={profileT(-armLenPx, 0)[0]}
          cy={profileT(-armLenPx, 0)[1]}
          r={motorR * scale}
          fill="var(--bg-surface)"
          stroke="var(--ink-primary)"
          strokeWidth={SW_MED}
        />
        <circle
          cx={profileT(armLenPx, 0)[0]}
          cy={profileT(armLenPx, 0)[1]}
          r={motorR * scale}
          fill="var(--bg-surface)"
          stroke="var(--ink-primary)"
          strokeWidth={SW_MED}
        />
        {/* Motor shafts visible above each */}
        <line
          x1={profileT(-armLenPx, motorR)[0]}
          y1={profileT(-armLenPx, motorR)[1]}
          x2={profileT(-armLenPx, motorR + armWidth * 0.5)[0]}
          y2={profileT(-armLenPx, motorR + armWidth * 0.5)[1]}
          stroke="var(--ink-primary)"
          strokeWidth={SW_THIN}
        />
        <line
          x1={profileT(armLenPx, motorR)[0]}
          y1={profileT(armLenPx, motorR)[1]}
          x2={profileT(armLenPx, motorR + armWidth * 0.5)[0]}
          y2={profileT(armLenPx, motorR + armWidth * 0.5)[1]}
          stroke="var(--ink-primary)"
          strokeWidth={SW_THIN}
        />

        {/* Propeller disks edge-on (two vertical lines at motor centres) */}
        <line
          x1={profileT(-armLenPx, -propR)[0]}
          y1={profileT(-armLenPx, -propR)[1]}
          x2={profileT(-armLenPx, propR)[0]}
          y2={profileT(-armLenPx, propR)[1]}
          stroke="var(--ink-secondary)"
          strokeWidth={SW_THIN}
          opacity={0.7}
        />
        <line
          x1={profileT(armLenPx, -propR)[0]}
          y1={profileT(armLenPx, -propR)[1]}
          x2={profileT(armLenPx, propR)[0]}
          y2={profileT(armLenPx, propR)[1]}
          stroke="var(--ink-secondary)"
          strokeWidth={SW_THIN}
          opacity={0.7}
        />

        {/* Gimbal camera below the hub */}
        <circle
          cx={profileT(0, -hubR - gimbalR * 1.1)[0]}
          cy={profileT(0, -hubR - gimbalR * 1.1)[1]}
          r={gimbalR * scale}
          fill="var(--bg-subtle)"
          stroke="var(--ink-secondary)"
          strokeWidth={SW_THIN}
        />
        <circle
          cx={profileT(0, -hubR - gimbalR * 1.1)[0]}
          cy={profileT(0, -hubR - gimbalR * 1.1)[1]}
          r={gimbalR * 0.5 * scale}
          fill="none"
          stroke="var(--ink-tertiary)"
          strokeWidth={SW_HAIR}
        />
        {/* Support yoke from hub down to gimbal */}
        <line
          x1={profileT(0, -hubR)[0]}
          y1={profileT(0, -hubR)[1]}
          x2={profileT(0, -hubR - gimbalR * 0.6)[0]}
          y2={profileT(0, -hubR - gimbalR * 0.6)[1]}
          stroke="var(--ink-primary)"
          strokeWidth={SW_THIN}
        />

        {/* Ground reference line for the skid */}
        <line
          x1={profileT(-skidLen * 0.6, -hubR - armWidth * 0.5 - gimbalR - motorR - armWidth * 0.3)[0]}
          y1={profileT(-skidLen * 0.6, -hubR - armWidth * 0.5 - gimbalR - motorR - armWidth * 0.3)[1]}
          x2={profileT(skidLen * 0.6, -hubR - armWidth * 0.5 - gimbalR - motorR - armWidth * 0.3)[0]}
          y2={profileT(skidLen * 0.6, -hubR - armWidth * 0.5 - gimbalR - motorR - armWidth * 0.3)[1]}
          stroke="var(--ink-tertiary)"
          strokeWidth={SW_HAIR}
          strokeDasharray="4 3"
          opacity={0.6}
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

  // -------- FRONT view -------------------------------------------------
  function renderFront(): ReactElement {
    // Viewed from the front, the four arms project forward-left,
    // forward-right, backward-left, backward-right. From this vantage,
    // you see the front two motors (left and right) prominently and
    // the rear two behind.
    // Horizontal axis = X, vertical = height above ground.

    return (
      <g>
        {/* Skid cross-bar at the bottom */}
        <rect
          x={frontT(-hubR * 1.15, -hubR - gimbalR - motorR - armWidth)[0]}
          y={frontT(-hubR * 1.15, -hubR - gimbalR - motorR - armWidth)[1]}
          width={hubR * 2.3 * scale}
          height={armWidth * 0.6 * scale}
          fill="var(--ink-primary)"
          opacity={0.65}
        />

        {/* Hub body oval (seen from the front) */}
        <ellipse
          cx={frontT(0, 0)[0]}
          cy={frontT(0, 0)[1]}
          rx={hubR * 0.95 * scale}
          ry={hubR * 1.1 * scale}
          fill="var(--bg-surface)"
          stroke="var(--ink-primary)"
          strokeWidth={SW_MAIN}
        />
        {/* Battery bay visible on the crown */}
        <rect
          x={frontT(-hubR * 0.5, hubR * 1.15)[0]}
          y={frontT(-hubR * 0.5, hubR * 1.15)[1]}
          width={hubR * 1.0 * scale}
          height={armWidth * 1.2 * scale}
          fill="var(--bg-subtle)"
          stroke="var(--ink-secondary)"
          strokeWidth={SW_THIN}
        />

        {/* Two arms project forward-left and forward-right.
            Each shows as a bar from the hub centre to the motor. */}
        {[-1, 1].map((side) => {
          const tipX = side * armLen * Math.cos(Math.PI / 4)
          const tipY = armLen * Math.sin(Math.PI / 4) // forward arm rises slightly in this projection
          return (
            <g key={side}>
              <line
                x1={frontT(0, 0)[0]}
                y1={frontT(0, 0)[1]}
                x2={frontT(tipX, tipY)[0]}
                y2={frontT(tipX, tipY)[1]}
                stroke="var(--ink-secondary)"
                strokeWidth={SW_MED}
              />
              {/* Motor housing at tip */}
              <circle
                cx={frontT(tipX, tipY)[0]}
                cy={frontT(tipX, tipY)[1]}
                r={motorR * scale}
                fill="var(--bg-surface)"
                stroke="var(--ink-primary)"
                strokeWidth={SW_MED}
              />
              {/* Cooling fins */}
              {Array.from({ length: 8 }).map((_, i) => {
                const a = (i * 2 * Math.PI) / 8
                return (
                  <line
                    key={i}
                    x1={frontT(tipX + Math.cos(a) * motorR * 0.5, tipY + Math.sin(a) * motorR * 0.5)[0]}
                    y1={frontT(tipX + Math.cos(a) * motorR * 0.5, tipY + Math.sin(a) * motorR * 0.5)[1]}
                    x2={frontT(tipX + Math.cos(a) * motorR * 0.9, tipY + Math.sin(a) * motorR * 0.9)[0]}
                    y2={frontT(tipX + Math.cos(a) * motorR * 0.9, tipY + Math.sin(a) * motorR * 0.9)[1]}
                    stroke="var(--ink-tertiary)"
                    strokeWidth={SW_HAIR}
                  />
                )
              })}
              {/* Propeller disk face-on */}
              <circle
                cx={frontT(tipX, tipY)[0]}
                cy={frontT(tipX, tipY)[1]}
                r={propR * scale}
                fill="none"
                stroke="var(--ink-tertiary)"
                strokeWidth={SW_THIN}
                strokeDasharray="3 2"
                opacity={0.6}
              />
              {/* Two blade-tip dots */}
              <circle
                cx={frontT(tipX + propR, tipY)[0]}
                cy={frontT(tipX + propR, tipY)[1]}
                r={2}
                fill="var(--ink-tertiary)"
              />
              <circle
                cx={frontT(tipX - propR, tipY)[0]}
                cy={frontT(tipX - propR, tipY)[1]}
                r={2}
                fill="var(--ink-tertiary)"
              />
            </g>
          )
        })}

        {/* Rear arms hinted as faint lines behind the hub */}
        {[-1, 1].map((side) => {
          const tipX = side * armLen * Math.cos(Math.PI / 4)
          const tipY = -armLen * Math.sin(Math.PI / 4)
          return (
            <g key={`rear${side}`} opacity={0.4}>
              <line
                x1={frontT(0, 0)[0]}
                y1={frontT(0, 0)[1]}
                x2={frontT(tipX, tipY)[0]}
                y2={frontT(tipX, tipY)[1]}
                stroke="var(--ink-tertiary)"
                strokeWidth={SW_THIN}
                strokeDasharray="2 2"
              />
              <circle
                cx={frontT(tipX, tipY)[0]}
                cy={frontT(tipX, tipY)[1]}
                r={motorR * scale * 0.85}
                fill="none"
                stroke="var(--ink-tertiary)"
                strokeWidth={SW_THIN}
              />
            </g>
          )
        })}

        {/* Gimbal camera below the hub */}
        <circle
          cx={frontT(0, -hubR - gimbalR * 1.1)[0]}
          cy={frontT(0, -hubR - gimbalR * 1.1)[1]}
          r={gimbalR * scale}
          fill="var(--bg-subtle)"
          stroke="var(--ink-secondary)"
          strokeWidth={SW_THIN}
        />
        <circle
          cx={frontT(0, -hubR - gimbalR * 1.1)[0]}
          cy={frontT(0, -hubR - gimbalR * 1.1)[1]}
          r={gimbalR * 0.5 * scale}
          fill="none"
          stroke="var(--ink-tertiary)"
          strokeWidth={SW_HAIR}
        />

        {/* View label */}
        <text
          x={FRONT.x + FRONT.w * 0.02}
          y={FRONT.y + FRONT.h * 0.08}
          fontFamily="ui-monospace, monospace"
          fontSize={FS_LABEL * 1.1}
          fill="var(--ink-secondary)"
        >
          FRONT
        </text>
      </g>
    )
  }

  // -------- Motor section inset ----------------------------------------
  function renderMotorSection(): ReactElement {
    const inset = SECTION
    const cx = inset.x + inset.w / 2
    const cy = inset.y + inset.h / 2 + 5
    const outerR = inset.w * 0.32

    // Cross-section of a brushless motor: outer bell with cooling
    // fins, stator teeth around the inner circumference, rotor shaft
    // through the centre with bearings.
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
          SECTION B-B
        </text>
        <text
          x={inset.x + inset.w * 0.03}
          y={inset.y + inset.h * 0.09 + FS_LABEL * 1.1}
          fontFamily="ui-monospace, monospace"
          fontSize={FS_LABEL * 0.9}
          fill="var(--ink-tertiary)"
        >
          outrunner brushless · 12N/14P
        </text>

        {/* Outer bell (housing) */}
        <circle
          cx={cx}
          cy={cy}
          r={outerR}
          fill="var(--bg-subtle)"
          stroke="var(--ink-primary)"
          strokeWidth={SW_MED}
        />
        {/* Cooling fins on the outer circumference */}
        {Array.from({ length: 12 }).map((_, i) => {
          const a = (i * 2 * Math.PI) / 12
          const r1 = outerR * 1.02
          const r2 = outerR * 1.10
          return (
            <line
              key={i}
              x1={cx + Math.cos(a) * r1}
              y1={cy + Math.sin(a) * r1}
              x2={cx + Math.cos(a) * r2}
              y2={cy + Math.sin(a) * r2}
              stroke="var(--ink-secondary)"
              strokeWidth={SW_THIN}
            />
          )
        })}
        {/* Inner stator teeth */}
        {Array.from({ length: RATIO.statorTeeth }).map((_, i) => {
          const a = (i * 2 * Math.PI) / RATIO.statorTeeth
          const r1 = outerR * 0.55
          const r2 = outerR * 0.85
          const toothW = (2 * Math.PI * outerR) / RATIO.statorTeeth * 0.35
          // Draw tooth as a small rectangle
          const tx = cx + Math.cos(a) * r1
          const ty = cy + Math.sin(a) * r1
          const rx = cx + Math.cos(a) * r2
          const ry = cy + Math.sin(a) * r2
          const perpA = a + Math.PI / 2
          const hx = Math.cos(perpA) * toothW * 0.5
          const hy = Math.sin(perpA) * toothW * 0.5
          const path = `M ${tx + hx} ${ty + hy} L ${rx + hx} ${ry + hy} L ${rx - hx} ${ry - hy} L ${tx - hx} ${ty - hy} Z`
          return (
            <path
              key={i}
              d={path}
              fill="var(--bg-surface)"
              stroke="var(--ink-secondary)"
              strokeWidth={SW_HAIR}
            />
          )
        })}
        {/* Rotor shaft */}
        <circle cx={cx} cy={cy} r={outerR * 0.28} fill="var(--ink-primary)" />
        {/* Bearings */}
        <circle cx={cx} cy={cy} r={outerR * 0.4} fill="none" stroke="var(--ink-tertiary)" strokeWidth={SW_HAIR} />
        <circle cx={cx} cy={cy} r={outerR * 0.5} fill="none" stroke="var(--ink-tertiary)" strokeWidth={SW_HAIR} />

        {/* Dimension label */}
        <text
          x={cx}
          y={inset.y + inset.h * 0.92}
          textAnchor="middle"
          fontFamily="ui-monospace, monospace"
          fontSize={FS_LABEL * 0.9}
          fill="var(--ink-tertiary)"
        >
          Ø {motorDia.toFixed(3)} m
        </text>
      </g>
    )
  }

  // --- Callouts --------------------------------------------------------
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
    const hubCrown = planT(hubR * 0.2, 0)
    const armTip = planT(motors[0].x, motors[0].y)
    const propEdge = planT(motors[0].x + propR, motors[0].y)
    const antenna = planT(hubR * 0.9, -hubR * 1.5)
    const gimbal = planT(gimbalR * 0.7, 0)

    callouts.push(
      {
        ax: hubCrown[0],
        ay: hubCrown[1],
        lx: 200,
        ly: 100,
        label: "RECEIVER APERTURE",
        sublabel: `A ${receiver_aperture_m2.toFixed(3)} m² · Ø ${(2 * apertureR).toFixed(3)} m`,
        side: "left",
      },
      {
        ax: armTip[0],
        ay: armTip[1],
        lx: 200,
        ly: 130,
        label: "MOTOR HOUSING",
        sublabel: `Ø ${motorDia.toFixed(3)} m · 12 fins`,
        side: "left",
      },
      {
        ax: propEdge[0],
        ay: propEdge[1],
        lx: 200,
        ly: 160,
        label: "PROPELLER",
        sublabel: `2-blade · r ${propR.toFixed(3)} m`,
        side: "left",
      },
      {
        ax: hubCrown[0],
        ay: hubCrown[1],
        lx: 500,
        ly: 100,
        label: "HUB",
        sublabel: `Ø ${hubDia.toFixed(3)} m`,
        side: "right",
      },
      {
        ax: antenna[0],
        ay: antenna[1],
        lx: 500,
        ly: 130,
        label: "ANTENNA ×2",
        sublabel: `whip · ${antennaLen.toFixed(3)} m`,
        side: "right",
      },
      {
        ax: gimbal[0],
        ay: gimbal[1],
        lx: 500,
        ly: 160,
        label: "GIMBAL CAMERA",
        sublabel: `Ø ${(gimbalR * 2).toFixed(3)} m`,
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
      aria-label="Multirotor UAV engineering drawing, three views and motor section"
      data-testid="drone-top-view"
    >
      <DrawingFrame
        x={0}
        y={0}
        width={FRAME_W}
        height={FRAME_H}
        title="UAV — MULTIROTOR — 3 VIEWS"
        drawingNumber="AG-DRW-UAV-MR-001"
        scaleLabel={`SCALE 1:${Math.round(1000 / scale)}`}
        revision="A"
        note="units = metres · parametric"
        footnote="plan, profile, front views share one scale; motor section at 8×"
      >
        {renderPlan()}
        {renderProfile()}
        {renderFront()}
        {renderMotorSection()}

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
          y={PROFILE.y + PROFILE.h + 22}
          widthData={Math.min(200, PROFILE.w * 0.3)}
          label={`${(Math.min(200, PROFILE.w * 0.3) / scale).toFixed(2)} m`}
          fontSize={9}
        />

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
            ─── carbon composite · /// metal · ··· dashed = outline
          </text>
        </g>
      </DrawingFrame>
    </svg>
  )
}
