import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { makeFakeWebSocketFactory } from "./fakeWebSocket"
import {
  DEFAULT_RING_CAPACITY,
  TelemetrySocket,
  buildTelemetryUrl,
  type TelemetrySnapshot,
} from "./telemetrySocket"

function makeSnapshot(sequence: number, lat = 0, lon = 0): TelemetrySnapshot {
  return {
    epistemic_tag: "simulation_result",
    sequence,
    time_utc: `2000-06-28T18:47:56.${String(sequence).padStart(3, "0")}Z`,
    satellite: { key: "vanguard_r3", name: "VANGUARD 1", orbit_class: "LEO" },
    orbital: {
      lat_deg: lat,
      lon_deg: lon,
      alt_m: 650000 + sequence,
      speed_km_s: 7.5,
      in_eclipse: false,
    },
    thermal: {
      t_plc_k: 360.0,
      t_plc_c: 86.85,
      t_te_k: 330.0,
      t_te_c: 56.85,
      thermal_runaway_power_w: 60.0,
      safety_margin_w: 40.0,
    },
  }
}

describe("buildTelemetryUrl", () => {
  it("constructs a WebSocket URL with both query parameters", () => {
    const url = buildTelemetryUrl("ws://127.0.0.1:8000", "vanguard_r3", 2)
    expect(url).toBe(
      "ws://127.0.0.1:8000/telemetry/stream?satellite=vanguard_r3&interval_seconds=2",
    )
  })

  it("strips a trailing slash from the base", () => {
    expect(buildTelemetryUrl("ws://127.0.0.1:8000/", "iss", 1)).toBe(
      "ws://127.0.0.1:8000/telemetry/stream?satellite=iss&interval_seconds=1",
    )
  })
})

describe("TelemetrySocket", () => {
  let fake: ReturnType<typeof makeFakeWebSocketFactory>

  beforeEach(() => {
    fake = makeFakeWebSocketFactory()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it("starts in idle status and connects on demand", () => {
    const statuses: string[] = []
    const client = new TelemetrySocket({
      url: "ws://test/telemetry",
      factory: fake.factory,
      onStatus: (s) => statuses.push(s),
      autoReconnect: false,
    })
    expect(client.getStatus()).toBe("idle")
    client.connect()
    expect(statuses).toContain("connecting")
    fake.last().emitOpen()
    expect(client.getStatus()).toBe("open")
  })

  it("updates the buffer and fires onSnapshot for each message", () => {
    const received: number[] = []
    const client = new TelemetrySocket({
      url: "ws://test/telemetry",
      factory: fake.factory,
      onSnapshot: (s) => received.push(s.sequence),
      autoReconnect: false,
    })
    client.connect()
    fake.last().emitOpen()
    fake.last().emitMessage(makeSnapshot(0))
    fake.last().emitMessage(makeSnapshot(1))
    fake.last().emitMessage(makeSnapshot(2))
    expect(received).toEqual([0, 1, 2])
    expect(client.size()).toBe(3)
    expect(client.latest()?.sequence).toBe(2)
  })

  it("bounds the buffer at the configured capacity", () => {
    const client = new TelemetrySocket({
      url: "ws://test/telemetry",
      factory: fake.factory,
      ringCapacity: 5,
      autoReconnect: false,
    })
    client.connect()
    fake.last().emitOpen()
    for (let i = 0; i < 12; i++) fake.last().emitMessage(makeSnapshot(i))
    expect(client.size()).toBe(5)
    const seqs = client.getBuffer().map((s) => s.sequence)
    // The ring keeps the most recent 5, in order.
    expect(seqs).toEqual([7, 8, 9, 10, 11])
  })

  it("default ring capacity is at least 1000", () => {
    expect(DEFAULT_RING_CAPACITY).toBeGreaterThanOrEqual(1000)
  })

  it("drops a malformed JSON payload without corrupting the buffer", () => {
    const received: number[] = []
    const client = new TelemetrySocket({
      url: "ws://test/telemetry",
      factory: fake.factory,
      onSnapshot: (s) => received.push(s.sequence),
      autoReconnect: false,
    })
    client.connect()
    fake.last().emitOpen()
    fake.last().emitMessage("not json")
    fake.last().emitMessage(JSON.stringify({ foo: "bar" }))
    fake.last().emitMessage(makeSnapshot(0))
    expect(received).toEqual([0])
    expect(client.size()).toBe(1)
  })

  it("marks status closed on a clean close and does not reconnect when disabled", () => {
    vi.useFakeTimers()
    const statuses: string[] = []
    const client = new TelemetrySocket({
      url: "ws://test/telemetry",
      factory: fake.factory,
      onStatus: (s) => statuses.push(s),
      autoReconnect: false,
    })
    client.connect()
    fake.last().emitOpen()
    fake.last().emitClose()
    expect(client.getStatus()).toBe("closed")
    vi.advanceTimersByTime(3000)
    // No new socket should have been created.
    expect(fake.sockets.length).toBe(1)
    expect(statuses[statuses.length - 1]).toBe("closed")
  })

  it("schedules a reconnect when autoReconnect is true", () => {
    vi.useFakeTimers()
    const client = new TelemetrySocket({
      url: "ws://test/telemetry",
      factory: fake.factory,
      autoReconnect: true,
      reconnectDelayMs: 500,
    })
    client.connect()
    fake.last().emitOpen()
    fake.last().emitClose()
    expect(fake.sockets.length).toBe(1)
    vi.advanceTimersByTime(600)
    expect(fake.sockets.length).toBe(2)
  })

  it("disconnect cancels the reconnect timer", () => {
    vi.useFakeTimers()
    const client = new TelemetrySocket({
      url: "ws://test/telemetry",
      factory: fake.factory,
      autoReconnect: true,
      reconnectDelayMs: 500,
    })
    client.connect()
    fake.last().emitOpen()
    fake.last().emitClose()
    client.disconnect()
    vi.advanceTimersByTime(1000)
    expect(fake.sockets.length).toBe(1)
    expect(client.getStatus()).toBe("closed")
  })

  it("rejects a ring capacity below one", () => {
    expect(
      () =>
        new TelemetrySocket({
          url: "ws://test/telemetry",
          factory: fake.factory,
          ringCapacity: 0,
        }),
    ).toThrow()
  })
})
