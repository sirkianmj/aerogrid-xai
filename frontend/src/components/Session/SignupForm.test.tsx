import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { SignupForm } from "./SignupForm"

function stubFetch(status: number, body: unknown) {
  const fn = vi.fn(() =>
    Promise.resolve({
      ok: status >= 200 && status < 300,
      status,
      json: () => Promise.resolve(body),
    } as Response),
  )
  vi.stubGlobal("fetch", fn)
  return fn
}

describe("SignupForm", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it("renders three inputs and a submit button", () => {
    render(<SignupForm onSuccess={() => {}} onSwitchToLogin={() => {}} />)
    expect(screen.getByLabelText("Slug")).toBeInTheDocument()
    expect(screen.getByLabelText("Display name")).toBeInTheDocument()
    expect(screen.getByLabelText("Password")).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: /Create account/i }),
    ).toBeInTheDocument()
  })

  it("disables submit until fields are valid", async () => {
    render(<SignupForm onSuccess={() => {}} onSwitchToLogin={() => {}} />)
    const submit = screen.getByRole("button", { name: /Create account/i })
    expect(submit).toBeDisabled()
    await userEvent.type(screen.getByLabelText("Slug"), "acme")
    await userEvent.type(screen.getByLabelText("Display name"), "Acme")
    await userEvent.type(screen.getByLabelText("Password"), "short")
    expect(submit).toBeDisabled()
    await userEvent.type(screen.getByLabelText("Password"), "-but-much-longer")
    expect(submit).toBeEnabled()
  })

  it("shows a server error when signup is rejected", async () => {
    stubFetch(409, { detail: "slug 'acme' is already taken" })
    render(<SignupForm onSuccess={() => {}} onSwitchToLogin={() => {}} />)
    await userEvent.type(screen.getByLabelText("Slug"), "acme")
    await userEvent.type(screen.getByLabelText("Display name"), "Acme")
    await userEvent.type(
      screen.getByLabelText("Password"),
      "correct-horse-battery-staple",
    )
    await userEvent.click(screen.getByRole("button", { name: /Create account/i }))
    await waitFor(() =>
      expect(screen.getByTestId("signup-error")).toHaveTextContent(/already taken/),
    )
  })

  it("calls onSuccess with the token on successful signup", async () => {
    stubFetch(201, {
      token: "jwt-token-xyz",
      tenant_id: "00000000-0000-0000-0000-000000000000",
      role: "admin",
      expires_in_seconds: 86400,
    })
    const onSuccess = vi.fn()
    render(<SignupForm onSuccess={onSuccess} onSwitchToLogin={() => {}} />)
    await userEvent.type(screen.getByLabelText("Slug"), "acme")
    await userEvent.type(screen.getByLabelText("Display name"), "Acme")
    await userEvent.type(
      screen.getByLabelText("Password"),
      "correct-horse-battery-staple",
    )
    await userEvent.click(screen.getByRole("button", { name: /Create account/i }))
    await waitFor(() => expect(onSuccess).toHaveBeenCalledWith("jwt-token-xyz"))
  })

  it("calls onSwitchToLogin when the link is clicked", async () => {
    const onSwitchToLogin = vi.fn()
    render(<SignupForm onSuccess={() => {}} onSwitchToLogin={onSwitchToLogin} />)
    await userEvent.click(screen.getByTestId("switch-to-login"))
    expect(onSwitchToLogin).toHaveBeenCalledTimes(1)
  })
})
