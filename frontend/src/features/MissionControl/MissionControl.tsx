/**
 * Mission Control — the vertical pipeline view.
 *
 * Renders Section 4 of the specification as a live instrument. Every
 * stage card reads from a single coherent mission state returned by
 * GET /mission/state; nothing is fabricated. Stages the backend has
 * not yet wired are visibly marked with a status pill and a reason
 * rather than hidden.
 *
 * The panel is a drill-in: each stage card has an expandable detail
 * area. Clicking the disclosure button toggles it. Nothing else is
 * clickable.
 */

import { useState } from "react"
import { TaggedOutput } from "../../components/EpistemicBadge/EpistemicBadge"
import type { MissionState, PipelineStage } from "./missionApi"
import { useMission } from "./missionContext"

const STATUS_COLOR: Record<string, string> = {
  wired: "var(--color-accent-teal)",
  partial: "var(--color-accent-violet)",
  pending: "var(--color-accent-slate)",
  offline: "var(--color-accent-amber)",
}

function StatusPill({ status, reason }: { status: string; reason?: string }) {
  const color = STATUS_COLOR[status] ?? "var(--color-accent-slate)"
  return (
    <span
      data-testid={`status-pill-${status}`}
      title={reason || undefined}
      style={{
        borderColor: color,
        color,
        display: "inline-flex",
        alignItems: "center",
        gap: "0.25rem",
        padding: "0.05rem 0.45rem",
        border: "1px solid",
        borderRadius: "999px",
        fontFamily: "ui-monospace, monospace",
        fontSize: "0.65rem",
        textTransform: "uppercase",
        letterSpacing: "0.05em",
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: "0.35rem",
          height: "0.35rem",
          borderRadius: "50%",
          background: color,
        }}
      />
      {status}
    </span>
  )
}

function KeyValue({
  label,
  value,
  mono = true,
}: {
  label: string
  value: string
  mono?: boolean
}) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="text-[0.65rem] uppercase tracking-wide opacity-50">{label}</span>
      <span className={mono ? "font-mono text-sm" : "text-sm"}>{value}</span>
    </div>
  )
}

function stageByKey(stages: PipelineStage[], key: string): PipelineStage {
  return (
    stages.find((s) => s.key === key) ?? {
      key,
      label: key,
      status: "pending",
      reason: "no status reported",
    }
  )
}

function Stage({
  code,
  title,
  status,
  statusReason,
  children,
  defaultOpen = false,
}: {
  code: string
  title: string
  status: string
  statusReason?: string
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <section
      data-testid={`stage-${code}`}
      className="rounded border border-current/15 bg-current/[0.015]"
    >
      <div className="flex items-center gap-3 px-4 py-3">
        <span className="font-mono text-[0.65rem] uppercase tracking-widest opacity-40 w-24 shrink-0">
          {code}
        </span>
        <h3 className="text-sm font-medium flex-1">{title}</h3>
        <StatusPill status={status} reason={statusReason} />
        <button
          type="button"
          aria-expanded={open}
          aria-controls={`stage-${code}-detail`}
          onClick={() => setOpen((v) => !v)}
          className="rounded border border-current/20 px-2 py-0.5 text-[0.65rem] uppercase tracking-wider opacity-70 hover:opacity-100 hover:bg-current/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-current/40"
        >
          {open ? "Hide detail" : "Detail"}
        </button>
      </div>
      {open && (
        <div
          id={`stage-${code}-detail`}
          className="border-t border-current/10 px-4 py-3 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3"
        >
          {children}
        </div>
      )}
    </section>
  )
}

function fmtDeg(v: number, axis: "lat" | "lon"): string {
  const hemi =
    axis === "lat" ? (v >= 0 ? "N" : "S") : v >= 0 ? "E" : "W"
  return `${Math.abs(v).toFixed(3)}° ${hemi}`
}

function fmtRelativeSeconds(seconds: number): string {
  const days = seconds / 86400
  if (Math.abs(days) < 1) return `${seconds.toFixed(0)} s`
  if (Math.abs(days) < 365) return `${days.toFixed(1)} days`
  return `${(days / 365.25).toFixed(1)} years`
}

export function MissionControl() {
  const { state: load, refresh } = useMission()

  return (
    <section aria-labelledby="mission-control-heading" className="mb-10">
      <div className="mb-1 flex items-baseline gap-3">
        <h2 id="mission-control-heading" className="text-lg font-medium">
          Mission Control
        </h2>
        <span className="text-xs opacity-50">
          Section 4 pipeline · live state from <code>GET /mission/state</code>
        </span>
      </div>
      <p className="mb-4 text-sm opacity-70 max-w-3xl">
        One coherent scenario: satellite propagated from a packaged TLE, atmosphere
        at the current geometry, a real Z3 SAT/UNSAT verdict on a generated
        architecture, a CLEAR-D snapshot, and a Tier 1 decision over the UAVs.
        No fabricated values; stages the backend has not yet wired say so.
      </p>

      {load.status === "loading" && (
        <p className="text-sm opacity-60" data-testid="mission-loading">
          Loading mission state…
        </p>
      )}

      {load.status === "error" && (
        <div className="rounded border border-current/15 p-4" data-testid="mission-error">
          <p className="text-sm" style={{ color: "var(--color-accent-amber)" }}>
            Error{load.status_code ? ` (${load.status_code})` : ""}: {load.message}
          </p>
          <button
            type="button"
            onClick={() => refresh()}
            className="mt-3 rounded border px-3 py-1 text-xs hover:bg-current/5"
          >
            Retry
          </button>
        </div>
      )}

      {load.status === "ok" && <PipelineView data={load.data} onRefresh={refresh} />}
    </section>
  )
}

function PipelineView({ data, onRefresh }: { data: MissionState; onRefresh: () => void }) {
  const s = data
  const stages = s.pipeline_stages
  const txStage = stageByKey(stages, "wireless_transmission")
  const atmStage = stageByKey(stages, "atmosphere")
  const uavStage = stageByKey(stages, "uav_network")
  const geoStage = stageByKey(stages, "geographic_region")
  const tier1Stage = stageByKey(stages, "tier1_decision")
  const z3Stage = stageByKey(stages, "z3_verification")
  const cleardStage = stageByKey(stages, "cleard_loop")
  const tier2Stage = stageByKey(stages, "tier2_surrogates")

  const sat = s.satellite
  const tleStatus = sat.valid ? "wired" : "offline"
  const tleReason = sat.valid ? "" : sat.invalid_reason

  return (
    <TaggedOutput tag="simulation_result" className="rounded border border-current/15 p-4">
      <div className="mb-4 flex flex-wrap items-baseline gap-4 text-xs opacity-70">
        <span className="font-mono">t = {s.t_utc}</span>
        <span className="font-mono">seed = {s.seed}</span>
        <span>{s.pipeline_stages.filter((p) => p.status === "wired").length} wired ·{" "}
              {s.pipeline_stages.filter((p) => p.status === "partial").length} partial ·{" "}
              {s.pipeline_stages.filter((p) => p.status === "pending").length} pending</span>
        <button
          type="button"
          onClick={onRefresh}
          className="ml-auto rounded border border-current/20 px-2 py-0.5 text-[0.65rem] uppercase tracking-wider hover:bg-current/5"
        >
          Refresh
        </button>
      </div>

      <div className="space-y-3">
        <Stage
          code="SPACE"
          title={`Satellite energy source — ${sat.name} (${sat.orbit_class})`}
          status={tleStatus}
          statusReason={tleReason}
          defaultOpen
        >
          <KeyValue label="lat" value={fmtDeg(sat.lat_deg, "lat")} />
          <KeyValue label="lon" value={fmtDeg(sat.lon_deg, "lon")} />
          <KeyValue label="alt" value={`${sat.alt_km.toFixed(1)} km`} />
          <KeyValue label="eclipse" value={sat.in_eclipse ? "yes" : "no"} />
          <KeyValue label="period" value={`${(sat.period_seconds / 60).toFixed(1)} min`} />
          <KeyValue
            label="TLE age"
            value={fmtRelativeSeconds(sat.tle_age_seconds)}
          />
          {!sat.valid && (
            <div className="col-span-full text-xs" style={{ color: "var(--color-accent-amber)" }}>
              {sat.invalid_reason}
            </div>
          )}
        </Stage>

        <Stage
          code="WIRELESS TX"
          title={`Wireless power transmission — ${s.transmission.modality}`}
          status={txStage.status}
          statusReason={txStage.reason}
          defaultOpen
        >
          <KeyValue label="wavelength" value={`${s.transmission.wavelength_nm.toFixed(0)} nm`} />
          <KeyValue
            label="transmitter"
            value={`${(s.transmission.transmitter_power_w / 1000).toFixed(1)} kW`}
          />
          <KeyValue
            label="slant range"
            value={`${(s.transmission.slant_range_m / 1000).toFixed(1)} km`}
          />
          <KeyValue
            label="atmos path"
            value={`${(s.transmission.atmospheric_path_m / 1000).toFixed(2)} km`}
          />
          <KeyValue
            label="elevation"
            value={`${s.transmission.elevation_deg.toFixed(2)}°`}
          />
          <KeyValue
            label="epistemic"
            value={s.transmission.modality === "laser" ? "simulation_result" : "offline"}
            mono
          />
        </Stage>

        <Stage
          code="ATMOSPHERE"
          title="Atmospheric transmission model"
          status={atmStage.status}
          statusReason={atmStage.reason}
        >
          <KeyValue label="τ" value={s.atmosphere.transmittance.toFixed(4)} />
          {s.atmosphere.transmittance_low !== null &&
            s.atmosphere.transmittance_high !== null &&
            s.atmosphere.nominal_coverage !== null && (
              <KeyValue
                label="τ interval"
                value={`[${s.atmosphere.transmittance_low.toFixed(3)}, ${s.atmosphere.transmittance_high.toFixed(3)}] @ ${(s.atmosphere.nominal_coverage * 100).toFixed(0)}%`}
              />
            )}
          <KeyValue label="visibility" value={`${s.atmosphere.visibility_km.toFixed(1)} km`} />
          <KeyValue label="cloud" value={s.atmosphere.cloud_factor.toFixed(2)} />
          <KeyValue
            label="extinction"
            value={`${s.atmosphere.extinction_coeff_per_m.toExponential(2)} /m`}
          />
        </Stage>

        <Stage
          code="UAV NETWORK"
          title={`UAV infrastructure network — ${s.uavs.length} node${s.uavs.length === 1 ? "" : "s"}`}
          status={uavStage.status}
          statusReason={uavStage.reason}
          defaultOpen
        >
          {s.uavs.map((u) => (
            <div
              key={u.uav_id}
              className="rounded border border-current/10 px-2 py-1 font-mono text-xs"
            >
              <div className="opacity-70">uav-{u.uav_id} · {u.role}</div>
              <div>battery {u.battery_pct.toFixed(0)}%</div>
              <div>thermal ΔT {u.thermal_headroom_c.toFixed(0)}°C</div>
            </div>
          ))}
        </Stage>

        <Stage
          code="GEOGRAPHY"
          title={`Geographic region — ${s.ground_station.name}`}
          status={geoStage.status}
          statusReason={geoStage.reason}
        >
          <KeyValue label="lat" value={fmtDeg(s.ground_station.lat_deg, "lat")} />
          <KeyValue label="lon" value={fmtDeg(s.ground_station.lon_deg, "lon")} />
          <KeyValue label="alt" value={`${s.ground_station.alt_m.toFixed(0)} m`} />
        </Stage>

        <div className="pt-2">
          <p className="mb-2 text-[0.7rem] uppercase tracking-widest opacity-40">
            Intelligence layer
          </p>
        </div>

        <Stage
          code="TIER 1"
          title={`Interpretable decision — ${s.tier1.selected_action} (${s.tier1.decision_kind})`}
          status={tier1Stage.status}
          statusReason={tier1Stage.reason}
          defaultOpen
        >
          <KeyValue label="score" value={s.tier1.score.toFixed(3)} />
          <KeyValue label="confidence" value={`${(s.tier1.confidence * 100).toFixed(1)}%`} />
          <KeyValue
            label="alternative"
            value={
              s.tier1.alternative_action
                ? `${s.tier1.alternative_action} (${s.tier1.alternative_score.toFixed(3)})`
                : "—"
            }
          />
          <KeyValue label="epistemic" value={s.tier1.epistemic_tag} />
        </Stage>

        <Stage
          code="Z3"
          title={`Formal verification — ${s.architecture.sat_verdict.toUpperCase()}`}
          status={z3Stage.status}
          statusReason={z3Stage.reason}
          defaultOpen
        >
          <KeyValue label="verdict" value={s.architecture.sat_verdict} />
          <KeyValue label="constraints" value={String(s.architecture.n_constraints)} />
          <KeyValue label="ε" value={s.architecture.epsilon_bound.toExponential(3)} />
          <KeyValue label="nodes" value={String(s.architecture.nodes)} />
          <KeyValue label="links" value={String(s.architecture.links)} />
        </Stage>

        <Stage
          code="CLEAR-D"
          title={`Discovery loop — ${s.cleard.feasible_final} feasible / ${s.cleard.population_size} population`}
          status={cleardStage.status}
          statusReason={cleardStage.reason}
          defaultOpen
        >
          <KeyValue label="generations" value={String(s.cleard.n_generations)} />
          <KeyValue label="feasible" value={String(s.cleard.feasible_final)} />
          <KeyValue label="infeasible" value={String(s.cleard.infeasible_final)} />
          <KeyValue
            label="conflict-prone"
            value={String(s.cleard.conflict_prone_features)}
          />
          <KeyValue
            label="mode"
            value={s.cleard.use_conflict_directed ? "conflict-directed" : "random"}
            mono={false}
          />
        </Stage>

        <Stage
          code="TIER 2"
          title="Auxiliary prediction surrogates"
          status={tier2Stage.status}
          statusReason={tier2Stage.reason}
        >
          <p className="col-span-full text-xs opacity-60">
            Tier 2 calibrated-interval rendering is a later PR. This stage exists
            in the specification and is not yet surfaced in the UI.
          </p>
        </Stage>
      </div>

      <footer className="mt-4 border-t border-current/10 pt-3 font-mono text-xs opacity-60">
        artefact: mission_state · seed {s.seed}
      </footer>
    </TaggedOutput>
  )
}
