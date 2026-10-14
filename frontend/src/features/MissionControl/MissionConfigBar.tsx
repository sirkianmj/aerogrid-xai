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
  satellite_elements?: string
  a_km?: string
  e?: string
  i_deg?: string
  raan_deg?: string
  argp_deg?: string
  m0_deg?: string
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
  if (c.satellite_elements) {
    const el = c.satellite_elements
    if (!Number.isFinite(el.a_km) || el.a_km <= 0) {
      e.a_km = "semi-major axis must be > 0 km"
    }
    if (!Number.isFinite(el.e) || el.e < 0 || el.e >= 1) {
      e.e = "eccentricity must be in [0, 1)"
    }
    if (!Number.isFinite(el.i_deg) || el.i_deg < 0 || el.i_deg > 180) {
      e.i_deg = "inclination must be in [0, 180]"
    }
    for (const [key, val] of [
      ["raan_deg", el.raan_deg],
      ["argp_deg", el.argp_deg],
      ["m0_deg", el.m0_deg],
    ] as const) {
      if (!Number.isFinite(val) || val < 0 || val >= 360) {
        e[key] = "angle must be in [0, 360)"
      }
    }
    if (!el.epoch_utc) {
      e.satellite_elements = "epoch is required"
    }
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
    draft.cloud_factor !== config.cloud_factor ||
    draft.transmitter_aperture_m !== config.transmitter_aperture_m ||
    draft.uav_alt_m !== config.uav_alt_m ||
    draft.uav_receiver_aperture_m2 !== config.uav_receiver_aperture_m2 ||
    draft.uav_receiver_type !== config.uav_receiver_type ||
    JSON.stringify(draft.satellite_elements ?? null) !==
      JSON.stringify(config.satellite_elements ?? null)

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

      <details className="mb-3 rounded border border-[var(--border-hairline)] p-2 text-xs" open={!!draft.satellite_elements}>
        <summary className="cursor-pointer text-[0.7rem] font-medium uppercase tracking-wide text-[var(--ink-secondary)]">
          Custom orbit{draft.satellite_elements ? " — enabled" : ""}
        </summary>
        <div className="mt-3 space-y-2">
          <p className="text-[0.65rem] text-[var(--ink-tertiary)]">
            Mean Keplerian elements. When enabled, overrides the satellite
            catalogue. Leave disabled to use a catalogue TLE.
          </p>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              aria-label="Enable custom orbit"
              checked={!!draft.satellite_elements}
              onChange={(e) => {
                if (e.target.checked) {
                  const nowIso = new Date().toISOString().slice(0, 19) + "Z"
                  set("satellite_elements", {
                    epoch_utc: nowIso,
                    a_km: 6871.0,
                    e: 0.0,
                    i_deg: 51.6,
                    raan_deg: 0.0,
                    argp_deg: 0.0,
                    m0_deg: 0.0,
                  })
                } else {
                  set("satellite_elements", null)
                }
              }}
            />
            <span>Enable custom orbit</span>
          </label>
          {draft.satellite_elements && (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
              {(
                [
                  ["epoch_utc", "Epoch (UTC)", "text"],
                  ["a_km", "a (km)", "number"],
                  ["e", "e", "number"],
                  ["i_deg", "i (deg)", "number"],
                  ["raan_deg", "RAAN (deg)", "number"],
                  ["argp_deg", "argp (deg)", "number"],
                  ["m0_deg", "M0 (deg)", "number"],
                ] as const
              ).map(([key, label, kind]) => {
                const el = draft.satellite_elements!
                const err =
                  key === "epoch_utc"
                    ? errors.satellite_elements
                    : errors[key as keyof FieldErrors]
                return (
                  <label key={key} className="flex flex-col gap-1">
                    <span className="text-[0.6rem] uppercase tracking-wide text-[var(--ink-tertiary)]">
                      {label}
                    </span>
                    {kind === "text" ? (
                      <input
                        type="text"
                        aria-label={label}
                        value={el.epoch_utc}
                        onChange={(e) =>
                          set("satellite_elements", {
                            ...el,
                            epoch_utc: e.target.value,
                          })
                        }
                        className="rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-2 py-1 font-mono text-xs"
                      />
                    ) : (
                      <input
                        type="number"
                        step="any"
                        aria-label={label}
                        value={el[key as keyof typeof el] as number}
                        onChange={(e) =>
                          set("satellite_elements", {
                            ...el,
                            [key]: num(
                              e.target.value,
                              el[key as keyof typeof el] as number,
                            ),
                          })
                        }
                        className="rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-2 py-1 font-mono text-xs"
                      />
                    )}
                    {err && (
                      <span
                        className="text-[0.6rem]"
                        style={{ color: "var(--status-red)" }}
                      >
                        {err}
                      </span>
                    )}
                  </label>
                )
              })}
            </div>
          )}
        </div>
      </details>

      <details className="mb-3 rounded border border-[var(--border-hairline)] p-2 text-xs" open>
        <summary className="cursor-pointer text-[0.7rem] font-medium uppercase tracking-wide text-[var(--ink-secondary)]">
          Transmitter &amp; UAV receiver
        </summary>
        <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-[0.65rem] uppercase tracking-wide text-[var(--ink-tertiary)]">
              Transmitter aperture (m)
            </span>
            <input
              type="number"
              step="0.005"
              min={0.001}
              max={1}
              aria-label="Transmitter aperture"
              value={draft.transmitter_aperture_m}
              onChange={(e) =>
                set("transmitter_aperture_m", num(e.target.value, draft.transmitter_aperture_m))
              }
              className="rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-2 py-1 font-mono text-xs"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[0.65rem] uppercase tracking-wide text-[var(--ink-tertiary)]">
              UAV altitude (m)
            </span>
            <input
              type="number"
              step="100"
              min={10}
              max={20000}
              aria-label="UAV altitude"
              value={draft.uav_alt_m}
              onChange={(e) =>
                set("uav_alt_m", num(e.target.value, draft.uav_alt_m))
              }
              className="rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-2 py-1 font-mono text-xs"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[0.65rem] uppercase tracking-wide text-[var(--ink-tertiary)]">
              Receiver aperture (m²)
            </span>
            <input
              type="number"
              step="0.1"
              min={0.01}
              max={100}
              aria-label="Receiver aperture"
              value={draft.uav_receiver_aperture_m2}
              onChange={(e) =>
                set("uav_receiver_aperture_m2", num(e.target.value, draft.uav_receiver_aperture_m2))
              }
              className="rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-2 py-1 font-mono text-xs"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[0.65rem] uppercase tracking-wide text-[var(--ink-tertiary)]">
              Receiver type
            </span>
            <select
              aria-label="Receiver type"
              value={draft.uav_receiver_type}
              onChange={(e) =>
                set(
                  "uav_receiver_type",
                  e.target.value as MissionConfig["uav_receiver_type"],
                )
              }
              className="rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-2 py-1 font-mono text-xs"
            >
              <option value="laser_photovoltaic">laser photovoltaic (perovskite-TE)</option>
              <option value="rectenna">rectenna (RF)</option>
            </select>
          </label>
        </div>
      </details>

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

        <label
          className={`flex flex-col gap-1 ${draft.satellite_elements ? "opacity-40" : ""}`}
        >
          <span className="text-[0.65rem] uppercase tracking-wide text-[var(--ink-tertiary)]">Satellite</span>
          <select
            aria-label="Satellite key"
            disabled={!!draft.satellite_elements}
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
