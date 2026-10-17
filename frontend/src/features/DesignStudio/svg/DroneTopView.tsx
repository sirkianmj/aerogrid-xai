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

import { FixedWingDetail } from "./FixedWingDetail"
import { MultirotorDetail } from "./MultirotorDetail"

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
  const isMulti = airframe === "multirotor"
  const title = isMulti ? "UAV — MULTIROTOR — 3 VIEWS" : "UAV — FIXED WING — 3 VIEWS"
  const drawingNumber = isMulti ? "AG-DRW-UAV-MR-001" : "AG-DRW-UAV-FW-001"
  const footnote = isMulti
    ? "plan, profile, front views share one scale; motor section at 8×"
    : "plan, profile, front views share one scale; section at 4×"

  const svg = isMulti ? (
    <MultirotorDetail
      wingspan_m={wingspan_m}
      receiver_aperture_m2={receiver_aperture_m2}
      onChange={onChange}
      highlighted={highlighted}
    />
  ) : (
    <FixedWingDetail
      wingspan_m={wingspan_m}
      receiver_aperture_m2={receiver_aperture_m2}
      onChange={onChange}
      highlighted={highlighted}
    />
  )

  return (
    <div className="relative mx-auto max-w-[1100px] rounded-xl border border-[var(--border-hairline)] bg-[var(--bg-surface)] shadow-sm overflow-hidden">
      {/* Top Bar: Title & Material Key */}
      <div className="flex justify-between items-start border-b border-[var(--border-hairline)] p-4 bg-[var(--bg-subtle)]">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
          <p className="font-mono text-[10px] text-[var(--ink-tertiary)] mt-1">units = metres · parametric</p>
        </div>
        <div className="font-mono text-[9px] text-[var(--ink-tertiary)] border border-[var(--border-hairline)] p-2 rounded bg-[var(--bg-surface)]">
          <div className="font-semibold mb-1 text-[var(--ink-secondary)]">MATERIAL KEY</div>
          <div>── composite · ~~ foam core · /// metal</div>
        </div>
      </div>

      {/* The SVG Drawing */}
      <div className="p-4 bg-[var(--bg-canvas)]">
         {svg}
      </div>

      {/* Bottom Grid: Notes & Title Block */}
      <div className="grid grid-cols-3 gap-0 border-t border-[var(--border-hairline)] bg-[var(--bg-subtle)]">
        {/* Notes */}
        <div className="col-span-2 border-r border-[var(--border-hairline)] p-4 bg-[var(--bg-surface)]">
          <div className="font-mono text-[10px] text-[var(--ink-tertiary)]">
            {footnote}
            <br/><br/>
            airfoil thickness exaggerated 3x for legibility
          </div>
        </div>

        {/* Title Block */}
        <div className="flex flex-col justify-between bg-[var(--bg-surface)]">
          <div className="p-4 border-b border-[var(--border-hairline)]">
            <div className="font-bold text-sm tracking-wider">{title}</div>
            <div className="text-[10px] text-[var(--ink-tertiary)] font-mono mt-1">units = metres · parametric</div>
          </div>
          <div className="grid grid-cols-2 text-[10px] font-mono divide-x divide-[var(--border-hairline)] border-b border-[var(--border-hairline)]">
            <div className="p-3">{drawingNumber}</div>
            <div className="p-3 text-right">SCALE 1:9</div>
          </div>
          <div className="grid grid-cols-2 text-[10px] font-mono divide-x divide-[var(--border-hairline)]">
            <div className="p-3">REV A</div>
            <div className="p-3 text-right">SI units</div>
          </div>
        </div>
      </div>
    </div>
  )
}
