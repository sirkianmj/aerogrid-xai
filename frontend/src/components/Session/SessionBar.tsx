/**
 * SessionBar — minimal JWT session control.
 *
 * Reads the `aerogrid.token` key from localStorage. When the input is
 * empty and no token is stored, it shows a prompt. When a token is
 * stored, it shows a masked indicator with Save / Clear actions.
 *
 * The component deliberately does not validate the token itself. JWT
 * verification is the backend's responsibility; a bad token is
 * surfaced by whichever panel tries to use it (401 / 403 in the
 * payload). This keeps the component stateless about server
 * semantics.
 *
 * Why a component and not a full auth flow: the specification
 * (s8-7) built the admin panel superadmin-only. A real signup / login
 * UI is a separate sprint item; the SessionBar exists so that a
 * developer or operator can paste a token without opening DevTools.
 */

import { useState } from "react"

const TOKEN_KEY = "aerogrid.token"

function readToken(): string | null {
  if (typeof window === "undefined") return null
  return window.localStorage.getItem(TOKEN_KEY)
}

export function SessionBar() {
  const [draft, setDraft] = useState("")
  const [token, setToken] = useState<string | null>(() => readToken())

  function save() {
    const trimmed = draft.trim()
    if (!trimmed) return
    window.localStorage.setItem(TOKEN_KEY, trimmed)
    setToken(trimmed)
    setDraft("")
    window.location.reload()
  }

  function clear() {
    window.localStorage.removeItem(TOKEN_KEY)
    setToken(null)
    setDraft("")
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
            Clear
          </button>
        </>
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
              if (e.key === "Enter") save()
            }}
            placeholder="paste JWT to enable metered endpoints"
            className="flex-1 min-w-64 rounded border border-current/20 bg-transparent px-2 py-1 font-mono text-xs"
            autoComplete="off"
            spellCheck={false}
          />
          <button
            type="button"
            onClick={save}
            disabled={!draft.trim()}
            className="rounded border px-2 py-1 text-xs hover:bg-current/5 disabled:opacity-40"
          >
            Save
          </button>
        </>
      )}
    </section>
  )
}
