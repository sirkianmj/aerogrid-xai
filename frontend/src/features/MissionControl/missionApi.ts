/**
 * Typed client for GET /mission/state and GET /mission/satellites.
 *
 * The mission state is a single coherent scenario computed by the
 * backend: satellite position from a packaged TLE, atmospheric
 * transmittance at the current geometry, a real Z3 SAT/UNSAT verdict
 * on a generated architecture, a CLEAR-D snapshot, and a Tier 1
 * decision trace over the UAVs. See backend/app/mission/state.py.
 */

export type SatelliteState = {
  key: string
  name: string
  orbit_class: string
  tle_epoch_utc: string
  tle_age_seconds: number
  valid: boolean
  invalid_reason: string
  period_seconds: number
  lat_deg: number
  lon_deg: number
  alt_km: number
  in_eclipse: boolean
  epistemic_tag: string
}

export type GroundStationState = {
  name: string
  lat_deg: number
  lon_deg: number
  alt_m: number
}

export type TransmissionState = {
  modality: string
  wavelength_nm: number
  transmitter_power_w: number
  slant_range_m: number
  atmospheric_path_m: number
  elevation_deg: number
}

export type AtmosphereState = {
  transmittance: number
  visibility_km: number
  cloud_factor: number
  extinction_coeff_per_m: number
}

export type UavState = {
  uav_id: number
  lat_deg: number
  lon_deg: number
  role: string
  battery_pct: number
  mission_priority: number
  network_centrality: number
  coverage_contribution: number
  workload_urgency: number
  thermal_headroom_c: number
  atmospheric_factor: number
  beam_alignment: number
  transfer_loss: number
}

export type ArchitectureSummary = {
  nodes: number
  links: number
  node_kinds: Record<string, number>
  link_kinds: Record<string, number>
  sat_verdict: string
  n_constraints: number
  epsilon_bound: number
}

export type ClearDSnapshot = {
  population_size: number
  n_generations: number
  feasible_final: number
  infeasible_final: number
  conflict_prone_features: number
  use_conflict_directed: boolean
  epistemic_tag: string
}

export type Tier1Snapshot = {
  selected_action: string
  decision_kind: string
  score: number
  alternative_action: string
  alternative_score: number
  confidence: number
  epistemic_tag: string
}

export type PipelineStage = {
  key: string
  label: string
  status: string
  reason: string
}

export type MissionState = {
  t_utc: string
  seed: number
  satellite: SatelliteState
  ground_station: GroundStationState
  transmission: TransmissionState
  atmosphere: AtmosphereState
  uavs: UavState[]
  architecture: ArchitectureSummary
  cleard: ClearDSnapshot
  tier1: Tier1Snapshot
  pipeline_stages: PipelineStage[]
  epistemic_tag: string
}

export class MissionApiError extends Error {
  readonly status: number
  readonly detail: string
  constructor(status: number, detail: string) {
    super(`mission api returned ${status}: ${detail}`)
    this.name = "MissionApiError"
    this.status = status
    this.detail = detail
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal })
  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const payload = (await response.json()) as { detail?: unknown }
      if (typeof payload.detail === "string") detail = payload.detail
    } catch {
      // not JSON
    }
    throw new MissionApiError(response.status, detail)
  }
  return (await response.json()) as T
}

export async function fetchMissionState(
  signal?: AbortSignal,
): Promise<MissionState> {
  return getJson<MissionState>("/api/mission/state", signal)
}

export async function fetchMissionSatellites(
  signal?: AbortSignal,
): Promise<string[]> {
  return getJson<string[]>("/api/mission/satellites", signal)
}
