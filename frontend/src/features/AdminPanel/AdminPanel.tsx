/**
 * AdminPanel — superadmin-only tenant management and usage view.
 *
 * The panel takes the bearer token as a prop. A null token means the
 * caller is not signed in; the panel renders a placeholder and does
 * not fetch. With a token, it fetches the tenant list on mount and,
 * on clicking a row, fetches that tenant's usage for the current
 * calendar month.
 *
 * RBAC is enforced by the backend: a viewer or admin token receives
 * 403 and the panel renders "Forbidden"; an absent/invalid token
 * receives 401 and the panel renders "Sign in required". The panel
 * does not decide authority; it displays what the server says.
 *
 * Epistemic tagging: tenant and usage rows are operational state of
 * the running platform. Section 21 category: simulation_result
 * (output of the Digital Twin running the live system).
 */

import { useCallback, useEffect, useRef, useState } from "react"
import { TaggedOutput } from "../../components/EpistemicBadge/EpistemicBadge"
import {
  AdminApiError,
  fetchTenantUsage,
  listTenants,
  type TenantListResponse,
  type TenantUsageResponse,
} from "./adminApi"

type Load<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; data: T }
  | { status: "error"; message: string; status_code?: number }

export type AdminPanelProps = {
  token: string | null
}

function describe(err: unknown): { message: string; status_code?: number } {
  if (err instanceof AdminApiError) {
    if (err.status === 401) return { message: "Sign in required", status_code: 401 }
    if (err.status === 403) return { message: "Forbidden — superadmin required", status_code: 403 }
    if (err.status === 404) return { message: err.detail, status_code: 404 }
    return { message: err.detail, status_code: err.status }
  }
  if (err instanceof Error) return { message: err.message }
  return { message: String(err) }
}

export function AdminPanel({ token }: AdminPanelProps) {
  // Initial state is derived from the token prop so the effect does not
  // need to call setState synchronously. React Compiler's
  // set-state-in-effect rule flags the pattern this replaces.
  const [tenants, setTenants] = useState<Load<TenantListResponse>>(() =>
    token === null ? { status: "idle" } : { status: "loading" },
  )
  const [selected, setSelected] = useState<string | null>(null)
  const [usage, setUsage] = useState<Load<TenantUsageResponse>>({ status: "idle" })
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (token === null) return
    let cancelled = false
    const controller = new AbortController()
    abortRef.current?.abort()
    abortRef.current = controller
    listTenants(token, controller.signal)
      .then((data) => {
        if (cancelled || controller.signal.aborted) return
        setTenants({ status: "ok", data })
      })
      .catch((err: unknown) => {
        if (cancelled || controller.signal.aborted) return
        setTenants({ status: "error", ...describe(err) })
      })
    return () => {
      cancelled = true
      controller.abort()
    }
  }, [token])

  const selectTenant = useCallback(
    async (tenantId: string) => {
      if (token === null) return
      setSelected(tenantId)
      const controller = new AbortController()
      abortRef.current?.abort()
      abortRef.current = controller
      setUsage({ status: "loading" })
      try {
        const data = await fetchTenantUsage(token, tenantId, controller.signal)
        if (controller.signal.aborted) return
        setUsage({ status: "ok", data })
      } catch (err: unknown) {
        if (controller.signal.aborted) return
        setUsage({ status: "error", ...describe(err) })
      }
    },
    [token],
  )

  return (
    <section aria-labelledby="admin-heading" className="mb-10">
      <h2 id="admin-heading" className="mb-1 text-lg font-medium">
        Admin — tenant management
      </h2>
      <p className="mb-4 text-sm opacity-70">
        Superadmin-only view of every tenant on the platform and the
        current month's per-metric quota usage. Requires a bearer JWT
        with role superadmin.
      </p>

      {token === null && (
        <p className="text-sm opacity-70" data-testid="admin-signin-required">
          Sign in required. No admin token is available in this session.
        </p>
      )}

      {tenants.status === "loading" && <p className="text-sm opacity-70">Loading tenants...</p>}

      {tenants.status === "error" && (
        <p className="text-sm" style={{ color: "var(--color-accent-amber)" }}>
          {`Error${tenants.status_code ? ` (${tenants.status_code})` : ""}: ${tenants.message}`}
        </p>
      )}

      {tenants.status === "ok" && (
        <TaggedOutput tag="simulation_result" className="rounded border border-current/15 p-4">
          <div className="mb-3 text-xs opacity-60">
            {`${tenants.data.count} tenant${tenants.data.count === 1 ? "" : "s"}`}
          </div>
          <div className="overflow-auto">
            <table className="w-full text-xs">
              <thead className="text-left opacity-70">
                <tr>
                  <th className="py-1 font-normal">slug</th>
                  <th className="py-1 font-normal">display name</th>
                  <th className="py-1 font-normal">plan</th>
                  <th className="py-1 font-normal">subscription</th>
                </tr>
              </thead>
              <tbody>
                {tenants.data.tenants.map((t) => (
                  <tr
                    key={t.id}
                    data-testid={`tenant-row-${t.id}`}
                    aria-selected={selected === t.id}
                    className="cursor-pointer border-t border-current/10"
                    onClick={() => void selectTenant(t.id)}
                  >
                    <td className="py-1 font-mono">{t.slug}</td>
                    <td className="py-1">{t.display_name}</td>
                    <td className="py-1 font-mono">{t.plan}</td>
                    <td className="py-1 font-mono opacity-70">
                      {t.stripe_subscription_status ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {selected !== null && (
            <div className="mt-4 border-t border-current/10 pt-4">
              <h3 className="mb-2 text-sm font-medium">Usage this month</h3>
              {usage.status === "loading" && (
                <p className="text-xs opacity-60">Loading usage...</p>
              )}
              {usage.status === "error" && (
                <p className="text-xs" style={{ color: "var(--color-accent-amber)" }}>
                  {`Error${usage.status_code ? ` (${usage.status_code})` : ""}: ${usage.message}`}
                </p>
              )}
              {usage.status === "ok" && (
                <table className="w-full text-xs">
                  <thead className="text-left opacity-70">
                    <tr>
                      <th className="py-1 font-normal">metric</th>
                      <th className="py-1 font-normal">used</th>
                      <th className="py-1 font-normal">limit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {usage.data.usage.map((m) => (
                      <tr key={m.metric} className="border-t border-current/10">
                        <td className="py-1 font-mono">{m.metric}</td>
                        <td className="py-1 font-mono">{m.count}</td>
                        <td className="py-1 font-mono">{m.limit}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          <footer className="mt-4 border-t border-current/10 pt-3 font-mono text-xs opacity-60">
            artefact: admin_tenant_management
          </footer>
        </TaggedOutput>
      )}
    </section>
  )
}
