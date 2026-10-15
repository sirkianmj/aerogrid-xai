/**
 * Telemetry — Section 7 / Section 24 real-time telemetry dashboard.
 *
 * Connects to the telemetry WebSocket, displays the latest snapshot,
 * tracks the ring buffer, and shows a compact history of recent
 * orbital positions. Connection is user-triggered: the panel does not
 * connect until the button is pressed, so a page with several panels
 * does not open several sockets on load.
 *
 * Epistemic tagging
 * -----------------
 * Every value displayed is a snapshot pushed by the backend, which is
 * a model output. Section 21 category: simulation_result. The whole
 * content is wrapped in a TaggedOutput with that tag.
 *
 * WebSocket base URL
 * ------------------
 * In development the Vite dev server does not proxy WebSocket traffic
 * (only the HTTP /api prefix is proxied), so the panel connects
 * directly to the backend. The base URL is read from
 * import.meta.env.VITE_TELEMETRY_WS_BASE, defaulting to
 * ws://127.0.0.1:8000. A production deployment behind a reverse proxy
 * would set this environment variable to its public WebSocket origin.
 */

import { useEffect, useMemo, useRef, useState } from "react"
import { TaggedOutput } from "../../components/EpistemicBadge/EpistemicBadge"
import {
  TelemetrySocket,
  buildTelemetryUrl,
  type ConnectionStatus,
  type TelemetrySnapshot,
  type WebSocketFactory,
} from "./telemetrySocket"

const DEFAULT_SATELLITE = "vanguard_r3"
const DEFAULT_INTERVAL_SECONDS = 1.0
const HISTORY_PREVIEW_ROWS = 20

function defaultWebSocketBase(): string {
  // import.meta.env is a Vite feature; jsdom in tests does not define
  // it, so the fallback covers both. The cast keeps TypeScript happy
  // without requiring a global declaration.
  const env = (import.meta as unknown as { env?: Record<string, string | undefined> }).env
  return env?.VITE_TELEMETRY_WS_BASE ?? "ws://127.0.0.1:8000"
}

export type TelemetryProps = {
  /** Injected WebSocket factory for tests. Defaults to the global WebSocket. */
  socketFactory?: WebSocketFactory
  /** Satellite key to stream. Defaults to vanguard_r3. */
  satellite?: string
  /** Push interval in seconds. Defaults to 1.0. */
  intervalSeconds?: number
  /** Base URL for the WebSocket. Defaults to the env var or ws://127.0.0.1:8000. */
  base?: string
}

export function Telemetry({
  socketFactory,
  satellite = DEFAULT_SATELLITE,
  intervalSeconds = DEFAULT_INTERVAL_SECONDS,
  base,
}: TelemetryProps) {
  const [status, setStatus] = useState<ConnectionStatus>("idle")
  const [latest, setLatest] = useState<TelemetrySnapshot | null>(null)
  const [bufferSize, setBufferSize] = useState(0)
  const [history, setHistory] = useState<TelemetrySnapshot[]>([])
  const socketRef = useRef<TelemetrySocket | null>(null)

  const url = useMemo(
    () => buildTelemetryUrl(base ?? defaultWebSocketBase(), satellite, intervalSeconds),
    [base, satellite, intervalSeconds],
  )

  useEffect(() => {
    // Construct (but do not connect) the socket. Status starts at
    // "idle"; the user connects on demand. Cleanup disconnects if a
    // connection is open.
    const sock = new TelemetrySocket({
      url,
      factory: socketFactory,
      onStatus: (s) => setStatus(s),
      onSnapshot: (snap) => {
        setLatest(snap)
        // read the buffer AFTER the socket has pushed the snapshot,
        // which happens before onSnapshot fires.
        setBufferSize(sock.size())
        setHistory(sock.getBuffer().slice(-HISTORY_PREVIEW_ROWS))
      },
    })
    socketRef.current = sock
    return () => {
      sock.disconnect()
      socketRef.current = null
    }
  }, [url, socketFactory])

  function toggle() {
    const sock = socketRef.current
    if (!sock) return
    if (sock.getStatus() === "open" || sock.getStatus() === "connecting") {
      sock.disconnect()
    } else {
      sock.connect()
    }
  }

  const isActive = status === "open" || status === "connecting"

  return (
    <section
      data-tour-id="telemetry"
      aria-labelledby="telemetry-heading"
      className="mb-10"
    >
      <h2 id="telemetry-heading" className="mb-1 text-lg font-medium">
        Telemetry (real-time)
      </h2>
      <p className="mb-4 text-sm opacity-70">
        Live stream from the telemetry WebSocket. Each snapshot carries
        the satellite&apos;s orbital state and the current Digital Twin
        thermal state at the demo conditions.
      </p>

      <div className="mb-4 flex flex-wrap items-center gap-3 text-sm">
        <button
          type="button"
          onClick={toggle}
          className="rounded border px-3 py-1.5 text-sm"
        >
          {isActive ? "Disconnect" : "Connect"}
        </button>
        <StatusPill status={status} />
        <span className="text-xs opacity-60">
          satellite: <span className="font-mono">{satellite}</span>
        </span>
        <span className="text-xs opacity-60">
          interval: <span className="font-mono">{intervalSeconds}s</span>
        </span>
        <span className="ml-auto text-xs opacity-60">
          buffer: <span className="font-mono">{bufferSize}</span> / 1000
        </span>
      </div>

      {latest === null && (
        <p className="text-sm opacity-60">
          No snapshot yet. Press Connect to start the stream.
        </p>
      )}

      {latest !== null && (
        <TaggedOutput tag="simulation_result" className="rounded border border-current/15 p-4">
          <header className="mb-3 flex flex-wrap items-baseline gap-3">
            <span className="text-base font-medium">{latest.satellite.name}</span>
            <span className="text-xs uppercase tracking-wide opacity-60">
              {latest.satellite.orbit_class}
            </span>
            <span className="ml-auto font-mono text-xs opacity-70">
              seq {latest.sequence}
            </span>
          </header>

          <div className="mb-4 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
            <Readout label="time" value={latest.time_utc} mono />
            <Readout label="lat" value={`${latest.orbital.lat_deg.toFixed(3)} deg`} />
            <Readout label="lon" value={`${latest.orbital.lon_deg.toFixed(3)} deg`} />
            <Readout label="alt" value={`${(latest.orbital.alt_m / 1000).toFixed(1)} km`} />
            <Readout label="speed" value={`${latest.orbital.speed_km_s.toFixed(3)} km/s`} />
            <Readout
              label="eclipse"
              value={latest.orbital.in_eclipse ? "yes" : "no"}
              highlight={latest.orbital.in_eclipse}
            />
            <Readout label="T_PLC" value={`${latest.thermal.t_plc_c.toFixed(2)} C`} />
            <Readout label="T_TE" value={`${latest.thermal.t_te_c.toFixed(2)} C`} />
          </div>

          {history.length > 1 && (
            <details>
              <summary className="cursor-pointer text-sm font-medium">
                Recent positions ({history.length})
              </summary>
              <div className="mt-2 max-h-64 overflow-auto">
                <table className="w-full text-xs">
                  <thead className="text-left opacity-70">
                    <tr>
                      <th className="py-1 font-normal">seq</th>
                      <th className="py-1 font-normal">time_utc</th>
                      <th className="py-1 font-normal">lat</th>
                      <th className="py-1 font-normal">lon</th>
                      <th className="py-1 font-normal">alt_km</th>
                      <th className="py-1 font-normal">eclipse</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((s) => (
                      <tr key={s.sequence} className="border-t border-current/10">
                        <td className="py-1 font-mono">{s.sequence}</td>
                        <td className="py-1 font-mono">{s.time_utc}</td>
                        <td className="py-1 font-mono">{s.orbital.lat_deg.toFixed(3)}</td>
                        <td className="py-1 font-mono">{s.orbital.lon_deg.toFixed(3)}</td>
                        <td className="py-1 font-mono">
                          {(s.orbital.alt_m / 1000).toFixed(1)}
                        </td>
                        <td className="py-1 font-mono">
                          {s.orbital.in_eclipse ? "yes" : "no"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}

          <footer className="mt-4 border-t border-current/10 pt-3 font-mono text-xs opacity-60">
            artefact: telemetry_snapshot
          </footer>
        </TaggedOutput>
      )}
    </section>
  )
}

function StatusPill({ status }: { status: ConnectionStatus }) {
  const tone: Record<ConnectionStatus, string> = {
    idle: "var(--color-accent-slate)",
    connecting: "var(--color-accent-amber)",
    open: "var(--color-accent-teal)",
    closed: "var(--color-accent-slate)",
    error: "var(--color-accent-amber)",
  }
  return (
    <span
      className="inline-flex items-center gap-2 rounded-full border px-2 py-0.5 text-xs"
      data-telemetry-status={status}
      style={{ borderColor: "color-mix(in srgb, currentColor 20%, transparent)" }}
    >
      <span
        aria-hidden="true"
        style={{
          width: "0.5rem",
          height: "0.5rem",
          borderRadius: 9999,
          background: tone[status],
          display: "inline-block",
        }}
      />
      {status}
    </span>
  )
}

function Readout({
  label,
  value,
  mono,
  highlight,
}: {
  label: string
  value: string
  mono?: boolean
  highlight?: boolean
}) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide opacity-60">{label}</div>
      <div
        className={mono ? "font-mono" : ""}
        style={highlight ? { color: "var(--color-accent-amber)" } : undefined}
      >
        {value}
      </div>
    </div>
  )
}
