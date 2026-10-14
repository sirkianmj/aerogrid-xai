import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { SessionBar } from "./SessionBar"
import type { LoginResponse } from "./authApi"

const SAMPLE: LoginResponse = {
  token: "eyJhbGciOiJIUzI1NiJ9.payload.signature",
  tenant_id: "11111111-2222-3333-4444-555555555555",
  role: "admin",
  expires_in_seconds: 86400,
}

// SessionBar calls window.location.reload() on successful login and on
// sign-out. jsdom refuses to navigate; stub it so the test can assert
// the storage side effect without a page reload attempt.
function stubReload(): ReturnType<typeof vi.fn> {
  const fn = vi.fn()
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { ...window.location, reload: fn },
  })
  return fn
}

function stubFetchOk(payload: LoginResponse = SAMPLE): ReturnType<typeof vi.fn> {
  const fn = vi.fn(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve(payload),
    } as Response),
  )
  vi.stubGlobal("fetch", fn)
  return fn
}

describe("SessionBar", () => {
  afterEach(() => {
    window.localStorage.removeItem("aerogrid.token")
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it("shows the sign-in form when no token is stored", () => {
    window.localStorage.removeItem("aerogrid.token")
    render(<SessionBar />)
    expect(screen.getByRole("heading", { name: /session/i })).toBeInTheDocument()
    expect(screen.getByTestId("login-form")).toBeInTheDocument()
    expect(screen.getByLabelText(/tenant slug/i)).toBeInTheDocument()
  })

  it("switches to the paste-a-JWT input when Use token is clicked", async () => {
    window.localStorage.removeItem("aerogrid.token")
    const user = userEvent.setup()
    render(<SessionBar />)
    await user.click(screen.getByRole("button", { name: /use token/i }))
    expect(screen.getByPlaceholderText(/paste JWT/i)).toBeInTheDocument()
    expect(screen.queryByTestId("login-form")).not.toBeInTheDocument()
  })

  it("paste-a-JWT Save stores the token and shows the indicator", async () => {
    window.localStorage.removeItem("aerogrid.token")
    stubReload()
    const user = userEvent.setup()
    render(<SessionBar />)
    await user.click(screen.getByRole("button", { name: /use token/i }))
    await user.type(screen.getByPlaceholderText(/paste JWT/i), "abcdefghijklmnop")
    await user.click(screen.getByRole("button", { name: /save/i }))
    expect(window.localStorage.getItem("aerogrid.token")).toBe("abcdefghijklmnop")
    await waitFor(() =>
      expect(screen.getByTestId("session-token-present")).toBeInTheDocument(),
    )
  })

  it("successful sign-in stores the returned token", async () => {
    window.localStorage.removeItem("aerogrid.token")
    stubFetchOk()
    stubReload()
    const user = userEvent.setup()
    render(<SessionBar />)
    await user.type(screen.getByLabelText(/tenant slug/i), "acme")
    await user.type(screen.getByLabelText(/password/i), "hunter2")
    await user.click(screen.getByRole("button", { name: /sign in/i }))
    await waitFor(() =>
      expect(window.localStorage.getItem("aerogrid.token")).toBe(SAMPLE.token),
    )
  })

  it("shows the masked indicator when a token is stored at mount", () => {
    window.localStorage.setItem("aerogrid.token", "abcdefghijklmnop")
    render(<SessionBar />)
    expect(screen.getByTestId("session-token-present")).toBeInTheDocument()
    expect(screen.queryByTestId("login-form")).not.toBeInTheDocument()
  })

  it("Sign out clears the token", async () => {
    window.localStorage.setItem("aerogrid.token", "abcdefghijklmnop")
    stubReload()
    const user = userEvent.setup()
    render(<SessionBar />)
    await user.click(screen.getByRole("button", { name: /sign out/i }))
    expect(window.localStorage.getItem("aerogrid.token")).toBeNull()
  })
})
