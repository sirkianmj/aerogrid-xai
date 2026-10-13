/**
 * Globe — Section 7 orbital-mechanics panel.
 *
 * Fetches the satellite catalog and one satellite's track on demand,
 * renders the track in a Three.js scene (GlobeScene), and displays the
 * track metadata in a table. The panel is deliberately minimal: it
 * shows what the backend computed and does not interpolate or
 * extrapolate.
 *
 * Epistemic tagging
 * -----------------
 * The rendered track is a model output: SGP4/SDP4 propagation of a TLE
 * by the backend. Section 21 category: simulation_result. The panel is
 * wrapped in a TaggedOutput with that tag.
 */

import { useEffect, useMemo, useState } from "react"
import { Canvas } from "@react-three/fiber"
import { OrbitControls } from "@react-three/drei"
import { TaggedOutput } from "../../components/EpistemicBadge/EpistemicBadge"
import {
  fetchTrack,
  listSatellites,
  OrbitalApiError,
  type SatelliteInfo,
  type TrackResponse,
} from "./orbitalApi"
import { GlobeScene, type GroundMarker } from "./GlobeScene"

// The demo TLEs shipped in the repository. Newest epochs first so the
// default selection propagates near-epoch positions.
const DEFAULT_SATELLITE = "vanguard_r3"

// Fixed demo window centered on the Vanguard 1 TLE epoch (2000-06-28).
// SGP4 is only meaningful within a few weeks of the TLE epoch.
const DEFAULT_T0 = "2000-06-28T17:00:00Z"
const DEFAULT_T1 = "2000-06-28T19:00:00Z"

// A ground site for the demo. Chosen to be in view for a low-inclination
// orbit for part of the window.
const DEMO_GROUNDS: GroundMarker[] = [
  { name: "GS-Alpha", lat_deg: 30.0, lon_deg: -60.0 },
  { name: "GS-Beta", lat_deg: -20.0, lon_deg: 120.0 },
]

type PanelState =
  | { status: "loading" }
  | {
      status: "ok"
      catalog: SatelliteInfo[]
      selected: string
      track: TrackResponse
    }
  | { status: "error"; message: string; status_code?: number }

export function Globe() {
  const [state, setState] = useState<PanelState>({ status: "loading" })

  useEffect(() => {
    const controller = new AbortController()
    ;(async () => {
      try {
        const catalog = await listSatellites(controller.signal)
        if (controller.signal.aborted) return
        const selected = catalog.some((s) => s.key === DEFAULT_SATELLITE)
          ? DEFAULT_SATELLITE
          : (catalog[0]?.key ?? "")
        if (!selected) {
          setState({ status: "error", message: "no satellites in catalog" })
          return
        }
        const track = await fetchTrack({
          satellite: selected,
          tStartIso: DEFAULT_T0,
          tEndIso: DEFAULT_T1,
          stepSeconds: 30,
          signal: controller.signal,
        })
        if (controller.signal.aborted) return
        setState({ status: "ok", catalog, selected, track })
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
  }, [])

  const satellite = useMemo(() => {
    if (state.status !== "ok") return null
    return state.catalog.find((s) => s.key === state.selected) ?? null
  }, [state])

  return (
    <section aria-labelledby="globe-heading" className="mb-10">
      <h2 id="globe-heading" className="mb-1 text-lg font-medium">
        Globe (Section 7)
      </h2>
      <p className="mb-4 text-sm opacity-70">
        SGP4/SDP4 propagation of the packaged TLE. Positions are computed
        at request time by the backend; the scene renders what the backend
        returned.
      </p>

      {state.status === "loading" && <p className="opacity-70">Loading orbital data...</p>}

      {state.status === "error" && (
        <p className="text-sm" style={{ color: "var(--color-accent-amber)" }}>
          Error{state.status_code ? ` (${state.status_code})` : ""}: {state.message}
        </p>
      )}

      {state.status === "ok" && satellite && (
        <TaggedOutput tag="simulation_result" className="rounded border border-current/15 p-4">
          <header className="mb-3 flex flex-wrap items-baseline gap-3">
            <span className="text-base font-medium">{satellite.name}</span>
            <span className="text-xs uppercase tracking-wide opacity-60">
              {satellite.orbit_class}
            </span>
            <span className="ml-auto font-mono text-xs opacity-70">
              {state.track.n_points} points @ {state.track.step_seconds}s
            </span>
          </header>

          <div className="mb-4 rounded" style={{ height: 420 }}>
            <Canvas
              camera={{ position: [0, 0, 3], fov: 45 }}
              style={{ background: "var(--color-bg)" }}
            >
              <OrbitControls enablePan={false} minDistance={1.5} maxDistance={6} />
              <GlobeScene track={state.track.points} grounds={DEMO_GROUNDS} />
            </Canvas>
          </div>

          <div className="mb-3 flex flex-wrap gap-3 text-xs opacity-70">
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
                <thead className="text-left opacity-70">
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
                  {state.track.points.map((p) => (
                    <tr key={p.time_utc} className="border-t border-current/10">
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

          <footer className="mt-4 border-t border-current/10 pt-3 font-mono text-xs opacity-60">
            artefact: orbital_track (SGP4/SDP4)
          </footer>
        </TaggedOutput>
      )}
    </section>
  )
}
