import { render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import App from "./App"
import {
  ALL_TAGS,
  EPISTEMIC_TAGS,
} from "./components/EpistemicBadge/epistemic"

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
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ status: "healthy" }),
        } as Response),
      ),
    )
    render(<App />)
    await waitFor(() => {
      expect(screen.getByText(/connected: healthy/i)).toBeInTheDocument()
    })
  })

  it("shows error state when the fetch fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("network failure"))),
    )
    render(<App />)
    await waitFor(() => {
      expect(screen.getByText(/error: network failure/i)).toBeInTheDocument()
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
