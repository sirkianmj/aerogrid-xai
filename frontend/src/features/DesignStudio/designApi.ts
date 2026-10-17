/**
 * HTTP client for the design evaluation endpoints.
 *
 * Presets: GET  /design/presets
 * Evaluate: POST /design/satellite, POST /design/drone
 *
 * Every endpoint returns numbers computed from the mission physics,
 * not from a lookup table. The verdict is a rule-of-thumb combination
 * of the wing-loading flag, the thermal flag, and the delivered power.
 */

export type SatellitePreset = {
  id: string
  label: string
  a_km: number
  e: number
  i_deg: number
  raan_deg: number
  argp_deg: number
  m0_deg: number
  transmitter_power_w: number
  wavelength_nm: number
  transmitter_aperture_m: number
}

export type DronePreset = {
  id: string
  label: string
  mass_kg: number
  wingspan_m: number
  battery_wh: number
  receiver_aperture_m2: number
  receiver_type: string
  battery_efficiency: number
  thermal_limit_c: number
  airframe: string
}

export type PresetsResponse = {
  satellites: SatellitePreset[]
  drones: DronePreset[]
}

export type FeasibilityReport = {
  epistemic_tag: string
  verdict: "feasible" | "infeasible"
  delivered_power_w: number
  notes: string[]
  metrics: Record<string, number>
}

export class DesignApiError extends Error {
  readonly status: number
  readonly detail: string
  constructor(status: number, detail: string) {
    super(`design api returned ${status}: ${detail}`)
    this.name = "DesignApiError"
    this.status = status
    this.detail = detail
  }
}


function extractDetail(payload: { detail?: unknown }, fallback: string): string {
  if (typeof payload.detail === "string") return payload.detail
  if (Array.isArray(payload.detail)) {
    return payload.detail
      .map((err: any) => {
        const loc = Array.isArray(err?.loc) ? err.loc.slice(1).join(".") : ""
        const msg = err?.msg || "Invalid value"
        return loc ? `${loc}: ${msg}` : msg
      })
      .join("; ")
  }
  return fallback
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal })
  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const payload = (await response.json()) as { detail?: unknown }
      detail = extractDetail(payload, detail)
    } catch {
      // not JSON
    }
    throw new DesignApiError(response.status, detail)
  }
  return (await response.json()) as T
}

async function postJson<TReq, TRes>(
  path: string,
  body: TReq,
  signal?: AbortSignal,
): Promise<TRes> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  })
  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const payload = (await response.json()) as { detail?: unknown }
      detail = extractDetail(payload, detail)
    } catch {
      // not JSON
    }
    throw new DesignApiError(response.status, detail)
  }
  return (await response.json()) as TRes
}

export async function fetchDesignPresets(
  signal?: AbortSignal,
): Promise<PresetsResponse> {
  return getJson<PresetsResponse>("/api/design/presets", signal)
}

export type SatelliteDesignRequest = {
  a_km: number
  e: number
  i_deg: number
  raan_deg: number
  argp_deg: number
  m0_deg: number
  epoch_utc: string
  transmitter_power_w: number
  wavelength_nm: number
  transmitter_aperture_m: number
  ground_lat_deg: number
  ground_lon_deg: number
  n_uavs: number
  uav_alt_m: number
  uav_receiver_aperture_m2: number
  uav_receiver_type: string
  visibility_km: number
  cloud_factor: number
}

export async function evaluateSatellite(
  req: SatelliteDesignRequest,
  signal?: AbortSignal,
): Promise<FeasibilityReport> {
  return postJson<SatelliteDesignRequest, FeasibilityReport>(
    "/api/design/satellite",
    req,
    signal,
  )
}

export type DroneDesignRequest = {
  receiver_aperture_m2: number
  receiver_type: string
  battery_efficiency: number
  mass_kg: number
  wingspan_m: number
  battery_wh: number
  thermal_limit_c: number
  airframe: string
  satellite_key: string
  ground_lat_deg: number
  ground_lon_deg: number
  uav_alt_m: number
  transmitter_power_w: number
  wavelength_nm: number
  transmitter_aperture_m: number
  visibility_km: number
  cloud_factor: number
}

export async function evaluateDrone(
  req: DroneDesignRequest,
  signal?: AbortSignal,
): Promise<FeasibilityReport> {
  return postJson<DroneDesignRequest, FeasibilityReport>(
    "/api/design/drone",
    req,
    signal,
  )
}
