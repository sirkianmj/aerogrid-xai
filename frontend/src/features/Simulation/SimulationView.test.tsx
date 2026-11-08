import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

vi.mock("echarts-for-react", () => ({
  default: () => null,
}))

vi.mock("../MissionControl/missionContext", () => ({
  useMission: () => ({
    config: {
      seed: 1,
      satellite_key: "iss",
      n_uavs: 3,
      ground_lat_deg: 40.798,
      ground_lon_deg: -77.86,
      transmitter_power_w: 10000,
      wavelength_nm: 1064,
      visibility_km: 10,
      cloud_factor: 0,
      transmitter_type: "satellite" as const,
      transmitter_min_elevation_deg: 5.0,
      relay_topology: null,
      relay_fraction: 0.7,
    },
    markStepComplete: vi.fn(),
    setStepOutput: vi.fn(),
    completedSteps: new Set<number>(),
  }),
}))

vi.mock("./simulationApi", async () => {
  const actual = await vi.importActual<typeof import("./simulationApi")>(
    "./simulationApi",
  )
  return { ...actual, runSimulation: vi.fn() }
})

import { SimulationView } from "./SimulationView"
import { runSimulation, type SimulationResponse } from "./simulationApi"

const mockedRun = vi.mocked(runSimulation)

function sampleResult(): SimulationResponse {
  return {
    epistemic_tag: "simulation_result",
    preset: "10min",
    duration_s: 600,
    step_s: 60,
    n_samples: 11,
    config_summary: {},
    warnings: [],
    samples: Array.from({ length: 11 }, (_, i) => ({
      t_utc: `2026-11-06T19:${String(i).padStart(2, "0")}:00Z`,
      elapsed_s: i * 60,
      received_power_w: 100,
      delivered_power_w: 50,
      cumulative_energy_j: i * 3000,
      atmospheric_transmittance: 0.8,
      satellite_elevation_deg: 30,
      link_status: "laser",
      uavs: [
        { uav_id: 0, received_power_w: 50, delivered_power_w: 25, receiver_efficiency: 0.5, thermal_headroom_c: 40, relay_hop_index: -1, thermal_runaway: false },
        { uav_id: 1, received_power_w: 30, delivered_power_w: 15, receiver_efficiency: 0.5, thermal_headroom_c: 35, relay_hop_index: -1, thermal_runaway: false },
        { uav_id: 2, received_power_w: 20, delivered_power_w: 10, receiver_efficiency: 0.5, thermal_headroom_c: 30, relay_hop_index: -1, thermal_runaway: false },
      ],
      epistemic_tag: "simulation_result",
    })),
  }
}

describe("SimulationView", () => {
  beforeEach(() => {
    mockedRun.mockReset()
  })

  it("renders header and run button in idle state", () => {
    render(<SimulationView />)
    expect(screen.getByText("5 · Simulation")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /run simulation/i })).toBeInTheDocument()
  })

  it("renders preset options", () => {
    render(<SimulationView />)
    expect(screen.getByRole("button", { name: /10 min/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /1 hour/i })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /1 pass/i })).toBeInTheDocument()
  })

  it("calls runSimulation when Run clicked", async () => {
    mockedRun.mockResolvedValueOnce(sampleResult())
    const user = userEvent.setup()
    render(<SimulationView />)
    await user.click(screen.getByRole("button", { name: /run simulation/i }))
    await waitFor(() => expect(mockedRun).toHaveBeenCalledOnce())
  })

  it("renders summary and charts on success", async () => {
    mockedRun.mockResolvedValueOnce(sampleResult())
    const user = userEvent.setup()
    render(<SimulationView />)
    await user.click(screen.getByRole("button", { name: /run simulation/i }))
    await waitFor(() => expect(screen.getByText("11")).toBeInTheDocument())
    expect(screen.getByText("Received power per UAV")).toBeInTheDocument()
    expect(screen.getByText("Delivered power per UAV")).toBeInTheDocument()
    expect(screen.getByText("Cumulative energy")).toBeInTheDocument()
    expect(screen.getByText("Atmospheric transmittance")).toBeInTheDocument()
  })

  it("shows error message on failure", async () => {
    mockedRun.mockRejectedValueOnce(new Error("network down"))
    const user = userEvent.setup()
    render(<SimulationView />)
    await user.click(screen.getByRole("button", { name: /run simulation/i }))
    await waitFor(() => expect(screen.getByText(/network down/)).toBeInTheDocument())
  })

  it("passes selected preset to runSimulation", async () => {
    mockedRun.mockResolvedValueOnce(sampleResult())
    const user = userEvent.setup()
    render(<SimulationView />)
    await user.click(screen.getByRole("button", { name: /10 min/i }))
    await user.click(screen.getByRole("button", { name: /run simulation/i }))
    await waitFor(() => expect(mockedRun).toHaveBeenCalledOnce())
    const req = mockedRun.mock.calls[0][0]
    expect(req.preset).toBe("10min")
    expect(req.seed).toBe(1)
    expect(req.n_uavs).toBe(3)
    // Fields that must be forwarded from config to the backend. Without
    // transmitter_type, /simulation/run defaults to "satellite" and the
    // ground-mode mission produces satellite-shaped curves.
    expect(req.transmitter_type).toBeDefined()
    expect(req.transmitter_min_elevation_deg).toBeDefined()
  })
})
