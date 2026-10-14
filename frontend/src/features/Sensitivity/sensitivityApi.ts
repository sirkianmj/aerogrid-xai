/**
 * HTTP client for POST /discovery/sensitivity.
 *
 * The backend computes the sensitivity of total delivered power to
 * each configurable mission parameter by finite differences. The
 * response is a ranked list: parameters are ordered by |elasticity|,
 * so the first entry is the knob that moves delivered power most.
 */

export type ParameterSensitivity = {
  name: string
  base_value: number
  low_value: number
  high_value: number
  power_at_low_w: number
  power_at_high_w: number
  derivative_w_per_unit: number
  elasticity: number | null
  direction: "increase" | "decrease" | "flat"
}

export type SensitivityResponse = {
  epistemic_tag: string
  base_delivered_power_w: number
  base_sat_verdict: string
  parameters: ParameterSensitivity[]
}

export type SensitivityRequestBody = {
  base: Record<string, unknown>
  perturb_fraction?: number
}

export class SensitivityApiError extends Error {
  readonly status: number
  readonly detail: string
  constructor(status: number, detail: string) {
    super(`sensitivity api returned ${status}: ${detail}`)
    this.name = "SensitivityApiError"
    this.status = status
    this.detail = detail
  }
}

export async function runSensitivity(
  body: SensitivityRequestBody,
  signal?: AbortSignal,
): Promise<SensitivityResponse> {
  const response = await fetch("/api/discovery/sensitivity", {
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
      // not JSON
    }
    throw new SensitivityApiError(response.status, detail)
  }
  return (await response.json()) as SensitivityResponse
}
