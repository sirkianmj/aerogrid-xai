/**
 * Mission Control — engineering schematic + live data table.
 *
 * Layout: a wide SVG schematic on the left (satellite → beam →
 * atmosphere → UAV cluster → ground station) rendered with real
 * shapes from components/Orbit/svg. To the right, a table with one
 * row per pipeline stage, its status pill, and its live numbers.
 *
 * Every value in the table is read from the single mission state
 * returned by GET /mission/state. Nothing is fabricated. Stages the
 * backend has not wired show a `pending` pill with a reason.
 */

import { useState } from "react"
import { TaggedOutput } from "../../components/EpistemicBadge/EpistemicBadge"
import { SatelliteSVG } from "../../components/Orbit/svg/SatelliteSVG"
import { UavSVG } from "../../components/Orbit/svg/UavSVG"
import { GroundStationSVG } from "../../components/Orbit/svg/GroundStationSVG"
import { AtmosphereBand } from "../../components/Orbit/svg/AtmosphereBand"
import type { MissionState, PipelineStage } from "./missionApi"
import { useMission } from "./missionContext"

const STATUS_COLOR: Record<string, string> = {
  wired: "var(--status-green)",
  partial: "var(--status-orange)",
  pending: "var(--ink-tertiary)",
  offline: "var(--status-red)",
}

function StatusPill({ status, reason }: { status: string; reason?: string }) {
  const color = STATUS_COLOR[status] ?? "var(--ink-tertiary)"
  return (
    <span
      data-testid={`status-pill-${status}`}
      title={reason || undefined}
      style={{
        borderColor: color,
        color,
        display: "inline-flex",
        alignItems: "center",
        gap: "0.3rem",
        padding: "0.05rem 0.45rem",
        border: "1px solid",
        borderRadius: "999px",
        fontFamily: "ui-monospace, SFMono-Regular, monospace",
        fontSize: "0.65rem",
        textTransform: "uppercase",
        letterSpacing: "0.04em",
        whiteSpace: "nowrap",
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

function fmtDeg(v: number, axis: "lat" | "lon"): string {
  const hemi = axis === "lat" ? (v >= 0 ? "N" : "S") : v >= 0 ? "E" : "W"
  return `${Math.abs(v).toFixed(3)}° ${hemi}`
}

function formatPower(w: number): string {
  if (w >= 1.0) return `${w.toFixed(2)} W`
  if (w >= 1e-3) return `${(w * 1e3).toFixed(1)} mW`
  if (w >= 1e-6) return `${(w * 1e6).toFixed(1)} µW`
  return `${w.toExponential(2)} W`
}

function fmtRelativeSeconds(seconds: number): string {
  const days = seconds / 86400
  if (Math.abs(days) < 1) return `${seconds.toFixed(0)} s`
  if (Math.abs(days) < 365) return `${days.toFixed(1)} d`
  return `${(days / 365.25).toFixed(1)} y`
}

export function MissionControl() {
  const { state: load, refresh, markStepComplete } = useMission()

  return (
    <section
      data-tour-id="mission-control"
      aria-labelledby="mission-control-heading"
      className="mb-10"
    >
      <div className="mb-1 flex flex-wrap items-baseline gap-3">
        <h2 id="mission-control-heading" className="text-lg font-semibold">
          Mission Control
        </h2>
        <span className="text-xs text-[var(--ink-secondary)]">
          Section 4 pipeline · live state from{" "}
          <code className="font-mono">GET /mission/state</code>
        </span>
        <button
          type="button"
          onClick={refresh}
          className="ml-auto rounded-md border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-3 py-1 text-xs hover:bg-[var(--bg-subtle)]"
        >
          Refresh
        </button>
      </div>

      {load.status === "loading" && (
        <p className="text-sm text-[var(--ink-secondary)]" data-testid="mission-loading">
          Loading mission state…
        </p>
      )}

      {load.status === "error" && (
        <div className="apple-card p-4" data-testid="mission-error">
          <p className="text-sm" style={{ color: "var(--status-red)" }}>
            Error{load.status_code ? ` (${load.status_code})` : ""}: {load.message}
          </p>
          <button
            type="button"
            onClick={() => refresh()}
            className="mt-3 rounded border border-[var(--border-hairline)] px-3 py-1 text-xs hover:bg-[var(--bg-subtle)]"
          >
            Retry
          </button>
        </div>
      )}

      {load.status === "ok" && (
        <TaggedOutput tag="simulation_result">
          <div className="mb-3 flex flex-wrap items-baseline gap-4 font-mono text-[11px] text-[var(--ink-secondary)]">
            <span>t = {load.data.t_utc}</span>
            <span>seed = {load.data.seed}</span>
            <span>
              {load.data.pipeline_stages.filter((p) => p.status === "wired").length} wired ·{" "}
              {load.data.pipeline_stages.filter((p) => p.status === "partial").length} partial ·{" "}
              {load.data.pipeline_stages.filter((p) => p.status === "pending").length} pending
            </span>
          </div>
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-[500px_1fr]">
            <Schematic data={load.data} />
            <StageTable data={load.data} />
          </div>
        </TaggedOutput>
      )}
          <div
        className="mt-8 flex flex-wrap items-center gap-3 border-t border-[var(--border-hairline)] pt-4"
      >
        <button
          type="button"
          onClick={() => markStepComplete(2)}
          className="apple-btn apple-btn-primary"
          data-testid="confirm-mission"
        >
          Confirm this mission
        </button>
        <span className="text-[11px] text-[var(--ink-tertiary)]">
          Marks step 2 complete. Required before Discovery can run.
        </span>
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------ */
/* Left: the schematic                                                 */
/* ------------------------------------------------------------------ */

function Schematic({ data }: { data: MissionState }) {
  const sat = data.satellite
  const uavs = data.uavs
  const nUavs = Math.max(1, uavs.length)
  const uavCount = Math.min(nUavs, 5)
  const uavXs = Array.from({ length: uavCount }, (_, i) => {
    const spacing = 90
    const totalW = spacing * (uavCount - 1)
    return 250 - totalW / 2 + i * spacing
  })

  // Beam direction: if the transmission is offline (below horizon)
  // draw the beam as dashed and do not connect to the UAV cluster.
  const isOffline = data.transmission.modality === "offline"
  const beamStroke = isOffline ? "var(--ink-tertiary)" : "var(--ink-primary)"

  return (
    <div className="apple-card p-3">
      <svg
        viewBox="0 0 500 640"
        className="h-full w-full"
        role="img"
        aria-label="Mission topology schematic"
      >
        {/* Subtle grid */}
        <g stroke="var(--border-hairline)" strokeWidth="0.5" opacity="0.6">
          {[80, 160, 240, 320, 400, 480, 560].map((y) => (
            <line key={`h${y}`} x1="0" y1={y} x2="500" y2={y} />
          ))}
          {[100, 200, 300, 400].map((x) => (
            <line key={`v${x}`} x1={x} y1="0" x2={x} y2="640" />
          ))}
        </g>

        {/* Stage labels */}
        <g
          fontFamily="ui-monospace, monospace"
          fontSize="9"
          fill="var(--ink-tertiary)"
          letterSpacing="0.06em"
        >
          <text x="16" y="26">01 · SPACE — SGP4/SDP4</text>
          <text x="16" y="196">02 · WIRELESS TX</text>
          <text x="16" y="290">03 · ATMOSPHERE</text>
          <text x="16" y="426">04 · UAV NETWORK</text>
          <text x="16" y="546">05 · GEOGRAPHY</text>
        </g>

        {/* SPACE — satellite */}
        <g transform="translate(200, 60)">
          <SatelliteSVG variant={sat.orbit_class === "GEO" ? "geo" : "leo"} />
        </g>
        <text
          x="250"
          y="155"
          textAnchor="middle"
          fontFamily="ui-monospace, monospace"
          fontSize="10"
          fill="var(--ink-primary)"
        >
          {sat.name} · {sat.orbit_class}
        </text>

        {/* WIRELESS TX — beam */}
        <line
          x1="250"
          y1="175"
          x2="250"
          y2="440"
          stroke={beamStroke}
          strokeWidth="2"
          strokeDasharray={isOffline ? "6 4" : undefined}
        />
        <line
          x1="236"
          y1="175"
          x2="250"
          y2="440"
          stroke="var(--ink-tertiary)"
          strokeWidth="0.6"
          strokeDasharray="3 3"
        />
        <line
          x1="264"
          y1="175"
          x2="250"
          y2="440"
          stroke="var(--ink-tertiary)"
          strokeWidth="0.6"
          strokeDasharray="3 3"
        />
        <text
          x="258"
          y="230"
          fontFamily="ui-monospace, monospace"
          fontSize="9"
          fill="var(--ink-secondary)"
        >
          {isOffline
            ? "LINK OFFLINE"
            : `${data.transmission.wavelength_nm.toFixed(0)} nm · ${(data.transmission.transmitter_power_w / 1000).toFixed(1)} kW`}
        </text>

        {/* ATMOSPHERE — band across the beam */}
        <AtmosphereBand
          x={120}
          y={330}
          width={260}
          height={40}
          opticalDepth={
            isOffline ? 0 : Math.max(0.02, 1 - data.atmosphere.transmittance)
          }
        />

        {/* UAV NETWORK — drone silhouettes */}
        <g>
          {uavXs.map((x, i) => (
            <g key={i} transform={`translate(${x - 30}, 440)`}>
              <UavSVG variant={uavs[i]?.role === "UAV_Compute" ? "fixed" : "quad"} />
            </g>
          ))}
        </g>

        {/* FANET mesh links */}
        <g stroke="var(--ink-tertiary)" strokeWidth="0.8" strokeDasharray="3 3" opacity="0.5">
          {uavXs.slice(1).map((x, i) => (
            <line key={i} x1={uavXs[i]} y1="462" x2={x} y2="462" />
          ))}
        </g>

        {/* GEOGRAPHY — ground station */}
        <g transform="translate(220, 560)">
          <GroundStationSVG />
        </g>
      </svg>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Right: the data table                                               */
/* ------------------------------------------------------------------ */

function StageRow({
  code,
  title,
  status,
  statusReason,
  children,
}: {
  code: string
  title: string
  status: string
  statusReason?: string
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(true)
  return (
    <div
      data-testid={`stage-${code}`}
      className="border-b border-[var(--border-hairline)] py-2 last:border-b-0"
    >
      <div className="flex items-center gap-3">
        <span className="w-24 shrink-0 font-mono text-[10px] uppercase tracking-widest text-[var(--ink-tertiary)]">
          {code}
        </span>
        <span className="flex-1 text-[12px] font-medium">{title}</span>
        <StatusPill status={status} reason={statusReason} />
        <button
          type="button"
          aria-expanded={open}
          aria-controls={`stage-${code}-detail`}
          onClick={() => setOpen((v) => !v)}
          className="rounded border border-[var(--border-hairline)] px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-[var(--ink-secondary)] hover:bg-[var(--bg-subtle)]"
        >
          {open ? "−" : "+"}
        </button>
      </div>
      {open && (
        <div
          id={`stage-${code}-detail`}
          className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 pl-[6.5rem] font-mono text-[11px]"
        >
          {children}
        </div>
      )}
    </div>
  )
}

function KV({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-[10px] uppercase tracking-wide text-[var(--ink-tertiary)]">
        {label}
      </span>
      <span className="text-[var(--ink-primary)]">{value}</span>
    </div>
  )
}

function StageTable({ data }: { data: MissionState }) {
  const s = data
  const stages = s.pipeline_stages
  const sat = s.satellite
  const tleStatus = sat.valid ? "wired" : "offline"
  const tleReason = sat.valid ? "" : sat.invalid_reason
  const atm = s.atmosphere

  return (
    <div className="apple-card p-4">
      <StageRow
        code="SPACE"
        title={`Satellite — ${sat.name} (${sat.orbit_class})`}
        status={tleStatus}
        statusReason={tleReason}
      >
        <KV label="lat" value={fmtDeg(sat.lat_deg, "lat")} />
        <KV label="lon" value={fmtDeg(sat.lon_deg, "lon")} />
        <KV label="alt" value={`${sat.alt_km.toFixed(1)} km`} />
        <KV label="eclipse" value={sat.in_eclipse ? "yes" : "no"} />
        <KV label="period" value={`${(sat.period_seconds / 60).toFixed(1)} min`} />
        <KV label="TLE age" value={fmtRelativeSeconds(sat.tle_age_seconds)} />
        {!sat.valid && (
          <p className="col-span-2 text-[10px]" style={{ color: "var(--status-red)" }}>
            {sat.invalid_reason}
          </p>
        )}
      </StageRow>

      <StageRow
        code="WIRELESS TX"
        title={`Wireless transmission — ${s.transmission.modality}`}
        status={stageByKey(stages, "wireless_transmission").status}
        statusReason={stageByKey(stages, "wireless_transmission").reason}
      >
        <KV label="wavelength" value={`${s.transmission.wavelength_nm.toFixed(0)} nm`} />
        <KV label="transmitter" value={`${(s.transmission.transmitter_power_w / 1000).toFixed(1)} kW`} />
        <KV label="slant" value={`${(s.transmission.slant_range_m / 1000).toFixed(0)} km`} />
        <KV label="elevation" value={`${s.transmission.elevation_deg.toFixed(2)}°`} />
      </StageRow>

      <StageRow
        code="ATMOSPHERE"
        title="Atmospheric transmission"
        status={stageByKey(stages, "atmosphere").status}
        statusReason={stageByKey(stages, "atmosphere").reason}
      >
        <KV label="τ" value={atm.transmittance.toFixed(4)} />
        {atm.transmittance_low !== null &&
          atm.transmittance_high !== null &&
          atm.nominal_coverage !== null && (
            <KV
              label="τ interval"
              value={`[${atm.transmittance_low.toFixed(3)}, ${atm.transmittance_high.toFixed(3)}] @ ${(atm.nominal_coverage * 100).toFixed(0)}%`}
            />
          )}
        <KV label="visibility" value={`${atm.visibility_km.toFixed(0)} km`} />
        <KV label="cloud" value={atm.cloud_factor.toFixed(2)} />
      </StageRow>

      <StageRow
        code="UAV NETWORK"
        title={`UAV network — ${s.uavs.length} node${s.uavs.length === 1 ? "" : "s"}`}
        status={stageByKey(stages, "uav_network").status}
        statusReason={stageByKey(stages, "uav_network").reason}
      >
        {s.uavs.slice(0, 6).map((u) => (
          <KV
            key={`state-${u.uav_id}`}
            label={`uav-${u.uav_id}`}
            value={`${u.role} · ${u.battery_pct.toFixed(0)}% · ΔT ${u.thermal_headroom_c.toFixed(0)}°C`}
          />
        ))}
        {s.uavs.slice(0, 6).map((u) => (
          <KV
            key={`power-${u.uav_id}`}
            label={`uav-${u.uav_id} power`}
            value={`${formatPower(u.delivered_power_w)} · η=${(u.receiver_efficiency * 100).toFixed(1)}% · ${u.link_elevation_deg.toFixed(1)}°`}
          />
        ))}
      </StageRow>

      <StageRow
        code="GEOGRAPHY"
        title={`Ground station — ${s.ground_station.name}`}
        status={stageByKey(stages, "geographic_region").status}
        statusReason={stageByKey(stages, "geographic_region").reason}
      >
        <KV label="lat" value={fmtDeg(s.ground_station.lat_deg, "lat")} />
        <KV label="lon" value={fmtDeg(s.ground_station.lon_deg, "lon")} />
        <KV label="alt" value={`${s.ground_station.alt_m.toFixed(0)} m`} />
      </StageRow>

      <div className="mt-3 mb-2 text-[10px] font-semibold uppercase tracking-widest text-[var(--ink-tertiary)]">
        Intelligence layer
      </div>

      <StageRow
        code="TIER 1"
        title={`Interpretable decision — ${s.tier1.selected_action} (${s.tier1.decision_kind})`}
        status={stageByKey(stages, "tier1_decision").status}
        statusReason={stageByKey(stages, "tier1_decision").reason}
      >
        <KV label="score" value={s.tier1.score.toFixed(3)} />
        <KV label="confidence" value={`${(s.tier1.confidence * 100).toFixed(1)}%`} />
        <KV
          label="alternative"
          value={s.tier1.alternative_action || "—"}
        />
        <KV label="epistemic" value={s.tier1.epistemic_tag} />
      </StageRow>

      <StageRow
        code="Z3"
        title={`Formal verification — ${s.architecture.sat_verdict.toUpperCase()}`}
        status={stageByKey(stages, "z3_verification").status}
        statusReason={stageByKey(stages, "z3_verification").reason}
      >
        <KV label="verdict" value={s.architecture.sat_verdict} />
        <KV label="constraints" value={String(s.architecture.n_constraints)} />
        <KV label="ε" value={s.architecture.epsilon_bound.toExponential(3)} />
        <KV label="nodes" value={String(s.architecture.nodes)} />
        <KV label="links" value={String(s.architecture.links)} />
      </StageRow>

      <StageRow
        code="CLEAR-D"
        title={`Discovery loop — ${s.cleard.feasible_final} feasible / ${s.cleard.population_size}`}
        status={stageByKey(stages, "cleard_loop").status}
        statusReason={stageByKey(stages, "cleard_loop").reason}
      >
        <KV label="generations" value={String(s.cleard.n_generations)} />
        <KV label="feasible" value={String(s.cleard.feasible_final)} />
        <KV label="infeasible" value={String(s.cleard.infeasible_final)} />
        <KV label="conflict-prone" value={String(s.cleard.conflict_prone_features)} />
        <KV
          label="mode"
          value={s.cleard.use_conflict_directed ? "conflict-directed" : "random"}
        />
      </StageRow>

      <StageRow
        code="TIER 2"
        title="Auxiliary prediction surrogates"
        status={stageByKey(stages, "tier2_surrogates").status}
        statusReason={stageByKey(stages, "tier2_surrogates").reason}
      >
        <p className="col-span-2 text-[10px] text-[var(--ink-secondary)]">
          Tier 2 calibrated-interval rendering is a later PR.
        </p>
      </StageRow>
    </div>
  )
}
