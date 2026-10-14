/**
 * Typed client for POST /discovery/run.
 *
 * The endpoint exposes the CLEAR-D loop with full attribution trace:
 * every classification (SAT / UNSAT), the constraints emitted, and
 * the grammar features the attribution mechanism marked
 * conflict-prone. See backend/app/discovery/api.py.
 */

export type ClearDRequest = {
  population_size?: number
  n_generations?: number
  seed?: number
  min_nodes?: number
  max_nodes?: number
  max_links?: number
  use_conflict_directed?: boolean
  ground_station_lat_deg?: number
  ground_station_lon_deg?: number
}

export type GenerationStat = {
  generation: number
  n_feasible: number
  n_infeasible: number
  n_conflict_prone_features: number
}

export type ConflictProneFeature = {
  kind: string
  identifier: string
  count: number
}

export type TraceEvent = {
  generation: number
  individual_index: number
  status: string
  n_constraints: number
  conflict_prone: string[]
}

export type DiscoveredNode = {
  node_id: string
  kind: string
  params: Record<string, number>
}

export type DiscoveredLink = {
  link_id: string
  kind: string
  source_id: string
  target_id: string
}

export type DiscoveredArchitecture = {
  generation: number
  nodes: number
  links: number
  objectives: number[]
  /** Node instances for this architecture, from the discovery engine. */
  node_list: DiscoveredNode[]
  /** Directed links for this architecture. */
  link_list: DiscoveredLink[]
}

export type ClearDResponse = {
  epistemic_tag: string
  population_size: number
  n_generations: number
  use_conflict_directed: boolean
  generation_stats: GenerationStat[]
  hypervolume_history: number[]
  conflict_prone_table: ConflictProneFeature[]
  trace: TraceEvent[]
  trace_truncated: boolean
  discovered: DiscoveredArchitecture[]
}

export class ClearDApiError extends Error {
  readonly status: number
  readonly detail: string
  constructor(status: number, detail: string) {
    super(`discovery api returned ${status}: ${detail}`)
    this.name = "ClearDApiError"
    this.status = status
    this.detail = detail
  }
}

export async function runClearD(
  request: ClearDRequest = {},
  signal?: AbortSignal,
): Promise<ClearDResponse> {
  const headers: Record<string, string> = { "Content-Type": "application/json" }
  if (typeof window !== "undefined") {
    const token = window.localStorage.getItem("aerogrid.token")
    if (token) headers["Authorization"] = `Bearer ${token}`
  }
  const response = await fetch("/api/discovery/run", {
    method: "POST",
    headers,
    body: JSON.stringify(request),
    signal,
  })
  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const payload = (await response.json()) as { detail?: unknown }
      if (typeof payload.detail === "string") detail = payload.detail
    } catch {
      // not JSON
    }
    throw new ClearDApiError(response.status, detail)
  }
  return (await response.json()) as ClearDResponse
}
