import { useState } from "react"
import { AppShell, type AppShellNavItem } from "./components/AppShell/AppShell"
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
import { TourProvider } from "./features/Tour/TourProvider"
import { Telemetry } from "./features/Telemetry/Telemetry"
import { XAITrace } from "./features/XAITrace/XAITrace"

const NAV: AppShellNavItem[] = [
  { id: "twin", label: "Digital Twin & Orbit", tag: "4·7·10" },
  { id: "cleard", label: "CLEAR-D Synthesis", tag: "Part V" },
  { id: "xai", label: "Two-Tier XAI Core", tag: "15·26" },
  { id: "design", label: "Design Studio", tag: "P-V" },
  { id: "about", label: "About & Legend", tag: "21" },
  { id: "legal", label: "Terms & Privacy", tag: "S11·4" },
  { id: "status", label: "Status", tag: "S11·5" },
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

function LegalView() {
  return (
    <div className="mx-auto max-w-3xl space-y-6" data-testid="legal-view">
      <div className="apple-card space-y-3 p-6">
        <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--ink-tertiary)]">
          Legal — Sprint 11 s11-4
        </div>
        <h2 id="tos-heading" className="text-lg font-semibold">
          Terms of Service
        </h2>
        <p className="text-[12px] text-[var(--ink-secondary)]">
          Version 0.1 (template). Not legal advice; requires review by
          counsel before public deployment.
        </p>
        <ol className="list-decimal space-y-2 pl-5 text-[12px] text-[var(--ink-secondary)]">
          <li><b className="text-[var(--ink-primary)]">Acceptance.</b> By accessing the Service you agree to be bound by these Terms.</li>
          <li><b className="text-[var(--ink-primary)]">About the Service.</b>{" "}AeroGrid-XAI is a software-only research instrument. It does not build, test, or deploy physical hardware.</li>
          <li><b className="text-[var(--ink-primary)]">Licence.</b> Source code is dual-licensed AGPL-3.0 (community) and a proprietary Commercial EULA (enterprise).</li>
          <li><b className="text-[var(--ink-primary)]">Accounts.</b> You are responsible for the confidentiality of your credentials and all activity under your account.</li>
          <li><b className="text-[var(--ink-primary)]">Acceptable use.</b>{" "}No unauthorised access, no exceeding rate limits, no designing physical weapon systems.</li>
          <li><b className="text-[var(--ink-primary)]">Your content.</b>{" "}You retain all rights to mission configurations, architecture definitions, and designs you create.</li>
          <li><b className="text-[var(--ink-primary)]">Availability.</b>{" "}Provided as-is; no uptime commitment unless separately agreed.</li>
          <li><b className="text-[var(--ink-primary)]">Disclaimers.</b> No warranty, express or implied, of any simulation result, formal verification verdict, or AI prediction.</li>
          <li><b className="text-[var(--ink-primary)]">Liability.</b> No indirect, incidental, or consequential damages.</li>
          <li><b className="text-[var(--ink-primary)]">Termination.</b>{" "}Either party may terminate with reasonable notice.</li>
        </ol>
        <p className="text-[11px] text-[var(--ink-tertiary)]">
          Full text: <code className="font-mono">docs/legal/TERMS_OF_SERVICE.md</code>
        </p>
      </div>

      <div className="apple-card space-y-3 p-6">
        <h2 id="privacy-heading" className="text-lg font-semibold">
          Privacy Policy
        </h2>
        <p className="text-[12px] text-[var(--ink-secondary)]">
          Version 0.1 (template). Not legal advice; requires review by
          counsel before public deployment.
        </p>
        <h3 className="text-sm font-semibold text-[var(--ink-primary)]">What we collect</h3>
        <ul className="list-disc space-y-1 pl-5 text-[12px] text-[var(--ink-secondary)]">
          <li>Account data: slug, display name, bcrypt-hashed password.</li>
          <li>Session data: a JWT in browser localStorage, 24-hour expiry.</li>
          <li>Request metadata: IP, path, status, duration.</li>
          <li>Content you create: mission configurations, designs, exports.</li>
        </ul>
        <h3 className="text-sm font-semibold text-[var(--ink-primary)]">What we do NOT collect</h3>
        <p className="text-[12px] text-[var(--ink-secondary)]">
          No cookies. No third-party analytics. No tracking pixels. No email addresses. No biometric data.
        </p>
        <h3 className="text-sm font-semibold text-[var(--ink-primary)]">Where data lives</h3>
        <p className="text-[12px] text-[var(--ink-secondary)]">
          Everything runs on the operator&apos;s local macOS deployment: PostgreSQL, Redis, MinIO, Prometheus. No data leaves the machine unless you deliberately export it. Stripe sees billing details only if paid subscriptions are enabled.
        </p>
        <h3 className="text-sm font-semibold text-[var(--ink-primary)]">Your rights</h3>
        <p className="text-[12px] text-[var(--ink-secondary)]">
          Access, correction, deletion, and portability. Contact <code className="font-mono">sirkianmj@forgex4.com</code>.
        </p>
        <p className="text-[11px] text-[var(--ink-tertiary)]">
          Full text: <code className="font-mono">docs/legal/PRIVACY_POLICY.md</code>
        </p>
      </div>
    </div>
  )
}

function App() {
  const [activeView, setActiveView] = useState("twin")
  return (
    <TourProvider onRequestView={setActiveView}>
      <MissionProvider>
      <AppShell
        navItems={NAV}
        activeView={activeView}
        onViewChange={setActiveView}
      >
        <div className="mb-8">
          <MissionConfigBar />
        </div>

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
            <ArchitecturesView />
            <SensitivityPanel />
            <FanetGraph />
          </div>
        )}
        {activeView === "xai" && (
          <div className="mx-auto max-w-5xl space-y-6">
            <XAITrace />
          </div>
        )}
        {activeView === "design" && (
          <div className="mx-auto max-w-5xl space-y-6">
            <DesignStudio />
          </div>
        )}
        {activeView === "about" && <AboutView />}
        {activeView === "legal" && <LegalView />}
        {activeView === "status" && <StatusView />}
      </AppShell>
      </MissionProvider>
    </TourProvider>
  )
}

export default App
