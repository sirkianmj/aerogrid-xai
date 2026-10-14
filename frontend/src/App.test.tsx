/**
 * App shell tests.
 *
 * The shell is what this file tests: the title bar, the sidebar nav,
 * the segmented view switcher, the invariant badge, the six module
 * items, and the fact that switching a nav item mounts the correct
 * panel. Panels are mocked so this file does not need to stub every
 * endpoint that every panel fetches, and it does not depend on any
 * panel's data shape. Panel-level behavior lives in each panel's own
 * test module.
 *
 * MissionProvider and MissionConfigBar stay real because the shell
 * mounts MissionConfigBar into the sidebar and it reads from the
 * MissionProvider context. The provider's only network call is
 * /mission/state; the fetch stub below handles that one URL.
 */

import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

// --- panel mocks (before the App import) ---------------------------------

vi.mock("./features/MissionControl/MissionControl", () => ({
  MissionControl: () => <div data-testid="panel-mission-control" />,
}))
vi.mock("./features/ClearDDashboard/ClearDDashboard", () => ({
  ClearDDashboard: () => <div data-testid="panel-cleard" />,
}))
vi.mock("./features/Fanet/FanetGraph", () => ({
  FanetGraph: () => <div data-testid="panel-fanet" />,
}))
vi.mock("./features/Globe/Globe", () => ({
  Globe: () => <div data-testid="panel-globe" />,
}))
vi.mock("./features/DigitalTwin/DigitalTwin", () => ({
  DigitalTwin: () => <div data-testid="panel-digital-twin" />,
}))
vi.mock("./features/Telemetry/Telemetry", () => ({
  Telemetry: () => <div data-testid="panel-telemetry" />,
}))
vi.mock("./features/TradeSpace/TradeSpace", () => ({
  TradeSpace: () => <div data-testid="panel-tradespace" />,
}))
vi.mock("./features/AdminPanel/AdminPanel", () => ({
  AdminPanel: () => <div data-testid="panel-admin" />,
}))
vi.mock("./features/XAITrace/XAITrace", () => ({
  XAITrace: () => <div data-testid="panel-xai-trace" />,
}))

import App from "./App"

// --- fetch stub: only /mission/state is exercised ------------------------

function stubFetchMissionState(): ReturnType<typeof vi.fn> {
  const fn = vi.fn((url: string | URL | Request) => {
    const u = String(url)
    if (u.includes("/api/mission/state")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({
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
              lat_deg: 0,
              lon_deg: 0,
              alt_km: 400,
              in_eclipse: false,
              epistemic_tag: "validated_physical_model",
            },
            ground_station: { name: "GS", lat_deg: 0, lon_deg: 0, alt_m: 0 },
            transmission: {
              modality: "offline",
              wavelength_nm: 1064,
              transmitter_power_w: 10000,
              slant_range_m: 0,
              atmospheric_path_m: 0,
              elevation_deg: -90,
            },
            atmosphere: {
              transmittance: 0,
              visibility_km: 10,
              cloud_factor: 0.2,
              extinction_coeff_per_m: 1e-5,
              transmittance_low: null,
              transmittance_high: null,
              nominal_coverage: null,
            },
            uavs: [],
            architecture: {
              nodes: 0,
              links: 0,
              node_kinds: {},
              link_kinds: {},
              sat_verdict: "sat",
              n_constraints: 0,
              epsilon_bound: 0,
              node_list: [],
              link_list: [],
            },
            cleard: {
              population_size: 0,
              n_generations: 0,
              feasible_final: 0,
              infeasible_final: 0,
              conflict_prone_features: 0,
              use_conflict_directed: true,
              epistemic_tag: "simulation_result",
            },
            tier1: {
              selected_action: "",
              decision_kind: "charge",
              score: 0,
              alternative_action: "",
              alternative_score: 0,
              confidence: 1,
              epistemic_tag: "tier1_decision_trace",
            },
            pipeline_stages: [],
            epistemic_tag: "simulation_result",
            satellites: [],
          }),
      } as Response)
    }
    // Any other URL is a test bug: no panel should fetch because all
    // are mocked. Reject loudly so a future mock removal is caught.
    return Promise.reject(new Error(`unexpected fetch: ${u}`))
  })
  vi.stubGlobal("fetch", fn)
  return fn
}

beforeEach(() => {
  stubFetchMissionState()
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  window.localStorage.removeItem("aerogrid.token")
})

// --- tests ----------------------------------------------------------------

describe("App shell", () => {
  it("renders the application title in the title bar", () => {
    render(<App />)
    expect(screen.getByText("AeroGrid-XAI")).toBeInTheDocument()
  })

  it("renders the six module navigation items", () => {
    render(<App />)
    const nav = screen.getByRole("navigation", { name: /workspace views/i })
    expect(within(nav).getAllByRole("button").length).toBe(6)
  })

  it("renders the Tier-2 firewall invariant badge", () => {
    render(<App />)
    expect(screen.getByText(/tier-2 firewall verified/i)).toBeInTheDocument()
  })

  it("defaults to the Digital Twin view (mission control panel mounted)", () => {
    render(<App />)
    expect(screen.getByTestId("panel-mission-control")).toBeInTheDocument()
    expect(screen.getByTestId("panel-globe")).toBeInTheDocument()
    expect(screen.getByTestId("panel-digital-twin")).toBeInTheDocument()
    expect(screen.getByTestId("panel-telemetry")).toBeInTheDocument()
  })

  it("switches to the CLEAR-D view and mounts the correct panels", async () => {
    const user = userEvent.setup()
    render(<App />)
    const sidebar = screen.getByRole("complementary", { name: /primary/i })
    await user.click(
      within(sidebar).getByRole("button", { name: /clear-d synthesis/i }),
    )
    await waitFor(() =>
      expect(screen.getByTestId("panel-cleard")).toBeInTheDocument(),
    )
    expect(screen.getByTestId("panel-fanet")).toBeInTheDocument()
    expect(screen.queryByTestId("panel-mission-control")).not.toBeInTheDocument()
  })

  it("switches to the XAI view and mounts the trace panel", async () => {
    const user = userEvent.setup()
    render(<App />)
    const sidebar = screen.getByRole("complementary", { name: /primary/i })
    await user.click(
      within(sidebar).getByRole("button", { name: /two-tier xai core/i }),
    )
    await waitFor(() =>
      expect(screen.getByTestId("panel-xai-trace")).toBeInTheDocument(),
    )
  })

  it("switches to the Trade Space view", async () => {
    const user = userEvent.setup()
    render(<App />)
    const sidebar = screen.getByRole("complementary", { name: /primary/i })
    await user.click(within(sidebar).getByRole("button", { name: /trade space/i }))
    await waitFor(() =>
      expect(screen.getByTestId("panel-tradespace")).toBeInTheDocument(),
    )
  })

  it("switches to the SaaS & Admin view", async () => {
    const user = userEvent.setup()
    render(<App />)
    const sidebar = screen.getByRole("complementary", { name: /primary/i })
    await user.click(within(sidebar).getByRole("button", { name: /saas & admin/i }))
    await waitFor(() =>
      expect(screen.getByTestId("panel-admin")).toBeInTheDocument(),
    )
  })

  it("switches to the About view and shows all seven Section 21 badges", async () => {
    const user = userEvent.setup()
    const { container } = render(<App />)
    const sidebar = screen.getByRole("complementary", { name: /primary/i })
    await user.click(
      within(sidebar).getByRole("button", { name: /about & legend/i }),
    )
    await waitFor(() =>
      expect(
        screen.getByText(/section 21 epistemic hierarchy/i),
      ).toBeInTheDocument(),
    )
    const badges = container.querySelectorAll("[data-epistemic-tag]")
    expect(badges.length).toBeGreaterThanOrEqual(7)
  })

  it("mounts the SessionBar inside the sidebar", () => {
    render(<App />)
    const sidebar = screen.getByRole("complementary", { name: /primary/i })
    expect(
      within(sidebar).getByRole("heading", { name: /^session$/i }),
    ).toBeInTheDocument()
  })
})
