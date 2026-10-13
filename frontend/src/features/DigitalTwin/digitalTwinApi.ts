/**
 * Typed client for the Digital Twin endpoints in
 * backend/app/digital_twin/api.py.
 *
 * Three functions correspond to the three POST routes:
 *   postState()        -> POST /digital-twin/state
 *   postTrajectory()   -> POST /digital-twin/trajectory
 *   postDiscrepancy()  -> POST /digital-twin/discrepancy
 *
 * The Vite dev-server proxy rewrites /api/* to the backend root, so
 * request paths are /api/digital-twin/... .
 */

export type StateRequest = {
  incident_power_w: number
  airflow_m_per_s: number
  ambient_temperature_k: number
}

export type SteadyState = {
  t_plc_k: number
  t_te_k: number
  t_plc_c: number
  t_te_c: number
}

export type StateResponse = {
  epistemic_tag: string
  incident_power_w: number
  airflow_m_per_s: number
  ambient_temperature_k: number
  steady_state: SteadyState | null
  thermal_runaway_power_w: number
  safety_margin_w: number
  safety_margin_fraction: number
  receiver_efficiency: number | null
  receiver_efficiency_source: string
}

export type TrajectoryRequest = {
  incident_power_w: number
  airflow_m_per_s: number
  ambient_temperature_k: number
  t_end_s: number
  n_samples?: number
}

export type TrajectorySample = {
  time_s: number
  t_plc_k: number
  t_te_k: number
}

export type TrajectoryResponse = {
  epistemic_tag: string
  t_end_s: number
  n_samples: number
  samples: TrajectorySample[]
}

export type Observation = {
  field_name: string
  predicted: number
  observed: number
}

export type DiscrepancyRecord = {
  field_name: string
  predicted: number
  observed: number
  absolute_error: number
  relative_error: number
  triggered: boolean
  step: number
}

export type DiscrepancyResponse = {
  epistemic_tag: string
  n_observations: number
  n_triggered: number
  triggered_fields: string[]
  should_refine: boolean
  threshold_summary: Record<string, { absolute: number | null; relative: number | null }>
  records: DiscrepancyRecord[]
}

export class DigitalTwinApiError extends Error {
  readonly status: number
  readonly detail: string
  constructor(status: number, detail: string) {
    super(`digital-twin api returned ${status}: ${detail}`)
    this.name = "DigitalTwinApiError"
    this.status = status
    this.detail = detail
  }
}

async function postJson<TReq, TRes>(
  url: string,
  body: TReq,
  signal?: AbortSignal,
): Promise<TRes> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  })
  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const payload = (await response.json()) as { detail?: unknown }
      if (typeof payload.detail === "string") detail = payload.detail
    } catch {
      // body was not JSON; keep the HTTP status message
    }
    throw new DigitalTwinApiError(response.status, detail)
  }
  return (await response.json()) as TRes
}

export async function postState(
  request: StateRequest,
  signal?: AbortSignal,
): Promise<StateResponse> {
  return postJson<StateRequest, StateResponse>(
    "/api/digital-twin/state",
    request,
    signal,
  )
}

export async function postTrajectory(
  request: TrajectoryRequest,
  signal?: AbortSignal,
): Promise<TrajectoryResponse> {
  return postJson<TrajectoryRequest, TrajectoryResponse>(
    "/api/digital-twin/trajectory",
    request,
    signal,
  )
}

export async function postDiscrepancy(
  observations: Observation[],
  signal?: AbortSignal,
): Promise<DiscrepancyResponse> {
  return postJson<{ observations: Observation[] }, DiscrepancyResponse>(
    "/api/digital-twin/discrepancy",
    { observations },
    signal,
  )
}
