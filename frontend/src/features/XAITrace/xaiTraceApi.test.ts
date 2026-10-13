import { afterEach, describe, expect, it, vi } from "vitest"
import {
  XaiTraceApiError,
  postChargeDecision,
  type ChargeDecisionResponse,
} from "./xaiTraceApi"

const SAMPLE_RESPONSE: ChargeDecisionResponse = {
  epistemic_tag: "tier1_decision_trace",
  decision: "charge_uav_32",
  decision_kind: "charge",
  primary_reasons: [
    { label: "charge_ranking.low_battery", comparison: "rule low_battery matched", weight: 3.0 },
  ],
  consulted_rules: [
    { label: "charge_ranking.low_battery", comparison: "rule low_battery matched", result: "match" },
    { label: "charge_ranking.mission_priority_high", comparison: "rule mission_priority_high did not match", result: "no_match" },
  ],
  alternative: { action: "charge_uav_18", score: 4.0 },
  confidence: 0.9,
  confidence_note: "Tier 1 rule-confidence; not a physical-reality guarantee (Section 15.5).",
}

describe("postChargeDecision", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it("posts the request as JSON with the right path and method", async () => {
    const fetchMock = vi.fn(
      (_url: string, _init?: RequestInit) =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(SAMPLE_RESPONSE),
        } as Response),
    )
    vi.stubGlobal("fetch", fetchMock)

    const req = {
      candidates: [{ uav_id: 32, battery_pct: 19, mission_priority: 0.9 }],
    }
    const result = await postChargeDecision(req)

    expect(fetchMock).toHaveBeenCalledTimes(1)
    // The mock signature guarantees one call with (url, init). Non-null
    // assertions here are safe because of the call-count expectation
    // above, and they avoid the short-circuit warning oxlint raises for
    // optional chaining inside a non-optional context.
    const url = fetchMock.mock.calls[0]![0]
    const init = fetchMock.mock.calls[0]![1]!
    expect(url).toBe("/api/decisions/charge")
    expect(init.method).toBe("POST")
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json")
    expect(JSON.parse(init.body as string)).toEqual(req)
    expect(result).toEqual(SAMPLE_RESPONSE)
  })

  it("forwards the abort signal", async () => {
    const fetchMock = vi.fn(
      (_url: string, _init?: RequestInit) =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(SAMPLE_RESPONSE),
        } as Response),
    )
    vi.stubGlobal("fetch", fetchMock)
    const controller = new AbortController()
    await postChargeDecision({ candidates: [{ uav_id: 1 }] }, controller.signal)
    const init = fetchMock.mock.calls[0]![1]!
    expect(init.signal).toBe(controller.signal)
  })

  it("throws XaiTraceApiError with the backend detail on 400", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 400,
          json: () => Promise.resolve({ detail: "candidate at index 0 is missing required key 'uav_id'" }),
        } as Response),
      ),
    )
    await expect(postChargeDecision({ candidates: [{ uav_id: 1 }] })).rejects.toMatchObject({
      name: "XaiTraceApiError",
      status: 400,
      detail: expect.stringContaining("uav_id"),
    })
  })

  it("throws XaiTraceApiError with an HTTP fallback detail when the body is not JSON", async () => {
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
      await postChargeDecision({ candidates: [{ uav_id: 1 }] })
      throw new Error("expected the call to reject")
    } catch (err) {
      expect(err).toBeInstanceOf(XaiTraceApiError)
      expect((err as XaiTraceApiError).status).toBe(500)
      expect((err as XaiTraceApiError).detail).toBe("HTTP 500")
    }
  })

  it("propagates fetch network errors", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("network failure"))))
    await expect(postChargeDecision({ candidates: [{ uav_id: 1 }] })).rejects.toThrow("network failure")
  })
})
