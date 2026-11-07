/**
 * Starter templates for the Launcher.
 *
 * A template is a starting point, not a pre-run demo: picking one
 * resets the mission to DEFAULT_CONFIG, applies the template's
 * configPatch, and navigates to Step 1. The user then walks the
 * six-step workflow themselves.
 *
 * Templates are anonymous by construction: they describe physical
 * conditions and hardware classes, not named real-world systems.
 */

import type { MissionConfig, UavHardware } from "../MissionControl/missionContext"

export type TemplateConfig = {
  id: string
  name: string
  description: string
  badge: string
  configPatch: Partial<MissionConfig>
}

/** Three fixed-wing UAVs with larger receiver apertures, higher-capacity
 *  batteries, and higher mass. Exercises the fixed-wing drawing path
 *  and the endurance model. */
const FIXED_WING_HARDWARE: UavHardware[] = [
  {
    receiver_aperture_m2: 1.2,
    receiver_type: "laser_photovoltaic",
    battery_efficiency: 0.92,
    mass_kg: 8.5,
    wingspan_m: 3.0,
    battery_wh: 220,
    thermal_limit_c: 85,
    airframe: "fixed_wing",
  },
  {
    receiver_aperture_m2: 1.0,
    receiver_type: "laser_photovoltaic",
    battery_efficiency: 0.92,
    mass_kg: 7.2,
    wingspan_m: 2.6,
    battery_wh: 180,
    thermal_limit_c: 85,
    airframe: "fixed_wing",
  },
  {
    receiver_aperture_m2: 0.9,
    receiver_type: "laser_photovoltaic",
    battery_efficiency: 0.92,
    mass_kg: 6.8,
    wingspan_m: 2.4,
    battery_wh: 160,
    thermal_limit_c: 85,
    airframe: "fixed_wing",
  },
]

export const TEMPLATES: TemplateConfig[] = [
  {
    id: "quickstart",
    name: "Quickstart",
    description:
      "Four quadrotors, clear sky, ISS pass. The simplest end-to-end walkthrough: every step completes with default conditions, designed to run in under a minute.",
    badge: "MULTIROTOR · CLEAR SKY",
    configPatch: {
      n_uavs: 4,
      visibility_km: 10.0,
      cloud_factor: 0.0,
      uav_receiver_type: "laser_photovoltaic",
      transmitter_power_w: 10000.0,
    },
  },
  {
    id: "fixed-wing-endurance",
    name: "Fixed-Wing Endurance",
    description:
      "Three fixed-wing UAVs with larger receiver apertures and high-capacity batteries. Exercises the fixed-wing drawing path and the wing-loading feasibility rule.",
    badge: "FIXED WING · ENDURANCE",
    configPatch: {
      n_uavs: 3,
      visibility_km: 15.0,
      cloud_factor: 0.1,
      uav_receiver_type: "laser_photovoltaic",
      uav_hardware_list: FIXED_WING_HARDWARE,
    },
  },
  {
    id: "degraded-atmosphere",
    name: "Degraded Atmosphere (ISR)",
    description:
      "Low visibility and heavy cloud, with higher-altitude UAVs and a boosted transmitter to compensate. Exercises the atmospheric attenuation path and the epistemic transmittance intervals.",
    badge: "DEGRADED · ISR",
    configPatch: {
      n_uavs: 4,
      visibility_km: 4.0,
      cloud_factor: 0.75,
      uav_alt_m: 2000.0,
      transmitter_power_w: 15000.0,
      uav_receiver_type: "laser_photovoltaic",
    },
  },
]
