import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { ClearDDashboard } from "./ClearDDashboard"
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
    { generation: 0, nodes: 6, links: 4, objectives: [0.8, 0.5, 0.3, 0.9, 0.6, 0.2] },
    { generation: 2, nodes: 7, links: 5, objectives: [0.9, 0.6, 0.2, 1.0, 0.7, 0.1] },
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

describe("ClearDDashboard", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    window.localStorage.removeItem("aerogrid.token")
  })

  it("renders the heading and idle state on mount", () => {
    stubFetchOk()
    render(<ClearDDashboard />)
    expect(
      screen.getByRole("heading", { name: /clear-d discovery/i, level: 2 }),
    ).toBeInTheDocument()
    expect(screen.getByText(/no run yet/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /run clear-d/i })).toBeEnabled()
  })

  it("does not fetch on mount", () => {
    const fetchMock = vi.fn()
    vi.stubGlobal("fetch", fetchMock)
    render(<ClearDDashboard />)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it("runs CLEAR-D when the user clicks the button", async () => {
    const fn = stubFetchOk()
    const user = userEvent.setup()
    render(<ClearDDashboard />)
    await user.click(screen.getByRole("button", { name: /run clear-d/i }))
    await waitFor(() => expect(fn).toHaveBeenCalledTimes(1))
    const init = fn.mock.calls[0][1] as RequestInit
    const body = JSON.parse(init.body as string) as Record<string, unknown>
    expect(body.population_size).toBe(12)
    expect(body.n_generations).toBe(10)
    expect(body.use_conflict_directed).toBe(true)
  })

  it("renders the generation table with one row per generation", async () => {
    stubFetchOk()
    const user = userEvent.setup()
    render(<ClearDDashboard />)
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
    render(<ClearDDashboard />)
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
    render(<ClearDDashboard />)
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
    render(<ClearDDashboard />)
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
    render(<ClearDDashboard />)
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
    render(<ClearDDashboard />)
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
    render(<ClearDDashboard />)
    await user.click(screen.getByRole("button", { name: /run clear-d/i }))
    expect(screen.getByRole("button", { name: /running/i })).toBeDisabled()
    resolver.current?.({
      ok: true,
      status: 200,
      json: () => Promise.resolve(SAMPLE),
    } as Response)
  })

  it("sends Authorization: Bearer when a token is stored", async () => {
    window.localStorage.setItem("aerogrid.token", "test-token")
    const fn = stubFetchOk()
    const user = userEvent.setup()
    render(<ClearDDashboard />)
    await user.click(screen.getByRole("button", { name: /run clear-d/i }))
    await waitFor(() => expect(fn).toHaveBeenCalled())
    const init = fn.mock.calls[0][1] as RequestInit
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token")
  })

  it("renders the Section 21 simulation_result badge on success", async () => {
    stubFetchOk()
    const user = userEvent.setup()
    const { container } = render(<ClearDDashboard />)
    await user.click(screen.getByRole("button", { name: /run clear-d/i }))
    await waitFor(() => {
      const badges = container.querySelectorAll('[data-epistemic-tag="simulation_result"]')
      expect(badges.length).toBeGreaterThanOrEqual(1)
    })
  })
})
