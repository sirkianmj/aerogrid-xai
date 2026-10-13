import { afterEach, describe, expect, it, vi } from "vitest"
import {
  DigitalTwinApiError,
  postDiscrepancy,
  postState,
  postTrajectory,
  type DiscrepancyResponse,
  type StateResponse,
  type TrajectoryResponse,
} from "./digitalTwinApi"

const STATE_SAMPLE: StateResponse = {
  epistemic_tag: "simulation_result",
  incident_power_w: 20,
  airflow_m_per_s: 5,
  ambient_temperature_k: 298.15,
  steady_state: { t_plc_k: 360, t_te_k: 330, t_plc_c: 86.85, t_te_c: 56.85 },
  thermal_runaway_power_w: 60,
  safety_margin_w: 40,
  safety_margin_fraction: 0.667,
  receiver_efficiency: 0.0015,
  receiver_efficiency_source: "eta_total",
}

const TRAJ_SAMPLE: TrajectoryResponse = {
  epistemic_tag: "simulation_result",
  t_end_s: 600,
  n_samples: 2,
  samples: [
    { time_s: 0, t_plc_k: 298.15, t_te_k: 298.15 },
    { time_s: 600, t_plc_k: 350.0, t_te_k: 320.0 },
  ],
}

const DISC_SAMPLE: DiscrepancyResponse = {
  epistemic_tag: "simulation_result",
  n_observations: 1,
  n_triggered: 1,
  triggered_fields: ["temperature_k"],
  should_refine: true,
  threshold_summary: {
    temperature_k: { absolute: 2.0, relative: null },
  },
  records: [
    {
      field_name: "temperature_k",
      predicted: 320.0,
      observed: 325.0,
      absolute_error: 5.0,
      relative_error: 0.015625,
      triggered: true,
      step: 0,
    },
  ],
}

function stubPost(body: unknown, ok = true, status = 200) {
  return vi.fn((_url: string, _init?: RequestInit) =>
    Promise.resolve({
      ok,
      status,
      json: () => Promise.resolve(body),
    } as Response),
  )
}

describe("postState", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it("POSTs the request to /api/digital-twin/state and returns the body", async () => {
    const fetchMock = stubPost(STATE_SAMPLE)
    vi.stubGlobal("fetch", fetchMock)
    const out = await postState({
      incident_power_w: 20,
      airflow_m_per_s: 5,
      ambient_temperature_k: 298.15,
    })
    expect(fetchMock.mock.calls[0]![0]).toBe("/api/digital-twin/state")
    expect((fetchMock.mock.calls[0]![1] as RequestInit).method).toBe("POST")
    expect(out).toEqual(STATE_SAMPLE)
  })

  it("raises DigitalTwinApiError on non-200", async () => {
    vi.stubGlobal("fetch", stubPost({ detail: "broken" }, false, 500))
    await expect(
      postState({ incident_power_w: 20, airflow_m_per_s: 5, ambient_temperature_k: 298.15 }),
    ).rejects.toMatchObject({ name: "DigitalTwinApiError", status: 500, detail: "broken" })
  })

  it("falls back to an HTTP status when the body is not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 503,
          json: () => Promise.reject(new Error("not json")),
        } as Response),
      ),
    )
    try {
      await postState({ incident_power_w: 20, airflow_m_per_s: 5, ambient_temperature_k: 298.15 })
      throw new Error("expected the call to reject")
    } catch (err) {
      expect(err).toBeInstanceOf(DigitalTwinApiError)
      expect((err as DigitalTwinApiError).detail).toBe("HTTP 503")
    }
  })
})

describe("postTrajectory", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it("POSTs to /api/digital-twin/trajectory", async () => {
    const fetchMock = stubPost(TRAJ_SAMPLE)
    vi.stubGlobal("fetch", fetchMock)
    const out = await postTrajectory({
      incident_power_w: 20,
      airflow_m_per_s: 5,
      ambient_temperature_k: 298.15,
      t_end_s: 600,
      n_samples: 2,
    })
    expect(fetchMock.mock.calls[0]![0]).toBe("/api/digital-twin/trajectory")
    expect(out.samples).toHaveLength(2)
  })

  it("forwards the abort signal", async () => {
    const fetchMock = stubPost(TRAJ_SAMPLE)
    vi.stubGlobal("fetch", fetchMock)
    const ctrl = new AbortController()
    await postTrajectory(
      { incident_power_w: 20, airflow_m_per_s: 5, ambient_temperature_k: 298.15, t_end_s: 600 },
      ctrl.signal,
    )
    expect((fetchMock.mock.calls[0]![1] as RequestInit).signal).toBe(ctrl.signal)
  })
})

describe("postDiscrepancy", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it("wraps the observations array in the request body", async () => {
    const fetchMock = stubPost(DISC_SAMPLE)
    vi.stubGlobal("fetch", fetchMock)
    await postDiscrepancy([
      { field_name: "temperature_k", predicted: 320.0, observed: 325.0 },
    ])
    const init = fetchMock.mock.calls[0]![1] as RequestInit
    const body = JSON.parse(init.body as string) as { observations: unknown[] }
    expect(body.observations).toHaveLength(1)
  })

  it("returns the full discrepancy response", async () => {
    const fetchMock = stubPost(DISC_SAMPLE)
    vi.stubGlobal("fetch", fetchMock)
    const out = await postDiscrepancy([])
    expect(out.n_triggered).toBe(1)
    expect(out.should_refine).toBe(true)
    expect(out.triggered_fields).toEqual(["temperature_k"])
  })
})
