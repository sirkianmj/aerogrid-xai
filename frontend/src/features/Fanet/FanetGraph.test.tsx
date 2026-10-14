import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { FanetGraph } from "./FanetGraph"
import { MissionProvider } from "../MissionControl/MissionProvider"
import type { MissionState } from "../MissionControl/missionApi"

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
  },
  uavs: [],
  architecture: {
    nodes: 4,
    links: 3,
    node_kinds: { UAV_Energy: 2, UAV_Compute: 1, Ground_Station: 1 },
    link_kinds: { Laser_Link: 2, Microwave_Link: 1 },
    sat_verdict: "sat",
    n_constraints: 20,
    epsilon_bound: 3.281e-3,
    node_list: [
      { node_id: "n0", kind: "UAV_Energy", params: { battery_pct: 45 } },
      { node_id: "n1", kind: "UAV_Compute", params: { battery_pct: 30 } },
      { node_id: "n2", kind: "UAV_Energy", params: { battery_pct: 60 } },
      { node_id: "n3", kind: "Ground_Station", params: {} },
    ],
    link_list: [
      { link_id: "l0", kind: "Laser_Link", source_id: "n0", target_id: "n1" },
      { link_id: "l1", kind: "Microwave_Link", source_id: "n0", target_id: "n2" },
      { link_id: "l2", kind: "Laser_Link", source_id: "n3", target_id: "n0" },
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

function renderWithProvider(ui: React.ReactElement) {
  return render(ui, { wrapper: MissionProvider })
}

describe("FanetGraph", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    window.localStorage.removeItem("aerogrid.token")
  })

  it("renders the heading and a loading state on mount", () => {
    stubFetchOk()
    renderWithProvider(<FanetGraph />)
    expect(
      screen.getByRole("heading", { name: /uav network \(fanet\)/i, level: 2 }),
    ).toBeInTheDocument()
    expect(screen.getByTestId("fanet-loading")).toBeInTheDocument()
  })

  it("fetches the mission state on mount, with the config as query params", async () => {
    const fn = stubFetchOk()
    renderWithProvider(<FanetGraph />)
    await waitFor(() => expect(fn).toHaveBeenCalledTimes(1))
    const url = String(fn.mock.calls[0][0])
    // The provider appends the mission configuration as query params,
    // so the exact URL is not fixed. Assert the path prefix and that
    // the config is present.
    expect(url.startsWith("/api/mission/state?")).toBe(true)
    expect(url).toContain("satellite_key=iss")
    expect(url).toContain("transmitter_power_w=10000")
  })

  it("renders one SVG node per entry in node_list", async () => {
    stubFetchOk()
    renderWithProvider(<FanetGraph />)
    await waitFor(() => expect(screen.getByTestId("fanet-svg")).toBeInTheDocument())
    for (const id of ["n0", "n1", "n2", "n3"]) {
      expect(screen.getByTestId(`fanet-node-${id}`)).toBeInTheDocument()
    }
  })

  it("renders one SVG edge per entry in link_list", async () => {
    stubFetchOk()
    renderWithProvider(<FanetGraph />)
    await waitFor(() => expect(screen.getByTestId("fanet-svg")).toBeInTheDocument())
    for (const id of ["l0", "l1", "l2"]) {
      expect(screen.getByTestId(`fanet-edge-${id}`)).toBeInTheDocument()
    }
  })

  it("tags each node with its kind as a data attribute", async () => {
    stubFetchOk()
    renderWithProvider(<FanetGraph />)
    const n0 = await screen.findByTestId("fanet-node-n0")
    expect(n0.getAttribute("data-node-kind")).toBe("UAV_Energy")
    const n1 = screen.getByTestId("fanet-node-n1")
    expect(n1.getAttribute("data-node-kind")).toBe("UAV_Compute")
    const n3 = screen.getByTestId("fanet-node-n3")
    expect(n3.getAttribute("data-node-kind")).toBe("Ground_Station")
  })

  it("tags each edge with its link kind", async () => {
    stubFetchOk()
    renderWithProvider(<FanetGraph />)
    const l0 = await screen.findByTestId("fanet-edge-l0")
    expect(l0.getAttribute("data-link-kind")).toBe("Laser_Link")
    const l1 = screen.getByTestId("fanet-edge-l1")
    expect(l1.getAttribute("data-link-kind")).toBe("Microwave_Link")
  })

  it("shows the summary row with node and link counts", async () => {
    stubFetchOk()
    renderWithProvider(<FanetGraph />)
    await waitFor(() => expect(screen.getByTestId("fanet-svg")).toBeInTheDocument())
    expect(screen.getByText(/4 nodes/)).toBeInTheDocument()
    expect(screen.getByText(/3 links/)).toBeInTheDocument()
    expect(screen.getByText(/verdict: sat/i)).toBeInTheDocument()
  })

  it("selects a node on click and shows the inspector", async () => {
    stubFetchOk()
    const user = userEvent.setup()
    renderWithProvider(<FanetGraph />)
    const n0 = await screen.findByTestId("fanet-node-n0")
    await user.click(n0)
    const inspector = await screen.findByTestId("fanet-inspector")
    expect(within(inspector).getByText(/UAV_Energy/)).toBeInTheDocument()
    expect(within(inspector).getByText(/45.00/)).toBeInTheDocument()
  })

  it("inspector lists the links connected to the selected node", async () => {
    stubFetchOk()
    const user = userEvent.setup()
    renderWithProvider(<FanetGraph />)
    const n0 = await screen.findByTestId("fanet-node-n0")
    await user.click(n0)
    const inspector = await screen.findByTestId("fanet-inspector")
    expect(within(inspector).getByText(/n0 → n1/)).toBeInTheDocument()
    expect(within(inspector).getByText(/n0 → n2/)).toBeInTheDocument()
    expect(within(inspector).getByText(/n3 → n0/)).toBeInTheDocument()
  })

  it("deselects a node on second click and hides the inspector", async () => {
    stubFetchOk()
    const user = userEvent.setup()
    renderWithProvider(<FanetGraph />)
    const n0 = await screen.findByTestId("fanet-node-n0")
    await user.click(n0)
    expect(await screen.findByTestId("fanet-inspector")).toBeInTheDocument()
    await user.click(n0)
    await waitFor(() =>
      expect(screen.queryByTestId("fanet-inspector")).not.toBeInTheDocument(),
    )
  })

  it("shows an error state when fetch rejects", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("network failure"))))
    renderWithProvider(<FanetGraph />)
    await waitFor(() => expect(screen.getByTestId("fanet-error")).toBeInTheDocument())
    expect(screen.getByText(/network failure/)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument()
  })

  it("renders the Section 21 simulation_result badge on success", async () => {
    stubFetchOk()
    const { container } = renderWithProvider(<FanetGraph />)
    await waitFor(() => {
      const badges = container.querySelectorAll('[data-epistemic-tag="simulation_result"]')
      expect(badges.length).toBeGreaterThanOrEqual(1)
    })
  })

  it("renders the artefact sub-label on success", async () => {
    stubFetchOk()
    renderWithProvider(<FanetGraph />)
    await waitFor(() =>
      expect(screen.getByText(/artefact: fanet_architecture/i)).toBeInTheDocument(),
    )
  })
})
