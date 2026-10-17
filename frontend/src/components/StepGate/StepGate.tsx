/**
 * StepGate — a hard gate between workflow steps.
 *
 * If the step this gate depends on has not been completed, the gate
 * does not render its children at all. The user sees a full-page
 * message telling them which step to complete first. There is no
 * "warning" state: either the prerequisite is done and the panel
 * renders, or it is not and the panel does not exist on this page.
 *
 * The user can still click any step in the sidebar. They just do not
 * get the panel until they have done the work that panel depends on.
 */

import type { ReactNode } from "react"
import { useMission } from "../../features/MissionControl/missionContext"

const STEP_LABEL: Record<number, string> = {
  1: "1 · Design",
  2: "2 · Mission",
  3: "3 · Discovery",
  4: "4 · Selection",
  5: "5 · Simulation",
}

export type StepGateProps = {
  /** The step this content depends on. Not the step it belongs to. */
  requires: number
  children: ReactNode
}

export function StepGate({ requires, children }: StepGateProps) {
  const { completedSteps } = useMission()

  if (completedSteps.has(requires)) {
    return <>{children}</>
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div
        className="apple-card p-8"
        data-testid={`step-gate-${requires}`}
        role="alert"
      >
        <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--status-orange)]">
          Blocked
        </div>
        <h2 className="text-title-3 mb-3">
          Step {STEP_LABEL[requires] ?? requires} is not complete
        </h2>
        <p className="text-footnote text-[var(--ink-secondary)]">
          This step depends on the output of {STEP_LABEL[requires] ?? `step ${requires}`}.
          Complete that step first, then return here.
        </p>
        <p className="mt-4 text-caption-1 text-[var(--ink-tertiary)]">
          The workflow is sequential. Every step produces an artifact
          the next step consumes. Running a later step against a
          default artifact is the failure mode this gate prevents.
        </p>
      </div>
    </div>
  )
}
