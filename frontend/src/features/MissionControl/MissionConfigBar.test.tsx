import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { MissionConfigBar } from "./MissionConfigBar"
import { MissionProvider } from "./MissionProvider"
import type { MissionState } from "./missionApi"

const SAMPLE: MissionState = {
  t_utc: "2014-01-20T22:23:04+00:00",
  seed: 20261014,
  satellite: {
    key: "iss",
    name: "ISS (ZARYA)",
    orbit_class: "LEO",
    tle_epoch_utc: "2014-01-20T22:23:04+00:00",
    tle_age_seconds: 0,
    valid: true,
    invalid_reason: "",
    period_seconds: 5580,
    lat_deg: 15.5,
    lon_deg: -30.2,
    alt_km: 423.3,
    in_eclipse: false,
    epistemic_tag: "validated_physical_model",
  },
  ground_station: {
    name: "Ground Station Alpha",
    lat_deg: 40.798,
    lon_deg: -77.86,
    alt_m: 350,
  },
  transmission: {
    modality: "offline",
    wavelength_nm: 1064,
    transmitter_power_w: 10000,
    slant_range_m: 0,
    atmospheric_path_m: 0,
    elevation_deg: -10,
  },
  atmosphere: {
    transmittance: 0,
    visibility_km: 10,
    cloud_factor: 0.2,
    extinction_coeff_per_m: 1e-5,
    transmittance_low: null,
    transmittance_high: null,
    nominal_coverage: null,
  },
  uavs: [],
  architecture: {
    nodes: 0,
    links: 0,
    node_kinds: {},
    link_kinds: {},
    sat_verdict: "sat",
    n_constraints: 0,
    epsilon_bound: 0,
    node_list: [],
    link_list: [],
  },
  cleard: {
    population_size: 6,
    n_generations: 1,
    feasible_final: 0,
    infeasible_final: 0,
    conflict_prone_features: 0,
    use_conflict_directed: true,
    epistemic_tag: "simulation_result",
  },
  tier1: {
    selected_action: "",
    decision_kind: "charge",
    score: 0,
    alternative_action: "",
    alternative_score: 0,
    confidence: 1,
    epistemic_tag: "tier1_decision_trace",
  },
  pipeline_stages: [],
  epistemic_tag: "simulation_result",
}

function stubFetchOk(payload: MissionState = SAMPLE): ReturnType<typeof vi.fn> {
  const fn = vi.fn(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve(payload),
    } as Response),
  )
  vi.stubGlobal("fetch", fn)
  return fn
}

function renderWithProvider() {
  return render(<MissionConfigBar />, { wrapper: MissionProvider })
}

describe("MissionConfigBar", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    window.localStorage.removeItem("aerogrid.token")
  })

  it("renders the config bar heading and all nine inputs", () => {
    stubFetchOk()
    renderWithProvider()
    expect(
      screen.getByRole("heading", { name: /mission configuration/i }),
    ).toBeInTheDocument()
    expect(screen.getByLabelText(/satellite key/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/ground latitude/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/ground longitude/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/transmitter power watts/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/uav count/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/^seed$/i)).toBeInTheDocument()
  })

  it("Apply button is disabled when the draft is not dirty", () => {
    stubFetchOk()
    renderWithProvider()
    expect(screen.getByTestId("mission-apply")).toBeDisabled()
    expect(screen.queryByTestId("mission-dirty")).not.toBeInTheDocument()
  })

  it("typing a new transmitter power enables Apply and shows the dirty badge", async () => {
    stubFetchOk()
    const user = userEvent.setup()
    renderWithProvider()
    const input = screen.getByLabelText(/transmitter power watts/i)
    await user.clear(input)
    await user.type(input, "50000")
    await waitFor(() => expect(screen.getByTestId("mission-apply")).toBeEnabled())
    expect(screen.getByTestId("mission-dirty")).toBeInTheDocument()
  })

  it("Apply refetches with the new power value", async () => {
    const fn = stubFetchOk()
    const user = userEvent.setup()
    renderWithProvider()
    // Initial fetch on mount
    await waitFor(() => expect(fn).toHaveBeenCalledTimes(1))
    expect(String(fn.mock.calls[0][0])).toContain("transmitter_power_w=10000")

    const input = screen.getByLabelText(/transmitter power watts/i)
    await user.clear(input)
    await user.type(input, "50000")
    await user.click(screen.getByTestId("mission-apply"))

    await waitFor(() => expect(fn).toHaveBeenCalledTimes(2))
    expect(String(fn.mock.calls[1][0])).toContain("transmitter_power_w=50000")
  })

  it("rejects an out-of-range latitude and disables Apply", async () => {
    stubFetchOk()
    const user = userEvent.setup()
    renderWithProvider()
    const input = screen.getByLabelText(/ground latitude/i)
    await user.clear(input)
    await user.type(input, "200")
    await waitFor(() =>
      expect(screen.getByText(/latitude must be in/i)).toBeInTheDocument(),
    )
    expect(screen.getByTestId("mission-apply")).toBeDisabled()
  })

  it("rejects a non-positive transmitter power and disables Apply", async () => {
    stubFetchOk()
    const user = userEvent.setup()
    renderWithProvider()
    const input = screen.getByLabelText(/transmitter power watts/i)
    await user.clear(input)
    await user.type(input, "0")
    await waitFor(() =>
      expect(screen.getByText(/power must be > 0/i)).toBeInTheDocument(),
    )
    expect(screen.getByTestId("mission-apply")).toBeDisabled()
  })

  it("Reset restores the defaults and refetches", async () => {
    const fn = stubFetchOk()
    const user = userEvent.setup()
    renderWithProvider()
    await waitFor(() => expect(fn).toHaveBeenCalledTimes(1))

    // Change power, apply
    const input = screen.getByLabelText(/transmitter power watts/i)
    await user.clear(input)
    await user.type(input, "50000")
    await user.click(screen.getByTestId("mission-apply"))
    await waitFor(() => expect(fn).toHaveBeenCalledTimes(2))

    // Reset; the provider goes back to defaults, which triggers a fresh fetch
    await user.click(screen.getByTestId("mission-reset"))
    await waitFor(() => {
      const last = String(fn.mock.calls[fn.mock.calls.length - 1][0])
      expect(last).toContain("transmitter_power_w=10000")
    })
  })

  it("enabling the custom-orbit checkbox shows the seven element inputs", async () => {
    renderWithProvider()
    const user = userEvent.setup()
    const toggle = screen.getByRole("checkbox", { name: /Enable custom orbit/i })
    expect(toggle).not.toBeChecked()
    await user.click(toggle)
    expect(toggle).toBeChecked()
    for (const name of [
      "Epoch (UTC)",
      "a (km)",
      "e",
      "i (deg)",
      "RAAN (deg)",
      "argp (deg)",
      "M0 (deg)",
    ]) {
      expect(screen.getByLabelText(name)).toBeInTheDocument()
    }
  })

  it("disabling the custom-orbit checkbox clears the elements", async () => {
    renderWithProvider()
    const user = userEvent.setup()
    const toggle = screen.getByRole("checkbox", { name: /Enable custom orbit/i })
    await user.click(toggle)
    expect(toggle).toBeChecked()
    await user.click(toggle)
    expect(toggle).not.toBeChecked()
    // The element inputs disappear when elements are cleared.
    expect(screen.queryByLabelText("a (km)")).not.toBeInTheDocument()
  })

})
