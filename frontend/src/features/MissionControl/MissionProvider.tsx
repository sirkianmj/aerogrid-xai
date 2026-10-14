/**
 * MissionProvider — one source of truth for the current mission.
 *
 * The provider holds a MissionConfig and the most recently fetched
 * MissionState. Panels that consume the mission read from
 * `useMission()`; the config bar writes via `applyConfig()`.
 *
 * Why a provider and not local state per panel: multiple panels
 * (MissionControl, FanetGraph) render the same mission. If each held
 * its own config, changing a parameter in one would leave the other
 * showing stale topology.
 *
 * This file exports only the component. The context, the hook, the
 * types, and DEFAULT_CONFIG live in `missionContext.ts`, matching the
 * React Fast Refresh convention already used for EpistemicBadge.
 */

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react"
import { fetchMissionState, MissionApiError } from "./missionApi"
import {
  DEFAULT_CONFIG,
  MissionCtx,
  type MissionConfig,
  type MissionLoad,
} from "./missionContext"

function describeError(err: unknown): { message: string; status_code?: number } {
  if (err instanceof MissionApiError) {
    return { message: err.detail, status_code: err.status }
  }
  if (err instanceof Error) {
    return { message: err.message }
  }
  return { message: String(err) }
}

function queryString(c: MissionConfig): string {
  const p = new URLSearchParams()
  p.set("seed", String(c.seed))
  // Custom orbit overrides the catalogue key. The two are mutually
  // exclusive at the API level (mutual-exclusion check on the backend),
  // so only one of them may be sent.
  if (c.satellite_elements) {
    const el = c.satellite_elements
    p.set("a_km", String(el.a_km))
    p.set("e", String(el.e))
    p.set("i_deg", String(el.i_deg))
    p.set("raan_deg", String(el.raan_deg))
    p.set("argp_deg", String(el.argp_deg))
    p.set("m0_deg", String(el.m0_deg))
    p.set("elements_epoch_utc", el.epoch_utc)
  } else {
    p.set("satellite_key", c.satellite_key)
  }
  p.set("n_uavs", String(c.n_uavs))
  p.set("ground_lat_deg", String(c.ground_lat_deg))
  p.set("ground_lon_deg", String(c.ground_lon_deg))
  p.set("transmitter_power_w", String(c.transmitter_power_w))
  p.set("visibility_km", String(c.visibility_km))
  p.set("cloud_factor", String(c.cloud_factor))
  if (c.t_utc) p.set("t_utc", c.t_utc)
  return p.toString()
}

export function MissionProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<MissionConfig>(DEFAULT_CONFIG)
  const [state, setState] = useState<MissionLoad>({ status: "loading" })
  const [refreshNonce, setRefreshNonce] = useState(0)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    const cfgSnapshot: MissionConfig = { ...config }
    fetchMissionState(queryString(cfgSnapshot), controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return
        setState({ status: "ok", data, configUsed: cfgSnapshot })
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        setState({ status: "error", ...describeError(err) })
      })
    return () => controller.abort()
  }, [config, refreshNonce])

  const applyConfig = useCallback((patch: Partial<MissionConfig>) => {
    setConfig((prev) => ({ ...prev, ...patch }))
  }, [])

  const refresh = useCallback(() => {
    setRefreshNonce((n) => n + 1)
  }, [])

  const reset = useCallback(() => {
    setConfig(DEFAULT_CONFIG)
  }, [])

  return (
    <MissionCtx.Provider value={{ config, state, applyConfig, refresh, reset }}>
      {children}
    </MissionCtx.Provider>
  )
}
