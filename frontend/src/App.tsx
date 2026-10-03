import { useEffect, useState } from 'react'
import './App.css'

type HealthState =
  | { status: 'loading' }
  | { status: 'ok'; data: { status: string } }
  | { status: 'error'; message: string }

function App() {
  const [health, setHealth] = useState<HealthState>({ status: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/health', { signal: controller.signal })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json() as Promise<{ status: string }>
      })
      .then((data) => setHealth({ status: 'ok', data }))
      .catch((err: Error) => {
        if (err.name === 'AbortError') return
        setHealth({ status: 'error', message: err.message })
      })
    return () => controller.abort()
  }, [])

  return (
    <div className="app">
      <header className="app-header">
        <h1>AeroGrid-XAI</h1>
        <p className="subtitle">Mission Control — Sprint 0 scaffold</p>
      </header>

      <section className="status-panel">
        <h2>Backend status</h2>
        {health.status === 'loading' && <p className="state-loading">Checking...</p>}
        {health.status === 'ok' && (
          <p className="state-ok">Connected: {health.data.status}</p>
        )}
        {health.status === 'error' && (
          <p className="state-error">Error: {health.message}</p>
        )}
      </section>

      <footer className="app-footer">
        <p>Phase 0 — Foundation &amp; CI/CD</p>
      </footer>
    </div>
  )
}

export default App
