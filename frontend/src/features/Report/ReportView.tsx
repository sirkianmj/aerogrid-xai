/**
 * Step 6 — Report.
 *
 * Assembles the current session's state into the payload the backend's
 * POST /report/generate expects, POSTs it, and triggers a download of
 * the returned PDF. The view also previews which sections will be
 * present and which will render as "Not executed in this session" —
 * the same list the PDF's table of contents shows.
 *
 * Every output in the generated PDF is a Section 21 tagged artefact;
 * the panel itself carries the simulation_result tag because the
 * report is the Digital Twin's summary of the session.
 */

import { useRef, useState } from "react"
import { EpistemicBadge } from "../../components/EpistemicBadge/EpistemicBadge"
import { useMission } from "../MissionControl/missionContext"
import {
  downloadBlob,
  generateReport,
  ReportApiError,
  type ReportRequest,
} from "./reportApi"

type PanelState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; filename: string }
  | { status: "error"; message: string }

const SECTIONS: { step: number | null; label: string }[] = [
  { step: 1, label: "Step 1 · Design (from config)" },
  { step: 2, label: "Step 2 · Mission (from state)" },
  { step: 3, label: "Step 3 · Discovery" },
  { step: 4, label: "Step 4 · Selection (Trade Space)" },
  { step: 5, label: "Step 5 · Simulation" },
]

export function ReportView() {
  const { config, state, stepOutputs, completedSteps, markStepComplete } = useMission()
  const [panel, setPanel] = useState<PanelState>({ status: "idle" })
  const abortRef = useRef<AbortController | null>(null)

  async function run() {
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setPanel({ status: "loading" })

    const payload: ReportRequest = {
      mission_config: { ...config } as Record<string, unknown>,
      step_outputs: { ...stepOutputs },
      mission_state:
        state.status === "ok"
          ? (state.data as unknown as Record<string, unknown>)
          : null,
    }

    try {
      const blob = await generateReport(payload, ctrl.signal)
      if (ctrl.signal.aborted) return
      const timestamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19)
      const filename = `aerogrid-report-${timestamp}.pdf`
      downloadBlob(blob, filename)
      setPanel({ status: "ok", filename })
      if (!completedSteps.has(6)) markStepComplete(6)
    } catch (e) {
      if (ctrl.signal.aborted) return
      const message =
        e instanceof ReportApiError || e instanceof Error
          ? e.message
          : "unknown error"
      setPanel({ status: "error", message })
    }
  }

  function sectionStatus(step: number | null): { label: string; executed: boolean } {
    if (step === null) return { label: "—", executed: true }
    if (step === 1) return { label: "from config", executed: true }
    if (step === 2) return { label: state.status === "ok" ? "from state" : "not executed", executed: state.status === "ok" }
    const present = step in stepOutputs
    return { label: present ? "executed" : "not executed", executed: present }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">6 · Report</h2>
          <p className="mt-1 text-sm text-[var(--ink-secondary)]">
            Assembles the current session into a DARPA-style PDF: cover page,
            section-by-section results with Section 21 epistemic tags, and a
            reproducibility appendix. Sections not executed in this session
            appear as such rather than being omitted.
          </p>
        </div>
        <EpistemicBadge tag="simulation_result" />
      </header>

      <div className="rounded-xl border border-[var(--border-hairline)] bg-[var(--bg-surface)] p-4">
        <h3 className="mb-3 text-xs uppercase tracking-wider text-[var(--ink-tertiary)]">
          Sections that will be in the report
        </h3>
        <table className="w-full text-xs">
          <thead className="text-left text-[var(--ink-tertiary)]">
            <tr>
              <th className="py-1 font-normal">Section</th>
              <th className="py-1 font-normal text-right">Status</th>
            </tr>
          </thead>
          <tbody>
            {SECTIONS.map(({ step, label }) => {
              const s = sectionStatus(step)
              return (
                <tr
                  key={label}
                  className="border-t border-[var(--border-hairline)]"
                >
                  <td className="py-1.5">{label}</td>
                  <td
                    className={
                      "py-1.5 text-right " +
                      (s.executed
                        ? "text-[var(--ink-secondary)]"
                        : "text-[var(--ink-tertiary)] italic")
                    }
                  >
                    {s.label}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={run}
            disabled={panel.status === "loading"}
            className="apple-btn apple-btn-primary disabled:opacity-40"
          >
            {panel.status === "loading" ? "Generating…" : "Generate PDF report"}
          </button>
          {panel.status === "ok" && (
            <span className="text-xs text-[var(--ink-tertiary)]">
              Downloaded {panel.filename}
            </span>
          )}
        </div>

        {panel.status === "error" && (
          <div className="mt-3 rounded-lg border border-[#ff3b30]/40 bg-[#ff3b30]/5 p-3 text-sm text-[#ff3b30]">
            {panel.message}
          </div>
        )}
      </div>
    </div>
  )
}
