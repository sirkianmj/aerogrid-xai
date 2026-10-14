/**
 * SensitivityPanel — Section 22 capability.
 *
 * Runs the sensitivity endpoint on the current mission configuration
 * and renders a ranked table of parameters by |elasticity|. The top
 * row is the parameter that moves delivered UAV power most per
 * fraction of change; the panel suggests the concrete action (raise
 * or lower).
 *
 * No fabricated recommendations. Every number in the table is the
 * response of a finite-difference evaluation of the mission state
 * under perturbed parameters.
 */

import { useState } from "react"
import { TaggedOutput } from "../../components/EpistemicBadge/EpistemicBadge"
import { useMission } from "../MissionControl/missionContext"
import {
  runSensitivity,
  SensitivityApiError,
  type SensitivityResponse,
  type ParameterSensitivity,
} from "./sensitivityApi"

type PanelState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; result: SensitivityResponse; elapsedMs: number }
  | { status: "error"; message: string; status_code?: number }

function formatPower(w: number): string {
  if (w >= 1.0) return `${w.toFixed(3)} W`
  if (w >= 1e-3) return `${(w * 1e3).toFixed(2)} mW`
  if (w >= 1e-6) return `${(w * 1e6).toFixed(2)} µW`
  return `${w.toExponential(2)} W`
}

export function SensitivityPanel() {
  const { config } = useMission()
  const [state, setState] = useState<PanelState>({ status: "idle" })

  async function run() {
    setState({ status: "loading" })
    const started = Date.now()
    try {
      const body: Record<string, unknown> = {
        seed: config.seed,
        n_uavs: config.n_uavs,
        ground_lat_deg: config.ground_lat_deg,
        ground_lon_deg: config.ground_lon_deg,
        transmitter_power_w: config.transmitter_power_w,
        visibility_km: config.visibility_km,
        cloud_factor: config.cloud_factor,
        transmitter_aperture_m: config.transmitter_aperture_m,
        uav_alt_m: config.uav_alt_m,
        uav_receiver_aperture_m2: config.uav_receiver_aperture_m2,
        uav_receiver_type: config.uav_receiver_type,
      }
      if (config.satellite_elements) {
        body.a_km = config.satellite_elements.a_km
        body.e = config.satellite_elements.e
        body.i_deg = config.satellite_elements.i_deg
        body.raan_deg = config.satellite_elements.raan_deg
        body.argp_deg = config.satellite_elements.argp_deg
        body.m0_deg = config.satellite_elements.m0_deg
        body.elements_epoch_utc = config.satellite_elements.epoch_utc
      } else {
        body.satellite_key = config.satellite_key
      }
      const result = await runSensitivity({ base: body })
      setState({ status: "ok", result, elapsedMs: Date.now() - started })
    } catch (err) {
      if (err instanceof SensitivityApiError) {
        setState({ status: "error", message: err.detail, status_code: err.status })
      } else if (err instanceof Error) {
        setState({ status: "error", message: err.message })
      } else {
        setState({ status: "error", message: String(err) })
      }
    }
  }

  return (
    <section aria-labelledby="sensitivity-heading" className="mb-10">
      <h2 id="sensitivity-heading" className="mb-1 text-lg font-semibold">
        Design suggestions (Section 22)
      </h2>
      <p className="mb-4 text-sm text-[var(--ink-secondary)]">
        Which parameter moves delivered UAV power most. Computed by
        finite differences on the mission-state physics at the current
        configuration. The top row is the highest-leverage change.
      </p>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={run}
          disabled={state.status === "loading"}
          className="rounded border border-[var(--border-hairline)] px-3 py-1.5 text-sm hover:bg-[var(--bg-subtle)] disabled:opacity-50"
        >
          {state.status === "loading" ? "Running..." : "Analyse sensitivities"}
        </button>
        {state.status === "ok" && (
          <span className="text-xs text-[var(--ink-tertiary)]">
            base delivered power {formatPower(state.result.base_delivered_power_w)}
            {" · "}verdict {state.result.base_sat_verdict}
            {" · "}elapsed {state.elapsedMs} ms
          </span>
        )}
      </div>

      {state.status === "idle" && (
        <p className="text-sm text-[var(--ink-secondary)]">
          No analysis yet. Press Analyse sensitivities to run one.
        </p>
      )}

      {state.status === "error" && (
        <p className="text-sm" style={{ color: "var(--status-red)" }}>
          Error{state.status_code ? ` (${state.status_code})` : ""}: {state.message}
        </p>
      )}

      {state.status === "ok" && (
        <TaggedOutput tag="simulation_result" className="apple-card p-4">
          <table className="w-full text-xs">
            <thead className="text-left text-[var(--ink-tertiary)]">
              <tr>
                <th className="py-1 font-normal">#</th>
                <th className="py-1 font-normal">parameter</th>
                <th className="py-1 font-normal text-right">base</th>
                <th className="py-1 font-normal text-right">elasticity</th>
                <th className="py-1 font-normal text-right">direction</th>
              </tr>
            </thead>
            <tbody>
              {state.result.parameters.map((p, i) => (
                <Row key={p.name} p={p} index={i} />
              ))}
            </tbody>
          </table>
          <p className="mt-3 text-[0.7rem] text-[var(--ink-tertiary)]">
            Elasticity is the fractional change in delivered power per
            fractional change in the parameter. +1 means a 1% parameter
            increase raises power 1%.
          </p>
          <footer className="mt-3 border-t border-[var(--border-hairline)] pt-3 font-mono text-xs text-[var(--ink-tertiary)]">
            artefact: design_sensitivity
          </footer>
        </TaggedOutput>
      )}
    </section>
  )
}

function Row({ p, index }: { p: ParameterSensitivity; index: number }) {
  const el =
    p.elasticity === null ? "—" : p.elasticity >= 0
      ? `+${p.elasticity.toFixed(3)}`
      : p.elasticity.toFixed(3)
  const arrow = p.direction === "increase" ? "↑" : p.direction === "decrease" ? "↓" : "="
  const highlight = index === 0 && p.direction !== "flat"

  return (
    <tr
      className={"border-t border-[var(--border-hairline)]" + (highlight ? " bg-[var(--bg-subtle)]" : "")}
      data-testid={`sensitivity-row-${p.name}`}
    >
      <td className="py-1 font-mono text-[var(--ink-tertiary)]">{index + 1}</td>
      <td className="py-1 font-mono">{p.name}</td>
      <td className="py-1 font-mono text-right">
        {p.base_value === 0 ? "0" : p.base_value.toExponential(2)}
      </td>
      <td className="py-1 font-mono text-right">{el}</td>
      <td className="py-1 text-right">{arrow}</td>
    </tr>
  )
}
