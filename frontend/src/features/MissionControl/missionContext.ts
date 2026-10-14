/**
 * Mission context — the shared state hook, types, and defaults.
 *
 * Kept separate from MissionProvider.tsx because that file exports a
 * React component and this file exports a hook, a type, and a
 * constant. React Fast Refresh (and the oxlint rule
 * `react(only-export-components)`) requires that split; the same
 * convention was already applied to EpistemicBadge.
 *
 * The context object is intentionally module-private. Only the hook
 * and the provider's value type are exported.
 */

import { createContext, useContext } from "react"
import type { MissionState, SelectedArchitecture } from "./missionApi"

/**
 * User-supplied mean Keplerian elements. When present, override the
 * catalogue satellite key. Fields map 1:1 to the backend
 * SatelliteElements dataclass.
 *
 * Epoch is an ISO 8601 string; the backend accepts any tz.
 */
export type SatelliteElements = {
  epoch_utc: string
  a_km: number
  e: number
  i_deg: number
  raan_deg: number
  argp_deg: number
  m0_deg: number
}

export type MissionConfig = {
  satellite_key: string
  /** When set, overrides satellite_key with a user-defined orbit. */
  satellite_elements?: SatelliteElements | null
  ground_lat_deg: number
  ground_lon_deg: number
  transmitter_power_w: number
  /** Transmitter wavelength in nm. */
  wavelength_nm: number
  n_uavs: number
  seed: number
  t_utc: string | null
  /** Meteorological visibility in km; feeds Kruse-Kim attenuation. */
  visibility_km: number
  /** Cloud cover fraction in [0, 1]; feeds attenuation. */
  cloud_factor: number
  /** Transmitter beam waist radius, metres. */
  transmitter_aperture_m: number
  /** UAV altitude above the ground station, metres. */
  uav_alt_m: number
  /** UAV receiver aperture area, square metres. */
  uav_receiver_aperture_m2: number
  /** UAV receiver conversion model: laser_photovoltaic or rectenna. */
  uav_receiver_type: "laser_photovoltaic" | "rectenna"
  /** When set, the mission uses this topology instead of generating
   *  one. Loaded from the architecture explorer. */
  selected_architecture?: SelectedArchitecture | null
  /** Per-UAV hardware, index-aligned with the UAVs the mission places.
   *  When null, every UAV uses the uniform `uav_receiver_*` values
   *  above. Set by the Design Studio. */
  uav_hardware_list?: UavHardware[] | null
}

/** One UAV's hardware. Mirrors the backend UavHardware dataclass. */
export type UavHardware = {
  receiver_aperture_m2: number
  receiver_type: "laser_photovoltaic" | "rectenna"
  battery_efficiency: number
  mass_kg: number
  wingspan_m: number
  battery_wh: number
  thermal_limit_c: number
}

export const DEFAULT_CONFIG: MissionConfig = {
  satellite_key: "iss",
  ground_lat_deg: 40.798,
  ground_lon_deg: -77.86,
  transmitter_power_w: 10000,
  wavelength_nm: 1064.0,
  n_uavs: 6,
  seed: 20261014,
  t_utc: null,
  visibility_km: 10.0,
  cloud_factor: 0.0,
  satellite_elements: null,
  transmitter_aperture_m: 0.02,
  uav_alt_m: 1000.0,
  uav_receiver_aperture_m2: 0.5,
  uav_receiver_type: "laser_photovoltaic",
  selected_architecture: null,
  uav_hardware_list: null,
}

export type MissionLoad =
  | { status: "loading" }
  | { status: "ok"; data: MissionState; configUsed: MissionConfig }
  | { status: "error"; message: string; status_code?: number }

export type MissionContextValue = {
  config: MissionConfig
  state: MissionLoad
  applyConfig: (patch: Partial<MissionConfig>) => void
  refresh: () => void
  reset: () => void
}

export const MissionCtx = createContext<MissionContextValue | null>(null)

export function useMission(): MissionContextValue {
  const v = useContext(MissionCtx)
  if (v === null) {
    throw new Error("useMission must be called inside <MissionProvider>")
  }
  return v
}
