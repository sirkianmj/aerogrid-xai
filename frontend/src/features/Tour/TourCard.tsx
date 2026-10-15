/**
 * TourCard — the card content for one tour step.
 *
 * Pure presentational component. The overlay positions it; the card
 * renders the chapter title, step title, body, progress indicator,
 * and the three navigation buttons.
 */

import type { TourStep } from "./tourDefinitions"

export type TourCardProps = {
  step: TourStep
  stepIndex: number
  totalSteps: number
  onBack: () => void
  onNext: () => void
  onSkip: () => void
}

export function TourCard({
  step,
  stepIndex,
  totalSteps,
  onBack,
  onNext,
  onSkip,
}: TourCardProps) {
  const isFirst = stepIndex === 0
  const isLast = stepIndex === totalSteps - 1

  return (
    <div
      role="dialog"
      aria-label={`Tour step ${step.id}: ${step.title}`}
      className="flex w-[360px] flex-col gap-3 rounded-xl border border-[var(--border-hairline)] bg-[var(--bg-surface)] p-5 shadow-[var(--shadow-lg)]"
      data-testid="tour-card"
    >
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--ink-tertiary)]">
          Chapter {step.chapterId} — {step.chapterTitle}
        </span>
        <span className="font-mono text-[11px] text-[var(--ink-tertiary)]">
          {stepIndex + 1} / {totalSteps}
        </span>
      </div>

      <h3 className="text-title-3">{step.title}</h3>

      <p className="text-footnote text-[var(--ink-secondary)]">{step.body}</p>

      <div className="mt-2 flex items-center justify-between gap-2">
        <button
          type="button"
          className="text-footnote text-[var(--ink-tertiary)] hover:text-[var(--ink-primary)]"
          onClick={onSkip}
        >
          {isLast ? "Done" : "Skip tour"}
        </button>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onBack}
            disabled={isFirst}
            className="apple-btn apple-btn-secondary disabled:cursor-not-allowed disabled:opacity-40"
          >
            Back
          </button>
          <button
            type="button"
            onClick={onNext}
            className="apple-btn apple-btn-primary"
          >
            {isLast ? "Finish" : "Next"}
          </button>
        </div>
      </div>
    </div>
  )
}
