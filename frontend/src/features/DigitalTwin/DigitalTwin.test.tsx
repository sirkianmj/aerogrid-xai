import { render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { DigitalTwin } from "./DigitalTwin"
import type { DiscrepancyResponse, StateResponse, TrajectoryResponse } from "./digitalTwinApi"

const STATE: StateResponse = {
  epistemic_tag: "simulation_result",
  incident_power_w: 20,
  airflow_m_per_s: 5,
  ambient_temperature_k: 298.15,
  steady_state: { t_plc_k: 360, t_te_k: 330, t_plc_c: 86.85, t_te_c: 56.85 },
  thermal_runaway_power_w: 60,
  safety_margin_w: 40,
  safety_margin_fraction: 0.6667,
  receiver_efficiency: 0.0015,
  receiver_efficiency_source: "physics.receiver.eta_total at the steady-state temperatures",
}

const TRAJ: TrajectoryResponse = {
  epistemic_tag: "simulation_result",
  t_end_s: 600,
  n_samples: 3,
  samples: [
    { time_s: 0, t_plc_k: 298.15, t_te_k: 298.15 },
    { time_s: 300, t_plc_k: 350.0, t_te_k: 320.0 },
    { time_s: 600, t_plc_k: 360.0, t_te_k: 330.0 },
  ],
}

const DISC: DiscrepancyResponse = {
  epistemic_tag: "simulation_result",
  n_observations: 3,
  n_triggered: 2,
  triggered_fields: ["temperature_k", "received_power_w"],
  should_refine: true,
  threshold_summary: {
    temperature_k: { absolute: 2.0, relative: null },
  },
  records: [
    { field_name: "temperature_k", predicted: 360.0, observed: 365.0, absolute_error: 5.0, relative_error: 0.0139, triggered: true, step: 0 },
    { field_name: "efficiency", predicted: 0.20, observed: 0.202, absolute_error: 0.002, relative_error: 0.01, triggered: false, step: 1 },
    { field_name: "received_power_w", predicted: 100.0, observed: 105.0, absolute_error: 5.0, relative_error: 0.05, triggered: true, step: 2 },
  ],
}

function stubDigitalTwinFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, _init?: RequestInit) => {
      if (url.endsWith("/digital-twin/state")) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(STATE) } as Response)
      }
      if (url.endsWith("/digital-twin/trajectory")) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(TRAJ) } as Response)
      }
      if (url.endsWith("/digital-twin/discrepancy")) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(DISC) } as Response)
      }
      return Promise.reject(new Error("unexpected url: " + url))
    }),
  )
}

describe("DigitalTwin", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it("renders the panel heading and a loading message on mount", () => {
    stubDigitalTwinFetch()
    render(<DigitalTwin />)
    expect(screen.getByRole("heading", { name: /digital twin/i, level: 2 })).toBeInTheDocument()
    expect(screen.getByText(/loading digital twin state/i)).toBeInTheDocument()
  })

  it("renders the steady-state temperatures from the backend", async () => {
    stubDigitalTwinFetch()
    render(<DigitalTwin />)
    await waitFor(() => {
      expect(screen.getByText("86.85 C")).toBeInTheDocument()
    })
    expect(screen.getByText("56.85 C")).toBeInTheDocument()
  })

  it("renders the safety margin and runaway boundary", async () => {
    stubDigitalTwinFetch()
    render(<DigitalTwin />)
    await waitFor(() => {
      expect(screen.getByText("60.00 W")).toBeInTheDocument()
    })
    expect(screen.getByText(/40.00 W \(66.7%\)/)).toBeInTheDocument()
  })

  it("renders the Section 21 simulation_result badge", async () => {
    stubDigitalTwinFetch()
    const { container } = render(<DigitalTwin />)
    await waitFor(() => {
      const badges = container.querySelectorAll('[data-epistemic-tag="simulation_result"]')
      expect(badges.length).toBeGreaterThanOrEqual(1)
    })
  })

  it("renders the trajectory chart with one polyline per series", async () => {
    stubDigitalTwinFetch()
    const { container } = render(<DigitalTwin />)
    await waitFor(() => {
      expect(screen.getByText(/thermal transient/i)).toBeInTheDocument()
    })
    const polylines = container.querySelectorAll("polyline")
    expect(polylines.length).toBe(2)
  })

  it("shows the discrepancy table with one row per record", async () => {
    stubDigitalTwinFetch()
    render(<DigitalTwin />)
    await waitFor(() => {
      expect(screen.getByText(/predicted vs. observed/i)).toBeInTheDocument()
    })
    const rows = document.querySelectorAll("tbody tr")
    // 3 discrepancy rows
    expect(rows.length).toBe(3)
  })

  it("shows the refine-triggered marker when should_refine is true", async () => {
    stubDigitalTwinFetch()
    render(<DigitalTwin />)
    await waitFor(() => {
      expect(screen.getByText(/refine triggered/i)).toBeInTheDocument()
    })
  })

  it("shows the artefact sub-label", async () => {
    stubDigitalTwinFetch()
    render(<DigitalTwin />)
    await waitFor(() => {
      expect(screen.getByText(/artefact: digital_twin_state/i)).toBeInTheDocument()
    })
  })

  it("shows an error message when the backend returns 500", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 500,
          json: () => Promise.resolve({ detail: "thermal service down" }),
        } as Response),
      ),
    )
    render(<DigitalTwin />)
    await waitFor(() => {
      expect(screen.getByText(/error \(500\): thermal service down/i)).toBeInTheDocument()
    })
  })

  it("shows an error message when the fetch fails", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("network failure"))))
    render(<DigitalTwin />)
    await waitFor(() => {
      expect(screen.getByText(/network failure/i)).toBeInTheDocument()
    })
  })
})
