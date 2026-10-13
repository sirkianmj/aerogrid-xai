import { render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import App from "./App"
import {
  ALL_TAGS,
  EPISTEMIC_TAGS,
} from "./components/EpistemicBadge/epistemic"

/**
 * URL-aware fetch stub for the App shell.
 *
 * The shell mounts two panels that fetch on mount: the health check
 * (Health section) and the Globe (orbital catalog). A blanket stub that
 * returns the same body for every URL would break one of them. This
 * helper dispatches by URL and returns an empty catalog and error for
 * the orbital routes by default, so a test that cares only about the
 * health section sees exactly one outcome.
 */
type StubOptions = {
  health?: { ok: true; body: { status: string } } | { ok: false; status: number; detail: string } | { reject: string }
}

function stubAppFetch(opts: StubOptions = {}) {
  const health =
    opts.health ?? { ok: true as const, body: { status: "healthy" } }
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.includes("/api/health")) {
        if ("reject" in health) return Promise.reject(new Error(health.reject))
        if (health.ok) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: () => Promise.resolve(health.body),
          } as Response)
        }
        return Promise.resolve({
          ok: false,
          status: health.status,
          json: () => Promise.resolve({ detail: health.detail }),
        } as Response)
      }
      if (url.includes("/api/orbital/satellites")) {
        // Empty catalog so the Globe renders nothing rather than firing
        // a follow-up track request in tests that are not about the Globe.
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ satellites: [] }),
        } as Response)
      }
      if (url.endsWith("/digital-twin/state")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            epistemic_tag: "simulation_result",
            incident_power_w: 20, airflow_m_per_s: 5, ambient_temperature_k: 298.15,
            steady_state: null,
            thermal_runaway_power_w: 60, safety_margin_w: 40, safety_margin_fraction: 0.667,
            receiver_efficiency: null, receiver_efficiency_source: "",
          }),
        } as Response)
      }
      if (url.endsWith("/digital-twin/trajectory")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            epistemic_tag: "simulation_result",
            t_end_s: 10, n_samples: 2,
            samples: [
              { time_s: 0, t_plc_k: 298.15, t_te_k: 298.15 },
              { time_s: 10, t_plc_k: 299.0, t_te_k: 298.5 },
            ],
          }),
        } as Response)
      }
      if (url.endsWith("/digital-twin/discrepancy")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            epistemic_tag: "simulation_result",
            n_observations: 0, n_triggered: 0, triggered_fields: [],
            should_refine: false, threshold_summary: {}, records: [],
          }),
        } as Response)
      }
      return Promise.reject(new Error(`unexpected url in App test: ${url}`))
    }),
  )
}

describe("App", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it("renders the AeroGrid-XAI heading", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})))
    render(<App />)
    expect(
      screen.getByRole("heading", { name: /aerogrid-xai/i, level: 1 }),
    ).toBeInTheDocument()
  })

  it("shows connected state on successful /api/health fetch", async () => {
    stubAppFetch()
    render(<App />)
    await waitFor(() => {
      expect(screen.getByText(/connected: healthy/i)).toBeInTheDocument()
    })
  })

  it("shows error state when the health fetch fails", async () => {
    stubAppFetch({ health: { reject: "network failure" } })
    render(<App />)
    await waitFor(() => {
      // Scope the query to the health section so a Globe error, if any,
      // does not cause a multiple-match failure.
      const healthSection = screen.getByRole("region", {
        name: /backend status/i,
      })
      expect(healthSection.textContent).toMatch(/error: network failure/i)
    })
  })

  it("renders every Section 21 epistemic badge on the page", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})))
    render(<App />)
    for (const tag of ALL_TAGS) {
      expect(screen.getByText(EPISTEMIC_TAGS[tag].label)).toBeInTheDocument()
    }
  })

  it("tags each epistemic badge with its data attribute", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})))
    const { container } = render(<App />)
    const badges = container.querySelectorAll("[data-epistemic-tag]")
    expect(badges.length).toBeGreaterThanOrEqual(ALL_TAGS.length)
  })
})
