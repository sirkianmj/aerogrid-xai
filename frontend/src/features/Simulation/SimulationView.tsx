/**
 * Step 5 — Simulation.
 *
 * Runs the selected architecture against the mission over a time window
 * and displays per-UAV power series, cumulative energy, atmospheric
 * transmittance, and satellite elevation. Every sample comes from
 * POST /simulation/run and is a Section 21 simulation_result.
 * The panel carries a single epistemic badge because every sample
 * shares that category — one tag per panel, not per series.
 */

import { useEffect, useRef, useState, type ReactNode } from "react"
import ReactECharts from "echarts-for-react"
import { EpistemicBadge } from "../../components/EpistemicBadge/EpistemicBadge"
import { useMission } from "../MissionControl/missionContext"
import { exportArtifact } from "../../lib/download"
import {
  SimulationApiError,
  runSimulation,
  type SimulationPreset,
  type SimulationResponse,
} from "./simulationApi"
import { aggregateOption, perUavPowerOption } from "./chartOptions"

type PanelState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; result: SimulationResponse; elapsedMs: number }
  | { status: "error"; message: string }

const PRESETS: { id: SimulationPreset; label: string; description: string }[] = [
  { id: "10min", label: "10 min", description: "±5 min around peak elevation" },
  { id: "1hour", label: "1 hour", description: "±30 min around peak elevation" },
  { id: "1pass", label: "1 pass", description: "Pass window" },
]

export function SimulationView() {
  const { config, markStepComplete, completedSteps, setStepOutput } = useMission()
  const [preset, setPreset] = useState<SimulationPreset>("10min")
  const [state, setState] = useState<PanelState>({ status: "idle" })
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  async function run() {
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setState({ status: "loading" })
    const t0 = performance.now()
    try {
      const result = await runSimulation(
        {
          preset,
          seed: config.seed,
          satellite_key: config.satellite_key,
          n_uavs: config.n_uavs,
          ground_lat_deg: config.ground_lat_deg,
          ground_lon_deg: config.ground_lon_deg,
          transmitter_power_w: config.transmitter_power_w,
          wavelength_nm: config.wavelength_nm,
          visibility_km: config.visibility_km,
          cloud_factor: config.cloud_factor,
          transmitter_type: config.transmitter_type,
          transmitter_min_elevation_deg: config.transmitter_min_elevation_deg,
        },
        ctrl.signal,
      )
      const elapsedMs = Math.round(performance.now() - t0)
      setState({ status: "ok", result, elapsedMs })
      if (!completedSteps.has(5)) markStepComplete(5)
      setStepOutput(5, result)
    } catch (e) {
      if (ctrl.signal.aborted) return
      const message =
        e instanceof SimulationApiError || e instanceof Error
          ? e.message
          : "unknown error"
      setState({ status: "error", message })
    }
  }

  function exportRun() {
    if (state.status !== "ok") return
    exportArtifact("simulation-run", "simulation_result", state.result, {
      mission_config: config,
      preset,
    })
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">5 · Simulation</h2>
          <p className="mt-1 text-sm text-[var(--ink-secondary)]">
            Runs the selected architecture against the mission over a time window.
            Every sample is a Section 21 simulation_result.
          </p>
        </div>
        <EpistemicBadge tag="simulation_result" />
      </header>

      <div className="rounded-xl border border-[var(--border-hairline)] bg-[var(--bg-surface)] p-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-[11px] uppercase tracking-wider text-[var(--ink-tertiary)]">
            Preset
          </span>
          {PRESETS.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => setPreset(p.id)}
              className={
                "rounded-md px-3 py-1 text-xs font-medium transition-colors " +
                (preset === p.id
                  ? "bg-[var(--accent-pressed)] text-white"
                  : "text-[var(--ink-secondary)] hover:bg-[var(--bg-subtle)]")
              }
              title={p.description}
            >
              {p.label}
            </button>
          ))}
          <span className="ml-auto text-[11px] text-[var(--ink-tertiary)]">
            {PRESETS.find((p) => p.id === preset)?.description}
          </span>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={run}
            disabled={state.status === "loading"}
            className="apple-btn apple-btn-primary disabled:opacity-40"
          >
            {state.status === "loading" ? "Running…" : "Run simulation"}
          </button>
          {state.status === "ok" && (
            <>
              <span className="text-xs text-[var(--ink-tertiary)]">
                {state.result.n_samples} samples in {state.elapsedMs} ms
              </span>
              <button
                type="button"
                onClick={exportRun}
                className="text-xs text-[var(--accent-pressed)] hover:underline"
              >
                Export JSON
              </button>
            </>
          )}
        </div>
      </div>

      {state.status === "idle" && (
        <p className="text-sm text-[var(--ink-tertiary)]">
          Press Run to execute a time-stepping simulation.
        </p>
      )}

      {state.status === "error" && (
        <div className="rounded-lg border border-[#ff3b30]/40 bg-[#ff3b30]/5 p-3 text-sm text-[#ff3b30]">
          {state.message}
        </div>
      )}

      {state.status === "ok" && (
        <>
          {state.result.warnings.length > 0 && (
            <div className="rounded-lg border border-[#ff9500]/40 bg-[#ff9500]/5 p-3 text-xs text-[#ff9500]">
              <div className="font-semibold">Warnings</div>
              <ul className="mt-1 list-disc pl-5">
                {state.result.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          <SummaryPanel result={state.result} />

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <ChartCard title="Received power per UAV">
              <ReactECharts
                option={perUavPowerOption(
                  state.result.samples,
                  "received_power_w",
                  "received (W)",
                )}
                style={{ height: 280 }}
                notMerge
              />
            </ChartCard>
            <ChartCard title="Delivered power per UAV">
              <ReactECharts
                option={perUavPowerOption(
                  state.result.samples,
                  "delivered_power_w",
                  "delivered (W)",
                )}
                style={{ height: 280 }}
                notMerge
              />
            </ChartCard>
            <ChartCard title="Cumulative energy">
              <ReactECharts
                option={aggregateOption(
                  state.result.samples,
                  "cumulative_energy_j",
                  "energy (J)",
                  true,
                )}
                style={{ height: 280 }}
                notMerge
              />
            </ChartCard>
            <ChartCard title="Atmospheric transmittance">
              <ReactECharts
                option={aggregateOption(
                  state.result.samples,
                  "atmospheric_transmittance",
                  "tau",
                  false,
                )}
                style={{ height: 280 }}
                notMerge
              />
            </ChartCard>
          </div>
        </>
      )}
    </div>
  )
}

function SummaryPanel({ result }: { result: SimulationResponse }) {
  const last = result.samples[result.samples.length - 1]
  const totalEnergy = last?.cumulative_energy_j ?? 0
  const peakPower = Math.max(...result.samples.map((s) => s.delivered_power_w), 0)
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      <Stat label="Samples" value={String(result.n_samples)} />
      <Stat label="Duration" value={`${Math.round(result.duration_s)} s`} />
      <Stat label="Peak delivered" value={`${peakPower.toFixed(1)} W`} />
      <Stat label="Total energy" value={`${(totalEnergy / 1000).toFixed(2)} kJ`} />
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[var(--border-hairline)] bg-[var(--bg-surface)] p-3">
      <div className="text-[10px] uppercase tracking-wider text-[var(--ink-tertiary)]">
        {label}
      </div>
      <div className="mt-1 font-mono text-sm text-[var(--ink-primary)]">{value}</div>
    </div>
  )
}

function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-[var(--border-hairline)] bg-[var(--bg-surface)] p-3">
      <div className="mb-2 text-xs font-semibold text-[var(--ink-secondary)]">{title}</div>
      {children}
    </div>
  )
}
