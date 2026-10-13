import { useEffect, useState } from "react"
import { EpistemicBadge } from "./components/EpistemicBadge/EpistemicBadge"
import { ALL_TAGS, EPISTEMIC_TAGS } from "./components/EpistemicBadge/epistemic"
import { XAITrace } from "./features/XAITrace/XAITrace"

type HealthState =
  | { status: "loading" }
  | { status: "ok"; data: { status: string } }
  | { status: "error"; message: string }

function App() {
  const [health, setHealth] = useState<HealthState>({ status: "loading" })

  useEffect(() => {
    const controller = new AbortController()
    fetch("/api/health", { signal: controller.signal })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json() as Promise<{ status: string }>
      })
      .then((data) => setHealth({ status: "ok", data }))
      .catch((err: Error) => {
        if (err.name === "AbortError") return
        setHealth({ status: "error", message: err.message })
      })
    return () => controller.abort()
  }, [])

  return (
    <div className="min-h-screen p-8">
      <header className="mb-10">
        <h1 className="text-3xl font-semibold tracking-tight">AeroGrid-XAI</h1>
        <p className="mt-1 text-sm opacity-70">
          Mission Control — Sprint 7
        </p>
      </header>

      <section className="mb-10" aria-labelledby="backend-status-heading">
        <h2 id="backend-status-heading" className="mb-3 text-lg font-medium">
          Backend status
        </h2>
        {health.status === "loading" && <p className="opacity-70">Checking...</p>}
        {health.status === "ok" && (
          <p className="opacity-90">Connected: {health.data.status}</p>
        )}
        {health.status === "error" && (
          <p style={{ color: "var(--color-accent-amber)" }}>Error: {health.message}</p>
        )}
      </section>

      <XAITrace />

      <section aria-labelledby="epistemic-heading">
        <h2 id="epistemic-heading" className="mb-1 text-lg font-medium">
          Section 21 epistemic hierarchy
        </h2>
        <p className="mb-4 text-sm opacity-70">
          Every output artifact from the platform is tagged with one of
          these seven categories. The component enforces the tag at the
          type level.
        </p>
        <ul className="m-0 flex list-none flex-wrap gap-3 p-0">
          {ALL_TAGS.map((tag) => (
            <li key={tag} className="flex items-center gap-2">
              <EpistemicBadge tag={tag} />
              <span className="text-xs opacity-50">
                level {EPISTEMIC_TAGS[tag].level}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}

export default App
