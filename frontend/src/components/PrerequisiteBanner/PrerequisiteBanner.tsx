/**
 * PrerequisiteBanner — a visible honesty notice.
 *
 * Shown at the top of a step page when a step it depends on has not
 * been completed. The step is still usable (the app has defaults), but
 * the numbers on the page do not reflect the user's actual choices.
 * That is what this banner says.
 */

export type PrerequisiteBannerProps = {
  /** Human-readable description of the missing step, e.g. "Step 1
   *  (Design)". */
  missing: string
  /** What the panel does instead of using the missing step's output. */
  fallback: string
}

export function PrerequisiteBanner({ missing, fallback }: PrerequisiteBannerProps) {
  return (
    <div
      role="status"
      data-testid="prerequisite-banner"
      className="mb-4 flex items-start gap-3 rounded-md border border-[var(--status-orange)] bg-[var(--bg-subtle)] px-3 py-2 text-[12px]"
      style={{ borderColor: "var(--status-orange)" }}
    >
      <span aria-hidden="true" className="mt-0.5 text-[var(--status-orange)]">
        ⚠
      </span>
      <div>
        <div className="font-semibold text-[var(--ink-primary)]">
          {missing} not completed
        </div>
        <div className="text-[var(--ink-secondary)]">{fallback}</div>
      </div>
    </div>
  )
}
