import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { XAITrace } from "./XAITrace"
import type { ChargeDecisionResponse } from "./xaiTraceApi"

const SAMPLE: ChargeDecisionResponse = {
  epistemic_tag: "tier1_decision_trace",
  decision: "charge_uav_32",
  decision_kind: "charge",
  primary_reasons: [
    { label: "charge_ranking.low_battery", comparison: "rule low_battery matched", weight: 3.0 },
    { label: "charge_ranking.mission_priority_high", comparison: "rule mission_priority_high matched", weight: 2.5 },
  ],
  consulted_rules: [
    { label: "charge_ranking.low_battery", comparison: "rule low_battery matched", result: "match" },
    { label: "charge_ranking.thermal_headroom_ok", comparison: "rule thermal_headroom_ok did not match", result: "no_match" },
  ],
  alternative: { action: "charge_uav_18", score: 4.0 },
  confidence: 0.91,
  confidence_note: "Tier 1 rule-confidence; not a physical-reality guarantee (Section 15.5).",
}

function stubFetchOk() {
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

describe("XAITrace", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it("renders the panel heading and an idle message", () => {
    render(<XAITrace />)
    expect(
      screen.getByRole("heading", { name: /xai trace/i, level: 2 }),
    ).toBeInTheDocument()
    expect(screen.getByText(/no trace yet/i)).toBeInTheDocument()
  })

  it("runs the decision and renders the trace on success", async () => {
    stubFetchOk()
    const user = userEvent.setup()
    render(<XAITrace />)
    await user.click(screen.getByRole("button", { name: /run decision/i }))

    await waitFor(() => {
      expect(screen.getByText("charge_uav_32")).toBeInTheDocument()
    })
    expect(screen.getByText("charge")).toBeInTheDocument()
    expect(screen.getByText(/confidence 91%/i)).toBeInTheDocument()
    expect(screen.getByText(/physical-reality guarantee/i)).toBeInTheDocument()
  })

  it("lists the primary reasons with their weights", async () => {
    stubFetchOk()
    const user = userEvent.setup()
    render(<XAITrace />)
    await user.click(screen.getByRole("button", { name: /run decision/i }))
    await waitFor(() => {
      expect(screen.getByText(/primary reasons/i)).toBeInTheDocument()
    })
    expect(screen.getByText("+3.00")).toBeInTheDocument()
    expect(screen.getByText("+2.50")).toBeInTheDocument()
  })

  it("shows the alternative action", async () => {
    stubFetchOk()
    const user = userEvent.setup()
    render(<XAITrace />)
    await user.click(screen.getByRole("button", { name: /run decision/i }))
    await waitFor(() => {
      expect(screen.getByText("charge_uav_18")).toBeInTheDocument()
    })
    expect(screen.getByText(/score 4\.000/)).toBeInTheDocument()
  })

  it("renders the Section 21 badge as simulation_result and the artefact sub-label", async () => {
    stubFetchOk()
    const user = userEvent.setup()
    render(<XAITrace />)
    await user.click(screen.getByRole("button", { name: /run decision/i }))
    await waitFor(() => {
      expect(screen.getByText("Simulation result")).toBeInTheDocument()
    })
    // The tag is enforced by TaggedOutput. The badge carries the
    // data-epistemic-tag attribute; verify it is present in the tree.
    const { container } = render(<XAITrace />)
    await user.click(
      container.querySelector("button") as HTMLButtonElement,
    )
    await waitFor(() => {
      const badges = container.querySelectorAll(
        '[data-epistemic-tag="simulation_result"]',
      )
      expect(badges.length).toBeGreaterThanOrEqual(1)
    })
    expect(screen.getAllByText(/artefact: tier1_decision_trace/i).length).toBeGreaterThanOrEqual(1)
  })

  it("shows an error when the backend returns a 400", async () => {
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
    const user = userEvent.setup()
    render(<XAITrace />)
    await user.click(screen.getByRole("button", { name: /run decision/i }))
    await waitFor(() => {
      expect(screen.getByText(/error \(400\)/i)).toBeInTheDocument()
    })
    expect(screen.getByText(/uav_id/i)).toBeInTheDocument()
  })

  it("shows an error when the fetch fails", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("network failure"))))
    const user = userEvent.setup()
    render(<XAITrace />)
    await user.click(screen.getByRole("button", { name: /run decision/i }))
    await waitFor(() => {
      expect(screen.getByText(/network failure/i)).toBeInTheDocument()
    })
  })
})
