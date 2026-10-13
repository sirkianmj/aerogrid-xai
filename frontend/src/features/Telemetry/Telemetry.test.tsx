import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { makeFakeWebSocketFactory } from "./fakeWebSocket"
import { Telemetry } from "./Telemetry"
import type { TelemetrySnapshot } from "./telemetrySocket"

function snap(sequence: number, lat = 0, lon = 0, eclipse = false): TelemetrySnapshot {
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
      in_eclipse: eclipse,
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

describe("Telemetry", () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("renders the panel heading and an idle prompt", () => {
    const fake = makeFakeWebSocketFactory()
    render(<Telemetry socketFactory={fake.factory} />)
    expect(
      screen.getByRole("heading", { name: /telemetry/i, level: 2 }),
    ).toBeInTheDocument()
    expect(screen.getByText(/no snapshot yet/i)).toBeInTheDocument()
    // No socket has been constructed until the user clicks Connect.
    expect(fake.sockets.length).toBe(0)
  })

  it("opens a WebSocket when the user clicks Connect", async () => {
    const fake = makeFakeWebSocketFactory()
    const user = userEvent.setup()
    render(<Telemetry socketFactory={fake.factory} />)
    await user.click(screen.getByRole("button", { name: /^connect$/i }))
    expect(fake.sockets.length).toBe(1)
  })

  it("renders the latest snapshot after the server pushes one", async () => {
    const fake = makeFakeWebSocketFactory()
    const user = userEvent.setup()
    render(<Telemetry socketFactory={fake.factory} />)
    await user.click(screen.getByRole("button", { name: /^connect$/i }))
    const socket = fake.last()
    socket.emitOpen()
    socket.emitMessage(snap(0, 12.345, -67.890))
    await waitFor(() => {
      expect(screen.getByText("VANGUARD 1")).toBeInTheDocument()
    })
    expect(screen.getByText(/12\.345 deg/)).toBeInTheDocument()
    expect(screen.getByText(/-67\.890 deg/)).toBeInTheDocument()
  })

  it("shows the sequence number in the header", async () => {
    const fake = makeFakeWebSocketFactory()
    const user = userEvent.setup()
    render(<Telemetry socketFactory={fake.factory} />)
    await user.click(screen.getByRole("button", { name: /^connect$/i }))
    fake.last().emitOpen()
    fake.last().emitMessage(snap(7))
    await waitFor(() => {
      expect(screen.getByText("seq 7")).toBeInTheDocument()
    })
  })

  it("marks eclipse snapshots", async () => {
    const fake = makeFakeWebSocketFactory()
    const user = userEvent.setup()
    render(<Telemetry socketFactory={fake.factory} />)
    await user.click(screen.getByRole("button", { name: /^connect$/i }))
    fake.last().emitOpen()
    fake.last().emitMessage(snap(0, 0, 0, true))
    await waitFor(() => {
      // "eclipse" row shows "yes"
      const eclipseLabel = screen.getByText(/^eclipse$/i)
      const value = eclipseLabel.nextElementSibling
      expect(value?.textContent).toBe("yes")
    })
  })

  it("updates the buffer counter as more snapshots arrive", async () => {
    const fake = makeFakeWebSocketFactory()
    const user = userEvent.setup()
    render(<Telemetry socketFactory={fake.factory} />)
    await user.click(screen.getByRole("button", { name: /^connect$/i }))
    fake.last().emitOpen()
    fake.last().emitMessage(snap(0))
    fake.last().emitMessage(snap(1))
    fake.last().emitMessage(snap(2))
    await waitFor(() => {
      expect(screen.getByText("3")).toBeInTheDocument()
    })
  })

  it("shows the Section 21 simulation_result badge once a snapshot arrives", async () => {
    const fake = makeFakeWebSocketFactory()
    const user = userEvent.setup()
    const { container } = render(<Telemetry socketFactory={fake.factory} />)
    await user.click(screen.getByRole("button", { name: /^connect$/i }))
    fake.last().emitOpen()
    fake.last().emitMessage(snap(0))
    await waitFor(() => {
      const badges = container.querySelectorAll(
        '[data-epistemic-tag="simulation_result"]',
      )
      expect(badges.length).toBeGreaterThanOrEqual(1)
    })
  })

  it("shows the artefact sub-label", async () => {
    const fake = makeFakeWebSocketFactory()
    const user = userEvent.setup()
    render(<Telemetry socketFactory={fake.factory} />)
    await user.click(screen.getByRole("button", { name: /^connect$/i }))
    fake.last().emitOpen()
    fake.last().emitMessage(snap(0))
    await waitFor(() => {
      expect(screen.getByText(/artefact: telemetry_snapshot/i)).toBeInTheDocument()
    })
  })

  it("renders the history table once more than one snapshot has arrived", async () => {
    const fake = makeFakeWebSocketFactory()
    const user = userEvent.setup()
    render(<Telemetry socketFactory={fake.factory} />)
    await user.click(screen.getByRole("button", { name: /^connect$/i }))
    fake.last().emitOpen()
    fake.last().emitMessage(snap(0))
    fake.last().emitMessage(snap(1))
    await waitFor(() => {
      expect(screen.getByText(/recent positions/i)).toBeInTheDocument()
    })
    const rows = document.querySelectorAll("tbody tr")
    expect(rows.length).toBe(2)
  })

  it("button label switches to Disconnect after Connect", async () => {
    const fake = makeFakeWebSocketFactory()
    const user = userEvent.setup()
    render(<Telemetry socketFactory={fake.factory} />)
    await user.click(screen.getByRole("button", { name: /^connect$/i }))
    expect(screen.getByRole("button", { name: /disconnect/i })).toBeInTheDocument()
  })

  it("shows the idle status pill before connecting", () => {
    const fake = makeFakeWebSocketFactory()
    const { container } = render(<Telemetry socketFactory={fake.factory} />)
    const pill = container.querySelector("[data-telemetry-status]")
    expect(pill?.getAttribute("data-telemetry-status")).toBe("idle")
  })
})
