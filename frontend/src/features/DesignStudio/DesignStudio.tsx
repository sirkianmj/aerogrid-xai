/**
 * DesignStudio — satellite and drone design with live evaluation.
 *
 * Two sub-panels:
 *
 *   Satellite designer: orbit elements + bus parameters, evaluated
 *     through POST /design/satellite. The verdict, delivered power,
 *     and notes are computed by the mission physics.
 *
 *   Drone designer: an add/remove list of UAV hardware. Each row is
 *     evaluated through POST /design/drone. The last action is
 *     "Use this fleet", which sets uav_hardware_list on the mission
 *     config; every panel that reads per-UAV state then reflects the
 *     designed fleet.
 *
 * No real place, country, manufacturer, or model name appears
 * anywhere. The presets are anonymous class descriptors and every
 * field they fill remains editable.
 */

import { useEffect, useState } from "react"
import { TaggedOutput } from "../../components/EpistemicBadge/EpistemicBadge"
import { useMission, type UavHardware } from "../MissionControl/missionContext"
import {
  DesignApiError,
  evaluateDrone,
  evaluateSatellite,
  fetchDesignPresets,
  type DronePreset,
  type FeasibilityReport,
  type PresetsResponse,
  type SatellitePreset,
} from "./designApi"
import { OrbitDiagram } from "./svg/OrbitDiagram"
import { SatelliteBusDiagram } from "./svg/SatelliteBusDiagram"
import { DroneTopView } from "./svg/DroneTopView"

function fmtPower(w: number): string {
  if (w >= 1.0) return `${w.toFixed(3)} W`
  if (w >= 1e-3) return `${(w * 1e3).toFixed(2)} mW`
  if (w >= 1e-6) return `${(w * 1e6).toFixed(2)} µW`
  return `${w.toExponential(2)} W`
}

export function DesignStudio() {
  const [presets, setPresets] = useState<PresetsResponse | null>(null)
  const [presetsError, setPresetsError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchDesignPresets(controller.signal)
      .then((p) => setPresets(p))
      .catch((err) => {
        if (controller.signal.aborted) return
        setPresetsError(err instanceof Error ? err.message : String(err))
      })
    return () => controller.abort()
  }, [])

  return (
    <section aria-labelledby="design-studio-heading" className="mb-10">
      <h2 id="design-studio-heading" className="mb-1 text-lg font-semibold">
        Design Studio
      </h2>
      <p className="mb-4 text-sm text-[var(--ink-secondary)]">
        Design a satellite or a fleet of drones. Every evaluation runs
        through the mission physics; no value is fabricated. Presets are
        anonymous starting points, all fields editable.
      </p>

      {presetsError && (
        <p className="text-sm" style={{ color: "var(--status-red)" }}>
          Could not load presets: {presetsError}
        </p>
      )}

      {presets && <SatelliteDesigner presets={presets.satellites} />}
      {presets && <DroneDesigner presets={presets.drones} />}
    </section>
  )
}

// --------------------------------------------------------------------------
// Satellite designer
// --------------------------------------------------------------------------

type SatFields = {
  a_km: number
  e: number
  i_deg: number
  raan_deg: number
  argp_deg: number
  m0_deg: number
  epoch_utc: string
  transmitter_power_w: number
  wavelength_nm: number
  transmitter_aperture_m: number
}

function SatelliteDesigner({ presets }: { presets: SatellitePreset[] }) {
  const { config, applyConfig } = useMission()
  const [fields, setFields] = useState<SatFields>(() => ({
    a_km: 6771.0,
    e: 0,
    i_deg: 51.6,
    raan_deg: 0,
    argp_deg: 0,
    m0_deg: 0,
    epoch_utc: new Date().toISOString().slice(0, 19) + "Z",
    transmitter_power_w: config.transmitter_power_w,
    wavelength_nm: 1064.0,
    transmitter_aperture_m: config.transmitter_aperture_m,
  }))
  const [report, setReport] = useState<FeasibilityReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  function applyPreset(p: SatellitePreset) {
    setFields({
      a_km: p.a_km,
      e: p.e,
      i_deg: p.i_deg,
      raan_deg: p.raan_deg,
      argp_deg: p.argp_deg,
      m0_deg: p.m0_deg,
      epoch_utc: new Date().toISOString().slice(0, 19) + "Z",
      transmitter_power_w: p.transmitter_power_w,
      wavelength_nm: p.wavelength_nm,
      transmitter_aperture_m: p.transmitter_aperture_m,
    })
    setReport(null)
    setError(null)
  }

  async function evaluate() {
    setLoading(true)
    setError(null)
    try {
      const r = await evaluateSatellite({
        ...fields,
        ground_lat_deg: config.ground_lat_deg,
        ground_lon_deg: config.ground_lon_deg,
        n_uavs: config.n_uavs,
        uav_alt_m: config.uav_alt_m,
        uav_receiver_aperture_m2: config.uav_receiver_aperture_m2,
        uav_receiver_type: config.uav_receiver_type,
        visibility_km: config.visibility_km,
        cloud_factor: config.cloud_factor,
      })
      setReport(r)
    } catch (err) {
      if (err instanceof DesignApiError) setError(err.detail)
      else if (err instanceof Error) setError(err.message)
      else setError(String(err))
    } finally {
      setLoading(false)
    }
  }

  function useThisSatellite() {
    applyConfig({
      satellite_elements: {
        epoch_utc: fields.epoch_utc,
        a_km: fields.a_km,
        e: fields.e,
        i_deg: fields.i_deg,
        raan_deg: fields.raan_deg,
        argp_deg: fields.argp_deg,
        m0_deg: fields.m0_deg,
      },
      transmitter_power_w: fields.transmitter_power_w,
      wavelength_nm: fields.wavelength_nm,
      transmitter_aperture_m: fields.transmitter_aperture_m,
    })
  }

  return (
    <div className="apple-card p-4 mb-6">
      <h3 className="mb-2 text-sm font-semibold">Satellite designer</h3>
      <div className="grid grid-cols-1 lg:grid-cols-[2fr_3fr] gap-4">
        <div className="space-y-3">
          <OrbitDiagram
            a_km={fields.a_km}
            e={fields.e}
            onChange={(patch) => setFields((f) => ({ ...f, ...patch }))}
          />
          <SatelliteBusDiagram
            transmitter_power_w={fields.transmitter_power_w}
            transmitter_aperture_m={fields.transmitter_aperture_m}
            onChange={(patch) => setFields((f) => ({ ...f, ...patch }))}
          />
          <p className="text-[0.65rem] text-[var(--ink-tertiary)]">
            Drag the periapsis or apoapsis marker to change the orbit;
            drag the aperture edge to widen or narrow the beam. Numbers
            on the right stay in sync.
          </p>
        </div>

        <div>
          <div className="mb-3 flex flex-wrap items-center gap-3 text-xs">
            <label className="flex items-center gap-2">
              <span className="text-[var(--ink-tertiary)]">preset</span>
              <select
                aria-label="Satellite preset"
                onChange={(e) => {
                  const p = presets.find((x) => x.id === e.target.value)
                  if (p) applyPreset(p)
                }}
                className="rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-2 py-1 font-mono text-xs"
              >
                <option value="">— pick a starting point —</option>
                {presets.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.id} · {p.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {(
              [
                ["a_km", "a (km)"],
                ["e", "e"],
                ["i_deg", "i (deg)"],
                ["raan_deg", "RAAN (deg)"],
                ["argp_deg", "argp (deg)"],
                ["m0_deg", "M0 (deg)"],
                ["transmitter_power_w", "P_tx (W)"],
                ["wavelength_nm", "λ (nm)"],
                ["transmitter_aperture_m", "aperture (m)"],
              ] as const
            ).map(([key, label]) => (
              <label key={key} className="flex flex-col gap-1">
                <span className="text-[0.6rem] uppercase tracking-wide text-[var(--ink-tertiary)]">
                  {label}
                </span>
                <input
                  type="number"
                  step="any"
                  aria-label={label}
                  value={fields[key]}
                  onChange={(e) =>
                    setFields((f) => ({ ...f, [key]: Number(e.target.value) || 0 }))
                  }
                  className="rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-2 py-1 font-mono text-xs"
                />
              </label>
            ))}
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={evaluate}
              disabled={loading}
              className="rounded border border-[var(--border-hairline)] px-3 py-1 text-xs uppercase tracking-wider hover:bg-[var(--bg-subtle)] disabled:opacity-50"
            >
              {loading ? "Evaluating..." : "Evaluate design"}
            </button>
            <button
              type="button"
              onClick={useThisSatellite}
              className="rounded border border-[var(--border-hairline)] px-3 py-1 text-xs uppercase tracking-wider hover:bg-[var(--bg-subtle)]"
            >
              Use this satellite
            </button>
          </div>

          {error && (
            <p className="mt-3 text-xs" style={{ color: "var(--status-red)" }}>
              Error: {error}
            </p>
          )}
          {report && <ReportCard report={report} />}
        </div>
      </div>
    </div>
  )
}

// --------------------------------------------------------------------------
// Drone designer
// --------------------------------------------------------------------------

type DroneDraft = UavHardware & { _id: string }

function normalizeAirframe(s: string): "fixed_wing" | "multirotor" {
  return s === "multirotor" ? "multirotor" : "fixed_wing"
}

function droneFromPreset(p: DronePreset): DroneDraft {
  return {
    _id: `d-${Math.random().toString(36).slice(2, 9)}`,
    receiver_aperture_m2: p.receiver_aperture_m2,
    receiver_type: p.receiver_type === "rectenna" ? "rectenna" : "laser_photovoltaic",
    battery_efficiency: p.battery_efficiency,
    mass_kg: p.mass_kg,
    wingspan_m: p.wingspan_m,
    battery_wh: p.battery_wh,
    thermal_limit_c: p.thermal_limit_c,
    airframe: normalizeAirframe(p.airframe),
  }
}

function defaultDrone(): DroneDraft {
  return {
    _id: `d-${Math.random().toString(36).slice(2, 9)}`,
    receiver_aperture_m2: 0.5,
    receiver_type: "laser_photovoltaic",
    battery_efficiency: 0.92,
    mass_kg: 5,
    wingspan_m: 2,
    battery_wh: 100,
    thermal_limit_c: 80,
    airframe: "fixed_wing",
  }
}

function DroneDesigner({ presets }: { presets: DronePreset[] }) {
  const { config, applyConfig } = useMission()
  const [rows, setRows] = useState<DroneDraft[]>(() => [defaultDrone()])
  const [reports, setReports] = useState<Record<string, FeasibilityReport>>({})
  const [selectedId, setSelectedId] = useState<string | null>(null)

  function updateRow(id: string, patch: Partial<DroneDraft>) {
    setRows((rs) => rs.map((r) => (r._id === id ? { ...r, ...patch } : r)))
  }

  function addRow() {
    setRows((rs) => [...rs, defaultDrone()])
  }

  function removeRow(id: string) {
    setRows((rs) => rs.filter((r) => r._id !== id))
    setReports((r) => {
      const copy = { ...r }
      delete copy[id]
      return copy
    })
  }

  async function evaluateRow(row: DroneDraft) {
    try {
      const r = await evaluateDrone({
        receiver_aperture_m2: row.receiver_aperture_m2,
        receiver_type: row.receiver_type,
        battery_efficiency: row.battery_efficiency,
        mass_kg: row.mass_kg,
        wingspan_m: row.wingspan_m,
        battery_wh: row.battery_wh,
        thermal_limit_c: row.thermal_limit_c,
        airframe: row.airframe,
        satellite_key: config.satellite_key,
        ground_lat_deg: config.ground_lat_deg,
        ground_lon_deg: config.ground_lon_deg,
        uav_alt_m: config.uav_alt_m,
        transmitter_power_w: config.transmitter_power_w,
        wavelength_nm: 1064.0,
        transmitter_aperture_m: config.transmitter_aperture_m,
        visibility_km: config.visibility_km,
        cloud_factor: config.cloud_factor,
      })
      setReports((prev) => ({ ...prev, [row._id]: r }))
    } catch (err) {
      setReports((prev) => ({
        ...prev,
        [row._id]: {
          epistemic_tag: "simulation_result",
          verdict: "infeasible",
          delivered_power_w: 0,
          notes: [err instanceof Error ? err.message : String(err)],
          metrics: {},
        },
      }))
    }
  }

  function useThisFleet() {
    applyConfig({
      uav_hardware_list: rows.map((r) => ({
        receiver_aperture_m2: r.receiver_aperture_m2,
        receiver_type: r.receiver_type,
        battery_efficiency: r.battery_efficiency,
        mass_kg: r.mass_kg,
        wingspan_m: r.wingspan_m,
        battery_wh: r.battery_wh,
        thermal_limit_c: r.thermal_limit_c,
        airframe: r.airframe,
      })),
    })
  }

  function clearFleet() {
    applyConfig({ uav_hardware_list: null })
  }

  return (
    <div className="apple-card p-4">
      <h3 className="mb-2 text-sm font-semibold">Drone designer</h3>
      <p className="mb-3 text-xs text-[var(--ink-secondary)]">
        Add one row per drone. Each row is evaluated against the current
        mission geometry; press "Use this fleet" to make the mission use
        these drones. Drag the wingtip and aperture markers on the
        diagram to change the selected drone.
      </p>

      {rows.length > 0 &&
        (() => {
          const row = rows.find((r) => r._id === selectedId) ?? rows[0]!
          const rowIndex = rows.indexOf(row)
          return (
            <div className="mb-4 rounded border border-[var(--border-hairline)] bg-[var(--bg-subtle)] p-3">
              <div className="mb-2 flex items-baseline justify-between text-[0.7rem]">
                <span className="font-mono text-[var(--ink-secondary)]">
                  editing row {rowIndex + 1}
                </span>
                <span className="text-[var(--ink-tertiary)]">
                  drag wingtips · drag aperture edge
                </span>
              </div>
              <DroneTopView
                wingspan_m={row.wingspan_m}
                receiver_aperture_m2={row.receiver_aperture_m2}
                airframe={row.airframe}
                onChange={(patch) => updateRow(row._id, patch)}
              />
            </div>
          )
        })()}

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-left text-[var(--ink-tertiary)]">
            <tr>
              <th className="py-1 font-normal">preset</th>
              <th className="py-1 font-normal">mass (kg)</th>
              <th className="py-1 font-normal">span (m)</th>
              <th className="py-1 font-normal">Wh</th>
              <th className="py-1 font-normal">aperture (m²)</th>
              <th className="py-1 font-normal">type</th>
              <th className="py-1 font-normal">T_max (°C)</th>
              <th className="py-1 font-normal">airframe</th>
              <th className="py-1 font-normal">verdict</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const rpt = reports[row._id]
              return (
                <tr
                  key={row._id}
                  className={
                    "border-t border-[var(--border-hairline)] cursor-pointer " +
                    (row._id === (selectedId ?? rows[0]?._id)
                      ? "bg-[var(--bg-subtle)]"
                      : "")
                  }
                  onClick={() => setSelectedId(row._id)}
                >
                  <td className="py-1">
                    <select
                      aria-label="Drone preset"
                      value=""
                      onChange={(e) => {
                        const p = presets.find((x) => x.id === e.target.value)
                        if (p) {
                          const d = droneFromPreset(p)
                          updateRow(row._id, d)
                        }
                      }}
                      className="rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-1 py-0.5 font-mono"
                    >
                      <option value="">—</option>
                      {presets.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.id}
                        </option>
                      ))}
                    </select>
                  </td>
                  {(
                    [
                      "mass_kg",
                      "wingspan_m",
                      "battery_wh",
                      "receiver_aperture_m2",
                    ] as const
                  ).map((key) => (
                    <td key={key} className="py-1">
                      <input
                        type="number"
                        step="any"
                        aria-label={key}
                        value={row[key]}
                        onChange={(e) =>
                          updateRow(row._id, { [key]: Number(e.target.value) || 0 })
                        }
                        className="w-20 rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-1 py-0.5 font-mono"
                      />
                    </td>
                  ))}
                  <td className="py-1">
                    <select
                      aria-label="receiver_type"
                      value={row.receiver_type}
                      onChange={(e) =>
                        updateRow(row._id, {
                          receiver_type: e.target.value as UavHardware["receiver_type"],
                        })
                      }
                      className="rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-1 py-0.5 font-mono"
                    >
                      <option value="laser_photovoltaic">laser PV</option>
                      <option value="rectenna">rectenna</option>
                    </select>
                  </td>
                  <td className="py-1">
                    <input
                      type="number"
                      step="any"
                      aria-label="thermal_limit_c"
                      value={row.thermal_limit_c}
                      onChange={(e) =>
                        updateRow(row._id, {
                          thermal_limit_c: Number(e.target.value) || 0,
                        })
                      }
                      className="w-16 rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-1 py-0.5 font-mono"
                    />
                  </td>
                  <td className="py-1">
                    <select
                      aria-label="airframe"
                      value={row.airframe}
                      onChange={(e) =>
                        updateRow(row._id, {
                          airframe: normalizeAirframe(e.target.value),
                        })
                      }
                      className="rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-1 py-0.5 font-mono"
                    >
                      <option value="fixed_wing">fixed-wing</option>
                      <option value="multirotor">multirotor</option>
                    </select>
                  </td>
                  <td className="py-1">
                    {rpt ? (
                      <span
                        style={{
                          color:
                            rpt.verdict === "feasible"
                              ? "var(--status-green)"
                              : "var(--status-red)",
                        }}
                      >
                        {rpt.verdict}
                        {rpt.verdict === "feasible" && (
                          <> · {fmtPower(rpt.delivered_power_w)}</>
                        )}
                      </span>
                    ) : (
                      <span className="text-[var(--ink-tertiary)]">—</span>
                    )}
                  </td>
                  <td className="py-1">
                    <div className="flex gap-1">
                      <button
                        type="button"
                        onClick={() => evaluateRow(row)}
                        className="rounded border border-[var(--border-hairline)] px-1.5 py-0.5 text-[0.65rem] uppercase tracking-wider hover:bg-[var(--bg-subtle)]"
                      >
                        eval
                      </button>
                      <button
                        type="button"
                        onClick={() => removeRow(row._id)}
                        className="rounded border border-[var(--border-hairline)] px-1.5 py-0.5 text-[0.65rem] uppercase tracking-wider hover:bg-[var(--bg-subtle)]"
                      >
                        ×
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={addRow}
          className="rounded border border-[var(--border-hairline)] px-3 py-1 text-xs uppercase tracking-wider hover:bg-[var(--bg-subtle)]"
        >
          + Add drone
        </button>
        <button
          type="button"
          onClick={useThisFleet}
          className="rounded border border-[var(--border-hairline)] px-3 py-1 text-xs uppercase tracking-wider hover:bg-[var(--bg-subtle)]"
          data-testid="use-fleet"
        >
          Use this fleet
        </button>
        <button
          type="button"
          onClick={clearFleet}
          className="rounded border border-[var(--border-hairline)] px-3 py-1 text-xs uppercase tracking-wider hover:bg-[var(--bg-subtle)]"
        >
          Clear fleet
        </button>
      </div>

      {config.uav_hardware_list && (
        <p className="mt-3 text-xs" style={{ color: "var(--status-green)" }}>
          mission is using {config.uav_hardware_list.length} designed drone
          {config.uav_hardware_list.length === 1 ? "" : "s"}
        </p>
      )}
    </div>
  )
}

// --------------------------------------------------------------------------
// Shared report card
// --------------------------------------------------------------------------

function ReportCard({ report }: { report: FeasibilityReport }) {
  return (
    <TaggedOutput tag="simulation_result" className="mt-3 apple-card p-3">
      <div className="mb-2 flex flex-wrap items-baseline gap-3 text-xs">
        <span
          className="font-mono font-semibold uppercase tracking-wider"
          style={{
            color:
              report.verdict === "feasible"
                ? "var(--status-green)"
                : "var(--status-red)",
          }}
        >
          {report.verdict}
        </span>
        <span className="text-[var(--ink-secondary)]">
          delivered {fmtPower(report.delivered_power_w)}
        </span>
      </div>
      {report.notes.length > 0 && (
        <ul className="m-0 mb-2 list-disc pl-5 text-xs text-[var(--ink-secondary)]">
          {report.notes.map((n, i) => (
            <li key={i}>{n}</li>
          ))}
        </ul>
      )}
      <table className="w-full text-xs">
        <tbody>
          {Object.entries(report.metrics).map(([k, v]) => (
            <tr key={k}>
              <td className="py-0.5 font-mono text-[var(--ink-tertiary)]">{k}</td>
              <td className="py-0.5 text-right font-mono">
                {typeof v === "number" ? v.toExponential(3) : String(v)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </TaggedOutput>
  )
}
