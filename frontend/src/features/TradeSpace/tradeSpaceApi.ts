/**
 * Typed client for POST /tradespace/run.
 *
 * The backend runs NSGA-II over the synthetic evaluator and returns the
 * Pareto front. See backend/app/tradespace/api.py.
 */

export type ParetoPoint = {
  objectives: number[]
  generation: number
  node_count: number
  link_count: number
}

export type TradeSpaceRequest = {
  population_size?: number
  n_generations?: number
  seed?: number
  min_nodes?: number
  max_nodes?: number
  max_links?: number
  hypervolume_samples?: number
}

export type TradeSpaceResponse = {
  epistemic_tag: string
  objective_labels: string[]
  negative_objectives: number[]
  n_pareto: number
  n_final_population: number
  hypervolume_history: number[]
  pareto_front: ParetoPoint[]
}

export class TradeSpaceApiError extends Error {
  readonly status: number
  readonly detail: string
  constructor(status: number, detail: string) {
    super(`tradespace api returned ${status}: ${detail}`)
    this.name = "TradeSpaceApiError"
    this.status = status
    this.detail = detail
  }
}

function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" }
  if (typeof window !== "undefined") {
    const token = window.localStorage.getItem("aerogrid.token")
    if (token) headers["Authorization"] = `Bearer ${token}`
  }
  return headers
}

export async function runTradeSpace(
  request: TradeSpaceRequest = {},
  signal?: AbortSignal,
): Promise<TradeSpaceResponse> {
  const response = await fetch("/api/tradespace/run", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(request),
    signal,
  })
  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const payload = (await response.json()) as { detail?: unknown }
      if (typeof payload.detail === "string") detail = payload.detail
    } catch {
      // response body was not JSON; keep the HTTP status message
    }
    throw new TradeSpaceApiError(response.status, detail)
  }
  return (await response.json()) as TradeSpaceResponse
}
