/**
 * ArchitecturesView — the Pareto front as concrete topologies.
 *
 * Runs the CLEAR-D discovery loop on demand and renders each discovered
 * architecture as a card: a small topology sketch plus its six
 * objective values (C, R, E, N, T, U). The panel does not run on
 * mount; the user clicks "Discover architectures" to start a run. That
 * mirrors TradeSpace and avoids firing several optimization runs
 * before the user asks.
 *
 * The panel does not currently load a discovered architecture into the
 * mission. That is a separate change: it needs a defined override
 * shape and a place in MissionConfig to record it. Read-only explorer
 * first, load-into-mission later.
 *
 * Epistemic tagging: every architecture here is a discovery-engine
 * output. Section 21 category: simulation_result.
 */

import { useState } from "react"
import { TaggedOutput } from "../../components/EpistemicBadge/EpistemicBadge"
import {
  runClearD,
  ClearDApiError,
  type ClearDResponse,
  type DiscoveredArchitecture,
} from "../ClearDDashboard/clearDApi"
import { ArchitectureSketch } from "./ArchitectureSketch"
import { useMission } from "../MissionControl/missionContext"

const OBJECTIVE_LABELS = ["C", "R", "E", "N", "T", "U"] as const

type PanelState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; result: ClearDResponse; elapsedMs: number }
  | { status: "error"; message: string; status_code?: number }

export function ArchitecturesView() {
  const { config, applyConfig } = useMission()
  const [state, setState] = useState<PanelState>({ status: "idle" })

  async function run() {
    setState({ status: "loading" })
    const started = Date.now()
    try {
      const result = await runClearD({
        population_size: 8,
        n_generations: 3,
        seed: config.seed,
        ground_station_lat_deg: config.ground_lat_deg,
        ground_station_lon_deg: config.ground_lon_deg,
      })
      setState({
        status: "ok",
        result,
        elapsedMs: Date.now() - started,
      })
    } catch (err) {
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
    <section
      data-tour-id="architectures"
      aria-labelledby="architectures-heading" className="mb-10">
      <h2 id="architectures-heading" className="mb-1 text-lg font-semibold">
        Discovered architectures (Part V, Stage C)
      </h2>
      <p className="mb-4 text-sm text-[var(--ink-secondary)]">
        Every non-dominated architecture from the last CLEAR-D run,
        rendered as a topology sketch with its six objective values.
        C coverage, R resilience, E energy efficiency, N network
        continuity, T thermal margin, U uncertainty (minimized).
      </p>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={run}
          disabled={state.status === "loading"}
          className="rounded border border-[var(--border-hairline)] px-3 py-1.5 text-sm hover:bg-[var(--bg-subtle)] disabled:opacity-50"
        >
          {state.status === "loading"
            ? "Discovering..."
            : "Discover architectures"}
        </button>
        {state.status === "ok" && (
          <>
            <span className="text-xs text-[var(--ink-tertiary)]">
              {`${state.result.discovered.length} feasible`}
            </span>
            <span className="text-xs text-[var(--ink-tertiary)]">
              {`seed ${config.seed}`}
            </span>
            <span className="text-xs text-[var(--ink-tertiary)]">
              {`elapsed ${state.elapsedMs} ms`}
            </span>
          </>
        )}
      </div>

      {state.status === "idle" && (
        <p className="text-sm text-[var(--ink-secondary)]">
          No run yet. Press Discover architectures to start one.
        </p>
      )}

      {state.status === "error" && (
        <p className="text-sm" style={{ color: "var(--status-red)" }}>
          Error{state.status_code ? ` (${state.status_code})` : ""}: {state.message}
        </p>
      )}

      {state.status === "ok" && state.result.discovered.length === 0 && (
        <p className="text-sm text-[var(--ink-secondary)]">
          No feasible architectures discovered with the current seed.
        </p>
      )}

      {state.status === "ok" && state.result.discovered.length > 0 && (
        <TaggedOutput tag="simulation_result">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
            {state.result.discovered.map((arch, i) => (
              <ArchitectureCard
                key={i}
                arch={arch}
                index={i}
                onLoad={(a) =>
                  applyConfig({
                    selected_architecture: {
                      node_list: a.node_list,
                      link_list: a.link_list,
                    },
                  })
                }
              />
            ))}
          </div>
          <footer className="mt-4 border-t border-[var(--border-hairline)] pt-3 font-mono text-xs text-[var(--ink-tertiary)]">
            artefact: cleard_pareto_architectures
          </footer>
        </TaggedOutput>
      )}
    </section>
  )
}

function ArchitectureCard({
  arch,
  index,
  onLoad,
}: {
  arch: DiscoveredArchitecture
  index: number
  onLoad: (a: DiscoveredArchitecture) => void
}) {
  return (
    <div className="apple-card p-3" data-testid={`arch-card-${index}`}>
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <span className="font-mono text-xs font-semibold">#{index}</span>
        <span className="font-mono text-[10px] text-[var(--ink-tertiary)]">
          gen {arch.generation} · {arch.nodes}N {arch.links}L
        </span>
      </div>

      <ArchitectureSketch nodes={arch.node_list} links={arch.link_list} />

      <div className="mt-2 grid grid-cols-6 gap-1 font-mono text-[10px]">
        {OBJECTIVE_LABELS.map((label, j) => (
          <div key={label} className="text-center">
            <div className="text-[var(--ink-tertiary)]">{label}</div>
            <div>{(arch.objectives[j] ?? 0).toFixed(2)}</div>
          </div>
        ))}
      </div>

      <button
        type="button"
        onClick={() => onLoad(arch)}
        className="mt-3 w-full rounded border border-[var(--border-hairline)] px-2 py-1 text-xs uppercase tracking-wider hover:bg-[var(--bg-subtle)]"
        data-testid={`load-arch-${index}`}
      >
        Load into mission
      </button>
    </div>
  )
}
