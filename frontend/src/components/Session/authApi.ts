/**
 * Typed client for POST /auth/token.
 *
 * The Vite dev-server proxy rewrites /api/* to the backend root, so
 * the request path is /api/auth/token. See backend/app/saas/auth_routes.py.
 */

export type LoginResponse = {
  token: string
  tenant_id: string
  role: string
  expires_in_seconds: number
}

export class AuthApiError extends Error {
  readonly status: number
  readonly detail: string
  constructor(status: number, detail: string) {
    super(`auth api returned ${status}: ${detail}`)
    this.name = "AuthApiError"
    this.status = status
    this.detail = detail
  }
}

export async function login(
  slug: string,
  password: string,
  signal?: AbortSignal,
): Promise<LoginResponse> {
  const response = await fetch("/api/auth/token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slug, password }),
    signal,
  })
  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const payload = (await response.json()) as { detail?: unknown }
      if (typeof payload.detail === "string") detail = payload.detail
    } catch {
      // body was not JSON
    }
    throw new AuthApiError(response.status, detail)
  }
  return (await response.json()) as LoginResponse
}
