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
  if (airframe === "multirotor") {
    return (
      <MultirotorDetail
        wingspan_m={wingspan_m}
        receiver_aperture_m2={receiver_aperture_m2}
        onChange={onChange}
        highlighted={highlighted}
      />
    )
  }
  return (
    <FixedWingDetail
      wingspan_m={wingspan_m}
      receiver_aperture_m2={receiver_aperture_m2}
      onChange={onChange}
      highlighted={highlighted}
    />
  )
}
