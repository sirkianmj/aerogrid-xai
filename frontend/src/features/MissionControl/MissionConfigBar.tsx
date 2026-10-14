/**
 * MissionConfigBar — configure the live mission.
 *
 * Writes to the MissionProvider. Every panel that consumes mission
 * state (MissionControl, FanetGraph) re-renders when this changes.
 * Validation is local; Apply is disabled while any field is invalid.
 */

import { useState } from "react"
import { DEFAULT_CONFIG, useMission, type MissionConfig } from "./missionContext"
import { ENVIRONMENT_PRESETS } from "./environmentPresets"

type FieldErrors = {
  t_utc?: string
  visibility_km?: string
  cloud_factor?: string
  ground_lat_deg?: string
  ground_lon_deg?: string
  transmitter_power_w?: string
  n_uavs?: string
  seed?: string
}

function validate(c: MissionConfig): FieldErrors {
  const e: FieldErrors = {}
  if (c.ground_lat_deg < -90 || c.ground_lat_deg > 90) {
    e.ground_lat_deg = "latitude must be in [-90, 90]"
  }
  if (c.ground_lon_deg < -180 || c.ground_lon_deg > 180) {
    e.ground_lon_deg = "longitude must be in [-180, 180]"
  }
  if (c.transmitter_power_w <= 0) {
    e.transmitter_power_w = "power must be > 0"
  }
  if (c.n_uavs < 2 || c.n_uavs > 20) {
    e.n_uavs = "UAV count must be in [2, 20]"
  }
  if (c.seed < 0) {
    e.seed = "seed must be >= 0"
  }
  if (c.visibility_km <= 0 || c.visibility_km > 100) {
    e.visibility_km = "visibility must be in (0, 100] km"
  }
  if (c.cloud_factor < 0 || c.cloud_factor > 1) {
    e.cloud_factor = "cloud factor must be in [0, 1]"
  }
  return e
}

function num(s: string, fallback: number): number {
  const v = Number(s)
  return Number.isFinite(v) ? v : fallback
}

export function MissionConfigBar() {
  const { config, applyConfig, reset } = useMission()
  const [draft, setDraft] = useState<MissionConfig>(config)

  // The draft is initialised from the applied config on mount and only
  // changes when the user types or when Reset is clicked. Both of those
  // paths set the draft explicitly, so no effect is needed to
  // resynchronise. (An effect that ran setDraft on every config change
  // was flagged by React Compiler's set-state-in-effect rule.)

  const errors = validate(draft)
  const hasErrors = Object.keys(errors).length > 0
  const isDirty =
    draft.satellite_key !== config.satellite_key ||
    draft.ground_lat_deg !== config.ground_lat_deg ||
    draft.ground_lon_deg !== config.ground_lon_deg ||
    draft.transmitter_power_w !== config.transmitter_power_w ||
    draft.n_uavs !== config.n_uavs ||
    draft.seed !== config.seed ||
    draft.t_utc !== config.t_utc ||
    draft.visibility_km !== config.visibility_km ||
    draft.cloud_factor !== config.cloud_factor

  function set<K extends keyof MissionConfig>(key: K, value: MissionConfig[K]) {
    setDraft((prev) => ({ ...prev, [key]: value }))
  }

  return (
    <section
      aria-labelledby="mission-config-heading"
      className="mb-6 rounded border border-[var(--border-hairline)] p-3 text-sm"
      data-testid="mission-config-bar"
    >
      <div className="mb-3 flex items-baseline gap-3">
        <h2 id="mission-config-heading" className="text-sm font-medium">
          Mission configuration
        </h2>
        <span className="text-xs text-[var(--ink-tertiary)]">
          drives every panel below that reads mission state
        </span>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2">
          <span className="text-[0.65rem] uppercase tracking-wide text-[var(--ink-tertiary)]">
            Environment preset
          </span>
          <select
            aria-label="Environment preset"
            value=""
            onChange={(e) => {
              const preset = ENVIRONMENT_PRESETS.find((x) => x.id === e.target.value)
              if (preset) {
                setDraft((prev) => ({
                  ...prev,
                  visibility_km: preset.visibility_km,
                  cloud_factor: preset.cloud_factor,
                }))
              }
            }}
            className="rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-2 py-1 font-mono text-xs"
          >
            <option value="">— pick a starting point —</option>
            {ENVIRONMENT_PRESETS.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </label>
        <span className="text-[0.65rem] text-[var(--ink-tertiary)]">
          Sets visibility and cloud; both remain editable below.
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <label className="flex flex-col gap-1">
          <span className="text-[0.65rem] uppercase tracking-wide text-[var(--ink-tertiary)]">
            Mission time (UTC)
          </span>
          <input
            aria-label="Mission time UTC"
            type="datetime-local"
            value={draft.t_utc ? draft.t_utc.slice(0, 16) : ""}
            onChange={(e) => {
              const v = e.target.value
              set("t_utc", v ? `${v}:00Z` : null)
            }}
            className="rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-2 py-1 font-mono text-xs"
          />
          <span className="text-[0.6rem] text-[var(--ink-tertiary)]">
            {draft.t_utc
              ? "SGP4 accuracy degrades far from the TLE epoch."
              : "Empty: use the satellite TLE epoch."}
          </span>
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-[0.65rem] uppercase tracking-wide text-[var(--ink-tertiary)]">Satellite</span>
          <select
            aria-label="Satellite key"
            value={draft.satellite_key}
            onChange={(e) => set("satellite_key", e.target.value)}
            className="rounded border border-[var(--border-hairline)] bg-transparent px-2 py-1 font-mono text-xs"
          >
            <option value="iss">ISS</option>
            <option value="geo">GEO demo</option>
            <option value="vanguard_r3">Vanguard 1</option>
          </select>
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-[0.65rem] uppercase tracking-wide text-[var(--ink-tertiary)]">
            Ground lat (deg)
          </span>
          <input
            aria-label="Ground latitude"
            type="number"
            step="0.001"
            value={draft.ground_lat_deg}
            onChange={(e) => set("ground_lat_deg", num(e.target.value, draft.ground_lat_deg))}
            className="rounded border border-[var(--border-hairline)] bg-transparent px-2 py-1 font-mono text-xs"
          />
          {errors.ground_lat_deg && (
            <span className="text-[0.65rem]" style={{ color: "var(--status-red)" }}>
              {errors.ground_lat_deg}
            </span>
          )}
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-[0.65rem] uppercase tracking-wide text-[var(--ink-tertiary)]">
            Ground lon (deg)
          </span>
          <input
            aria-label="Ground longitude"
            type="number"
            step="0.001"
            value={draft.ground_lon_deg}
            onChange={(e) => set("ground_lon_deg", num(e.target.value, draft.ground_lon_deg))}
            className="rounded border border-[var(--border-hairline)] bg-transparent px-2 py-1 font-mono text-xs"
          />
          {errors.ground_lon_deg && (
            <span className="text-[0.65rem]" style={{ color: "var(--status-red)" }}>
              {errors.ground_lon_deg}
            </span>
          )}
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-[0.65rem] uppercase tracking-wide text-[var(--ink-tertiary)]">
            Transmitter power (W)
          </span>
          <input
            aria-label="Transmitter power watts"
            type="number"
            step="100"
            min={1}
            value={draft.transmitter_power_w}
            onChange={(e) =>
              set("transmitter_power_w", num(e.target.value, draft.transmitter_power_w))
            }
            className="rounded border border-[var(--border-hairline)] bg-transparent px-2 py-1 font-mono text-xs"
          />
          {errors.transmitter_power_w && (
            <span className="text-[0.65rem]" style={{ color: "var(--status-red)" }}>
              {errors.transmitter_power_w}
            </span>
          )}
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-[0.65rem] uppercase tracking-wide text-[var(--ink-tertiary)]">UAVs</span>
          <input
            aria-label="UAV count"
            type="number"
            step="1"
            min={2}
            max={20}
            value={draft.n_uavs}
            onChange={(e) => set("n_uavs", Math.round(num(e.target.value, draft.n_uavs)))}
            className="rounded border border-[var(--border-hairline)] bg-transparent px-2 py-1 font-mono text-xs"
          />
          {errors.n_uavs && (
            <span className="text-[0.65rem]" style={{ color: "var(--status-red)" }}>
              {errors.n_uavs}
            </span>
          )}
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-[0.65rem] uppercase tracking-wide text-[var(--ink-tertiary)]">Seed</span>
          <input
            aria-label="Seed"
            type="number"
            step="1"
            min={0}
            value={draft.seed}
            onChange={(e) => set("seed", Math.round(num(e.target.value, draft.seed)))}
            className="rounded border border-[var(--border-hairline)] bg-transparent px-2 py-1 font-mono text-xs"
          />
          {errors.seed && (
            <span className="text-[0.65rem]" style={{ color: "var(--status-red)" }}>
              {errors.seed}
            </span>
          )}
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-[0.65rem] uppercase tracking-wide text-[var(--ink-tertiary)]">
            Visibility (km)
          </span>
          <input
            aria-label="Visibility in kilometres"
            type="number"
            step="0.5"
            min={0.5}
            max={100}
            value={draft.visibility_km}
            onChange={(e) =>
              set("visibility_km", num(e.target.value, draft.visibility_km))
            }
            className="rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-2 py-1 font-mono text-xs"
          />
          {errors.visibility_km && (
            <span className="text-[0.65rem]" style={{ color: "var(--status-red)" }}>
              {errors.visibility_km}
            </span>
          )}
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-[0.65rem] uppercase tracking-wide text-[var(--ink-tertiary)]">
            Cloud cover (0-1)
          </span>
          <input
            aria-label="Cloud factor"
            type="number"
            step="0.05"
            min={0}
            max={1}
            value={draft.cloud_factor}
            onChange={(e) =>
              set("cloud_factor", num(e.target.value, draft.cloud_factor))
            }
            className="rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-2 py-1 font-mono text-xs"
          />
          {errors.cloud_factor && (
            <span className="text-[0.65rem]" style={{ color: "var(--status-red)" }}>
              {errors.cloud_factor}
            </span>
          )}
        </label>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={hasErrors || !isDirty}
          onClick={() => applyConfig(draft)}
          className="rounded border px-3 py-1 text-xs uppercase tracking-wider hover:bg-[var(--bg-subtle)] disabled:opacity-40"
          data-testid="mission-apply"
        >
          Apply
        </button>
        <button
          type="button"
          onClick={() => {
            setDraft(DEFAULT_CONFIG)
            reset()
          }}
          className="rounded border px-3 py-1 text-xs uppercase tracking-wider hover:bg-[var(--bg-subtle)]"
          data-testid="mission-reset"
        >
          Reset to defaults
        </button>
        {isDirty && !hasErrors && (
          <span className="text-xs text-[var(--ink-secondary)]" data-testid="mission-dirty">
            unsaved changes
          </span>
        )}
      </div>
    </section>
  )
}
