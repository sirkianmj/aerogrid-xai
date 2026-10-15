/**
 * TradeSpace — Section 14 Pareto-front explorer.
 *
 * Runs NSGA-II on demand and renders the Pareto front as a parallel-
 * coordinates plot. The panel does not fetch on mount, so a page with
 * several panels does not fire several optimization runs before the
 * user asks; the user clicks "Run" to start one.
 *
 * Epistemic tagging
 * -----------------
 * Every point in the Pareto front is an optimizer output. Section 21
 * category: simulation_result. Wrapped in a TaggedOutput with that tag.
 */

import { useRef, useState } from "react"
import { TaggedOutput } from "../../components/EpistemicBadge/EpistemicBadge"
import { ParallelCoordinates } from "./ParallelCoordinates"
import {
  runTradeSpace,
  TradeSpaceApiError,
  type TradeSpaceResponse,
} from "./tradeSpaceApi"

const DEMO_REQUEST = {
  population_size: 20,
  n_generations: 8,
  seed: 20261009,
  min_nodes: 4,
  max_nodes: 8,
  max_links: 6,
  hypervolume_samples: 1024,
}

type PanelState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; result: TradeSpaceResponse; elapsedMs: number }
  | { status: "error"; message: string; status_code?: number }

export function TradeSpace() {
  const [state, setState] = useState<PanelState>({ status: "idle" })
  const abortRef = useRef<AbortController | null>(null)

  async function run() {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    setState({ status: "loading" })
    // Date.now() rather than performance.now() because the jsdom
    // environment used by the test suite does not define the
    // Performance API. Wall-clock resolution is millisecond, which is
    // more than enough to display the run time of an interactive
    // optimization request.
    const started = Date.now()
    try {
      const result = await runTradeSpace(DEMO_REQUEST, controller.signal)
      if (controller.signal.aborted) return
      setState({
        status: "ok",
        result,
        elapsedMs: Date.now() - started,
      })
    } catch (err) {
      if (controller.signal.aborted) return
      if (err instanceof TradeSpaceApiError) {
        setState({ status: "error", message: err.detail, status_code: err.status })
      } else if (err instanceof Error) {
        setState({ status: "error", message: err.message })
      } else {
        setState({ status: "error", message: String(err) })
      }
    }
  }

  return (
    <section
      data-tour-id="tradespace"
      aria-labelledby="tradespace-heading" className="mb-10">
      <h2 id="tradespace-heading" className="mb-1 text-lg font-semibold">
        Trade Space (Section 14)
      </h2>
      <p className="mb-4 text-sm text-[var(--ink-secondary)]">
        NSGA-II over the (C, R, E, N, T, U) objective vector. U is
        minimized; the rest are maximized. The plot normalizes every axis
        so higher on screen always means better.
      </p>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={run}
          disabled={state.status === "loading"}
          className="rounded border border-[var(--border-hairline)] px-3 py-1.5 text-sm hover:bg-[var(--bg-subtle)] disabled:opacity-50"
        >
          {state.status === "loading" ? "Running..." : "Run NSGA-II"}
        </button>
        {state.status === "ok" && (
          <>
            <span className="text-xs text-[var(--ink-tertiary)]">
              {`${state.result.n_pareto} Pareto point${state.result.n_pareto === 1 ? "" : "s"}`}
            </span>
            <span className="text-xs text-[var(--ink-tertiary)]">
              {`${state.result.n_final_population} final population`}
            </span>
            <span className="text-xs text-[var(--ink-tertiary)]">{`elapsed ${state.elapsedMs} ms`}</span>
          </>
        )}
      </div>

      {state.status === "idle" && (
        <p className="text-sm text-[var(--ink-secondary)]">No run yet. Press Run NSGA-II.</p>
      )}

      {state.status === "error" && (
        <p className="text-sm" style={{ color: "var(--status-red)" }}>
          Error{state.status_code ? ` (${state.status_code})` : ""}: {state.message}
        </p>
      )}

      {state.status === "ok" && (
        <TaggedOutput tag="simulation_result" className="apple-card p-4">
          <ParallelCoordinates
            points={state.result.pareto_front}
            labels={state.result.objective_labels}
            negativeObjectives={state.result.negative_objectives}
            ariaLabel="Pareto front parallel coordinates for the CLEAR-D discovery run"
          />

          <div className="my-4 border-t border-current/10 pt-4">
            <h3 className="mb-2 text-sm font-medium">Hypervolume history</h3>
            <HypervolumeStrip history={state.result.hypervolume_history} />
          </div>

          <div className="border-t border-current/10 pt-4">
            <h3 className="mb-2 text-sm font-medium">
              {`Pareto front (${state.result.n_pareto})`}
            </h3>
            <ParetoTable result={state.result} />
          </div>

          <footer className="mt-4 border-t border-[var(--border-hairline)] pt-3 font-mono text-xs text-[var(--ink-tertiary)]">
            artefact: tradespace_pareto_front
          </footer>
        </TaggedOutput>
      )}
    </section>
  )
}

function HypervolumeStrip({ history }: { history: number[] }) {
  if (history.length === 0) {
    return <p className="text-xs text-[var(--ink-secondary)]">Empty history.</p>
  }
  const max = Math.max(...history)
  return (
    <div className="flex items-end gap-1" role="img" aria-label="Hypervolume history">
      {history.map((v, i) => {
        const h = max > 0 ? Math.max(2, (v / max) * 60) : 2
        return (
          <div
            key={i}
            title={`gen ${i}: ${v.toFixed(4)}`}
            style={{
              width: 8,
              height: h,
              background: "var(--plot-primary)",
              opacity: 0.7,
            }}
          />
        )
      })}
    </div>
  )
}

function ParetoTable({ result }: { result: TradeSpaceResponse }) {
  return (
    <div className="max-h-72 overflow-auto">
      <table className="w-full text-xs">
        <thead className="text-left text-[var(--ink-tertiary)]">
          <tr>
            <th className="py-1 font-normal">#</th>
            <th className="py-1 font-normal">gen</th>
            {result.objective_labels.map((label) => (
              <th key={label} className="py-1 font-normal">
                {label}
              </th>
            ))}
            <th className="py-1 font-normal">nodes</th>
            <th className="py-1 font-normal">links</th>
          </tr>
        </thead>
        <tbody>
          {result.pareto_front.map((p, i) => (
            <tr key={i} className="border-t border-[var(--border-hairline)]">
              <td className="py-1 font-mono">{i}</td>
              <td className="py-1 font-mono">{p.generation}</td>
              {p.objectives.map((v, j) => (
                <td key={j} className="py-1 font-mono">
                  {v.toFixed(4)}
                </td>
              ))}
              <td className="py-1 font-mono">{p.node_count}</td>
              <td className="py-1 font-mono">{p.link_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
