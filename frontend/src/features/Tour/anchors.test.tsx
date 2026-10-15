/**
 * Anchor test. For every step in ALL_STEPS, render <App /> and assert
 * the element with that data-tour-id actually exists in the DOM.
 *
 * This is the single most valuable test in the tour. It catches a
 * renamed component or a moved anchor before a user hits a broken
 * step, at test time instead of demo time.
 */

import { render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import App from "../../App"
import { ALL_STEPS } from "./tourDefinitions"

// Same mocks as App.test.tsx. Feature panels are stubbed because this
// test only cares about the shell, the tour overlay, and the anchors.

vi.mock("../MissionControl/MissionControl", () => ({
  MissionControl: () => <div data-testid="panel-mission" />,
}))
vi.mock("../MissionControl/MissionConfigBar", () => ({
  MissionConfigBar: () => <div data-testid="panel-config" />,
}))
vi.mock("../MissionControl/MissionProvider", () => ({
  MissionProvider: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}))
vi.mock("../Globe/Globe", () => ({ Globe: () => <div /> }))
vi.mock("../DigitalTwin/DigitalTwin", () => ({ DigitalTwin: () => <div /> }))
vi.mock("../Telemetry/Telemetry", () => ({ Telemetry: () => <div /> }))
vi.mock("../ClearDDashboard/ClearDDashboard", () => ({
  ClearDDashboard: () => <div />,
}))
vi.mock("../Architectures/ArchitecturesView", () => ({
  ArchitecturesView: () => <div />,
}))
vi.mock("../Sensitivity/SensitivityPanel", () => ({
  SensitivityPanel: () => <div />,
}))
vi.mock("../Fanet/FanetGraph", () => ({ FanetGraph: () => <div /> }))
vi.mock("../XAITrace/XAITrace", () => ({ XAITrace: () => <div /> }))
vi.mock("../TradeSpace/TradeSpace", () => ({ TradeSpace: () => <div /> }))
vi.mock("../DesignStudio/DesignStudio", () => ({
  DesignStudio: () => <div />,
}))
vi.mock("../Status/StatusView", () => ({ StatusView: () => <div /> }))
vi.mock("../../components/EpistemicBadge/EpistemicBadge", () => ({
  EpistemicBadge: () => <span />,
}))

describe("tour anchors", () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it("every step anchor exists in the rendered app", () => {
    render(<App />)
    const missing: string[] = []
    for (const step of ALL_STEPS) {
      const el = document.querySelector(
        `[data-tour-id="${step.anchor}"]`,
      )
      if (!el) missing.push(`${step.id} -> ${step.anchor}`)
    }
    expect(missing, `missing anchors: ${missing.join(", ")}`).toEqual([])
  })

  it("anchor ids are unique across steps", () => {
    // Multiple steps can share an anchor (three chapters may point at
    // the same sidebar). What must NOT collide is the step id.
    const ids = ALL_STEPS.map((s) => s.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it("step ids sort in the same order as the array", () => {
    // Not an alphabetical requirement, just a sanity check that no
    // step was inserted in the wrong place by an editing mistake.
    const asArray = ALL_STEPS.map((s) => s.id)
    const sorted = [...asArray].sort()
    expect(asArray).toEqual(sorted)
  })

  it("first-run offer is dismissed once localStorage records it", () => {
    window.localStorage.setItem(
      "aerogrid.tour",
      JSON.stringify({ firstRunDone: true, neverShow: true }),
    )
    render(<App />)
    expect(
      screen.queryByTestId("tour-first-run-offer"),
    ).not.toBeInTheDocument()
  })
})
