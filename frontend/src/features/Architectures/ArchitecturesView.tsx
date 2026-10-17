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

import { TaggedOutput } from "../../components/EpistemicBadge/EpistemicBadge"
import type {
  ClearDResponse,
  DiscoveredArchitecture,
} from "../ClearDDashboard/clearDApi"
import { ArchitectureSketch } from "./ArchitectureSketch"
import { useMission } from "../MissionControl/missionContext"

const OBJECTIVE_LABELS = ["C", "R", "E", "N", "T", "U"] as const

export function ArchitecturesView() {
  const { config, applyConfig, lastDiscoveryRun } = useMission()
  // Read the shared CLEAR-D result. The discovery panel writes it when
  // a run succeeds; this panel updates without a second button press.
  const result = lastDiscoveryRun
    ? (lastDiscoveryRun.data as ClearDResponse)
    : null
  const isEmpty = result === null
  const hasNone = result !== null && result.discovered.length === 0
  const hasSome = result !== null && result.discovered.length > 0

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

      {result && (
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <span className="text-xs text-[var(--ink-tertiary)]">
            {`${result.discovered.length} feasible`}
          </span>
          <span className="text-xs text-[var(--ink-tertiary)]">
            {`seed ${config.seed}`}
          </span>
        </div>
      )}

      {isEmpty && (
        <p className="text-sm text-[var(--ink-secondary)]">
          No CLEAR-D run yet. Press Run CLEAR-D in the Discovery panel above.
        </p>
      )}

      {hasNone && (
        <p className="text-sm text-[var(--ink-secondary)]">
          The last CLEAR-D run discovered no feasible architectures with
          the current seed.
        </p>
      )}

      {hasSome && result && (
        <TaggedOutput tag="simulation_result">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
            {result.discovered.map((arch, i) => (
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
