/**
 * XAITrace — the Section 15.5 decision trace panel.
 *
 * Renders the response of POST /decisions/charge. The panel is
 * deliberately minimal: it does not compute or interpret the decision,
 * it displays the trace exactly as the backend returned it. That is the
 * Section 15.3 requirement that the explanation be the literal
 * computation path of the Tier 1 model, not a post-hoc reconstruction.
 *
 * Epistemic labeling
 * ------------------
 * The response carries `epistemic_tag: "tier1_decision_trace"`. That
 * string is the Section 15.5 artefact label, not one of the seven
 * Section 21 categories. Section 21's seven categories classify
 * *claims*; a decision trace is a record of the Tier 1 model's own
 * arithmetic, i.e. a model output. Its Section 21 category is therefore
 * `simulation_result`. The panel shows that badge via TaggedOutput and
 * separately renders the backend's `tier1_decision_trace` sub-label, so
 * both the coarse Section 21 status and the specific artefact kind are
 * visible. This distinction is documented here because the backend
 * docstring calls `tier1_decision_trace` a Section 21 category, which
 * is not accurate against the seven-item list in the specification.
 */

import { useState } from "react"
import { TaggedOutput } from "../../components/EpistemicBadge/EpistemicBadge"
import {
  postChargeDecision,
  XaiTraceApiError,
  type ChargeCandidate,
  type ChargeDecisionResponse,
} from "./xaiTraceApi"

const DEMO_CANDIDATES: ChargeCandidate[] = [
  { uav_id: 32, battery_pct: 19, mission_priority: 0.9, network_centrality: 0.7, coverage_contribution: 0.084, workload_urgency: 0.85, thermal_headroom_c: 38, atmospheric_factor: 0.91, beam_alignment: 0.94, transfer_loss: 0.11 },
  { uav_id: 18, battery_pct: 55, mission_priority: 0.4, network_centrality: 0.5, coverage_contribution: 0.03, workload_urgency: 0.4, thermal_headroom_c: 42, atmospheric_factor: 0.88, beam_alignment: 0.90, transfer_loss: 0.14 },
]

type PanelState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; trace: ChargeDecisionResponse }
  | { status: "error"; message: string; status_code?: number }

function resultTone(result: string): string {
  switch (result) {
    case "match":
      return "text-teal-400"
    case "no_match":
      return "opacity-50"
    case "skipped":
      return "text-amber-400"
    default:
      return ""
  }
}

export function XAITrace() {
  const [state, setState] = useState<PanelState>({ status: "idle" })

  async function run() {
    setState({ status: "loading" })
    try {
      const trace = await postChargeDecision({ candidates: DEMO_CANDIDATES })
      setState({ status: "ok", trace })
    } catch (err) {
      if (err instanceof XaiTraceApiError) {
        setState({ status: "error", message: err.detail, status_code: err.status })
      } else if (err instanceof Error) {
        setState({ status: "error", message: err.message })
      } else {
        setState({ status: "error", message: String(err) })
      }
    }
  }

  return (
    <section aria-labelledby="xai-trace-heading" className="mb-10">
      <h2 id="xai-trace-heading" className="mb-1 text-lg font-medium">
        XAI trace (Section 15.5)
      </h2>
      <p className="mb-4 text-sm opacity-70">
        Tier 1 decision trace. The panel does not interpret the decision;
        it displays the model&apos;s own computation path as returned by
        the backend.
      </p>

      <button
        type="button"
        onClick={run}
        disabled={state.status === "loading"}
        className="mb-4 rounded border px-3 py-1.5 text-sm disabled:opacity-50"
      >
        {state.status === "loading" ? "Running..." : "Run decision"}
      </button>

      {state.status === "idle" && <p className="text-sm opacity-60">No trace yet.</p>}
      {state.status === "error" && (
        <p className="text-sm" style={{ color: "var(--color-accent-amber)" }}>
          Error{state.status_code ? ` (${state.status_code})` : ""}: {state.message}
        </p>
      )}
      {state.status === "ok" && <TraceView trace={state.trace} />}
    </section>
  )
}

function TraceView({ trace }: { trace: ChargeDecisionResponse }) {
  return (
    <TaggedOutput tag="simulation_result" className="rounded border border-current/15 p-4">
      <header className="mb-4 flex flex-wrap items-baseline gap-3">
        <span className="text-base font-medium">{trace.decision}</span>
        <span className="text-xs uppercase tracking-wide opacity-60">{trace.decision_kind}</span>
        <span className="ml-auto text-xs opacity-70">
          confidence {Math.round(trace.confidence * 100)}%
        </span>
      </header>

      <p className="mb-4 text-xs opacity-70">{trace.confidence_note}</p>

      <div className="mb-4">
        <h3 className="mb-2 text-sm font-medium">Primary reasons</h3>
        {trace.primary_reasons.length === 0 ? (
          <p className="text-sm opacity-60">No rules fired.</p>
        ) : (
          <ul className="m-0 list-none space-y-1 p-0 text-sm">
            {trace.primary_reasons.map((r) => (
              <li key={r.label} className="flex items-baseline gap-3">
                <span className="font-mono text-xs opacity-70">{r.label}</span>
                <span className="opacity-90">{r.comparison}</span>
                <span className="ml-auto font-mono text-xs">{r.weight >= 0 ? "+" : ""}{r.weight.toFixed(2)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {trace.alternative && (
        <div className="mb-4">
          <h3 className="mb-2 text-sm font-medium">Alternative</h3>
          <p className="text-sm">
            <span className="font-mono text-xs opacity-70">{trace.alternative.action}</span>{" "}
            <span className="opacity-80">score {trace.alternative.score.toFixed(3)}</span>
          </p>
        </div>
      )}

      {trace.counterfactuals.length > 0 && (
        <div className="mb-4">
          <h3 className="mb-2 text-sm font-medium">
            What would change this decision?
          </h3>
          <p className="mb-2 text-xs opacity-60">
            Each row shows the outcome if a single rule that fired on the
            winner had been removed. A change means the removed rule was
            decisive: the model would have selected a different action.
            Section 26 rule-ablation counterfactual — exact consequence
            of the Tier 1 rule arithmetic, not a physical prediction.
          </p>
          <ul className="m-0 list-none space-y-1 p-0 text-sm">
            {trace.counterfactuals.map((cf, i) => (
              <li
                key={`${cf.removed_rule}-${i}`}
                className="flex items-baseline gap-3"
                data-testid={`counterfactual-${i}`}
                data-counterfactual-changed={cf.changed ? "true" : "false"}
              >
                <span className="font-mono text-xs opacity-70">
                  {cf.removed_rule}
                </span>
                {cf.changed ? (
                  <span>
                    <span className="opacity-70">remove &rarr; would select </span>
                    <span className="font-mono">{cf.would_select}</span>
                    <span className="ml-2 text-xs opacity-60">
                      (score {cf.ablated_winner_score.toFixed(3)})
                    </span>
                  </span>
                ) : (
                  <span className="opacity-60">remove &rarr; no change</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      <details>
        <summary className="cursor-pointer text-sm font-medium">
          Consulted rules ({trace.consulted_rules.length})
        </summary>
        <ul className="m-0 mt-2 list-none space-y-1 p-0 text-xs">
          {trace.consulted_rules.map((r, i) => (
            <li key={`${r.label}-${i}`} className="flex items-baseline gap-3">
              <span className="font-mono opacity-70">{r.label}</span>
              <span className={`ml-auto ${resultTone(r.result)}`}>{r.result}</span>
            </li>
          ))}
        </ul>
      </details>

      <footer className="mt-4 flex flex-wrap items-center gap-3 border-t border-current/10 pt-3">
        <span className="font-mono text-xs opacity-60" data-artifact-kind>
          artefact: {trace.epistemic_tag}
        </span>
      </footer>
    </TaggedOutput>
  )
}
