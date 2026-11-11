/**
 * Crown-jewel starter templates.
 *
 * Each template is a fully-specified mission: satellite orbit, per-UAV
 * hardware, atmosphere, transmitter. Picking one resets the mission,
 * applies the patch, and navigates to Step 1. Every step's Run button
 * then produces real results through the same backend paths the user
 * would exercise manually — no fabricated outputs.
 *
 * The three templates exercise three distinct regimes. They are the
 * reference cases any new user should run first to see the full
 * instrument in action:
 *
 *   1. Reference LEO     — the canonical CLEAR-D case the paper describes.
 *                          ISS-class orbit, multirotor fleet, clear sky.
 *   2. SSO Fixed-Wing    — a sun-synchronous polar orbit at 1500 km,
 *                          fixed-wing endurance aircraft. Exercises the
 *                          fixed-wing drawing path, the polar orbit class,
 *                          and the long-slant-range link budget.
 *   3. Contested Sky     — ISS-class orbit with 4 km visibility, 75% cloud,
 *                          and UAVs at 2000 m altitude to climb above the
 *                          worst weather. Demonstrates the atmosphere as
 *                          the limiting factor: transmittance collapses
 *                          and epistemic intervals widen.
 *
 * Every template uses satellite_elements (custom Keplerian) so both the
 * satellite designer form AND the mission state reflect the same orbit.
 *
 * Values are documented and defensible. They are anonymous by construction:
 * no real place, satellite catalogue name, country, or programme is named.
 */

import type { MissionConfig, UavHardware } from "../MissionControl/missionContext"

export type TemplateConfig = {
  id: string
  name: string
  description: string
  badge: string
  configPatch: Partial<MissionConfig>
}

// ---- Template 1: Reference LEO -----------------------------------------
// 408 km circular, i=51.6 degrees (ISS-class orbit). Four identical
// multirotors sized to capture a meaningful fraction of a 10 kW beam at
// the pass geometry. Clear-sky baseline: the canonical case.

const LEO_MULTIROTOR: UavHardware = {
  receiver_aperture_m2: 0.5,
  receiver_type: "laser_photovoltaic",
  battery_efficiency: 0.9,
  mass_kg: 2.5,
  wingspan_m: 2.5,
  battery_wh: 100,
  thermal_limit_c: 80,
  airframe: "multirotor",
}

// ---- Template 2: SSO Fixed-Wing ----------------------------------------
// 1500 km sun-synchronous, i=98 degrees. Three fixed-wing endurance
// aircraft with larger receiver apertures (1.2 m^2) to compensate for the
// longer slant range. High-capacity batteries (220 Wh) support longer
// missions. The higher orbit means larger transmitter aperture (0.5 m)
// to keep the beam tight enough to be captured.

const SSO_FIXED_WING: UavHardware[] = [
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
    receiver_aperture_m2: 1.2,
    receiver_type: "laser_photovoltaic",
    battery_efficiency: 0.92,
    mass_kg: 8.5,
    wingspan_m: 3.0,
    battery_wh: 220,
    thermal_limit_c: 85,
    airframe: "fixed_wing",
  },
]

// ---- Template 3: Contested Sky -----------------------------------------
// 507 km circular, i=51.6 degrees. Four multirotors with larger receiver
// apertures (1.0 m^2) to partially compensate for the atmospheric loss.
// UAVs at 2000 m altitude — above the densest part of the boundary layer,
// where a chunk of the cloud and aerosol loading is. Transmitter boosted
// to 15 kW to push more photons through.

const CONTESTED_MULTIROTOR: UavHardware = {
  receiver_aperture_m2: 1.0,
  receiver_type: "laser_photovoltaic",
  battery_efficiency: 0.9,
  mass_kg: 3.0,
  wingspan_m: 2.5,
  battery_wh: 120,
  thermal_limit_c: 85,
  airframe: "multirotor",
}

export const TEMPLATES: TemplateConfig[] = [
  {
    id: "quickstart",
    name: "Reference LEO (ISS-class)",
    description:
      "The canonical CLEAR-D case. A 408 km circular orbit at i=51.6 degrees charges four multirotors through a clear-sky pass. Every step of the workflow produces non-degenerate output. Run this first to see the full instrument.",
    badge: "LEO · MULTIROTOR · CLEAR SKY",
    configPatch: {
      satellite_elements: {
        epoch_utc: "2024-01-01T00:00:00Z",
        a_km: 6778.0,
        e: 0.0005,
        i_deg: 51.6,
        raan_deg: 0.0,
        argp_deg: 0.0,
        m0_deg: 0.0,
      },
      n_uavs: 4,
      uav_hardware_list: [
        LEO_MULTIROTOR,
        LEO_MULTIROTOR,
        LEO_MULTIROTOR,
        LEO_MULTIROTOR,
      ],
      uav_alt_m: 1000.0,
      uav_receiver_aperture_m2: 0.5,
      uav_receiver_type: "laser_photovoltaic",
      visibility_km: 10.0,
      cloud_factor: 0.0,
      transmitter_power_w: 10000.0,
      wavelength_nm: 1064.0,
      transmitter_aperture_m: 0.5,
    },
  },
  {
    id: "fixed-wing-endurance",
    name: "SSO Fixed-Wing Endurance",
    description:
      "Sun-synchronous polar orbit at 1500 km, i=98 degrees. Three fixed-wing endurance aircraft with 1.2 m^2 receiver apertures and 220 Wh batteries. Exercises the fixed-wing drawing path, the polar orbit class, and the long-slant-range link budget.",
    badge: "SSO 1500 KM · FIXED WING · ENDURANCE",
    configPatch: {
      satellite_elements: {
        epoch_utc: "2024-01-01T00:00:00Z",
        a_km: 7871.0,
        e: 0.001,
        i_deg: 98.0,
        raan_deg: 0.0,
        argp_deg: 0.0,
        m0_deg: 0.0,
      },
      n_uavs: 3,
      uav_hardware_list: SSO_FIXED_WING,
      uav_alt_m: 1500.0,
      uav_receiver_aperture_m2: 1.2,
      uav_receiver_type: "laser_photovoltaic",
      visibility_km: 15.0,
      cloud_factor: 0.1,
      transmitter_power_w: 50000.0,
      wavelength_nm: 1064.0,
      transmitter_aperture_m: 0.5,
    },
  },
  {
    id: "degraded-atmosphere",
    name: "Contested Sky (Degraded ISR)",
    description:
      "ISS-class orbit through 4 km visibility and 75% cloud cover, with UAVs at 2000 m altitude to climb above the worst of the boundary layer. Transmitter boosted to 15 kW. Demonstrates the atmosphere as the limiting factor: transmittance collapses, epistemic intervals widen, Pareto front shifts.",
    badge: "LEO · MULTIROTOR · DEGRADED",
    configPatch: {
      satellite_elements: {
        epoch_utc: "2024-01-01T00:00:00Z",
        a_km: 6878.0,
        e: 0.001,
        i_deg: 51.6,
        raan_deg: 0.0,
        argp_deg: 0.0,
        m0_deg: 0.0,
      },
      n_uavs: 4,
      uav_hardware_list: [
        CONTESTED_MULTIROTOR,
        CONTESTED_MULTIROTOR,
        CONTESTED_MULTIROTOR,
        CONTESTED_MULTIROTOR,
      ],
      uav_alt_m: 2000.0,
      uav_receiver_aperture_m2: 1.0,
      uav_receiver_type: "laser_photovoltaic",
      visibility_km: 4.0,
      cloud_factor: 0.75,
      transmitter_power_w: 15000.0,
      wavelength_nm: 1064.0,
      transmitter_aperture_m: 0.05,
    },
  },
  {
    id: "ground-to-air-isr",
    name: "Ground-to-Air ISR",
    description:
      "Ground-based laser at the ground station transmitting to four multirotors at 1500 m altitude. No satellite required; the power source is the ground transmitter. Demonstrates the ground-to-air link path and the ITU-R P.528 effective-Earth-radius geometry.",
    badge: "GROUND LASER · MULTIROTOR · CLEAR SKY",
    configPatch: {
      transmitter_type: "ground",
      transmitter_min_elevation_deg: 5.0,
      n_uavs: 4,
      uav_hardware_list: [
        LEO_MULTIROTOR,
        LEO_MULTIROTOR,
        LEO_MULTIROTOR,
        LEO_MULTIROTOR,
      ],
      uav_alt_m: 1500.0,
      uav_receiver_aperture_m2: 0.5,
      uav_receiver_type: "laser_photovoltaic",
      visibility_km: 15.0,
      cloud_factor: 0.05,
      transmitter_power_w: 2000.0,
      wavelength_nm: 1064.0,
      transmitter_aperture_m: 0.15,
    },
  },
  {
    id: "multi-hop-relay",
    name: "Multi-Hop Relay Chain",
    description:
      "Five multirotors in a 5-hop relay chain from an ISS-class satellite. The satellite charges UAV-0; each subsequent hop forwards 70% of its delivered power to the next; UAV-4 is the terminal receiver. Exercises the UAV-to-UAV relay link budget and the per-hop power forwarding constraint.",
    badge: "LEO \u00b7 MULTI-HOP \u00b7 5 UAVs",
    configPatch: {
      satellite_elements: {
        epoch_utc: "2024-01-01T00:00:00Z",
        a_km: 6778.0,
        e: 0.0005,
        i_deg: 51.6,
        raan_deg: 0.0,
        argp_deg: 0.0,
        m0_deg: 0.0,
      },
      n_uavs: 5,
      uav_hardware_list: [
        LEO_MULTIROTOR,
        LEO_MULTIROTOR,
        LEO_MULTIROTOR,
        LEO_MULTIROTOR,
        LEO_MULTIROTOR,
      ],
      relay_topology: [0, 1, 2, 3, 4],
      relay_fraction: 0.7,
      uav_alt_m: 1000.0,
      uav_receiver_aperture_m2: 0.5,
      uav_receiver_type: "laser_photovoltaic",
      visibility_km: 15.0,
      cloud_factor: 0.0,
      transmitter_power_w: 10000.0,
      wavelength_nm: 1064.0,
      transmitter_aperture_m: 0.5,
    },
  },
  {
    id: "swarm-180",
    name: "180-UAV Swarm",
    description:
      "One hundred eighty independent multirotor UAVs in a single mission, exercising the platform at its largest supported fleet size. Custom 500 km LEO orbit, 500 kW transmitter, 5 m aperture to keep per-UAV incident power plausible. No relay chain. The aggregate 'Peak received' metric is the sum across all 180 UAVs at the peak instant, which assumes ideal time-sharing across the pass. Discovery subarchitecture is capped at 30 nodes; the mission runs all 180.",
    badge: "LEO \u00b7 SWARM \u00b7 180 UAVs",
    configPatch: {
      satellite_elements: {
        epoch_utc: "2024-01-01T00:00:00Z",
        a_km: 6878.0,
        e: 0.001,
        i_deg: 51.6,
        raan_deg: 0.0,
        argp_deg: 0.0,
        m0_deg: 0.0,
      },
      n_uavs: 180,
      uav_hardware_list: Array.from(
        { length: 180 },
        () => LEO_MULTIROTOR,
      ),
      uav_alt_m: 1000.0,
      uav_receiver_aperture_m2: 0.5,
      uav_receiver_type: "laser_photovoltaic",
      visibility_km: 15.0,
      cloud_factor: 0.0,
      transmitter_power_w: 500000.0,
      wavelength_nm: 1064.0,
      transmitter_aperture_m: 5.0,
    },
  },
]
