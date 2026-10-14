/**
 * GlobeControls — time scrubber, satellite picker, play/pause, speed.
 *
 * Purely presentational. All state lives in the parent Globe panel so
 * that the animation, the scene, and the metadata table stay in sync.
 * The controls do not fetch anything; they call the callbacks they are
 * given.
 */

import type { SatelliteInfo } from "./orbitalApi"

const SPEED_OPTIONS = [1, 4, 16, 64] as const

export type GlobeControlsProps = {
  catalog: SatelliteInfo[]
  selected: string
  onSelect: (key: string) => void
  playheadIndex: number
  totalPoints: number
  onScrub: (index: number) => void
  isPlaying: boolean
  onTogglePlay: () => void
  speed: number
  onSpeedChange: (speed: number) => void
  onReset: () => void
  currentTimeIso: string
  disabled: boolean
}

export function GlobeControls({
  catalog,
  selected,
  onSelect,
  playheadIndex,
  totalPoints,
  onScrub,
  isPlaying,
  onTogglePlay,
  speed,
  onSpeedChange,
  onReset,
  currentTimeIso,
  disabled,
}: GlobeControlsProps) {
  const maxIndex = Math.max(0, totalPoints - 1)
  return (
    <div
      className="mb-3 flex flex-wrap items-center gap-3 apple-card px-3 py-2 text-sm"
      data-testid="globe-controls"
    >
      <label className="flex items-center gap-2">
        <span className="text-[0.65rem] uppercase tracking-wide text-[var(--ink-tertiary)]">Satellite</span>
        <select
          aria-label="Satellite"
          value={selected}
          onChange={(e) => onSelect(e.target.value)}
          disabled={disabled}
          className="rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-2 py-0.5 font-mono text-xs"
        >
          {catalog.map((s) => (
            <option key={s.key} value={s.key}>
              {s.name}
            </option>
          ))}
        </select>
      </label>

      <button
        type="button"
        onClick={onTogglePlay}
        disabled={disabled || totalPoints < 2}
        className="rounded border border-[var(--border-hairline)] px-2 py-0.5 text-xs uppercase tracking-wider hover:bg-[var(--bg-subtle)] disabled:opacity-40"
        aria-label={isPlaying ? "Pause" : "Play"}
        data-testid="play-toggle"
      >
        {isPlaying ? "Pause" : "Play"}
      </button>

      <button
        type="button"
        onClick={onReset}
        disabled={disabled || totalPoints < 2}
        className="rounded border border-[var(--border-hairline)] px-2 py-0.5 text-xs uppercase tracking-wider hover:bg-[var(--bg-subtle)] disabled:opacity-40"
      >
        Reset
      </button>

      <label className="flex items-center gap-2 flex-1 min-w-72">
        <span className="text-[0.65rem] uppercase tracking-wide text-[var(--ink-tertiary)]">Time</span>
        <input
          type="range"
          aria-label="Time"
          min={0}
          max={maxIndex}
          value={playheadIndex}
          onChange={(e) => onScrub(Number(e.target.value))}
          disabled={disabled || totalPoints < 2}
          className="flex-1"
        />
        <span
          className="font-mono text-xs text-[var(--ink-tertiary)] w-56 truncate"
          data-testid="current-time"
          title={currentTimeIso}
        >
          {currentTimeIso}
        </span>
      </label>

      <label className="flex items-center gap-2">
        <span className="text-[0.65rem] uppercase tracking-wide text-[var(--ink-tertiary)]">Speed</span>
        <select
          aria-label="Speed"
          value={speed}
          onChange={(e) => onSpeedChange(Number(e.target.value))}
          disabled={disabled}
          className="rounded border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-2 py-0.5 font-mono text-xs"
        >
          {SPEED_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s}×
            </option>
          ))}
        </select>
      </label>
    </div>
  )
}
