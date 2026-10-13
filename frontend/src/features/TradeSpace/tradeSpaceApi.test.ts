import { afterEach, describe, expect, it, vi } from "vitest"
import {
  TradeSpaceApiError,
  runTradeSpace,
  type TradeSpaceResponse,
} from "./tradeSpaceApi"

const SAMPLE: TradeSpaceResponse = {
  epistemic_tag: "simulation_result",
  objective_labels: ["C", "R", "E", "N", "T", "U"],
  negative_objectives: [5],
  n_pareto: 2,
  n_final_population: 10,
  hypervolume_history: [1.0, 1.2, 1.3],
  pareto_front: [
    { objectives: [0.8, 0.5, 0.1, 0.9, 0.5, 0.3], generation: 2, node_count: 5, link_count: 3 },
    { objectives: [0.6, 0.7, 0.2, 0.8, 0.6, 0.2], generation: 2, node_count: 7, link_count: 4 },
  ],
}

function stubFetch(body: unknown, ok = true, status = 200) {
  return vi.fn((_url: string, _init?: RequestInit) =>
    Promise.resolve({
      ok,
      status,
      json: () => Promise.resolve(body),
    } as Response),
  )
}

describe("runTradeSpace", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it("POSTs to /api/tradespace/run and returns the body", async () => {
    const fetchMock = stubFetch(SAMPLE)
    vi.stubGlobal("fetch", fetchMock)
    const out = await runTradeSpace({ population_size: 10, n_generations: 3 })
    expect(fetchMock.mock.calls[0]![0]).toBe("/api/tradespace/run")
    const init = fetchMock.mock.calls[0]![1] as RequestInit
    expect(init.method).toBe("POST")
    const body = JSON.parse(init.body as string) as Record<string, unknown>
    expect(body.population_size).toBe(10)
    expect(body.n_generations).toBe(3)
    expect(out).toEqual(SAMPLE)
  })

  it("defaults to an empty request body when no options are given", async () => {
    const fetchMock = stubFetch(SAMPLE)
    vi.stubGlobal("fetch", fetchMock)
    await runTradeSpace()
    const init = fetchMock.mock.calls[0]![1] as RequestInit
    expect(init.body).toBe("{}")
  })

  it("forwards the abort signal", async () => {
    const fetchMock = stubFetch(SAMPLE)
    vi.stubGlobal("fetch", fetchMock)
    const ctrl = new AbortController()
    await runTradeSpace({}, ctrl.signal)
    expect((fetchMock.mock.calls[0]![1] as RequestInit).signal).toBe(ctrl.signal)
  })

  it("raises TradeSpaceApiError with the backend detail on 400", async () => {
    vi.stubGlobal("fetch", stubFetch({ detail: "max_nodes must be >= min_nodes" }, false, 400))
    await expect(runTradeSpace()).rejects.toMatchObject({
      name: "TradeSpaceApiError",
      status: 400,
      detail: "max_nodes must be >= min_nodes",
    })
  })

  it("falls back to an HTTP status when the error body is not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 500,
          json: () => Promise.reject(new Error("not json")),
        } as Response),
      ),
    )
    try {
      await runTradeSpace()
      throw new Error("expected the call to reject")
    } catch (err) {
      expect(err).toBeInstanceOf(TradeSpaceApiError)
      expect((err as TradeSpaceApiError).detail).toBe("HTTP 500")
    }
  })
})
