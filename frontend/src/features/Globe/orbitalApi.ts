/**
 * Typed client for the orbital endpoints in backend/app/physics/api.py.
 *
 * Three functions correspond to the three GET routes:
 *   listSatellites()   -> GET /orbital/satellites
 *   fetchTrack()       -> GET /orbital/track
 *   fetchVisibility()  -> GET /orbital/visibility
 *
 * The Vite dev-server proxy rewrites /api/* to the backend root, so
 * request paths are /api/orbital/... .
 */

export type SatelliteInfo = {
  key: string
  name: string
  epoch_utc: string
  mean_motion_rev_per_day: number
  period_seconds: number
  orbit_class: string
}

export type TrackPoint = {
  time_utc: string
  lat_deg: number
  lon_deg: number
  alt_m: number
  speed_km_s: number
  in_eclipse: boolean
}

export type TrackResponse = {
  key: string
  name: string
  t_start: string
  t_end: string
  step_seconds: number
  n_points: number
  points: TrackPoint[]
}

export type VisibilityWindow = {
  start_utc: string
  end_utc: string
  duration_seconds: number
  peak_elevation_deg: number
  peak_time_utc: string
}

export type VisibilityResponse = {
  key: string
  name: string
  ground: { name: string; lat_deg: number; lon_deg: number; alt_m: number }
  min_elevation_deg: number
  t_start: string
  t_end: string
  n_windows: number
  windows: VisibilityWindow[]
}

export class OrbitalApiError extends Error {
  readonly status: number
  readonly detail: string
  constructor(status: number, detail: string) {
    super(`orbital api returned ${status}: ${detail}`)
    this.name = "OrbitalApiError"
    this.status = status
    this.detail = detail
  }
}

async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal })
  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === "string") detail = body.detail
    } catch {
      // response body was not JSON; keep the HTTP status message
    }
    throw new OrbitalApiError(response.status, detail)
  }
  return (await response.json()) as T
}

export async function listSatellites(
  signal?: AbortSignal,
): Promise<SatelliteInfo[]> {
  const body = await getJson<{ satellites: SatelliteInfo[] }>(
    "/api/orbital/satellites",
    signal,
  )
  return body.satellites
}

export type FetchTrackOptions = {
  satellite: string
  tStartIso: string
  tEndIso: string
  stepSeconds?: number
  signal?: AbortSignal
}

export async function fetchTrack(
  options: FetchTrackOptions,
): Promise<TrackResponse> {
  const params = new URLSearchParams({
    satellite: options.satellite,
    t_start: options.tStartIso,
    t_end: options.tEndIso,
    step_seconds: String(options.stepSeconds ?? 60),
  })
  return getJson<TrackResponse>(`/api/orbital/track?${params}`, options.signal)
}

export type FetchVisibilityOptions = {
  satellite: string
  groundLatDeg: number
  groundLonDeg: number
  groundAltM?: number
  tStartIso: string
  tEndIso: string
  stepSeconds?: number
  minElevationDeg?: number
  signal?: AbortSignal
}

export async function fetchVisibility(
  options: FetchVisibilityOptions,
): Promise<VisibilityResponse> {
  const params = new URLSearchParams({
    satellite: options.satellite,
    ground_lat_deg: String(options.groundLatDeg),
    ground_lon_deg: String(options.groundLonDeg),
    ground_alt_m: String(options.groundAltM ?? 0),
    t_start: options.tStartIso,
    t_end: options.tEndIso,
    step_seconds: String(options.stepSeconds ?? 30),
    min_elevation_deg: String(options.minElevationDeg ?? 5),
  })
  return getJson<VisibilityResponse>(
    `/api/orbital/visibility?${params}`,
    options.signal,
  )
}
