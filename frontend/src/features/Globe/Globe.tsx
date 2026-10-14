/**
 * Globe — Section 7 orbital-mechanics panel with time control.
 *
 * Fetches the satellite catalog, one satellite's track over a window
 * centered on its TLE epoch, and exposes a time scrubber, satellite
 * picker, play/pause, and speed selector. The playhead advances over
 * the pre-computed track points; no re-fetch happens during playback.
 *
 * Epistemic tagging
 * -----------------
 * The rendered track is a model output: SGP4/SDP4 propagation of a
 * TLE by the backend. Section 21 category: simulation_result. The
 * panel is wrapped in a TaggedOutput with that tag.
 */

import { useCallback, useEffect, useMemo, useState } from "react"
import { Canvas } from "@react-three/fiber"
import { OrbitControls } from "@react-three/drei"
import { TaggedOutput } from "../../components/EpistemicBadge/EpistemicBadge"
import { GlobeControls } from "./GlobeControls"
import {
  fetchTrack,
  listSatellites,
  OrbitalApiError,
  type SatelliteInfo,
  type TrackResponse,
} from "./orbitalApi"
import { GlobeScene, type GroundMarker } from "./GlobeScene"
import { useMission } from "../MissionControl/missionContext"

type PanelState =
  | { status: "loading" }
  | {
      status: "ok"
      catalog: SatelliteInfo[]
      selected: string
      track: TrackResponse
    }
  | { status: "error"; message: string; status_code?: number }

/**
 * Two-hour window centered on the satellite's own TLE epoch. SGP4 is
 * only meaningful near the epoch, so the window is always epoch-
 * centered regardless of which satellite is selected.
 */
function windowFor(sat: SatelliteInfo): { t0: string; t1: string } {
  const epoch = new Date(sat.epoch_utc)
  const t1 = new Date(epoch.getTime() + 2 * 60 * 60 * 1000)
  return { t0: epoch.toISOString(), t1: t1.toISOString() }
}

export function Globe() {
  const { config, applyConfig } = useMission()
  const [state, setState] = useState<PanelState>({ status: "loading" })
  const [playheadIndex, setPlayheadIndex] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [speed, setSpeed] = useState<number>(4)

  const loadTrack = useCallback(
    async (satellite: SatelliteInfo, signal: AbortSignal) => {
      const { t0, t1 } = windowFor(satellite)
      return fetchTrack({
        satellite: satellite.key,
        tStartIso: t0,
        tEndIso: t1,
        stepSeconds: 30,
        signal,
      })
    },
    [],
  )

  // Mount: fetch the catalog once, then the default satellite's track.
  useEffect(() => {
    const controller = new AbortController()
    ;(async () => {
      try {
        const catalog = await listSatellites(controller.signal)
        if (controller.signal.aborted) return
        const selected = catalog.some((s) => s.key === config.satellite_key)
          ? config.satellite_key
          : (catalog[0]?.key ?? "")
        if (!selected) {
          setState({ status: "error", message: "no satellites in catalog" })
          return
        }
        const sat = catalog.find((s) => s.key === selected)
        if (!sat) {
          setState({ status: "error", message: "selected satellite not in catalog" })
          return
        }
        const track = await loadTrack(sat, controller.signal)
        if (controller.signal.aborted) return
        setState({ status: "ok", catalog, selected, track })
        setPlayheadIndex(0)
      } catch (err) {
        if (controller.signal.aborted) return
        if (err instanceof OrbitalApiError) {
          setState({ status: "error", message: err.detail, status_code: err.status })
        } else if (err instanceof Error) {
          setState({ status: "error", message: err.message })
        } else {
          setState({ status: "error", message: String(err) })
        }
      }
    })()
    return () => controller.abort()
  }, [config.satellite_key, loadTrack])

  const selectSatellite = useCallback(
    (key: string) => {
      setIsPlaying(false)
      applyConfig({ satellite_key: key })
    },
    [applyConfig],
  )

  const onPlaceGround = useCallback(
    (lat_deg: number, lon_deg: number) => {
      applyConfig({ ground_lat_deg: lat_deg, ground_lon_deg: lon_deg })
    },
    [applyConfig],
  )

  const grounds: GroundMarker[] = useMemo(
    () => [
      {
        name: "Configured site",
        lat_deg: config.ground_lat_deg,
        lon_deg: config.ground_lon_deg,
      },
    ],
    [config.ground_lat_deg, config.ground_lon_deg],
  )

  // Play loop: advance the playhead at `speed` samples per second.
  // Loops to the start after the last point so the animation is
  // continuous. No re-fetch occurs; the track is fully in memory.
  useEffect(() => {
    if (!isPlaying) return
    if (state.status !== "ok") return
    const n = state.track.points.length
    if (n < 2) return
    const intervalMs = Math.max(16, Math.floor(1000 / speed))
    const handle = setInterval(() => {
      setPlayheadIndex((i) => (i + 1) % n)
    }, intervalMs)
    return () => clearInterval(handle)
  }, [isPlaying, speed, state])

  const satellite = useMemo(() => {
    if (state.status !== "ok") return null
    return state.catalog.find((s) => s.key === state.selected) ?? null
  }, [state])

  const currentPoint = useMemo(() => {
    if (state.status !== "ok") return null
    const points = state.track.points
    if (points.length === 0) return null
    return points[Math.min(playheadIndex, points.length - 1)] ?? null
  }, [state, playheadIndex])

  return (
    <section aria-labelledby="globe-heading" className="mb-10">
      <h2 id="globe-heading" className="mb-1 text-lg font-semibold">
        Globe (Section 7)
      </h2>
      <p className="mb-4 text-sm text-[var(--ink-secondary)]">
        SGP4/SDP4 propagation of the packaged TLE. Positions are computed
        at request time by the backend; the scene renders what the backend
        returned.
      </p>

      {state.status === "loading" && <p className="text-[var(--ink-secondary)]">Loading orbital data...</p>}

      {state.status === "error" && (
        <p className="text-sm" style={{ color: "var(--status-red)" }}>
          Error{state.status_code ? ` (${state.status_code})` : ""}: {state.message}
        </p>
      )}

      {state.status === "ok" && satellite && (
        <TaggedOutput tag="simulation_result" className="apple-card p-4">
          <header className="mb-3 flex flex-wrap items-baseline gap-3">
            <span className="text-base font-medium">{satellite.name}</span>
            <span className="text-xs uppercase tracking-wide text-[var(--ink-tertiary)]">
              {satellite.orbit_class}
            </span>
            <span className="ml-auto font-mono text-xs text-[var(--ink-tertiary)]">
              {state.track.n_points} points @ {state.track.step_seconds}s
            </span>
          </header>

          <GlobeControls
            catalog={state.catalog}
            selected={state.selected}
            onSelect={selectSatellite}
            playheadIndex={playheadIndex}
            totalPoints={state.track.points.length}
            onScrub={setPlayheadIndex}
            isPlaying={isPlaying}
            onTogglePlay={() => setIsPlaying((v) => !v)}
            speed={speed}
            onSpeedChange={setSpeed}
            onReset={() => {
              setIsPlaying(false)
              setPlayheadIndex(0)
            }}
            currentTimeIso={currentPoint?.time_utc ?? state.track.t_start}
            disabled={false}
          />

          <div className="mb-4 rounded" style={{ height: 420 }}>
            <Canvas
              camera={{ position: [0, 0, 3], fov: 45 }}
              style={{ background: "var(--bg-canvas)" }}
            >
              <OrbitControls enablePan={false} minDistance={1.5} maxDistance={6} />
              <GlobeScene
                track={state.track.points}
                grounds={grounds}
                currentPoint={currentPoint}
                onPlaceGround={onPlaceGround}
              />
            </Canvas>
          </div>

          {currentPoint && (
            <div className="mb-3 grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
              <Readout label="time_utc" value={currentPoint.time_utc} />
              <Readout label="lat_deg" value={currentPoint.lat_deg.toFixed(3)} />
              <Readout label="lon_deg" value={currentPoint.lon_deg.toFixed(3)} />
              <Readout label="alt_m" value={currentPoint.alt_m.toFixed(0)} />
            </div>
          )}

          <div className="mb-3 flex flex-wrap gap-3 text-xs text-[var(--ink-secondary)]">
            <span>
              epoch: <span className="font-mono">{satellite.epoch_utc}</span>
            </span>
            <span>
              period: <span className="font-mono">{satellite.period_seconds.toFixed(0)} s</span>
            </span>
            <span>
              t_start: <span className="font-mono">{state.track.t_start}</span>
            </span>
            <span>
              t_end: <span className="font-mono">{state.track.t_end}</span>
            </span>
          </div>

          <details>
            <summary className="cursor-pointer text-sm font-medium">
              Track samples ({state.track.points.length})
            </summary>
            <div className="mt-2 max-h-64 overflow-auto">
              <table className="w-full text-xs">
                <thead className="text-left text-[var(--ink-tertiary)]">
                  <tr>
                    <th className="py-1 font-normal">time_utc</th>
                    <th className="py-1 font-normal">lat_deg</th>
                    <th className="py-1 font-normal">lon_deg</th>
                    <th className="py-1 font-normal">alt_m</th>
                    <th className="py-1 font-normal">speed_km_s</th>
                    <th className="py-1 font-normal">in_eclipse</th>
                  </tr>
                </thead>
                <tbody>
                  {state.track.points.map((p, i) => (
                    <tr
                      key={p.time_utc}
                      className={
                        "border-t border-current/10" +
                        (i === playheadIndex ? " bg-current/[0.06]" : "")
                      }
                    >
                      <td className="py-1 font-mono">{p.time_utc}</td>
                      <td className="py-1 font-mono">{p.lat_deg.toFixed(3)}</td>
                      <td className="py-1 font-mono">{p.lon_deg.toFixed(3)}</td>
                      <td className="py-1 font-mono">{p.alt_m.toFixed(0)}</td>
                      <td className="py-1 font-mono">{p.speed_km_s.toFixed(3)}</td>
                      <td className="py-1 font-mono">{p.in_eclipse ? "yes" : "no"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>

          <footer className="mt-4 border-t border-[var(--border-hairline)] pt-3 font-mono text-xs text-[var(--ink-tertiary)]">
            artefact: orbital_track (SGP4/SDP4)
          </footer>
        </TaggedOutput>
      )}
    </section>
  )
}

function Readout({ label, value }: { label: string; value: string }) {
  return (
    <div className="apple-subcard px-3 py-2">
      <div className="text-[0.65rem] uppercase tracking-wide text-[var(--ink-tertiary)]">{label}</div>
      <div className="font-mono text-xs">{value}</div>
    </div>
  )
}
