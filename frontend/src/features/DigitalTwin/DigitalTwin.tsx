/**
 * DigitalTwin — Section 24.1 / Section 37 Digital Twin state view.
 *
 * Fetches the current steady state, one transient trajectory, and one
 * set of discrepancy observations on mount, and displays them:
 *
 *   - StateCard: steady-state temperatures, thermal runaway boundary,
 *     safety margin, and receiver conversion efficiency.
 *   - TrajectoryChart: SVG polyline of the two-node thermal response.
 *   - DiscrepancyTable: every predicted-vs-observed record with its
 *     absolute and relative error and the triggered flag.
 *
 * Epistemic tagging
 * -----------------
 * Every value rendered here is a model output, not a measurement.
 * Section 21 category: simulation_result. The panel wraps its content
 * in a TaggedOutput with that tag; the inner sections do not repeat the
 * badge.
 */

import { useEffect, useState } from "react"
import { TaggedOutput } from "../../components/EpistemicBadge/EpistemicBadge"
import {
  DigitalTwinApiError,
  postDiscrepancy,
  postState,
  postTrajectory,
  type DiscrepancyResponse,
  type StateResponse,
  type TrajectoryResponse,
} from "./digitalTwinApi"
import { TrajectoryChart } from "./TrajectoryChart"

// Nominal conditions used by the demo. Chosen so the steady state lands
// in the 80-90 C PLC band documented for the Han et al. receiver, which
// makes the safety margin non-trivial and the trajectory rise visible.
const DEMO_INCIDENT_W = 20.0
const DEMO_AIRFLOW = 5.0
const DEMO_AMBIENT_K = 298.15
const DEMO_T_END_S = 600.0
const DEMO_N_SAMPLES = 120

// Three observations covering each of the three default thresholds.
// Two trigger, one does not, so the table shows both cases.
const DEMO_OBSERVATIONS = [
  { field_name: "temperature_k", predicted: 360.0, observed: 365.0 },
  { field_name: "efficiency", predicted: 0.20, observed: 0.202 },
  { field_name: "received_power_w", predicted: 100.0, observed: 105.0 },
]

type PanelState =
  | { status: "loading" }
  | {
      status: "ok"
      state: StateResponse
      trajectory: TrajectoryResponse
      discrepancy: DiscrepancyResponse
    }
  | { status: "error"; message: string; status_code?: number }

export function DigitalTwin() {
  const [state, setState] = useState<PanelState>({ status: "loading" })

  useEffect(() => {
    const controller = new AbortController()
    ;(async () => {
      try {
        const s = await postState(
          {
            incident_power_w: DEMO_INCIDENT_W,
            airflow_m_per_s: DEMO_AIRFLOW,
            ambient_temperature_k: DEMO_AMBIENT_K,
          },
          controller.signal,
        )
        if (controller.signal.aborted) return
        const traj = await postTrajectory(
          {
            incident_power_w: DEMO_INCIDENT_W,
            airflow_m_per_s: DEMO_AIRFLOW,
            ambient_temperature_k: DEMO_AMBIENT_K,
            t_end_s: DEMO_T_END_S,
            n_samples: DEMO_N_SAMPLES,
          },
          controller.signal,
        )
        if (controller.signal.aborted) return
        const disc = await postDiscrepancy(DEMO_OBSERVATIONS, controller.signal)
        if (controller.signal.aborted) return
        setState({ status: "ok", state: s, trajectory: traj, discrepancy: disc })
      } catch (err) {
        if (controller.signal.aborted) return
        if (err instanceof DigitalTwinApiError) {
          setState({ status: "error", message: err.detail, status_code: err.status })
        } else if (err instanceof Error) {
          setState({ status: "error", message: err.message })
        } else {
          setState({ status: "error", message: String(err) })
        }
      }
    })()
    return () => controller.abort()
  }, [])

  return (
    <section aria-labelledby="digital-twin-heading" className="mb-10">
      <h2 id="digital-twin-heading" className="mb-1 text-lg font-medium">
        Digital Twin (Section 24.1)
      </h2>
      <p className="mb-4 text-sm opacity-70">
        Two-node thermal state at the demo conditions. The predicted state
        and the transient trajectory are model outputs; the discrepancy
        table compares two hypothetical observations against the model.
      </p>

      {state.status === "loading" && <p className="opacity-70">Loading digital twin state...</p>}

      {state.status === "error" && (
        <p className="text-sm" style={{ color: "var(--color-accent-amber)" }}>
          Error{state.status_code ? ` (${state.status_code})` : ""}: {state.message}
        </p>
      )}

      {state.status === "ok" && (
        <TaggedOutput tag="simulation_result" className="rounded border border-current/15 p-4">
          <StateCard state={state.state} />

          <div className="my-4 border-t border-current/10 pt-4">
            <h3 className="mb-2 text-sm font-medium">Thermal transient</h3>
            <TrajectoryChart
              samples={state.trajectory.samples}
              label={`Thermal transient response over ${state.trajectory.t_end_s}s`}
            />
            <p className="mt-2 text-xs opacity-70">
              RK45 integration from ambient at both nodes. {state.trajectory.n_samples} samples
              over {state.trajectory.t_end_s} seconds.
            </p>
          </div>

          <div className="border-t border-current/10 pt-4">
            <h3 className="mb-2 text-sm font-medium">
              Predicted vs. observed
              {state.discrepancy.should_refine && (
                <span className="ml-2 text-xs" style={{ color: "var(--color-accent-amber)" }}>
                  refine triggered
                </span>
              )}
            </h3>
            <DiscrepancyTable response={state.discrepancy} />
          </div>

          <footer className="mt-4 border-t border-current/10 pt-3 font-mono text-xs opacity-60">
            artefact: digital_twin_state
          </footer>
        </TaggedOutput>
      )}
    </section>
  )
}

function StateCard({ state }: { state: StateResponse }) {
  const ss = state.steady_state
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
      <div>
        <dt className="text-xs uppercase tracking-wide opacity-60">T_PLC</dt>
        <dd className="font-mono">
          {ss ? `${ss.t_plc_c.toFixed(2)} C` : "no steady state"}
        </dd>
      </div>
      <div>
        <dt className="text-xs uppercase tracking-wide opacity-60">T_TE</dt>
        <dd className="font-mono">
          {ss ? `${ss.t_te_c.toFixed(2)} C` : "no steady state"}
        </dd>
      </div>
      <div>
        <dt className="text-xs uppercase tracking-wide opacity-60">runaway P_max</dt>
        <dd className="font-mono">{state.thermal_runaway_power_w.toFixed(2)} W</dd>
      </div>
      <div>
        <dt className="text-xs uppercase tracking-wide opacity-60">safety margin</dt>
        <dd className="font-mono">
          {state.safety_margin_w.toFixed(2)} W (
          {(state.safety_margin_fraction * 100).toFixed(1)}%)
        </dd>
      </div>
      <div className="col-span-2 sm:col-span-4">
        <dt className="text-xs uppercase tracking-wide opacity-60">
          receiver conversion efficiency
        </dt>
        <dd className="font-mono">
          {state.receiver_efficiency !== null
            ? state.receiver_efficiency.toExponential(3)
            : "—"}
          <span className="ml-2 text-xs opacity-60">
            {state.receiver_efficiency_source}
          </span>
        </dd>
      </div>
    </dl>
  )
}

function DiscrepancyTable({ response }: { response: DiscrepancyResponse }) {
  return (
    <div className="max-h-72 overflow-auto">
      <table className="w-full text-xs">
        <thead className="text-left opacity-70">
          <tr>
            <th className="py-1 font-normal">field</th>
            <th className="py-1 font-normal">predicted</th>
            <th className="py-1 font-normal">observed</th>
            <th className="py-1 font-normal">abs err</th>
            <th className="py-1 font-normal">rel err</th>
            <th className="py-1 font-normal">triggered</th>
          </tr>
        </thead>
        <tbody>
          {response.records.map((r) => (
            <tr key={`${r.field_name}-${r.step}`} className="border-t border-current/10">
              <td className="py-1 font-mono">{r.field_name}</td>
              <td className="py-1 font-mono">{r.predicted}</td>
              <td className="py-1 font-mono">{r.observed}</td>
              <td className="py-1 font-mono">{r.absolute_error.toFixed(4)}</td>
              <td className="py-1 font-mono">{r.relative_error.toFixed(4)}</td>
              <td
                className="py-1 font-mono"
                style={{ color: r.triggered ? "var(--color-accent-amber)" : undefined }}
              >
                {r.triggered ? "yes" : "no"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
