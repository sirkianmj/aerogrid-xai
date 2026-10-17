/**
 * StatusView — platform dependency health.
 *
 * Polls GET /api/status every 10 seconds and renders one row per
 * dependency. Reads the payload as returned; does not interpret the
 * overall status beyond coloring the summary line.
 */

import { useEffect, useState } from "react"

type Dependency = {
  name: string
  status: string
  detail: string
  latency_ms: number
}

type StatusResponse = {
  overall: string
  checked_at: string
  dependencies: Dependency[]
}

type PanelState =
  | { status: "loading" }
  | { status: "ok"; data: StatusResponse }
  | { status: "error"; message: string }

function dotColor(status: string): string {
  if (status === "ok") return "var(--status-green)"
  if (status === "degraded") return "var(--status-orange)"
  return "var(--status-red)"
}

export function StatusView() {
  const [state, setState] = useState<PanelState>({ status: "loading" })

  useEffect(() => {
    let cancelled = false
    async function fetchStatus() {
      try {
        const response = await fetch("/api/status")
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const data = (await response.json()) as StatusResponse
        if (!cancelled) setState({ status: "ok", data })
      } catch (err) {
        if (!cancelled) {
          setState({
            status: "error",
            message: err instanceof Error ? err.message : String(err),
          })
        }
      }
    }
    fetchStatus()
    const interval = setInterval(fetchStatus, 10_000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])

  return (
    <section
      data-tour-id="status-view"
      aria-labelledby="status-heading" className="mb-10" data-testid="status-view">
      <h2 id="status-heading" className="mb-1 text-lg font-semibold">
        Platform status
      </h2>
      <p className="mb-4 text-sm text-[var(--ink-secondary)]">
        Live health of every dependency. Refreshes every 10 seconds.
      </p>

      {state.status === "loading" && (
        <p className="text-sm text-[var(--ink-secondary)]">Loading…</p>
      )}

      {state.status === "error" && (
        <p className="text-sm" style={{ color: "var(--status-red)" }}>
          Error: {state.message}
        </p>
      )}

      {state.status === "ok" && (
        <>
          <div className="mb-4 flex flex-wrap items-baseline gap-3 text-sm">
            <span
              className="inline-flex items-center gap-2 rounded-full border border-[var(--border-hairline)] px-3 py-1 font-mono text-xs uppercase tracking-wider"
              data-testid="status-overall"
            >
              <span
                aria-hidden="true"
                className="h-2 w-2 rounded-full"
                style={{ background: dotColor(state.data.overall) }}
              />
              {state.data.overall}
            </span>
            <span className="font-mono text-xs text-[var(--ink-tertiary)]">
              checked {state.data.checked_at}
            </span>
          </div>

          <div className="apple-card p-4">
            <table className="w-full text-xs">
              <thead className="text-left text-[var(--ink-tertiary)]">
                <tr>
                  <th className="py-1 font-normal">dependency</th>
                  <th className="py-1 font-normal">status</th>
                  <th className="py-1 font-normal text-right">latency</th>
                  <th className="py-1 font-normal">detail</th>
                </tr>
              </thead>
              <tbody>
                {state.data.dependencies.map((d) => (
                  <tr
                    key={d.name}
                    className="border-t border-[var(--border-hairline)]"
                    data-testid={`status-row-${d.name}`}
                  >
                    <td className="py-1 font-mono">{d.name}</td>
                    <td className="py-1">
                      <span className="inline-flex items-center gap-2">
                        <span
                          aria-hidden="true"
                          className="h-2 w-2 rounded-full"
                          style={{ background: dotColor(d.status) }}
                        />
                        {d.status}
                      </span>
                    </td>
                    <td className="py-1 text-right font-mono">
                      {d.latency_ms.toFixed(1)} ms
                    </td>
                    <td className="py-1 truncate text-[var(--ink-secondary)]">
                      {d.detail}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  )
}
