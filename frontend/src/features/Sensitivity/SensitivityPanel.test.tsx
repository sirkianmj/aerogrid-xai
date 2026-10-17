import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { SensitivityPanel } from "./SensitivityPanel"

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
    },
    state: { status: "loading" as const },
    applyConfig: () => {},
    refresh: () => {},
    reset: () => {},
    lastDiscoveryRun: null,
    setLastDiscoveryRun: () => {},
    clearLastDiscoveryRun: () => {},
  }),
}))

const SAMPLE = {
  epistemic_tag: "simulation_result",
  base_delivered_power_w: 0.32,
  base_sat_verdict: "sat",
  parameters: [
    {
      name: "uav_receiver_aperture_m2",
      base_value: 0.5,
      low_value: 0.45,
      high_value: 0.55,
      power_at_low_w: 0.29,
      power_at_high_w: 0.35,
      derivative_w_per_unit: 0.6,
      elasticity: 1.02,
      direction: "increase" as const,
    },
    {
      name: "transmitter_power_w",
      base_value: 10000,
      low_value: 9000,
      high_value: 11000,
      power_at_low_w: 0.29,
      power_at_high_w: 0.35,
      derivative_w_per_unit: 0.00003,
      elasticity: 0.98,
      direction: "increase" as const,
    },
    {
      name: "cloud_factor",
      base_value: 0,
      low_value: 0,
      high_value: 0.05,
      power_at_low_w: 0.32,
      power_at_high_w: 0.30,
      derivative_w_per_unit: -0.4,
      elasticity: null,
      direction: "decrease" as const,
    },
  ],
}

function stubFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve(SAMPLE),
      } as Response),
    ),
  )
}

describe("SensitivityPanel", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it("renders the heading", () => {
    stubFetch()
    render(<SensitivityPanel />)
    expect(
      screen.getByRole("heading", { name: /Design suggestions/i }),
    ).toBeInTheDocument()
  })

  it("auto-runs the analysis on mount and shows the ranked table", async () => {
    stubFetch()
    render(<SensitivityPanel />)
    await waitFor(() =>
      expect(
        screen.getByTestId("sensitivity-row-uav_receiver_aperture_m2"),
      ).toBeInTheDocument(),
    )
    expect(screen.getByText("transmitter_power_w")).toBeInTheDocument()
    expect(screen.getByText("cloud_factor")).toBeInTheDocument()
  })

  it("shows base delivered power and verdict after the auto-run", async () => {
    stubFetch()
    render(<SensitivityPanel />)
    await waitFor(() =>
      expect(screen.getByText(/base delivered power/i)).toBeInTheDocument(),
    )
    expect(screen.getByText(/verdict sat/i)).toBeInTheDocument()
  })

  it("re-runs on manual button press", async () => {
    const fn = vi.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve(SAMPLE),
      } as Response),
    )
    vi.stubGlobal("fetch", fn)
    render(<SensitivityPanel />)
    await waitFor(() =>
      expect(
        screen.getByTestId("sensitivity-row-uav_receiver_aperture_m2"),
      ).toBeInTheDocument(),
    )
    const callsAfterAuto = fn.mock.calls.length
    await userEvent.click(
      screen.getByRole("button", { name: /Analyse sensitivities/i }),
    )
    await waitFor(() =>
      expect(fn.mock.calls.length).toBeGreaterThan(callsAfterAuto),
    )
  })
})
