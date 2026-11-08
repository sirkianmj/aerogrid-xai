/**
 * GroundDesigner — design and live-evaluate a ground-to-air transmitter.
 *
 * Unlike SatelliteDesigner, this panel has no separate draft state:
 * the four editable parameters (power, wavelength, aperture, min
 * elevation) apply to the mission immediately on change, and the
 * mission state displayed alongside updates via the MissionProvider's
 * existing fetch. That keeps the ground transmitter always consistent
 * with the mission it powers — the "design" is the config.
 *
 * The transmitter position is co-located with the ground station
 * (ground_lat_deg / ground_lon_deg / ground_alt_m), matching the
 * PowerLight PTROL-UAS deployment where the transmitter and ground
 * receiver share a site. See the backend _ground_to_uav_slant_range_m
 * for the geometry (haversine on ITU-R P.528 effective Earth radius,
 * 3D distance per 3GPP TR 36.777).
 */

import { TaggedOutput } from "../../components/EpistemicBadge/EpistemicBadge"
import { useMission } from "../MissionControl/missionContext"

export function GroundDesigner() {
  const { config, applyConfig, state } = useMission()

  function setNum(key: "transmitter_power_w" | "wavelength_nm" | "transmitter_aperture_m" | "transmitter_min_elevation_deg", raw: string) {
    const v = Number(raw)
    if (!Number.isFinite(v)) return
    applyConfig({ [key]: v } as Partial<typeof config>)
  }

  const live = state.status === "ok" ? state.data : null
  const totalDelivered = live ? live.uavs.reduce((sum, u) => sum + u.delivered_power_w, 0) : 0
  const elevation = live ? live.transmission.elevation_deg : 0
  const slantKm = live ? live.transmission.slant_range_m / 1000 : 0
  const transmittance = live ? live.atmosphere.transmittance : 0
  const modality = live ? live.transmission.modality : "loading"

  return (
    <div className="apple-card mb-6 p-4">
      <h3 className="mb-2 text-sm font-semibold">Ground transmitter</h3>
      <p className="mb-3 text-xs text-[var(--ink-secondary)]">
        Ground-to-air laser at the ground station position. Values apply
        to the live mission on change; the transmission metrics below
        update as you edit. Geometry uses the ITU-R P.528 effective Earth
        radius (k = 4/3) with 3GPP TR 36.777 slant-range formulation.
      </p>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1">
          <span className="text-[0.65rem] uppercase tracking-wide text-[var(--ink-tertiary)]">
            Transmitter power (W)
          </span>
          <input
            type="number"
            aria-label="Ground transmitter power watts"
            value={config.transmitter_power_w}
            onChange={(e) => setNum("transmitter_power_w", e.target.value)}
            min={1}
            step={100}
            className="rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-2 py-1 font-mono text-xs"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-[0.65rem] uppercase tracking-wide text-[var(--ink-tertiary)]">
            Wavelength (nm)
          </span>
          <input
            type="number"
            aria-label="Ground transmitter wavelength nm"
            value={config.wavelength_nm}
            onChange={(e) => setNum("wavelength_nm", e.target.value)}
            min={200}
            max={10000}
            step={1}
            className="rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-2 py-1 font-mono text-xs"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-[0.65rem] uppercase tracking-wide text-[var(--ink-tertiary)]">
            Aperture (m)
          </span>
          <input
            type="number"
            aria-label="Ground transmitter aperture metres"
            value={config.transmitter_aperture_m}
            onChange={(e) => setNum("transmitter_aperture_m", e.target.value)}
            min={0.01}
            max={10}
            step={0.01}
            className="rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-2 py-1 font-mono text-xs"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-[0.65rem] uppercase tracking-wide text-[var(--ink-tertiary)]">
            Min elevation (deg)
          </span>
          <input
            type="number"
            aria-label="Minimum elevation angle"
            value={config.transmitter_min_elevation_deg}
            onChange={(e) => setNum("transmitter_min_elevation_deg", e.target.value)}
            min={0}
            max={90}
            step={0.5}
            className="rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-2 py-1 font-mono text-xs"
          />
        </label>
      </div>

      {live && (
        <TaggedOutput tag="simulation_result" className="mt-4 rounded border border-[var(--border-hairline)] bg-[var(--bg-subtle)] p-3">
          <div className="mb-2 text-[0.7rem] uppercase tracking-wide text-[var(--ink-tertiary)]">
            Live transmission metrics
          </div>
          <div className="grid grid-cols-2 gap-2 font-mono text-xs sm:grid-cols-4">
            <div>
              <div className="text-[0.6rem] uppercase text-[var(--ink-tertiary)]">Modality</div>
              <div>{modality}</div>
            </div>
            <div>
              <div className="text-[0.6rem] uppercase text-[var(--ink-tertiary)]">Slant range</div>
              <div>{slantKm.toFixed(2)} km</div>
            </div>
            <div>
              <div className="text-[0.6rem] uppercase text-[var(--ink-tertiary)]">Elevation</div>
              <div>{elevation.toFixed(1)}°</div>
            </div>
            <div>
              <div className="text-[0.6rem] uppercase text-[var(--ink-tertiary)]">Transmittance</div>
              <div>{transmittance.toFixed(4)}</div>
            </div>
            <div className="sm:col-span-4">
              <div className="text-[0.6rem] uppercase text-[var(--ink-tertiary)]">Total delivered</div>
              <div>{totalDelivered.toFixed(3)} W</div>
            </div>
          </div>
        </TaggedOutput>
      )}

      {state.status === "error" && (
        <p className="mt-3 text-xs" style={{ color: "var(--status-red)" }}>
          Mission state error: {state.message}
        </p>
      )}
    </div>
  )
}
