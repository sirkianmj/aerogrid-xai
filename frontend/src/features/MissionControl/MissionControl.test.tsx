import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { MissionControl } from "./MissionControl"
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
    modality: "laser",
    wavelength_nm: 1064,
    transmitter_power_w: 10000,
    slant_range_m: 800000,
    atmospheric_path_m: 12000,
    elevation_deg: 45,
  },
  atmosphere: {
    transmittance: 0.88,
    visibility_km: 10,
    cloud_factor: 0.2,
    extinction_coeff_per_m: 1e-5,
    transmittance_low: 0.82,
    transmittance_high: 0.94,
    nominal_coverage: 0.9,
  },
  uavs: [
    {
      uav_id: 0,
      lat_deg: 40.8,
      lon_deg: -77.8,
      role: "UAV_Energy",
      battery_pct: 45,
      mission_priority: 0.8,
      network_centrality: 0.6,
      coverage_contribution: 0.08,
      workload_urgency: 0.7,
      thermal_headroom_c: 40,
      atmospheric_factor: 0.9,
      beam_alignment: 0.92,
      transfer_loss: 0.12,
    },
    {
      uav_id: 1,
      lat_deg: 40.85,
      lon_deg: -77.9,
      role: "UAV_Compute",
      battery_pct: 30,
      mission_priority: 0.5,
      network_centrality: 0.4,
      coverage_contribution: 0.05,
      workload_urgency: 0.3,
      thermal_headroom_c: 55,
      atmospheric_factor: 0.85,
      beam_alignment: 0.88,
      transfer_loss: 0.15,
    },
  ],
  architecture: {
    nodes: 6,
    links: 5,
    node_kinds: { UAV_Energy: 3, UAV_Compute: 2, Ground_Station: 1 },
    link_kinds: { Laser_Link: 5 },
    sat_verdict: "sat",
    n_constraints: 20,
    epsilon_bound: 3.281e-3,
    node_list: [
      { node_id: "n0", kind: "UAV_Energy", params: { battery_pct: 45 } },
      { node_id: "n1", kind: "UAV_Compute", params: { battery_pct: 30 } },
      { node_id: "n2", kind: "UAV_Energy", params: { battery_pct: 60 } },
      { node_id: "n3", kind: "UAV_Compute", params: { battery_pct: 20 } },
      { node_id: "n4", kind: "UAV_Energy", params: { battery_pct: 50 } },
      { node_id: "n5", kind: "Ground_Station", params: {} },
    ],
    link_list: [
      { link_id: "l0", kind: "Laser_Link", source_id: "n0", target_id: "n1" },
      { link_id: "l1", kind: "Laser_Link", source_id: "n0", target_id: "n2" },
      { link_id: "l2", kind: "Laser_Link", source_id: "n1", target_id: "n3" },
      { link_id: "l3", kind: "Laser_Link", source_id: "n2", target_id: "n4" },
      { link_id: "l4", kind: "Laser_Link", source_id: "n5", target_id: "n0" },
    ],
  },
  cleard: {
    population_size: 6,
    n_generations: 1,
    feasible_final: 5,
    infeasible_final: 1,
    conflict_prone_features: 3,
    use_conflict_directed: true,
    epistemic_tag: "simulation_result",
  },
  tier1: {
    selected_action: "charge_uav_1",
    decision_kind: "charge",
    score: 12.5,
    alternative_action: "charge_uav_0",
    alternative_score: 10.0,
    confidence: 0.75,
    epistemic_tag: "tier1_decision_trace",
  },
  pipeline_stages: [
    { key: "space", label: "Space", status: "wired", reason: "" },
    { key: "wireless_transmission", label: "Wireless power transmission", status: "wired", reason: "" },
    { key: "atmosphere", label: "Atmospheric transmission model", status: "partial", reason: "Kruse-Kim" },
    { key: "uav_network", label: "UAV network", status: "partial", reason: "PR 2" },
    { key: "geographic_region", label: "Geographic region", status: "partial", reason: "single" },
    { key: "tier1_decision", label: "Tier 1", status: "wired", reason: "" },
    { key: "z3_verification", label: "Z3", status: "wired", reason: "" },
    { key: "cleard_loop", label: "CLEAR-D", status: "partial", reason: "one-gen" },
    { key: "tier2_surrogates", label: "Tier 2", status: "pending", reason: "later PR" },
  ],
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

function renderWithProvider(ui: React.ReactElement) {
  return render(ui, { wrapper: MissionProvider })
}

describe("MissionControl", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    window.localStorage.removeItem("aerogrid.token")
  })

  it("renders the section heading and a loading state on mount", () => {
    stubFetchOk()
    renderWithProvider(<MissionControl />)
    expect(
      screen.getByRole("heading", { name: /mission control/i, level: 2 }),
    ).toBeInTheDocument()
    expect(screen.getByTestId("mission-loading")).toBeInTheDocument()
  })

  it("renders every pipeline stage code after load", async () => {
    stubFetchOk()
    renderWithProvider(<MissionControl />)
    for (const code of [
      "SPACE",
      "WIRELESS TX",
      "ATMOSPHERE",
      "UAV NETWORK",
      "GEOGRAPHY",
      "TIER 1",
      "Z3",
      "CLEAR-D",
      "TIER 2",
    ]) {
      await waitFor(() => expect(screen.getByTestId(`stage-${code}`)).toBeInTheDocument())
    }
  })

  it("renders the satellite name and orbit class", async () => {
    stubFetchOk()
    renderWithProvider(<MissionControl />)
    await waitFor(() => expect(screen.getByText(/ISS \(ZARYA\)/i)).toBeInTheDocument())
    expect(screen.getByText(/LEO/)).toBeInTheDocument()
  })

  it("renders the Z3 verdict and constraint count in the open detail", async () => {
    stubFetchOk()
    renderWithProvider(<MissionControl />)
    const z3 = await screen.findByTestId("stage-Z3")
    const scoped = within(z3)
    // "SAT" appears in the stage heading AND in the verdict field, by
    // design. Assert presence, not uniqueness.
    expect(scoped.getAllByText(/sat/i).length).toBeGreaterThanOrEqual(1)
    expect(scoped.getByText("20")).toBeInTheDocument() // n_constraints
  })

  it("renders the CLEAR-D feasible and infeasible counts", async () => {
    stubFetchOk()
    renderWithProvider(<MissionControl />)
    const cleard = await screen.findByTestId("stage-CLEAR-D")
    const scoped = within(cleard)
    // Feasible (5) is unique inside CLEAR-D; infeasible (1) coincides
    // with the generations value (also 1), so assert presence rather
    // than uniqueness.
    expect(scoped.getByText("5")).toBeInTheDocument()
    expect(scoped.getAllByText("1").length).toBeGreaterThanOrEqual(1)
    expect(scoped.getByText(/conflict-directed/i)).toBeInTheDocument()
  })

  it("renders the Tier 1 selected action and confidence", async () => {
    stubFetchOk()
    renderWithProvider(<MissionControl />)
    await waitFor(() =>
      expect(screen.getByText(/charge_uav_1/)).toBeInTheDocument(),
    )
    expect(screen.getByText(/75\.0%/)).toBeInTheDocument()
  })

  it("renders wired, partial, and pending status pills", async () => {
    stubFetchOk()
    renderWithProvider(<MissionControl />)
    await waitFor(() => expect(screen.getByTestId("stage-SPACE")).toBeInTheDocument())
    expect(screen.getAllByTestId("status-pill-wired").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByTestId("status-pill-partial").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByTestId("status-pill-pending").length).toBeGreaterThanOrEqual(1)
  })

  it("shows the invalid-reason warning when the satellite is invalid", async () => {
    stubFetchOk({
      ...SAMPLE,
      satellite: {
        ...SAMPLE.satellite,
        valid: false,
        invalid_reason: "TLE is 4650 days old; SGP4 drift likely",
      },
    })
    renderWithProvider(<MissionControl />)
    await waitFor(() =>
      expect(screen.getByText(/TLE is 4650 days old/)).toBeInTheDocument(),
    )
    expect(screen.getAllByTestId("status-pill-offline").length).toBeGreaterThanOrEqual(1)
  })

  it("shows an error state and a Retry button when fetch fails", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("network failure"))))
    renderWithProvider(<MissionControl />)
    await waitFor(() => expect(screen.getByTestId("mission-error")).toBeInTheDocument())
    expect(screen.getByText(/network failure/)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument()
  })

  it("re-fetches when Refresh is clicked", async () => {
    const fn = stubFetchOk()
    const user = userEvent.setup()
    renderWithProvider(<MissionControl />)
    const refresh = await screen.findByRole("button", { name: /refresh/i })
    await user.click(refresh)
    await waitFor(() => expect(fn).toHaveBeenCalledTimes(2))
  })

  it("does not send an Authorization header even when a token is present", async () => {
    window.localStorage.setItem("aerogrid.token", "some-token")
    const fn = stubFetchOk()
    renderWithProvider(<MissionControl />)
    await waitFor(() => expect(fn).toHaveBeenCalled())
    const init = fn.mock.calls[0][1] as RequestInit | undefined
    expect(init?.headers).toBeUndefined()
  })
})
