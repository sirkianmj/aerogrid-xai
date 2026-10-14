import { useState } from "react"
import { AppShell, type AppShellNavItem } from "./components/AppShell/AppShell"
import { EpistemicBadge } from "./components/EpistemicBadge/EpistemicBadge"
import { ALL_TAGS, EPISTEMIC_TAGS } from "./components/EpistemicBadge/epistemic"
import { SessionBar } from "./components/Session/SessionBar"
import { AdminPanel } from "./features/AdminPanel/AdminPanel"
import { ClearDDashboard } from "./features/ClearDDashboard/ClearDDashboard"
import { DigitalTwin } from "./features/DigitalTwin/DigitalTwin"
import { FanetGraph } from "./features/Fanet/FanetGraph"
import { Globe } from "./features/Globe/Globe"
import { MissionConfigBar } from "./features/MissionControl/MissionConfigBar"
import { MissionControl } from "./features/MissionControl/MissionControl"
import { MissionProvider } from "./features/MissionControl/MissionProvider"
import { Telemetry } from "./features/Telemetry/Telemetry"
import { TradeSpace } from "./features/TradeSpace/TradeSpace"
import { XAITrace } from "./features/XAITrace/XAITrace"

const NAV: AppShellNavItem[] = [
  { id: "twin", label: "Digital Twin & Orbit", tag: "4·7·10" },
  { id: "cleard", label: "CLEAR-D Synthesis", tag: "Part V" },
  { id: "xai", label: "Two-Tier XAI Core", tag: "15·26" },
  { id: "tradespace", label: "Trade Space", tag: "14" },
  { id: "admin", label: "SaaS & Admin", tag: "23" },
  { id: "about", label: "About & Legend", tag: "21" },
]

function AboutView() {
  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="apple-card space-y-3 p-5">
        <h2 className="text-[15px] font-semibold">
          Section 21 epistemic hierarchy
        </h2>
        <p className="text-[12px] text-[var(--ink-secondary)]">
          Every output artifact from the platform is tagged with one of
          seven categories, ordered from strongest to weakest evidentiary
          status. The badge component enforces the tag at the type level.
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

function App() {
  const [activeView, setActiveView] = useState("twin")
  const token =
    typeof window !== "undefined"
      ? window.localStorage.getItem("aerogrid.token")
      : null

  return (
    <MissionProvider>
      <AppShell
        navItems={NAV}
        activeView={activeView}
        onViewChange={setActiveView}
        sidebarExtra={
          <div className="space-y-3">
            <div className="px-2.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--ink-tertiary)]">
              Session
            </div>
            <SessionBar />
            <MissionConfigBar />
          </div>
        }
      >
        {activeView === "twin" && (
          <div className="mx-auto max-w-5xl space-y-6">
            <MissionControl />
            <Globe />
            <DigitalTwin />
            <Telemetry />
          </div>
        )}
        {activeView === "cleard" && (
          <div className="mx-auto max-w-5xl space-y-6">
            <ClearDDashboard />
            <FanetGraph />
          </div>
        )}
        {activeView === "xai" && (
          <div className="mx-auto max-w-5xl space-y-6">
            <XAITrace />
          </div>
        )}
        {activeView === "tradespace" && (
          <div className="mx-auto max-w-5xl space-y-6">
            <TradeSpace />
          </div>
        )}
        {activeView === "admin" && (
          <div className="mx-auto max-w-5xl space-y-6">
            <AdminPanel token={token} />
          </div>
        )}
        {activeView === "about" && <AboutView />}
      </AppShell>
    </MissionProvider>
  )
}

export default App
