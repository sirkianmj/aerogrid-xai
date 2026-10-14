import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { SessionBar } from "./SessionBar"

describe("SessionBar", () => {
  afterEach(() => {
    window.localStorage.removeItem("aerogrid.token")
    vi.restoreAllMocks()
  })

  it("shows the prompt when no token is stored", () => {
    window.localStorage.removeItem("aerogrid.token")
    render(<SessionBar />)
    expect(screen.getByRole("heading", { name: /session/i })).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/paste JWT/i)).toBeInTheDocument()
  })

  it("shows the indicator when a token is stored", () => {
    window.localStorage.setItem("aerogrid.token", "abcdefghijklmnop")
    render(<SessionBar />)
    expect(screen.getByTestId("session-token-present")).toBeInTheDocument()
    expect(screen.queryByPlaceholderText(/paste JWT/i)).not.toBeInTheDocument()
  })

  it("Save button is disabled while the input is empty", () => {
    window.localStorage.removeItem("aerogrid.token")
    render(<SessionBar />)
    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled()
  })

  it("typing a token enables Save", async () => {
    window.localStorage.removeItem("aerogrid.token")
    const user = userEvent.setup()
    render(<SessionBar />)
    await user.type(screen.getByPlaceholderText(/paste JWT/i), "abc")
    expect(screen.getByRole("button", { name: /save/i })).toBeEnabled()
  })
})
