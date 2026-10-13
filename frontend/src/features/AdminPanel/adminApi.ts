/**
 * Typed client for the two SaaS admin endpoints.
 *
 *   GET /saas/admin/tenants
 *   GET /saas/admin/tenants/{tenant_id}/usage
 *
 * Both require a bearer JWT whose role is superadmin. The client sends
 * the token as supplied; the panel is responsible for having one. See
 * backend/app/saas/admin_routes.py for the server side.
 */

export type TenantSummary = {
  id: string
  slug: string
  display_name: string
  created_at: string
  stripe_subscription_status: string | null
  plan: string
}

export type TenantListResponse = {
  tenants: TenantSummary[]
  count: number
}

export type MetricUsage = {
  metric: string
  count: number
  limit: number
}

export type TenantUsageResponse = {
  tenant_id: string
  period_start: string
  plan: string
  usage: MetricUsage[]
}

export class AdminApiError extends Error {
  readonly status: number
  readonly detail: string
  constructor(status: number, detail: string) {
    super(`admin api returned ${status}: ${detail}`)
    this.name = "AdminApiError"
    this.status = status
    this.detail = detail
  }
}

async function fetchJson<T>(
  path: string,
  token: string,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(path, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
    signal,
  })
  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const payload = (await response.json()) as { detail?: unknown }
      if (typeof payload.detail === "string") detail = payload.detail
    } catch {
      // body was not JSON
    }
    throw new AdminApiError(response.status, detail)
  }
  return (await response.json()) as T
}

export async function listTenants(
  token: string,
  signal?: AbortSignal,
): Promise<TenantListResponse> {
  return fetchJson<TenantListResponse>("/api/saas/admin/tenants", token, signal)
}

export async function fetchTenantUsage(
  token: string,
  tenantId: string,
  signal?: AbortSignal,
): Promise<TenantUsageResponse> {
  return fetchJson<TenantUsageResponse>(
    `/api/saas/admin/tenants/${tenantId}/usage`,
    token,
    signal,
  )
}
