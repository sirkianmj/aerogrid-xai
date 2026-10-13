/**
 * FakeWebSocket for tests.
 *
 * Implements enough of the WebSocket surface for TelemetrySocket to
 * drive it in jsdom, where the real WebSocket is not constructible into
 * a working connection.
 */

import type { WebSocketLike } from "./telemetrySocket"

export class FakeWebSocket implements WebSocketLike {
  readyState = 1
  onopen: (() => void) | null = null
  onclose: ((ev: { code: number; reason: string }) => void) | null = null
  onerror: (() => void) | null = null
  onmessage: ((ev: { data: string }) => void) | null = null

  readonly url: string
  private closed = false

  constructor(url: string) {
    this.url = url
  }

  /** Server-side helper: fire the open event. */
  emitOpen(): void {
    this.onopen?.()
  }

  /** Server-side helper: send a JSON payload. */
  emitMessage(payload: unknown): void {
    if (this.closed) return
    const text = typeof payload === "string" ? payload : JSON.stringify(payload)
    this.onmessage?.({ data: text } as { data: string })
  }

  /** Server-side helper: fire a clean close. */
  emitClose(code = 1000, reason = ""): void {
    this.closed = true
    this.readyState = 3
    this.onclose?.({ code, reason } as { code: number; reason: string })
  }

  /** Server-side helper: fire an error. */
  emitError(): void {
    this.onerror?.()
  }

  close(): void {
    if (this.closed) return
    this.closed = true
    this.readyState = 3
    this.onclose?.({ code: 1000, reason: "client" } as { code: number; reason: string })
  }

  send(data: string): void {
    // Outgoing messages are not used by the telemetry protocol; the
    // socket is receive-only from the client side. Kept as a no-op so
    // the WebSocketLike interface is satisfied.
    void data
  }
}

/**
 * Build a factory that constructs FakeWebSocket instances and keeps
 * references so the test can drive them.
 */
export function makeFakeWebSocketFactory(): {
  factory: (url: string) => FakeWebSocket
  sockets: FakeWebSocket[]
  last: () => FakeWebSocket
} {
  const sockets: FakeWebSocket[] = []
  const factory = (url: string): FakeWebSocket => {
    const s = new FakeWebSocket(url)
    sockets.push(s)
    return s
  }
  return {
    factory,
    sockets,
    last: () => {
      if (sockets.length === 0) throw new Error("no socket has been constructed")
      return sockets[sockets.length - 1]!
    },
  }
}
