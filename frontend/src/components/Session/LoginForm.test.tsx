import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { LoginForm } from "./LoginForm"
import type { LoginResponse } from "./authApi"

const SAMPLE: LoginResponse = {
  token: "eyJhbGciOiJIUzI1NiJ9.payload.signature",
  tenant_id: "11111111-2222-3333-4444-555555555555",
  role: "admin",
  expires_in_seconds: 86400,
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

describe("LoginForm", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it("renders the slug and password inputs and a disabled submit button", () => {
    render(<LoginForm onSuccess={() => {}} onSwitchToToken={() => {}} />)
    expect(screen.getByLabelText(/tenant slug/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /sign in/i })).toBeDisabled()
  })

  it("typing both fields enables the submit button", async () => {
    const user = userEvent.setup()
    render(<LoginForm onSuccess={() => {}} onSwitchToToken={() => {}} />)
    await user.type(screen.getByLabelText(/tenant slug/i), "acme")
    await user.type(screen.getByLabelText(/password/i), "hunter2")
    expect(screen.getByRole("button", { name: /sign in/i })).toBeEnabled()
  })

  it("submits and calls onSuccess with the returned token", async () => {
    const fn = stubFetchOk()
    const onSuccess = vi.fn()
    const user = userEvent.setup()
    render(<LoginForm onSuccess={onSuccess} onSwitchToToken={() => {}} />)
    await user.type(screen.getByLabelText(/tenant slug/i), "acme")
    await user.type(screen.getByLabelText(/password/i), "hunter2")
    await user.click(screen.getByRole("button", { name: /sign in/i }))
    await waitFor(() => expect(onSuccess).toHaveBeenCalledWith(SAMPLE.token))
    // POST body
    const init = fn.mock.calls[0][1] as RequestInit
    expect(fn.mock.calls[0][0]).toBe("/api/auth/token")
    const body = JSON.parse(init.body as string) as Record<string, unknown>
    expect(body.slug).toBe("acme")
    expect(body.password).toBe("hunter2")
  })

  it("shows the backend detail on 401 and does not call onSuccess", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: "invalid credentials" }),
        } as Response),
      ),
    )
    const onSuccess = vi.fn()
    const user = userEvent.setup()
    render(<LoginForm onSuccess={onSuccess} onSwitchToToken={() => {}} />)
    await user.type(screen.getByLabelText(/tenant slug/i), "acme")
    await user.type(screen.getByLabelText(/password/i), "wrong")
    await user.click(screen.getByRole("button", { name: /sign in/i }))
    await waitFor(() =>
      expect(screen.getByTestId("login-error")).toHaveTextContent(/invalid credentials/),
    )
    expect(onSuccess).not.toHaveBeenCalled()
  })

  it("shows a network error message when fetch rejects", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("network failure"))))
    const user = userEvent.setup()
    render(<LoginForm onSuccess={() => {}} onSwitchToToken={() => {}} />)
    await user.type(screen.getByLabelText(/tenant slug/i), "acme")
    await user.type(screen.getByLabelText(/password/i), "x")
    await user.click(screen.getByRole("button", { name: /sign in/i }))
    await waitFor(() =>
      expect(screen.getByTestId("login-error")).toHaveTextContent(/network failure/),
    )
  })

  it("switch-to-token button calls onSwitchToToken", async () => {
    const onSwitch = vi.fn()
    const user = userEvent.setup()
    render(<LoginForm onSuccess={() => {}} onSwitchToToken={onSwitch} />)
    await user.click(screen.getByRole("button", { name: /use token/i }))
    expect(onSwitch).toHaveBeenCalledTimes(1)
  })

  it("shows a submitting state while the request is in flight", async () => {
    const resolver: { current: ((r: Response) => void) | null } = { current: null }
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise<Response>((res) => {
            resolver.current = res
          }),
      ),
    )
    const user = userEvent.setup()
    render(<LoginForm onSuccess={() => {}} onSwitchToToken={() => {}} />)
    await user.type(screen.getByLabelText(/tenant slug/i), "acme")
    await user.type(screen.getByLabelText(/password/i), "x")
    await user.click(screen.getByRole("button", { name: /sign in/i }))
    expect(screen.getByRole("button", { name: /signing in/i })).toBeDisabled()
    resolver.current?.({
      ok: true,
      status: 200,
      json: () => Promise.resolve(SAMPLE),
    } as Response)
  })
})
