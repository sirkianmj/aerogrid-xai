import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { ClearDDashboard } from "./ClearDDashboard"
import { MissionProvider } from "../MissionControl/MissionProvider"
import type { ClearDResponse } from "./clearDApi"

const SAMPLE: ClearDResponse = {
  epistemic_tag: "simulation_result",
  population_size: 8,
  n_generations: 3,
  use_conflict_directed: true,
  generation_stats: [
    { generation: 0, n_feasible: 5, n_infeasible: 3, n_conflict_prone_features: 4 },
    { generation: 1, n_feasible: 6, n_infeasible: 2, n_conflict_prone_features: 6 },
    { generation: 2, n_feasible: 8, n_infeasible: 0, n_conflict_prone_features: 8 },
  ],
  hypervolume_history: [0.5, 0.7, 0.9],
  conflict_prone_table: [
    { kind: "link_instance", identifier: "l1", count: 3 },
    { kind: "link_type", identifier: "Microwave_Link", count: 2 },
    { kind: "node_instance", identifier: "n1", count: 1 },
  ],
  trace: [
    { generation: 0, individual_index: 0, status: "sat", n_constraints: 10, conflict_prone: [] },
    {
      generation: 0,
      individual_index: 1,
      status: "unsat",
      n_constraints: 12,
      conflict_prone: ["link_instance:l1", "link_type:Microwave_Link"],
    },
    {
      generation: 0,
      individual_index: 2,
      status: "unsat",
      n_constraints: 8,
      conflict_prone: ["node_instance:n1"],
    },
    { generation: 1, individual_index: 0, status: "sat", n_constraints: 15, conflict_prone: [] },
    {
      generation: 1,
      individual_index: 1,
      status: "unsat",
      n_constraints: 12,
      conflict_prone: ["link_instance:l1"],
    },
    { generation: 2, individual_index: 0, status: "sat", n_constraints: 9, conflict_prone: [] },
  ],
  trace_truncated: false,
  discovered: [
    {
      generation: 0,
      nodes: 6,
      links: 4,
      objectives: [0.8, 0.5, 0.3, 0.9, 0.6, 0.2],
      node_list: [],
      link_list: [],
    },
    {
      generation: 2,
      nodes: 7,
      links: 5,
      objectives: [0.9, 0.6, 0.2, 1.0, 0.7, 0.1],
      node_list: [],
      link_list: [],
    },
  ],
}

function stubFetchOk(payload: ClearDResponse = SAMPLE): ReturnType<typeof vi.fn> {
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

describe("ClearDDashboard", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    window.localStorage.removeItem("aerogrid.token")
  })

  it("renders the heading and idle state on mount", () => {
    stubFetchOk()
    renderWithProvider(<ClearDDashboard />)
    expect(
      screen.getByRole("heading", { name: /clear-d discovery/i, level: 2 }),
    ).toBeInTheDocument()
    expect(screen.getByText(/no run yet/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /run clear-d/i })).toBeEnabled()
  })

  it("does not trigger a CLEAR-D run on mount", () => {
    // The MissionProvider fetches /mission/state on mount; the panel
    // itself must not trigger a CLEAR-D run until the user clicks.
    const fetchMock = vi.fn()
    vi.stubGlobal("fetch", fetchMock)
    renderWithProvider(<ClearDDashboard />)
    const urls = fetchMock.mock.calls.map((c) => String(c[0]))
    expect(urls.some((u) => u.includes("/discovery/run"))).toBe(false)
  })

  it("runs CLEAR-D when the user clicks the button", async () => {
    const fn = stubFetchOk()
    const user = userEvent.setup()
    renderWithProvider(<ClearDDashboard />)
    await user.click(screen.getByRole("button", { name: /run clear-d/i }))
    await waitFor(() => {
      const urls = fn.mock.calls.map((c) => String(c[0]))
      expect(urls.some((u) => u.includes("/discovery/run"))).toBe(true)
    })
    const discoveryCall = fn.mock.calls.find((c) =>
      String(c[0]).includes("/discovery/run"),
    )
    const init = discoveryCall![1] as RequestInit
    const body = JSON.parse(init.body as string) as Record<string, unknown>
    // Default mission config has n_uavs=6, seed=20261014.
    expect(body.population_size).toBe(6)
    expect(body.seed).toBe(20261014)
    expect(body.use_conflict_directed).toBe(true)
  })

  it("renders the generation table with one row per generation", async () => {
    stubFetchOk()
    const user = userEvent.setup()
    renderWithProvider(<ClearDDashboard />)
    await user.click(screen.getByRole("button", { name: /run clear-d/i }))
    await waitFor(() =>
      expect(screen.getByText(/per-generation progress/i)).toBeInTheDocument(),
    )
    const rows = document.querySelectorAll("tbody tr")
    // Generation table has 3 rows; conflict table has 3 rows too.
    expect(rows.length).toBeGreaterThanOrEqual(3)
  })

  it("renders the conflict-prone features with counts", async () => {
    stubFetchOk()
    const user = userEvent.setup()
    renderWithProvider(<ClearDDashboard />)
    await user.click(screen.getByRole("button", { name: /run clear-d/i }))
    await waitFor(() =>
      expect(screen.getByText(/conflict-prone grammar features/i)).toBeInTheDocument(),
    )
    expect(screen.getByText("Microwave_Link")).toBeInTheDocument()
    expect(screen.getByText("link_instance")).toBeInTheDocument()
    expect(screen.getByText("node_instance")).toBeInTheDocument()
  })

  it("renders one trace line per UNSAT event and lists its mapped features", async () => {
    stubFetchOk()
    const user = userEvent.setup()
    renderWithProvider(<ClearDDashboard />)
    await user.click(screen.getByRole("button", { name: /run clear-d/i }))
    await waitFor(() =>
      expect(screen.getByText(/attribution trace — unsat events/i)).toBeInTheDocument(),
    )
    // Three UNSAT events in SAMPLE. Each appears with a "gen N · idx M" prefix.
    expect(screen.getAllByText(/gen 0 · idx 1/).length).toBe(1)
    expect(screen.getAllByText(/gen 0 · idx 2/).length).toBe(1)
    expect(screen.getAllByText(/gen 1 · idx 1/).length).toBe(1)
    // Mapped features appear as inline tags in the trace
    expect(screen.getAllByText("link_instance:l1").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("link_type:Microwave_Link").length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText("node_instance:n1").length).toBeGreaterThanOrEqual(1)
  })

  it("renders SAT and UNSAT totals", async () => {
    stubFetchOk()
    const user = userEvent.setup()
    renderWithProvider(<ClearDDashboard />)
    await user.click(screen.getByRole("button", { name: /run clear-d/i }))
    await waitFor(() =>
      expect(screen.getByTestId("stat-sat-value")).toBeInTheDocument(),
    )
    // SAMPLE has 3 SAT and 3 UNSAT. Query by testid, not by text, so
    // that "SAT classifications" / "UNSAT classifications" substring
    // collisions cannot occur.
    expect(screen.getByTestId("stat-sat-value")).toHaveTextContent("3")
    expect(screen.getByTestId("stat-unsat-value")).toHaveTextContent("3")
  })

  it("shows an error state when the backend returns 400", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 400,
          json: () => Promise.resolve({ detail: "max_nodes must be >= min_nodes" }),
        } as Response),
      ),
    )
    const user = userEvent.setup()
    renderWithProvider(<ClearDDashboard />)
    await user.click(screen.getByRole("button", { name: /run clear-d/i }))
    await waitFor(() =>
      expect(
        screen.getByText(/error \(400\): max_nodes must be >= min_nodes/i),
      ).toBeInTheDocument(),
    )
  })

  it("shows a network error when fetch rejects", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("network failure"))))
    const user = userEvent.setup()
    renderWithProvider(<ClearDDashboard />)
    await user.click(screen.getByRole("button", { name: /run clear-d/i }))
    await waitFor(() => expect(screen.getByText(/network failure/i)).toBeInTheDocument())
  })

  it("disables the button while the run is in flight", async () => {
    const resolver: { current: ((r: Response) => void) | null } = { current: null }
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise<Response>((res) => {
            resolver.current = res
          }),
      ),
    )
    const user = userEvent.setup()
    renderWithProvider(<ClearDDashboard />)
    await user.click(screen.getByRole("button", { name: /run clear-d/i }))
    expect(screen.getByRole("button", { name: /running/i })).toBeDisabled()
    resolver.current?.({
      ok: true,
      status: 200,
      json: () => Promise.resolve(SAMPLE),
    } as Response)
  })

  it("sends Authorization: Bearer on the CLEAR-D run when a token is stored", async () => {
    window.localStorage.setItem("aerogrid.token", "test-token")
    const fn = stubFetchOk()
    const user = userEvent.setup()
    renderWithProvider(<ClearDDashboard />)
    await user.click(screen.getByRole("button", { name: /run clear-d/i }))
    await waitFor(() => {
      const urls = fn.mock.calls.map((c) => String(c[0]))
      expect(urls.some((u) => u.includes("/discovery/run"))).toBe(true)
    })
    const discoveryCall = fn.mock.calls.find((c) =>
      String(c[0]).includes("/discovery/run"),
    )
    const init = discoveryCall![1] as RequestInit
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token")
  })

  it("renders the Section 21 simulation_result badge on success", async () => {
    stubFetchOk()
    const user = userEvent.setup()
    const { container } = renderWithProvider(<ClearDDashboard />)
    await user.click(screen.getByRole("button", { name: /run clear-d/i }))
    await waitFor(() => {
      const badges = container.querySelectorAll('[data-epistemic-tag="simulation_result"]')
      expect(badges.length).toBeGreaterThanOrEqual(1)
    })
  })

  it("builds its run request from the mission config", async () => {
    // The provider fetches /mission/state on mount, then the CLEAR-D
    // run posts to /discovery/run. Stub both so we can inspect the POST
    // body. The default mission config has n_uavs=6 and seed=20261014,
    // so the CLEAR-D run must use population_size>=4 (6 here) and
    // seed=20261014.
    const fn = vi.fn()
    fn.mockImplementation((url: string) => {
      if (String(url).startsWith("/api/mission/state")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () =>
            Promise.resolve({
              // minimal MissionState — the ClearDDashboard panel does
              // not read from the mission state, so a stub suffices.
              t_utc: "2014-01-20T22:23:04+00:00",
              seed: 20261014,
              satellite: {
                key: "iss", name: "ISS (ZARYA)", orbit_class: "LEO",
                tle_epoch_utc: "2014-01-20T22:23:04+00:00", tle_age_seconds: 0,
                valid: true, invalid_reason: "", period_seconds: 5580,
                lat_deg: 0, lon_deg: 0, alt_km: 400, in_eclipse: false,
                epistemic_tag: "validated_physical_model",
              },
              ground_station: { name: "GS", lat_deg: 0, lon_deg: 0, alt_m: 0 },
              transmission: { modality: "offline", wavelength_nm: 1064,
                transmitter_power_w: 10000, slant_range_m: 0,
                atmospheric_path_m: 0, elevation_deg: -90 },
              atmosphere: { transmittance: 0, visibility_km: 10,
                cloud_factor: 0.2, extinction_coeff_per_m: 1e-5 },
              uavs: [],
              architecture: { nodes: 0, links: 0, node_kinds: {}, link_kinds: {},
                sat_verdict: "sat", n_constraints: 0, epsilon_bound: 0,
                node_list: [], link_list: [] },
              cleard: { population_size: 0, n_generations: 0, feasible_final: 0,
                infeasible_final: 0, conflict_prone_features: 0,
                use_conflict_directed: true, epistemic_tag: "simulation_result" },
              tier1: { selected_action: "", decision_kind: "charge", score: 0,
                alternative_action: "", alternative_score: 0, confidence: 1,
                epistemic_tag: "tier1_decision_trace" },
              pipeline_stages: [],
              epistemic_tag: "simulation_result",
            }),
        } as Response)
      }
      // /discovery/run
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve(SAMPLE),
      } as Response)
    })
    vi.stubGlobal("fetch", fn)

    const user = userEvent.setup()
    renderWithProvider(<ClearDDashboard />)
    await user.click(screen.getByRole("button", { name: /run clear-d/i }))
    await waitFor(() => {
      const urls = fn.mock.calls.map((c) => String(c[0]))
      expect(urls.some((u) => u.includes("/discovery/run"))).toBe(true)
    })
    const discoveryCall = fn.mock.calls.find((c) =>
      String(c[0]).includes("/discovery/run"),
    )
    expect(discoveryCall).toBeDefined()
    const init = discoveryCall![1] as RequestInit
    const body = JSON.parse(init.body as string) as Record<string, unknown>
    // Default mission config: n_uavs=6, seed=20261014.
    expect(body.population_size).toBe(6)
    expect(body.seed).toBe(20261014)
  })
})
