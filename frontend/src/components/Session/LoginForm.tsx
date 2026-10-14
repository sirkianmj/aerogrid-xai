/**
 * LoginForm — tenant slug + password, POSTed to /auth/token.
 *
 * On success, calls `onSuccess(token)`. SessionBar saves the token
 * under the same `aerogrid.token` key that the paste-a-JWT input uses,
 * so every existing reader of that key keeps working unchanged.
 *
 * The form does not validate the password locally (no length check,
 * no complexity rule). The backend accepts any length and returns the
 * same uniform 401 "invalid credentials" for wrong password, unknown
 * slug, and NULL-hash tenants. Reproducing those rules on the client
 * would only add a divergence risk.
 *
 * Accessibility: every field has a label, the submit button is
 * disabled while the form is incomplete or in flight, the error is
 * announced via role="alert".
 */

import { useState, type FormEvent } from "react"
import { AuthApiError, login } from "./authApi"

export type LoginFormProps = {
  onSuccess: (token: string) => void
  onSwitchToToken: () => void
}

export function LoginForm({ onSuccess, onSwitchToToken }: LoginFormProps) {
  const [slug, setSlug] = useState("")
  const [password, setPassword] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const incomplete = !slug.trim() || !password

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (incomplete || submitting) return
    setSubmitting(true)
    setError(null)
    try {
      const resp = await login(slug.trim(), password)
      onSuccess(resp.token)
    } catch (err) {
      if (err instanceof AuthApiError) {
        setError(err.detail)
      } else if (err instanceof Error) {
        setError(err.message)
      } else {
        setError(String(err))
      }
      setSubmitting(false)
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-1 flex-wrap items-center gap-3"
      data-testid="login-form"
    >
      <label className="flex items-center gap-2">
        <span className="text-[0.65rem] uppercase tracking-wide opacity-50">
          Tenant
        </span>
        <input
          aria-label="Tenant slug"
          type="text"
          value={slug}
          onChange={(e) => setSlug(e.target.value)}
          autoComplete="username"
          spellCheck={false}
          className="w-40 rounded border border-current/20 bg-transparent px-2 py-1 font-mono text-xs"
        />
      </label>

      <label className="flex items-center gap-2">
        <span className="text-[0.65rem] uppercase tracking-wide opacity-50">
          Password
        </span>
        <input
          aria-label="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          className="w-56 rounded border border-current/20 bg-transparent px-2 py-1 font-mono text-xs"
        />
      </label>

      <button
        type="submit"
        disabled={incomplete || submitting}
        className="rounded border px-3 py-1 text-xs uppercase tracking-wider hover:bg-current/5 disabled:opacity-40"
      >
        {submitting ? "Signing in…" : "Sign in"}
      </button>

      <button
        type="button"
        onClick={onSwitchToToken}
        className="text-[0.65rem] uppercase tracking-wider opacity-60 hover:opacity-100"
      >
        Use token
      </button>

      {error && (
        <p
          role="alert"
          className="w-full text-xs"
          style={{ color: "var(--color-accent-amber)" }}
          data-testid="login-error"
        >
          {error}
        </p>
      )}
    </form>
  )
}
