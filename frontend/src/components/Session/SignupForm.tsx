/**
 * SignupForm — create a new tenant and immediately obtain a session.
 *
 * Three fields: slug (the login handle, must be lowercase and
 * URL-safe), display name (human-readable, not unique), password
 * (minimum 12 characters). Client-side validation mirrors the server
 * rules so the user sees field-level errors without a round trip.
 * The server re-validates everything; the client check is a
 * convenience, not the authority.
 *
 * On success the token is returned to the caller. The parent
 * (SessionBar) stores it and refreshes the session exactly as it does
 * for a login.
 */

import { useState } from "react"
import { AuthApiError, postSignup } from "./authApi"

const SLUG_RE = /^[a-z0-9](?:[a-z0-9-]{1,30}[a-z0-9])?$/
const MIN_PASSWORD = 12

export type SignupFormProps = {
  onSuccess: (token: string) => void
  onSwitchToLogin: () => void
}

export function SignupForm({ onSuccess, onSwitchToLogin }: SignupFormProps) {
  const [slug, setSlug] = useState("")
  const [displayName, setDisplayName] = useState("")
  const [password, setPassword] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const slugError =
    slug.length > 0 && !SLUG_RE.test(slug)
      ? "lowercase letters, digits, hyphens; 3-32 chars; alphanumeric ends"
      : null
  const passwordError =
    password.length > 0 && password.length < MIN_PASSWORD
      ? `at least ${MIN_PASSWORD} characters`
      : null
  const canSubmit =
    !submitting &&
    slug.length > 0 &&
    !slugError &&
    displayName.length > 0 &&
    password.length >= MIN_PASSWORD

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!canSubmit) return
    setSubmitting(true)
    setError(null)
    try {
      const res = await postSignup({
        slug,
        display_name: displayName,
        password,
      })
      onSuccess(res.token)
    } catch (err) {
      if (err instanceof AuthApiError) setError(err.detail)
      else if (err instanceof Error) setError(err.message)
      else setError(String(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form
      onSubmit={submit}
      className="space-y-2"
      data-testid="signup-form"
    >
      <label className="flex flex-col gap-1">
        <span className="text-[0.6rem] uppercase tracking-wide text-[var(--ink-tertiary)]">
          Slug
        </span>
        <input
          type="text"
          aria-label="Slug"
          value={slug}
          onChange={(e) => setSlug(e.target.value)}
          autoComplete="username"
          className="rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-2 py-1 font-mono text-xs"
        />
        {slugError && (
          <span className="text-[0.6rem]" style={{ color: "var(--status-red)" }}>
            {slugError}
          </span>
        )}
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-[0.6rem] uppercase tracking-wide text-[var(--ink-tertiary)]">
          Display name
        </span>
        <input
          type="text"
          aria-label="Display name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          className="rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-2 py-1 text-xs"
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-[0.6rem] uppercase tracking-wide text-[var(--ink-tertiary)]">
          Password
        </span>
        <input
          type="password"
          aria-label="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="new-password"
          className="rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-2 py-1 font-mono text-xs"
        />
        {passwordError && (
          <span className="text-[0.6rem]" style={{ color: "var(--status-red)" }}>
            {passwordError}
          </span>
        )}
      </label>

      <button
        type="submit"
        disabled={!canSubmit}
        className="w-full rounded border border-[var(--border-hairline)] px-3 py-1 text-xs uppercase tracking-wider hover:bg-[var(--bg-subtle)] disabled:opacity-40"
      >
        {submitting ? "Creating..." : "Create account"}
      </button>

      {error && (
        <p className="text-[0.7rem]" style={{ color: "var(--status-red)" }} data-testid="signup-error">
          {error}
        </p>
      )}

      <button
        type="button"
        onClick={onSwitchToLogin}
        className="w-full text-[0.7rem] text-[var(--ink-tertiary)] hover:text-[var(--ink-secondary)]"
        data-testid="switch-to-login"
      >
        Already have an account? Sign in
      </button>
    </form>
  )
}
