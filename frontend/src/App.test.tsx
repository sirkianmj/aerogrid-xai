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
