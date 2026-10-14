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
import type { MissionState } from "./missionApi"

export type MissionConfig = {
  satellite_key: string
  ground_lat_deg: number
  ground_lon_deg: number
  transmitter_power_w: number
  n_uavs: number
  seed: number
  t_utc: string | null
}

export const DEFAULT_CONFIG: MissionConfig = {
  satellite_key: "iss",
  ground_lat_deg: 40.798,
  ground_lon_deg: -77.86,
  transmitter_power_w: 10000,
  n_uavs: 6,
  seed: 20261014,
  t_utc: null,
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
