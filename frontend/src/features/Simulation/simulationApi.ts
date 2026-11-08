/**
 * Typed client for POST /simulation/run.
 * Mirrors backend/app/simulation/api.py.
 */

export type SimulationPreset = "10min" | "1hour" | "1pass" | "custom"

export type UavSnapshot = {
  uav_id: number
  received_power_w: number
  delivered_power_w: number
  receiver_efficiency: number
  thermal_headroom_c: number
}

export type SimulationSample = {
  t_utc: string
  elapsed_s: number
  received_power_w: number
  delivered_power_w: number
  cumulative_energy_j: number
  atmospheric_transmittance: number
  satellite_elevation_deg: number
  link_status: string
  uavs: UavSnapshot[]
  epistemic_tag: string
}

export type SimulationResponse = {
  epistemic_tag: string
  preset: string
  duration_s: number
  step_s: number
  n_samples: number
  config_summary: Record<string, unknown>
  warnings: string[]
  samples: SimulationSample[]
}

export type SimulationRequest = {
  preset: SimulationPreset
  seed: number
  satellite_key: string
  n_uavs: number
  ground_lat_deg: number
  ground_lon_deg: number
  transmitter_power_w: number
  wavelength_nm: number
  visibility_km: number
  cloud_factor: number
  transmitter_type: "satellite" | "ground"
  transmitter_min_elevation_deg: number
  relay_topology: number[] | null
  relay_fraction: number
}

export class SimulationApiError extends Error {
  readonly status_code?: number
  constructor(message: string, status_code?: number) {
    super(message)
    this.name = "SimulationApiError"
    this.status_code = status_code
  }
}

export async function runSimulation(
  req: SimulationRequest,
  signal?: AbortSignal,
): Promise<SimulationResponse> {
  const r = await fetch("/api/simulation/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
    signal,
  })
  if (!r.ok) {
    let detail = `simulation returned HTTP ${r.status}`
    try {
      const body = (await r.json()) as { detail?: unknown }
      if (body && body.detail) detail = String(body.detail)
    } catch {
      /* ignore parse errors */
    }
    throw new SimulationApiError(detail, r.status)
  }
  return (await r.json()) as SimulationResponse
}
