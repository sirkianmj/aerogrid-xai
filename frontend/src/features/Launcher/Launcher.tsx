/**
 * Launcher — the entry screen of the application.
 *
 * Three template cards (Quickstart, Fixed-Wing Endurance, Degraded
 * Atmosphere), each resets the mission to a known-good configuration
 * and navigates to Step 1. Plus a "New Project" card that resets to
 * DEFAULT_CONFIG without any template patch.
 *
 * Deliberate design choice: templates do NOT pre-run any step. They
 * set up the mission; the user walks the six-step workflow themselves.
 * That is what makes them useful as verification: run each template
 * end-to-end to confirm all features work under different conditions.
 */

import { EpistemicBadge } from "../../components/EpistemicBadge/EpistemicBadge"
import { useMission } from "../MissionControl/missionContext"
import { TEMPLATES, type TemplateConfig } from "./templates"

type LauncherProps = {
  onNavigateToWorkflow: (id: string) => void
}

export function Launcher({ onNavigateToWorkflow }: LauncherProps) {
  const { resetMission, applyConfig } = useMission()

  function handleNewProject() {
    resetMission()
    onNavigateToWorkflow("design")
  }

  function handleTemplate(t: TemplateConfig) {
    resetMission()
    applyConfig(t.configPatch)
    onNavigateToWorkflow("design")
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <header className="space-y-2">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">AeroGrid-XAI</h1>
          <EpistemicBadge tag="simulation_result" />
        </div>
        <p className="text-sm text-[var(--ink-secondary)]">
          CLEAR-D Mission Instrument. Pick a template to begin, or start
          with a fresh mission and configure the parameters yourself.
        </p>
      </header>

      <section>
        <h2 className="mb-3 text-xs uppercase tracking-wider text-[var(--ink-tertiary)]">
          Start a new project
        </h2>
        <button
          type="button"
          onClick={handleNewProject}
          className="w-full rounded-xl border border-[var(--border-hairline)] bg-[var(--bg-surface)] p-5 text-left transition-colors hover:border-[var(--accent-pressed)]"
          data-testid="launcher-new-project"
        >
          <div className="flex items-baseline justify-between gap-3">
            <span className="font-semibold">Blank project</span>
            <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--ink-tertiary)]">
              DEFAULT CONFIG
            </span>
          </div>
          <p className="mt-1 text-sm text-[var(--ink-secondary)]">
            Start from the default mission configuration. All parameters
            are editable in the sidebar after starting.
          </p>
        </button>
      </section>

      <section>
        <h2 className="mb-3 text-xs uppercase tracking-wider text-[var(--ink-tertiary)]">
          Templates
        </h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {TEMPLATES.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => handleTemplate(t)}
              className="rounded-xl border border-[var(--border-hairline)] bg-[var(--bg-surface)] p-5 text-left transition-colors hover:border-[var(--accent-pressed)]"
              data-testid={`launcher-template-${t.id}`}
            >
              <div className="mb-2 font-mono text-[10px] uppercase tracking-wider text-[var(--ink-tertiary)]">
                {t.badge}
              </div>
              <div className="font-semibold">{t.name}</div>
              <p className="mt-2 text-sm text-[var(--ink-secondary)]">
                {t.description}
              </p>
            </button>
          ))}
        </div>
      </section>

      <footer className="border-t border-[var(--border-hairline)] pt-4 font-mono text-[11px] text-[var(--ink-tertiary)]">
        Selecting a template resets the mission and navigates to Step 1.
        Nothing is run until you press a step&rsquo;s primary button.
      </footer>
    </div>
  )
}
