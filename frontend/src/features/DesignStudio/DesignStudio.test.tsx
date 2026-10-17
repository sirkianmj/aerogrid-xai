import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { DesignStudio } from "./DesignStudio"

const { applyConfigMock } = vi.hoisted(() => ({ applyConfigMock: vi.fn() }))

vi.mock("../MissionControl/missionContext", () => ({
  useMission: () => ({
    config: {
      satellite_key: "iss",
      ground_lat_deg: 40.798,
      ground_lon_deg: -77.86,
      transmitter_power_w: 10000,
      n_uavs: 6,
      seed: 20261014,
      t_utc: null,
      visibility_km: 10,
      cloud_factor: 0,
      transmitter_aperture_m: 0.02,
      uav_alt_m: 1000,
      uav_receiver_aperture_m2: 0.5,
      uav_receiver_type: "laser_photovoltaic" as const,
      satellite_elements: null,
      selected_architecture: null,
      uav_hardware_list: null,
    },
    state: { status: "loading" as const },
    applyConfig: applyConfigMock,
    refresh: () => {},
    reset: () => {},
    markStepComplete: () => {},
    completedSteps: new Set<number>(),
    lastDiscoveryRun: null,
    setLastDiscoveryRun: () => {},
    clearLastDiscoveryRun: () => {},
  }),
}))

const PRESETS = {
  satellites: [
    {
      id: "SAT-A1",
      label: "LEO smallsat",
      a_km: 6771, e: 0, i_deg: 51.6,
      raan_deg: 0, argp_deg: 0, m0_deg: 0,
      transmitter_power_w: 10000, wavelength_nm: 1064, transmitter_aperture_m: 0.02,
    },
  ],
  drones: [
    {
      id: "UAV-A1",
      label: "Micro UAV",
      mass_kg: 1, wingspan_m: 0.5, battery_wh: 20,
      receiver_aperture_m2: 0.05,
      receiver_type: "laser_photovoltaic",
      battery_efficiency: 0.92,
      thermal_limit_c: 70,
    },
  ],
}

const REPORT = {
  epistemic_tag: "simulation_result",
  verdict: "feasible" as const,
  delivered_power_w: 0.055,
  notes: [],
  metrics: { delivered_power_w: 0.055, receiver_efficiency: 0.15 },
}

function stubFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string | URL | Request) => {
      const u = String(url)
      if (u.includes("/design/presets")) {
        return Promise.resolve({
          ok: true, status: 200, json: () => Promise.resolve(PRESETS),
        } as Response)
      }
      return Promise.resolve({
        ok: true, status: 200, json: () => Promise.resolve(REPORT),
      } as Response)
    }),
  )
}

describe("DesignStudio", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    applyConfigMock.mockClear()
  })

  it("renders both designers after presets load", async () => {
    stubFetch()
    render(<DesignStudio />)
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /Satellite designer/i })).toBeInTheDocument(),
    )
    expect(screen.getByRole("heading", { name: /Drone designer/i })).toBeInTheDocument()
  })

  it("renders the preset selectors once presets are available", async () => {
    stubFetch()
    render(<DesignStudio />)
    await waitFor(() =>
      expect(screen.getByLabelText("Satellite preset")).toBeInTheDocument(),
    )
    expect(screen.getByLabelText("Drone preset")).toBeInTheDocument()
  })

  it("Use this fleet sets uav_hardware_list on the mission config", async () => {
    stubFetch()
    render(<DesignStudio />)
    await waitFor(() =>
      expect(screen.getByTestId("use-fleet")).toBeInTheDocument(),
    )
    // Adoption is gated: evaluate every row first, then the button
    // becomes enabled. That is what a real user must do.
    await userEvent.click(screen.getByTestId("evaluate-fleet"))
    await waitFor(() =>
      expect(screen.getByTestId("use-fleet")).toBeEnabled(),
    )
    await userEvent.click(screen.getByTestId("use-fleet"))
    expect(applyConfigMock).toHaveBeenCalledTimes(1)
    const call = applyConfigMock.mock.calls[0][0]
    expect(call).toHaveProperty("uav_hardware_list")
    expect(Array.isArray(call.uav_hardware_list)).toBe(true)
    expect(call.uav_hardware_list.length).toBeGreaterThan(0)
    expect(call.uav_hardware_list[0]).toHaveProperty("mass_kg")
    expect(call.uav_hardware_list[0]).toHaveProperty("receiver_aperture_m2")
  })

  it("add drone appends a row", async () => {
    stubFetch()
    render(<DesignStudio />)
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /\+ Add drone/i })).toBeInTheDocument(),
    )
    const before = screen.getAllByLabelText("mass_kg").length
    await userEvent.click(screen.getByRole("button", { name: /\+ Add drone/i }))
    const after = screen.getAllByLabelText("mass_kg").length
    expect(after).toBe(before + 1)
  })
})
