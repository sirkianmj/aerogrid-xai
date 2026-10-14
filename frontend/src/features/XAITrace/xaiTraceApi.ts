/**
 * HTTP client for POST /decisions/charge.
 *
 * The endpoint returns the Section 15.5 trace format. The types here
 * mirror the backend Pydantic models in backend/app/control/api.py
 * field for field. The Vite dev-server proxy rewrites /api/* to the
 * backend root, so the request path is /api/decisions/charge.
 */

export type PrimaryReason = {
  label: string
  comparison: string
  weight: number
}

export type ConsultedRule = {
  label: string
  comparison: string
  result: string
}

export type Alternative = {
  action: string
  score: number
}

export type Counterfactual = {
  /** family_name of the rule that was removed. */
  removed_rule: string
  /** Action selected by the original decision. */
  original_selected: string
  /** Action that would be selected with that single rule removed. */
  would_select: string
  /** True iff would_select differs from original_selected. */
  changed: boolean
  original_winner_score: number
  original_runner_up_score: number
  ablated_winner_score: number
}

export type ChargeCandidate = {
  uav_id: number
  [key: string]: number
}

export type ChargeDecisionRequest = {
  candidates: ChargeCandidate[]
  estimates?: Record<string, number>
}

export type ChargeDecisionResponse = {
  epistemic_tag: string
  decision: string
  decision_kind: string
  primary_reasons: PrimaryReason[]
  consulted_rules: ConsultedRule[]
  alternative: Alternative | null
  confidence: number
  confidence_note: string
  counterfactuals: Counterfactual[]
}

export type ApiError = {
  status: number
  detail: string
}

export class XaiTraceApiError extends Error {
  readonly status: number
  readonly detail: string
  constructor(status: number, detail: string) {
    super(`decisions/charge returned ${status}: ${detail}`)
    this.name = "XaiTraceApiError"
    this.status = status
    this.detail = detail
  }
}

export async function postChargeDecision(
  request: ChargeDecisionRequest,
  signal?: AbortSignal,
): Promise<ChargeDecisionResponse> {
  const response = await fetch("/api/decisions/charge", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  })
  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === "string") detail = body.detail
    } catch {
      // response body was not JSON; keep the HTTP status message
    }
    throw new XaiTraceApiError(response.status, detail)
  }
  return (await response.json()) as ChargeDecisionResponse
}
