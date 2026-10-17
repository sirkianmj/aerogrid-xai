import { useCallback, useState } from "react"
import { AppShell, type AppShellNavItem } from "./components/AppShell/AppShell"
import { StepGate } from "./components/StepGate/StepGate"
import { EpistemicBadge } from "./components/EpistemicBadge/EpistemicBadge"
import { ALL_TAGS, EPISTEMIC_TAGS } from "./components/EpistemicBadge/epistemic"
import { ArchitecturesView } from "./features/Architectures/ArchitecturesView"
import { SensitivityPanel } from "./features/Sensitivity/SensitivityPanel"
import { DesignStudio } from "./features/DesignStudio/DesignStudio"
import { StatusView } from "./features/Status/StatusView"
import { ClearDDashboard } from "./features/ClearDDashboard/ClearDDashboard"
import { DigitalTwin } from "./features/DigitalTwin/DigitalTwin"
import { FanetGraph } from "./features/Fanet/FanetGraph"
import { Globe } from "./features/Globe/Globe"
import { MissionConfigBar } from "./features/MissionControl/MissionConfigBar"
import { MissionControl } from "./features/MissionControl/MissionControl"
import { MissionProvider } from "./features/MissionControl/MissionProvider"
import { useMission } from "./features/MissionControl/missionContext"
import { TourProvider } from "./features/Tour/TourProvider"
import { Telemetry } from "./features/Telemetry/Telemetry"
import { TradeSpace } from "./features/TradeSpace/TradeSpace"
import { XAITrace } from "./features/XAITrace/XAITrace"

// The linear workflow. Order matters: it is the order the user is
// meant to walk through the instrument, from designing hardware to
// producing a report.
const WORKFLOW_STEPS: AppShellNavItem[] = [
  { id: "design", label: "1 · Design", tag: "P-V" },
  { id: "twin", label: "2 · Mission", tag: "4·7·10" },
  { id: "cleard", label: "3 · Discovery", tag: "Part V" },
  { id: "tradespace", label: "4 · Selection", tag: "14" },
  { id: "simulation", label: "5 · Simulation", tag: "S12" },
  { id: "report", label: "6 · Report", tag: "S12" },
]

const META_ITEMS: AppShellNavItem[] = [
  { id: "xai", label: "Trust & XAI", tag: "15·26" },
  { id: "about", label: "About", tag: "21" },
  { id: "legal", label: "Legal", tag: "S11·4" },
  { id: "status", label: "Status", tag: "S11·5" },
]

const NAV: AppShellNavItem[] = [...WORKFLOW_STEPS, ...META_ITEMS]

const STEP_OF: Record<string, number> = {
  design: 1, twin: 2, cleard: 3, tradespace: 4, simulation: 5, report: 6,
}

function nextStepFor(view: string): string | null {
  const step = STEP_OF[view]
  if (!step || step === WORKFLOW_STEPS.length) return null
  return WORKFLOW_STEPS[step]?.id ?? null
}

function NextButton({
  view,
  onGo,
  completes,
}: {
  view: string
  onGo: (id: string) => void
  completes: number
}) {
  const { completedSteps } = useMission()
  const next = nextStepFor(view)
  if (!next) return null
  const target = WORKFLOW_STEPS.find((s) => s.id === next)
  const isDone = completedSteps.has(completes)
  return (
    <div className="mx-auto mt-10 max-w-5xl border-t border-[var(--border-hairline)] pt-6">
      <button
        type="button"
        onClick={() => onGo(next)}
        disabled={!isDone}
        className="apple-btn apple-btn-primary disabled:cursor-not-allowed disabled:opacity-40"
        data-testid={`next-step-${next}`}
        title={isDone ? undefined : "Complete this step first"}
      >
        {isDone ? "Next: " : "Complete this step to continue: "}
        {target?.label.replace(/^\d+ · /, "")} →
      </button>
    </div>
  )
}

function Placeholder({ title, description }: { title: string; description: string }) {
  return (
    <div className="mx-auto max-w-3xl">
      <div className="apple-card p-8">
        <h2 className="text-title-2 mb-3">{title}</h2>
        <p className="text-footnote text-[var(--ink-secondary)]">{description}</p>
        <p className="mt-6 text-caption-1 text-[var(--ink-tertiary)]">
          This step is part of the linear workflow. It will be wired
          to the backend in a follow-up. The panels above are fully
          functional; this one is a placeholder that records the
          workflow slot.
        </p>
      </div>
    </div>
  )
}

function AboutView() {
  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="apple-card space-y-3 p-5">
        <h2 className="text-[15px] font-semibold">Section 21 epistemic hierarchy</h2>
        <p className="text-[12px] text-[var(--ink-secondary)]">
          Every output artifact is tagged with one of seven categories.
        </p>
        <ul className="space-y-2">
          {ALL_TAGS.map((tag) => (
            <li key={tag} className="flex items-center gap-3">
              <EpistemicBadge tag={tag} />
              <span className="font-mono text-[11px] text-[var(--ink-tertiary)]">
                level {EPISTEMIC_TAGS[tag].level}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

function LegalView() {
  return (
    <div className="mx-auto max-w-3xl space-y-6" data-testid="legal-view">
      <div className="apple-card space-y-3 p-6">
        <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--ink-tertiary)]">
          Legal — Sprint 11 s11-4
        </div>
        <h2 id="tos-heading" className="text-lg font-semibold">Terms of Service</h2>
        <p className="text-[12px] text-[var(--ink-secondary)]">
          Version 0.1 (template). Not legal advice; requires review by counsel before public deployment.
        </p>
        <p className="text-[11px] text-[var(--ink-tertiary)]">
          Full text: <code className="font-mono">docs/legal/TERMS_OF_SERVICE.md</code>
        </p>
      </div>
      <div className="apple-card space-y-3 p-6">
        <h2 id="privacy-heading" className="text-lg font-semibold">Privacy Policy</h2>
        <p className="text-[12px] text-[var(--ink-secondary)]">
          Version 0.1 (template). Not legal advice; requires review by counsel.
        </p>
        <p className="text-[11px] text-[var(--ink-tertiary)]">
          Full text: <code className="font-mono">docs/legal/PRIVACY_POLICY.md</code>
        </p>
      </div>
    </div>
  )
}

const STEP_TO_VIEW: Record<number, string> = {
  1: "design",
  2: "twin",
  3: "cleard",
  4: "tradespace",
  5: "simulation",
  6: "report",
}

type AppInnerProps = {
  activeView: string
  visited: ReadonlySet<string>
  handleViewChange: (id: string) => void
}

function AppInner({ activeView, visited, handleViewChange }: AppInnerProps) {
  const { completedSteps } = useMission()
  const completedViewIds = new Set<string>()
  for (const step of completedSteps) {
    const v = STEP_TO_VIEW[step]
    if (v) completedViewIds.add(v)
  }

  return (
    <AppShell
      navItems={NAV}
      activeView={activeView}
      onViewChange={handleViewChange}
      completedViewIds={completedViewIds}
    >
      <div className="mb-8">
        <MissionConfigBar />
      </div>

      {visited.has("design") && (
        <div hidden={activeView !== "design"}>
          <div className="mx-auto max-w-5xl space-y-6">
            <DesignStudio />
          </div>
          <NextButton view="design" onGo={handleViewChange} completes={1} />
        </div>
      )}

      {visited.has("twin") && (
        <div hidden={activeView !== "twin"}>
          <StepGate requires={1}>
            <div className="mx-auto max-w-5xl space-y-6">
              <MissionControl />
              <Globe />
              <DigitalTwin />
              <Telemetry />
            </div>
            <NextButton view="twin" onGo={handleViewChange} completes={2} />
          </StepGate>
        </div>
      )}

      {visited.has("cleard") && (
        <div hidden={activeView !== "cleard"}>
          <StepGate requires={2}>
            <div className="mx-auto max-w-5xl space-y-6">
              <ClearDDashboard />
              <ArchitecturesView />
              <SensitivityPanel />
              <FanetGraph />
            </div>
            <NextButton view="cleard" onGo={handleViewChange} completes={3} />
          </StepGate>
        </div>
      )}

      {visited.has("tradespace") && (
        <div hidden={activeView !== "tradespace"}>
          <StepGate requires={3}>
            <div className="mx-auto max-w-5xl space-y-6">
              <TradeSpace />
            </div>
            <NextButton view="tradespace" onGo={handleViewChange} completes={4} />
          </StepGate>
        </div>
      )}

      {visited.has("simulation") && (
        <div hidden={activeView !== "simulation"}>
          <StepGate requires={4}>
            <Placeholder
              title="5 · Simulation"
              description="Runs the selected architecture against the mission over a full orbit: power delivered over time, thermal margins, eclipse intervals, cumulative energy. Backend endpoint not yet wired."
            />
            <NextButton view="simulation" onGo={handleViewChange} completes={5} />
          </StepGate>
        </div>
      )}

      {visited.has("report") && (
        <div hidden={activeView !== "report"}>
          <StepGate requires={5}>
            <Placeholder
              title="6 · Report"
              description="The DARPA-grade export: PDF, structured JSON with per-number provenance, chart exports, manifest, reproduce.sh. Backend generator not yet built."
            />
          </StepGate>
        </div>
      )}

      {visited.has("xai") && (
        <div hidden={activeView !== "xai"}>
          <div className="mx-auto max-w-5xl space-y-6">
            <XAITrace />
          </div>
        </div>
      )}

      {visited.has("about") && (
        <div hidden={activeView !== "about"}><AboutView /></div>
      )}

      {visited.has("legal") && (
        <div hidden={activeView !== "legal"}><LegalView /></div>
      )}

      {visited.has("status") && (
        <div hidden={activeView !== "status"}><StatusView /></div>
      )}
    </AppShell>
  )
}

function App({
  initialCompletedSteps,
}: {
  initialCompletedSteps?: readonly number[]
} = {}) {
  const [activeView, setActiveView] = useState("design")
  const [visited, setVisited] = useState<Set<string>>(() => new Set(["design"]))

  const handleViewChange = useCallback((id: string) => {
    setActiveView(id)
    setVisited((prev) => {
      if (prev.has(id)) return prev
      const next = new Set(prev)
      next.add(id)
      return next
    })
  }, [])

  return (
    <TourProvider onRequestView={handleViewChange}>
      <MissionProvider initialCompletedSteps={initialCompletedSteps}>
        <AppInner
          activeView={activeView}
          visited={visited}
          handleViewChange={handleViewChange}
        />
      </MissionProvider>
    </TourProvider>
  )
}

export default App
