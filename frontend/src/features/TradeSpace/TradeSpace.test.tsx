import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { TradeSpace } from "./TradeSpace"
import type { TradeSpaceResponse } from "./tradeSpaceApi"

const SAMPLE: TradeSpaceResponse = {
  epistemic_tag: "simulation_result",
  objective_labels: ["C", "R", "E", "N", "T", "U"],
  negative_objectives: [5],
  n_pareto: 3,
  n_final_population: 20,
  hypervolume_history: [0.5, 0.8, 1.0],
  pareto_front: [
    { objectives: [0.8, 0.5, 0.1, 0.9, 0.5, 0.3], generation: 2, node_count: 5, link_count: 3 },
    { objectives: [0.6, 0.7, 0.2, 0.8, 0.6, 0.2], generation: 2, node_count: 7, link_count: 4 },
    { objectives: [0.5, 0.6, 0.3, 0.7, 0.4, 0.1], generation: 3, node_count: 6, link_count: 3 },
  ],
}

function stubFetchOk(): ReturnType<typeof vi.fn> {
  const fn = vi.fn(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve(SAMPLE),
    } as Response),
  )
  vi.stubGlobal("fetch", fn)
  return fn
}

describe("TradeSpace", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it("renders the panel heading and an idle prompt", () => {
    render(<TradeSpace />)
    expect(
      screen.getByRole("heading", { name: /trade space/i, level: 2 }),
    ).toBeInTheDocument()
    expect(screen.getByText(/no run yet/i)).toBeInTheDocument()
  })

  it("does not fetch on mount", () => {
    const fetchMock = vi.fn()
    vi.stubGlobal("fetch", fetchMock)
    render(<TradeSpace />)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it("runs NSGA-II when the user clicks Run", async () => {
    stubFetchOk()
    const user = userEvent.setup()
    render(<TradeSpace />)
    await user.click(screen.getByRole("button", { name: /run nsga-ii/i }))
    // The string "3 Pareto points" appears in two places: the info
    // span above the chart and the legend inside the chart SVG. Both
    // are correct; the test asserts the run produced at least one.
    await waitFor(() => {
      expect(screen.getAllByText(/3 Pareto points/).length).toBeGreaterThanOrEqual(1)
    })
  })

  it("shows the final population size and elapsed time", async () => {
    stubFetchOk()
    const user = userEvent.setup()
    render(<TradeSpace />)
    await user.click(screen.getByRole("button", { name: /run nsga-ii/i }))
    await waitFor(() => {
      expect(screen.getByText(/20 final population/)).toBeInTheDocument()
    })
    expect(screen.getByText(/elapsed \d+ ms/)).toBeInTheDocument()
  })

  it("renders the Section 21 simulation_result badge", async () => {
    stubFetchOk()
    const user = userEvent.setup()
    const { container } = render(<TradeSpace />)
    await user.click(screen.getByRole("button", { name: /run nsga-ii/i }))
    await waitFor(() => {
      const badges = container.querySelectorAll('[data-epistemic-tag="simulation_result"]')
      expect(badges.length).toBeGreaterThanOrEqual(1)
    })
  })

  it("renders the parallel-coordinates plot with one polyline per Pareto point", async () => {
    stubFetchOk()
    const user = userEvent.setup()
    const { container } = render(<TradeSpace />)
    await user.click(screen.getByRole("button", { name: /run nsga-ii/i }))
    await waitFor(() => {
      const polylines = container.querySelectorAll("polyline")
      expect(polylines.length).toBe(SAMPLE.pareto_front.length)
    })
  })

  it("renders the Pareto table with one row per point", async () => {
    stubFetchOk()
    const user = userEvent.setup()
    render(<TradeSpace />)
    await user.click(screen.getByRole("button", { name: /run nsga-ii/i }))
    await waitFor(() => {
      expect(screen.getByText(/pareto front \(3\)/i)).toBeInTheDocument()
    })
    // The Pareto table has 3 rows; the hypervolume strip has no rows.
    const rows = document.querySelectorAll("tbody tr")
    expect(rows.length).toBe(3)
  })

  it("shows the artefact sub-label", async () => {
    stubFetchOk()
    const user = userEvent.setup()
    render(<TradeSpace />)
    await user.click(screen.getByRole("button", { name: /run nsga-ii/i }))
    await waitFor(() => {
      expect(screen.getByText(/artefact: tradespace_pareto_front/i)).toBeInTheDocument()
    })
  })

  it("shows an error message when the backend returns 400", async () => {
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
    render(<TradeSpace />)
    await user.click(screen.getByRole("button", { name: /run nsga-ii/i }))
    await waitFor(() => {
      expect(screen.getByText(/error \(400\): max_nodes must be >= min_nodes/i)).toBeInTheDocument()
    })
  })

  it("shows an error message when the fetch fails", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("network failure"))))
    const user = userEvent.setup()
    render(<TradeSpace />)
    await user.click(screen.getByRole("button", { name: /run nsga-ii/i }))
    await waitFor(() => {
      expect(screen.getByText(/network failure/i)).toBeInTheDocument()
    })
  })

  it("disables the button while the run is in flight", async () => {
    // A ref object rather than a bare variable: TypeScript's control
    // flow analysis does not see the assignment inside the promise
    // executor, and would otherwise narrow the variable to never.
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
    render(<TradeSpace />)
    await user.click(screen.getByRole("button", { name: /run nsga-ii/i }))
    expect(screen.getByRole("button", { name: /running/i })).toBeDisabled()
    resolver.current?.({
      ok: true,
      status: 200,
      json: () => Promise.resolve(SAMPLE),
    } as Response)
  })


  it("sends Authorization: Bearer when a token is present", async () => {
    window.localStorage.setItem("aerogrid.token", "test-token")
    try {
      const fn = stubFetchOk()
      const user = userEvent.setup()
      render(<TradeSpace />)
      await user.click(screen.getByRole("button", { name: /run nsga-ii/i }))
      await waitFor(() => expect(fn).toHaveBeenCalled())
      const init = fn.mock.calls[0][1] as RequestInit
      expect((init.headers as Record<string, string>).Authorization).toBe(
        "Bearer test-token",
      )
    } finally {
      window.localStorage.removeItem("aerogrid.token")
    }
  })

  it("omits Authorization when no token is stored", async () => {
    window.localStorage.removeItem("aerogrid.token")
    const fn = stubFetchOk()
    const user = userEvent.setup()
    render(<TradeSpace />)
    await user.click(screen.getByRole("button", { name: /run nsga-ii/i }))
    await waitFor(() => expect(fn).toHaveBeenCalled())
    const init = fn.mock.calls[0][1] as RequestInit
    expect((init.headers as Record<string, string>).Authorization).toBeUndefined()
  })
})
