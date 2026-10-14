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
import {
  fetchMissionState,
  MissionApiError,
  postMissionState,
  type MissionStateRequest,
} from "./missionApi"
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
  p.set("transmitter_aperture_m", String(c.transmitter_aperture_m))
  p.set("uav_alt_m", String(c.uav_alt_m))
  p.set("uav_receiver_aperture_m2", String(c.uav_receiver_aperture_m2))
  p.set("uav_receiver_type", c.uav_receiver_type)
  if (c.t_utc) p.set("t_utc", c.t_utc)
  return p.toString()
}

function requestBody(c: MissionConfig): MissionStateRequest {
  const body: MissionStateRequest = {
    seed: c.seed,
    n_uavs: c.n_uavs,
    ground_lat_deg: c.ground_lat_deg,
    ground_lon_deg: c.ground_lon_deg,
    transmitter_power_w: c.transmitter_power_w,
    visibility_km: c.visibility_km,
    cloud_factor: c.cloud_factor,
    transmitter_aperture_m: c.transmitter_aperture_m,
    uav_alt_m: c.uav_alt_m,
    uav_receiver_aperture_m2: c.uav_receiver_aperture_m2,
    uav_receiver_type: c.uav_receiver_type,
    t_utc: c.t_utc,
    selected_architecture: c.selected_architecture ?? null,
  }
  if (c.satellite_elements) {
    body.a_km = c.satellite_elements.a_km
    body.e = c.satellite_elements.e
    body.i_deg = c.satellite_elements.i_deg
    body.raan_deg = c.satellite_elements.raan_deg
    body.argp_deg = c.satellite_elements.argp_deg
    body.m0_deg = c.satellite_elements.m0_deg
    body.elements_epoch_utc = c.satellite_elements.epoch_utc
  } else {
    body.satellite_key = c.satellite_key
  }
  return body
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
    // A selected architecture may contain dozens of nodes and links and
    // cannot fit in a query string. When one is set, use POST; otherwise
    // GET keeps the simple, cacheable, curl-friendly path.
    const usePost = cfgSnapshot.selected_architecture !== null
    const request = usePost
      ? postMissionState(requestBody(cfgSnapshot), controller.signal)
      : fetchMissionState(queryString(cfgSnapshot), controller.signal)
    request
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
