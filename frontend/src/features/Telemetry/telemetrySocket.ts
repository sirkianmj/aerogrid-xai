/**
 * TelemetrySocket — a typed client for the telemetry WebSocket.
 *
 * The endpoint WS /telemetry/stream pushes one snapshot per interval
 * (see backend/app/telemetry/api.py). This module wraps the native
 * WebSocket, parses the JSON payloads, and keeps a bounded circular
 * ring buffer of the last N snapshots.
 *
 * Ring buffer
 * -----------
 *
 * The Sprint 7 gate for s7-3 requires the client to keep at least 1000
 * samples. The default ring capacity is 1000. When the buffer is full,
 * the oldest sample is overwritten. Reading `buffer()` returns samples
 * in chronological order with the oldest first.
 *
 * WebSocket factory injection
 * ---------------------------
 *
 * The native WebSocket is not constructible in jsdom (it exists but
 * does not actually connect). The class therefore accepts a factory
 * function so tests can supply a fake that emits prepared payloads.
 * The production code path passes the global WebSocket.
 *
 * Reconnection
 * ------------
 *
 * On an unexpected close the socket reconnects after a fixed delay.
 * Exponential backoff is deferred; the current delay is 2 seconds,
 * matching the default server interval. A caller that wants no
 * reconnection passes `autoReconnect: false`.
 */

export type OrbitalSnapshot = {
  lat_deg: number
  lon_deg: number
  alt_m: number
  speed_km_s: number
  in_eclipse: boolean
}

export type ThermalSnapshot = {
  t_plc_k: number
  t_plc_c: number
  t_te_k: number
  t_te_c: number
  thermal_runaway_power_w: number
  safety_margin_w: number
}

export type SatelliteInfo = {
  key: string
  name: string
  orbit_class: string
}

export type TelemetrySnapshot = {
  epistemic_tag: string
  sequence: number
  time_utc: string
  satellite: SatelliteInfo
  orbital: OrbitalSnapshot
  thermal: ThermalSnapshot
}

export type ConnectionStatus = "idle" | "connecting" | "open" | "closed" | "error"

export type WebSocketLike = {
  readyState: number
  close: (code?: number, reason?: string) => void
  send: (data: string) => void
}

export type WebSocketFactory = (url: string) => WebSocketLike

export const DEFAULT_RING_CAPACITY = 1000
export const DEFAULT_RECONNECT_DELAY_MS = 2000

export type TelemetrySocketOptions = {
  /** Full WebSocket URL, e.g. ws://127.0.0.1:8000/telemetry/stream?satellite=vanguard_r3 */
  url: string
  /** Injected WebSocket constructor. Defaults to the global WebSocket. */
  factory?: WebSocketFactory
  /** Ring buffer capacity. Defaults to 1000. */
  ringCapacity?: number
  /** If true, reconnect on unexpected close after a fixed delay. */
  autoReconnect?: boolean
  /** Reconnect delay in ms. Defaults to 2000. */
  reconnectDelayMs?: number
  /** Called with each new snapshot after the buffer has been updated. */
  onSnapshot?: (snapshot: TelemetrySnapshot) => void
  /** Called with every status change. */
  onStatus?: (status: ConnectionStatus) => void
}

export class TelemetrySocket {
  private readonly url: string
  private readonly factory: WebSocketFactory
  private readonly ringCapacity: number
  private readonly autoReconnect: boolean
  private readonly reconnectDelayMs: number
  private readonly onSnapshot?: (s: TelemetrySnapshot) => void
  private readonly onStatus?: (s: ConnectionStatus) => void

  private socket: WebSocketLike | null = null
  private status: ConnectionStatus = "idle"
  private buffer: TelemetrySnapshot[] = []
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private shouldRun = false

  constructor(options: TelemetrySocketOptions) {
    this.url = options.url
    const factory = options.factory
    if (factory) {
      this.factory = factory
    } else if (typeof WebSocket !== "undefined") {
      this.factory = (u) => new WebSocket(u) as unknown as WebSocketLike
    } else {
      throw new Error(
        "no WebSocket available; pass a factory in environments without one",
      )
    }
    this.ringCapacity = options.ringCapacity ?? DEFAULT_RING_CAPACITY
    if (this.ringCapacity < 1) {
      throw new Error(`ringCapacity must be >= 1; got ${this.ringCapacity}`)
    }
    this.autoReconnect = options.autoReconnect ?? true
    this.reconnectDelayMs = options.reconnectDelayMs ?? DEFAULT_RECONNECT_DELAY_MS
    this.onSnapshot = options.onSnapshot
    this.onStatus = options.onStatus
  }

  getStatus(): ConnectionStatus {
    return this.status
  }

  /** Return the ring buffer in chronological order, oldest first. */
  getBuffer(): readonly TelemetrySnapshot[] {
    return this.buffer
  }

  /** Number of snapshots currently held. */
  size(): number {
    return this.buffer.length
  }

  /** The most recently received snapshot, or null. */
  latest(): TelemetrySnapshot | null {
    return this.buffer.length > 0 ? this.buffer[this.buffer.length - 1]! : null
  }

  connect(): void {
    if (this.shouldRun) return
    this.shouldRun = true
    this.open()
  }

  disconnect(): void {
    this.shouldRun = false
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.socket) {
      try {
        this.socket.close()
      } catch {
        // close on an already-closed socket is harmless
      }
      this.socket = null
    }
    this.setStatus("closed")
  }

  private setStatus(s: ConnectionStatus): void {
    if (this.status === s) return
    this.status = s
    this.onStatus?.(s)
  }

  private pushSnapshot(s: TelemetrySnapshot): void {
    this.buffer.push(s)
    if (this.buffer.length > this.ringCapacity) {
      this.buffer.splice(0, this.buffer.length - this.ringCapacity)
    }
    this.onSnapshot?.(s)
  }

  private open(): void {
    this.setStatus("connecting")
    let sock: WebSocketLike
    try {
      sock = this.factory(this.url)
    } catch {
      this.setStatus("error")
      this.scheduleReconnect()
      return
    }
    this.socket = sock

    // The native WebSocket exposes event handlers as properties. The
    // fake used in tests exposes the same shape. We attach by property
    // rather than addEventListener because that is what the fake
    // implements most cleanly and what the browser supports.
    const anySock = sock as unknown as {
      onopen: (() => void) | null
      onclose: ((ev: { code: number; reason: string }) => void) | null
      onerror: (() => void) | null
      onmessage: ((ev: { data: string }) => void) | null
    }
    anySock.onopen = () => {
      this.setStatus("open")
    }
    anySock.onmessage = (ev) => {
      try {
        const parsed = JSON.parse(ev.data) as TelemetrySnapshot
        if (
          typeof parsed.sequence !== "number" ||
          typeof parsed.time_utc !== "string" ||
          !parsed.orbital ||
          !parsed.thermal
        ) {
          // A malformed payload is dropped, not parsed further; the
          // stream is a trusted source but the guard keeps a partial
          // server-side rollout from corrupting the buffer.
          return
        }
        this.pushSnapshot(parsed)
      } catch {
        // Non-JSON payload; drop it.
      }
    }
    anySock.onerror = () => {
      this.setStatus("error")
    }
    anySock.onclose = () => {
      this.socket = null
      this.setStatus("closed")
      if (this.shouldRun && this.autoReconnect) {
        this.scheduleReconnect()
      }
    }
  }

  private scheduleReconnect(): void {
    if (!this.shouldRun || !this.autoReconnect) return
    if (this.reconnectTimer !== null) return
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      if (this.shouldRun) this.open()
    }, this.reconnectDelayMs)
  }
}

/**
 * Build the default telemetry WebSocket URL for one satellite.
 *
 * The Vite dev-server proxy is configured for /api/* HTTP requests.
 * WebSocket proxying is separate; in dev the browser connects directly
 * to the backend host. This helper builds the URL from a base and the
 * backend's route path.
 */
export function buildTelemetryUrl(
  base: string,
  satellite: string,
  intervalSeconds: number,
): string {
  const trimmed = base.replace(/\/+$/, "")
  const params = new URLSearchParams({
    satellite,
    interval_seconds: String(intervalSeconds),
  })
  return `${trimmed}/telemetry/stream?${params}`
}
