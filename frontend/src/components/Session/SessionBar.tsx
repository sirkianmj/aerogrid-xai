/**
 * SessionBar — sign-in form and session state.
 *
 * Three modes when unauthenticated:
 *   login   (default)  tenant slug + password via LoginForm
 *   signup  (self-service)  create a new tenant via SignupForm
 *   token   (advanced) paste-a-JWT input, kept for integration tests,
 *                      CI, and the case where an operator has a
 *                      pre-issued token but no password on this tenant
 *
 * All three modes write to the same `aerogrid.token` localStorage key,
 * so every reader of that key across the app keeps working unchanged.
 *
 * When a token is present, the component shows a masked indicator and
 * a Sign out action. Sign out clears the token and reloads the page so
 * panels that cached a fetch reject it on the next request.
 */

import { useState } from "react"
import { LoginForm } from "./LoginForm"
import { SignupForm } from "./SignupForm"

const TOKEN_KEY = "aerogrid.token"

function readToken(): string | null {
  if (typeof window === "undefined") return null
  return window.localStorage.getItem(TOKEN_KEY)
}

type Mode = "login" | "signup" | "token"

export function SessionBar() {
  const [token, setToken] = useState<string | null>(() => readToken())
  const [mode, setMode] = useState<Mode>("login")
  const [draft, setDraft] = useState("")

  function persist(newToken: string) {
    window.localStorage.setItem(TOKEN_KEY, newToken)
    setToken(newToken)
    setDraft("")
  }

  function clear() {
    window.localStorage.removeItem(TOKEN_KEY)
    setToken(null)
    setDraft("")
    setMode("login")
    window.location.reload()
  }

  return (
    <section
      aria-labelledby="session-heading"
      className="mb-6 flex flex-wrap items-center gap-3 rounded border border-current/15 p-3 text-sm"
    >
      <h2 id="session-heading" className="text-xs uppercase tracking-wide opacity-60">
        Session
      </h2>

      {token ? (
        <>
          <span
            data-testid="session-token-present"
            className="font-mono text-xs opacity-70"
          >
            token …{token.slice(-12)}
          </span>
          <button
            type="button"
            onClick={clear}
            className="rounded border px-2 py-1 text-xs hover:bg-current/5"
          >
            Sign out
          </button>
        </>
      ) : mode === "login" ? (
        <>
          <LoginForm onSuccess={persist} onSwitchToToken={() => setMode("token")} />
          <button
            type="button"
            onClick={() => setMode("signup")}
            className="text-[0.65rem] uppercase tracking-wider opacity-60 hover:opacity-100"
            data-testid="switch-to-signup"
          >
            Create account
          </button>
        </>
      ) : mode === "signup" ? (
        <SignupForm
          onSuccess={persist}
          onSwitchToLogin={() => setMode("login")}
        />
      ) : (
        <>
          <label htmlFor="session-token-input" className="sr-only">
            JWT
          </label>
          <input
            id="session-token-input"
            type="password"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                const t = draft.trim()
                if (t) persist(t)
              }
            }}
            placeholder="paste JWT to enable metered endpoints"
            className="flex-1 min-w-64 rounded border border-current/20 bg-transparent px-2 py-1 font-mono text-xs"
            autoComplete="off"
            spellCheck={false}
          />
          <button
            type="button"
            onClick={() => {
              const t = draft.trim()
              if (t) persist(t)
            }}
            disabled={!draft.trim()}
            className="rounded border px-2 py-1 text-xs hover:bg-current/5 disabled:opacity-40"
          >
            Save
          </button>
          <button
            type="button"
            onClick={() => setMode("login")}
            className="text-[0.65rem] uppercase tracking-wider opacity-60 hover:opacity-100"
          >
            Use sign in
          </button>
        </>
      )}
    </section>
  )
}
