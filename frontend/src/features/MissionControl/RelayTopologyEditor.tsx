/**
 * RelayTopologyEditor — configure a multi-hop UAV relay chain.
 *
 * A chain is an ordered list of UAV IDs: source -> chain[0] -> chain[1]
 * -> ... -> chain[-1]. The first hop is charged directly by the source
 * (satellite or ground transmitter). Each subsequent hop receives power
 * forwarded by the previous hop. UAVs not in the chain receive zero
 * power under multi-hop mode.
 *
 * Input format: comma-separated UAV IDs (e.g. "0,1,2"). Order matters.
 * Blank = direct mode (each UAV charged independently).
 *
 * Validation is local: every ID must be in [0, n_uavs), no duplicates.
 * Invalid input is rejected and the last valid value stays applied.
 */

import { useState } from "react"

export type RelayTopologyEditorProps = {
  nUavs: number
  relayTopology: number[] | null
  relayFraction: number
  onChange: (patch: {
    relay_topology?: number[] | null
    relay_fraction?: number
  }) => void
}

export function parseRelayChain(
  text: string,
  nUavs: number,
): { chain: number[] | null; error: string | null } {
  const trimmed = text.trim()
  if (trimmed === "") return { chain: null, error: null }
  const parts = trimmed.split(",").map((p) => p.trim())
  if (parts.length === 0) return { chain: null, error: "empty chain" }
  const ids: number[] = []
  for (const p of parts) {
    const n = Number(p)
    if (!Number.isInteger(n)) {
      return { chain: null, error: `"${p}" is not an integer` }
    }
    if (n < 0 || n >= nUavs) {
      return { chain: null, error: `UAV ${n} is not in [0, ${nUavs})` }
    }
    if (ids.includes(n)) {
      return { chain: null, error: `UAV ${n} appears twice` }
    }
    ids.push(n)
  }
  return { chain: ids, error: null }
}

export function RelayTopologyEditor({
  nUavs,
  relayTopology,
  relayFraction,
  onChange,
}: RelayTopologyEditorProps) {
  const [draft, setDraft] = useState<string>(
    relayTopology === null ? "" : relayTopology.join(","),
  )
  const [error, setError] = useState<string | null>(null)

  if (nUavs < 2) {
    return (
      <div
        className="mb-3 rounded border border-[var(--border-hairline)] bg-[var(--bg-subtle)] p-2 text-xs text-[var(--ink-tertiary)]"
        data-testid="relay-editor-too-few-uavs"
      >
        Multi-hop relay requires at least 2 UAVs (currently {nUavs}).
      </div>
    )
  }

  function commit(next: string) {
    setDraft(next)
    const { chain, error: parseErr } = parseRelayChain(next, nUavs)
    if (parseErr) {
      setError(parseErr)
      return
    }
    setError(null)
    onChange({ relay_topology: chain })
  }

  return (
    <div
      className="mb-3 rounded border border-[var(--border-hairline)] bg-[var(--bg-subtle)] p-2"
      data-testid="relay-topology-editor"
    >
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <span className="text-[0.65rem] uppercase tracking-wide text-[var(--ink-tertiary)]">
          Multi-hop relay chain
        </span>
        <span className="text-[0.6rem] text-[var(--ink-tertiary)]">
          blank = direct mode
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="text"
          aria-label="Relay chain UAV IDs"
          placeholder="e.g. 0,1,2"
          value={draft}
          onChange={(e) => commit(e.target.value)}
          className="w-40 rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-2 py-1 font-mono text-xs"
        />
        <label className="flex items-center gap-1">
          <span className="text-[0.65rem] text-[var(--ink-tertiary)]">
            Forward fraction
          </span>
          <input
            type="number"
            aria-label="Relay forward fraction"
            min={0.05}
            max={1.0}
            step={0.05}
            value={relayFraction}
            onChange={(e) => {
              const v = Number(e.target.value)
              if (!Number.isFinite(v)) return
              if (v <= 0 || v > 1) return
              onChange({ relay_fraction: v })
            }}
            className="w-20 rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-2 py-1 font-mono text-xs"
          />
        </label>
      </div>
      {error && (
        <div
          className="mt-1 text-[0.65rem]"
          style={{ color: "var(--status-red)" }}
          data-testid="relay-editor-error"
        >
          {error}
        </div>
      )}
      {!error && relayTopology && relayTopology.length > 0 && (
        <div
          className="mt-1 font-mono text-[0.65rem] text-[var(--ink-secondary)]"
          data-testid="relay-editor-chain"
        >
          source {"\u2192"} {relayTopology.map((id) => `UAV-${id}`).join(" \u2192 ")}
        </div>
      )}
    </div>
  )
}
