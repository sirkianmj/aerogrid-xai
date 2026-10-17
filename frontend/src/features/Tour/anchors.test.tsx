/**
 * Anchor test.
 *
 * For every step in ALL_STEPS, render the real <App /> and assert the
 * element with that data-tour-id exists in the DOM.
 *
 * Only two things are stubbed, both because jsdom cannot run them:
 *
 *   1. fetch  — returns a never-resolving promise, so panels stay in
 *               their loading state instead of erroring. The outer
 *               sections render either way, which is where the
 *               anchors live.
 *   2. WebSocket — the telemetry socket has no server in jsdom.
 *   3. <Canvas> from @react-three/fiber — needs WebGL. Only the
 *               canvas element is replaced; the surrounding Globe
 *               section and its anchors are real.
 *
 * Every panel is real. Anchors are placed on unconditional elements,
 * so they exist regardless of the loading state.
 */

import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"
import App from "../../App"
import { ALL_STEPS } from "./tourDefinitions"

// jsdom boundary stubs.
vi.mock("@react-three/fiber", () => ({
  Canvas: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="canvas-stub">{children}</div>
  ),
}))

vi.mock("@react-three/drei", () => ({
  OrbitControls: () => null,
}))

beforeEach(() => {
  window.localStorage.clear()
  // Never-resolving fetch: panels stay loading, no unhandled rejections.
  vi.stubGlobal(
    "fetch",
    vi.fn(() => new Promise(() => undefined)),
  )
  // No-op WebSocket.
  class FakeWebSocket {
    close() {}
    send() {}
    addEventListener() {}
    removeEventListener() {}
    readyState = 0
  }
  vi.stubGlobal("WebSocket", FakeWebSocket)
})

describe("tour anchors", () => {
  it("every step anchor exists across all views", async () => {
    const user = userEvent.setup()
    render(<App />)
    const found = new Set<string>()

    const collect = () => {
      document.querySelectorAll("[data-tour-id]").forEach((el) => {
        const id = el.getAttribute("data-tour-id")
        if (id) found.add(id)
      })
    }

    collect()
    const sidebar = screen.getByRole("complementary", { name: /primary/i })
    const buttons = within(sidebar).getAllByRole("button")
    for (const btn of buttons) {
      await user.click(btn)
      collect()
    }

    const missing = ALL_STEPS
      .filter((s) => !found.has(s.anchor))
      .map((s) => `${s.id} -> ${s.anchor}`)
    expect(missing, `missing anchors: ${missing.join(", ")}`).toEqual([])
  })

  it("step ids are unique", () => {
    const ids = ALL_STEPS.map((s) => s.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it("step ids sort in the same order as the array", () => {
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
      document.querySelector('[data-testid="tour-first-run-offer"]'),
    ).toBeNull()
  })
})
