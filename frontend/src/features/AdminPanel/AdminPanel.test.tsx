import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { AdminPanel } from "./AdminPanel"
import type { TenantListResponse, TenantUsageResponse } from "./adminApi"

const TENANT_A = {
  id: "11111111-1111-1111-1111-111111111111",
  slug: "alpha",
  display_name: "Alpha Tenant",
  created_at: "2026-10-01T00:00:00+00:00",
  stripe_subscription_status: "active",
  plan: "pro",
}
const TENANT_B = {
  id: "22222222-2222-2222-2222-222222222222",
  slug: "beta",
  display_name: "Beta Tenant",
  created_at: "2026-10-02T00:00:00+00:00",
  stripe_subscription_status: null,
  plan: "free",
}

const LIST: TenantListResponse = { tenants: [TENANT_A, TENANT_B], count: 2 }

const USAGE_A: TenantUsageResponse = {
  tenant_id: TENANT_A.id,
  period_start: "2026-10-01",
  plan: "pro",
  usage: [
    { metric: "clear_d_runs", count: 3, limit: 200 },
    { metric: "tradespace_runs", count: 12, limit: 500 },
    { metric: "z3_solves", count: 0, limit: 20000 },
  ],
}

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as Response
}

function stubSequence(bodies: Response[]) {
  const fn = vi.fn()
  for (const b of bodies) fn.mockImplementationOnce(() => Promise.resolve(b))
  vi.stubGlobal("fetch", fn)
  return fn
}

describe("AdminPanel", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it("renders the heading and a sign-in placeholder when token is null", () => {
    const fetchMock = vi.fn()
    vi.stubGlobal("fetch", fetchMock)
    render(<AdminPanel token={null} />)
    expect(
      screen.getByRole("heading", { name: /admin — tenant management/i, level: 2 }),
    ).toBeInTheDocument()
    expect(screen.getByTestId("admin-signin-required")).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it("fetches the tenant list when a token is provided", async () => {
    const fn = stubSequence([jsonResponse(200, LIST)])
    render(<AdminPanel token="jwt-abc" />)
    await waitFor(() => {
      expect(screen.getByText("Alpha Tenant")).toBeInTheDocument()
    })
    expect(screen.getByText("Beta Tenant")).toBeInTheDocument()
    expect(fn).toHaveBeenCalledTimes(1)
    const call = fn.mock.calls[0]
    expect(call[0]).toBe("/api/saas/admin/tenants")
    const init = call[1] as RequestInit
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer jwt-abc")
  })

  it("renders the Section 21 simulation_result badge on success", async () => {
    stubSequence([jsonResponse(200, LIST)])
    const { container } = render(<AdminPanel token="jwt-abc" />)
    await waitFor(() => {
      const badges = container.querySelectorAll('[data-epistemic-tag="simulation_result"]')
      expect(badges.length).toBeGreaterThanOrEqual(1)
    })
  })

  it("renders a 403 message when the token has insufficient role", async () => {
    stubSequence([jsonResponse(403, { detail: "role viewer is below the required superadmin" })])
    render(<AdminPanel token="jwt-abc" />)
    await waitFor(() => {
      expect(screen.getByText(/Forbidden — superadmin required/i)).toBeInTheDocument()
    })
  })

  it("renders a 401 message when the token is missing or invalid", async () => {
    stubSequence([jsonResponse(401, { detail: "invalid token" })])
    render(<AdminPanel token="jwt-abc" />)
    await waitFor(() => {
      expect(screen.getByText(/Sign in required/i)).toBeInTheDocument()
    })
  })

  it("shows a network error when fetch rejects", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("network failure"))))
    render(<AdminPanel token="jwt-abc" />)
    await waitFor(() => {
      expect(screen.getByText(/network failure/i)).toBeInTheDocument()
    })
  })

  it("fetches tenant usage when a row is clicked", async () => {
    const fn = stubSequence([jsonResponse(200, LIST), jsonResponse(200, USAGE_A)])
    const user = userEvent.setup()
    render(<AdminPanel token="jwt-abc" />)
    await waitFor(() => {
      expect(screen.getByTestId(`tenant-row-${TENANT_A.id}`)).toBeInTheDocument()
    })
    await user.click(screen.getByTestId(`tenant-row-${TENANT_A.id}`))
    await waitFor(() => {
      expect(screen.getByText(/Usage this month/i)).toBeInTheDocument()
    })
    await waitFor(() => {
      expect(screen.getByText("tradespace_runs")).toBeInTheDocument()
    })
    expect(fn).toHaveBeenCalledTimes(2)
    const secondCall = fn.mock.calls[1]
    expect(secondCall[0]).toBe(`/api/saas/admin/tenants/${TENANT_A.id}/usage`)
  })

  it("shows a 404 error when usage is requested for a deleted tenant", async () => {
    stubSequence([
      jsonResponse(200, LIST),
      jsonResponse(404, { detail: `tenant ${TENANT_A.id} not found` }),
    ])
    const user = userEvent.setup()
    render(<AdminPanel token="jwt-abc" />)
    await waitFor(() => {
      expect(screen.getByTestId(`tenant-row-${TENANT_A.id}`)).toBeInTheDocument()
    })
    await user.click(screen.getByTestId(`tenant-row-${TENANT_A.id}`))
    await waitFor(() => {
      expect(screen.getByText(new RegExp(`tenant ${TENANT_A.id} not found`))).toBeInTheDocument()
    })
  })

  it("marks the selected tenant row with aria-selected=true", async () => {
    stubSequence([jsonResponse(200, LIST), jsonResponse(200, USAGE_A)])
    const user = userEvent.setup()
    render(<AdminPanel token="jwt-abc" />)
    const row = await screen.findByTestId(`tenant-row-${TENANT_A.id}`)
    expect(row).toHaveAttribute("aria-selected", "false")
    await user.click(row)
    await waitFor(() => {
      expect(row).toHaveAttribute("aria-selected", "true")
    })
  })

  it("shows the artefact sub-label on success", async () => {
    stubSequence([jsonResponse(200, LIST)])
    render(<AdminPanel token="jwt-abc" />)
    await waitFor(() => {
      expect(screen.getByText(/artefact: admin_tenant_management/i)).toBeInTheDocument()
    })
  })
})
