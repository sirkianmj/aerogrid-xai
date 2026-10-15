/**
 * CLEAR-D Discovery Dashboard.
 *
 * The inventive mechanism made visible. Press "Run CLEAR-D" and watch
 * the loop classify architectures, mark the grammar features that
 * appeared in each UNSAT core as conflict-prone, and carry that
 * signal forward into the next generation.
 *
 * Every number on this panel is the loop's own output. Nothing is
 * fabricated. Stages the loop does not exercise are not shown.
 */

import { useRef, useState } from "react"
import { TaggedOutput } from "../../components/EpistemicBadge/EpistemicBadge"
import { useMission, type MissionConfig } from "../MissionControl/missionContext"
import { exportArtifact } from "../../lib/download"
import {
  ClearDApiError,
  runClearD,
  type ClearDRequest,
  type ClearDResponse,
} from "./clearDApi"

/**
 * Build a CLEAR-D run request from the live mission configuration.
 *
 * The population size is at least the mission's UAV count (with a
 * floor of 4 so the Pareto search has something to work with), and the
 * seed is the mission's seed so two CLEAR-D runs on the same mission
 * produce identical architectures. The remaining generator bounds stay
 * at the panel's defaults until a future PR allows per-run
 * configuration of the architecture space itself.
 */
function requestFor(cfg: MissionConfig): ClearDRequest {
  return {
    population_size: Math.max(4, cfg.n_uavs),
    n_generations: 10,
    seed: cfg.seed,
    min_nodes: 4,
    max_nodes: 8,
    max_links: 6,
    use_conflict_directed: true,
    ground_station_lat_deg: cfg.ground_lat_deg,
    ground_station_lon_deg: cfg.ground_lon_deg,
  }
}

type PanelState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; result: ClearDResponse; elapsedMs: number }
  | { status: "error"; message: string; status_code?: number }

export function ClearDDashboard() {
  const { config } = useMission()
  const [state, setState] = useState<PanelState>({ status: "idle" })
  const abortRef = useRef<AbortController | null>(null)

  async function run() {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    setState({ status: "loading" })
    const started = Date.now()
    try {
      const result = await runClearD(requestFor(config), controller.signal)
      if (controller.signal.aborted) return
      setState({ status: "ok", result, elapsedMs: Date.now() - started })
    } catch (err) {
      if (controller.signal.aborted) return
      if (err instanceof ClearDApiError) {
        setState({ status: "error", message: err.detail, status_code: err.status })
      } else if (err instanceof Error) {
        setState({ status: "error", message: err.message })
      } else {
        setState({ status: "error", message: String(err) })
      }
    }
  }

  return (
    <section aria-labelledby="cleard-heading" className="mb-10">
      <div className="mb-1 flex items-baseline gap-3">
        <h2 id="cleard-heading" className="text-lg font-medium">
          CLEAR-D Discovery
        </h2>
        <span className="text-xs opacity-50">
          Section 35.3 · the unsat-core-to-grammar-feature attribution mechanism
        </span>
      </div>
      <p className="mb-4 text-sm opacity-70 max-w-3xl">
        Runs the closed-loop generative discovery method. Each candidate
        architecture is encoded as Stage B constraints and checked by Z3.
        When the check is UNSAT, the minimal core's clauses are mapped
        back to the grammar features that generated them; those features
        are marked conflict-prone, and the next generation&apos;s mutation
        is biased away from them.
      </p>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={run}
          disabled={state.status === "loading"}
          className="rounded border px-3 py-1.5 text-sm disabled:opacity-50"
        >
          {state.status === "loading" ? "Running…" : "Run CLEAR-D"}
        </button>
        {state.status === "ok" && (
          <>
            <span className="text-xs opacity-60">
              {`${state.result.generation_stats.length} generations`}
            </span>
            <span className="text-xs opacity-60">
              {`${state.result.trace.length} classifications`}
            </span>
            <span className="text-xs opacity-60">
              {`${state.result.conflict_prone_table.length} conflict-prone features`}
            </span>
            <span className="text-xs opacity-60">{`elapsed ${state.elapsedMs} ms`}</span>
          </>
        )}
      </div>

      {state.status === "idle" && (
        <p className="text-sm opacity-60">No run yet. Press Run CLEAR-D.</p>
      )}

      {state.status === "error" && (
        <p className="text-sm" style={{ color: "var(--color-accent-amber)" }}>
          Error{state.status_code ? ` (${state.status_code})` : ""}: {state.message}
        </p>
      )}

      {state.status === "ok" && <ResultView result={state.result} cfg={config} />}
    </section>
  )
}

function ResultView({ result, cfg }: { result: ClearDResponse; cfg: MissionConfig }) {
  const unsatEvents = result.trace.filter((e) => e.status === "unsat")
  const satEvents = result.trace.filter((e) => e.status === "sat")

  return (
    <TaggedOutput tag="simulation_result" className="rounded border border-current/15 p-4">
      <div className="mb-4 grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
        <Stat
          label="SAT classifications"
          value={String(satEvents.length)}
          testId="stat-sat"
        />
        <Stat
          label="UNSAT classifications"
          value={String(unsatEvents.length)}
          testId="stat-unsat"
        />
        <Stat
          label="Conflict-prone features"
          value={String(result.conflict_prone_table.length)}
        />
        <Stat
          label="Mode"
          value={result.use_conflict_directed ? "conflict-directed" : "random"}
        />
      </div>

      <div className="mb-5 border-t border-current/10 pt-4">
        <h3 className="mb-2 text-sm font-medium">Per-generation progress</h3>
        <GenerationTable stats={result.generation_stats} />
      </div>

      <div className="mb-5 border-t border-current/10 pt-4">
        <h3 className="mb-2 text-sm font-medium">Hypervolume history</h3>
        <HypervolumeStrip history={result.hypervolume_history} />
      </div>

      <div className="mb-5 border-t border-current/10 pt-4">
        <h3 className="mb-2 text-sm font-medium">
          {`Conflict-prone grammar features (${result.conflict_prone_table.length})`}
        </h3>
        <p className="mb-2 text-xs opacity-60">
          Every feature that ever appeared in an UNSAT core, with the
          number of cores it appeared in. This is the table the mutator
          reads when it selects the next mutation operator.
        </p>
        <ConflictTable entries={result.conflict_prone_table} />
      </div>

      <div className="border-t border-current/10 pt-4">
        <h3 className="mb-2 text-sm font-medium">
          {`Attribution trace — UNSAT events (${unsatEvents.length})`}
        </h3>
        <p className="mb-2 text-xs opacity-60">
          One line per UNSAT classification: which generation, which
          individual in the batch, and the grammar features its core
          was attributed to. SAT classifications are summarized above
          but not listed here.
        </p>
        <TraceList events={unsatEvents.slice(0, 30)} />
        {unsatEvents.length > 30 && (
          <p className="mt-2 text-xs opacity-50">
            {`… ${unsatEvents.length - 30} more UNSAT events not shown.`}
          </p>
        )}
      </div>

      <footer className="mt-4 flex flex-wrap items-center gap-3 border-t border-current/10 pt-3 font-mono text-xs opacity-60">
        <span>
          {`artefact: cleard_loop · seed ${cfg.seed} · population ${Math.max(4, cfg.n_uavs)}`}
        </span>
        <button
          type="button"
          onClick={() =>
            exportArtifact("cleard-loop", "simulation_result", result, {
              mission_config: cfg,
            })
          }
          className="ml-auto rounded border border-[var(--border-hairline)] px-2 py-0.5 text-[0.65rem] uppercase tracking-wider hover:bg-[var(--bg-subtle)]"
          data-testid="export-cleard-json"
        >
          Export JSON
        </button>
      </footer>
    </TaggedOutput>
  )
}

function Stat({
  label,
  value,
  testId,
}: {
  label: string
  value: string
  testId?: string
}) {
  return (
    <div
      className="rounded border border-current/10 px-3 py-2"
      data-testid={testId}
    >
      <div className="text-[0.65rem] uppercase tracking-wide opacity-50">{label}</div>
      <div className="font-mono text-sm" data-testid={testId ? `${testId}-value` : undefined}>
        {value}
      </div>
    </div>
  )
}

function GenerationTable({
  stats,
}: {
  stats: ClearDResponse["generation_stats"]
}) {
  return (
    <div className="max-h-64 overflow-auto">
      <table className="w-full text-xs">
        <thead className="text-left opacity-70">
          <tr>
            <th className="py-1 font-normal">gen</th>
            <th className="py-1 font-normal">feasible</th>
            <th className="py-1 font-normal">infeasible</th>
            <th className="py-1 font-normal">conflict-prone</th>
          </tr>
        </thead>
        <tbody>
          {stats.map((s) => (
            <tr key={s.generation} className="border-t border-current/10">
              <td className="py-1 font-mono">{s.generation}</td>
              <td className="py-1 font-mono">{s.n_feasible}</td>
              <td className="py-1 font-mono">{s.n_infeasible}</td>
              <td className="py-1 font-mono">{s.n_conflict_prone_features}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function HypervolumeStrip({ history }: { history: number[] }) {
  if (history.length === 0) return <p className="text-xs opacity-60">Empty history.</p>
  const max = Math.max(...history, 0)
  return (
    <div className="flex items-end gap-1" role="img" aria-label="Hypervolume history">
      {history.map((v, i) => {
        const h = max > 0 ? Math.max(2, (v / max) * 60) : 2
        return (
          <div
            key={i}
            title={`gen ${i}: ${v.toFixed(4)}`}
            style={{ width: 6, height: h, background: "#14b8a6", opacity: 0.7 }}
          />
        )
      })}
    </div>
  )
}

function ConflictTable({
  entries,
}: {
  entries: ClearDResponse["conflict_prone_table"]
}) {
  if (entries.length === 0) {
    return <p className="text-xs opacity-60">No conflict-prone features were marked.</p>
  }
  const sorted = [...entries].sort((a, b) => b.count - a.count)
  return (
    <div className="max-h-64 overflow-auto">
      <table className="w-full text-xs">
        <thead className="text-left opacity-70">
          <tr>
            <th className="py-1 font-normal">kind</th>
            <th className="py-1 font-normal">identifier</th>
            <th className="py-1 font-normal">cores</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((e, i) => (
            <tr key={`${e.kind}:${e.identifier}:${i}`} className="border-t border-current/10">
              <td className="py-1 font-mono opacity-70">{e.kind}</td>
              <td className="py-1 font-mono">{e.identifier}</td>
              <td className="py-1 font-mono">{e.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TraceList({ events }: { events: ClearDResponse["trace"] }) {
  if (events.length === 0) {
    return (
      <p className="text-xs opacity-60">
        No UNSAT classifications in this run — every candidate was
        feasible under the encoded constraints.
      </p>
    )
  }
  return (
    <div className="max-h-72 overflow-auto font-mono text-[0.7rem] space-y-1">
      {events.map((e, i) => (
        <div key={i} className="rounded border border-current/10 px-2 py-1">
          <span className="opacity-60">
            gen {e.generation} · idx {e.individual_index} ·
          </span>{" "}
          <span className="opacity-80">{`${e.n_constraints} constraints`}</span>
          {" → "}
          {e.conflict_prone.length === 0 ? (
            <span className="opacity-60">(no features attributed)</span>
          ) : (
            <span>
              {e.conflict_prone.map((f, j) => (
                <span
                  key={j}
                  className="ml-1 rounded border border-current/20 px-1"
                >
                  {f}
                </span>
              ))}
            </span>
          )}
        </div>
      ))}
    </div>
  )
}
