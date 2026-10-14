/**
 * AppShell — the macOS-style three-pane frame for the workstation.
 *
 * Layout:
 *
 *     ┌────────────────────────────────────────────────────────────┐
 *     │ title bar:  traffic lights │ segmented view switcher │ rhs  │
 *     ├──────────────┬─────────────────────────────────────────────┤
 *     │              │                                             │
 *     │   sidebar    │              center canvas                  │
 *     │              │                                             │
 *     └──────────────┴─────────────────────────────────────────────┘
 *
 * The title bar shows the two invariants this project actually enforces
 * at CI:
 *
 *   - "Tier-2 Firewall Verified"  — the static analyzer in
 *     backend/app/control/static_analyzer.py is a required CI gate;
 *     it verifies that no Tier 2 function is reachable from the action
 *     interface.
 *   - "AGPL-3.0"                  — the license the repository ships
 *     under (dual-license, but AGPL-3.0 is the community default).
 *
 * No live server status is displayed here. A real live-Z3 badge needs a
 * status source (a /mission/state field or a telemetry channel) and is
 * deferred to a later PR. Showing a static "SAT ε=0.019" string — as
 * the mockup does — would be a fabricated number, which the project's
 * own rules forbid.
 */

import type { ReactNode } from "react"

export type AppShellNavItem = {
  id: string
  label: string
  /** Optional short tag rendered to the right of the label. */
  tag?: string
}

export type AppShellProps = {
  navItems: AppShellNavItem[]
  activeView: string
  onViewChange: (id: string) => void
  /** Content of the center pane. */
  children: ReactNode
  /** Optional content rendered below the nav list in the sidebar. */
  sidebarExtra?: ReactNode
  /** Optional content rendered in the right-hand inspector. */
  inspector?: ReactNode
}

export function AppShell({
  navItems,
  activeView,
  onViewChange,
  children,
  sidebarExtra,
  inspector,
}: AppShellProps) {
  return (
    <div className="flex h-screen w-screen flex-col bg-[var(--bg-canvas)] text-[var(--ink-primary)]">
      <header className="flex h-12 shrink-0 items-center justify-between gap-4 border-b border-[var(--border-hairline)] bg-[var(--bg-surface)] px-4 backdrop-blur-md">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span
              aria-hidden="true"
              className="h-3 w-3 rounded-full border border-black/10 bg-[#ff5f56]"
            />
            <span
              aria-hidden="true"
              className="h-3 w-3 rounded-full border border-black/10 bg-[#ffbd2e]"
            />
            <span
              aria-hidden="true"
              className="h-3 w-3 rounded-full border border-black/10 bg-[#27c93f]"
            />
          </div>
          <div className="h-4 w-px bg-[var(--border-hairline)]" />
          <div className="flex items-baseline gap-2">
            <span className="text-[13px] font-semibold tracking-tight">
              AeroGrid-XAI
            </span>
            <span className="font-mono text-[11px] text-[var(--ink-secondary)]">
              Rev. 6 Unified Specification
            </span>
          </div>
        </div>

        <nav
          aria-label="Workspace views"
          className="segmented-track hidden lg:inline-flex"
        >
          {navItems.map((item) => {
            const active = activeView === item.id
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onViewChange(item.id)}
                aria-current={active ? "page" : undefined}
                className={`segmented-item ${active ? "active" : ""}`}
              >
                {item.label}
              </button>
            )
          })}
        </nav>

        <div className="flex items-center gap-2.5">
          <span
            title="Backend static analyzer (backend/app/control/static_analyzer.py) enforces at CI that no Tier 2 function is reachable from the action interface without passing through Tier 1."
            className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border-hairline)] bg-[var(--bg-subtle)] px-2.5 py-1 text-[11px] font-mono text-[var(--ink-primary)]"
          >
            <span
              aria-hidden="true"
              className="h-1.5 w-1.5 rounded-full bg-[var(--status-green)]"
            />
            <span>Tier-2 Firewall Verified</span>
          </span>
          <span
            title="Repository dual-license: AGPL-3.0 for community use, proprietary EULA for enterprise."
            className="hidden xl:inline-flex items-center gap-1.5 rounded-md border border-[var(--border-hairline)] bg-[var(--bg-subtle)] px-2.5 py-1 text-[11px] font-mono text-[var(--ink-primary)]"
          >
            <span>AGPL-3.0</span>
          </span>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside
          aria-label="Primary"
          className="flex w-60 shrink-0 flex-col gap-5 overflow-y-auto border-r border-[var(--border-hairline)] bg-[var(--bg-sidebar)] p-3"
        >
          <div>
            <div className="mb-1.5 px-2.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--ink-tertiary)]">
              Platform modules
            </div>
            <div className="space-y-0.5">
              {navItems.map((item) => {
                const active = activeView === item.id
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => onViewChange(item.id)}
                    className={`flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-left text-[12px] transition ${
                      active
                        ? "bg-[color-mix(in_srgb,var(--border-hairline)_60%,transparent)] font-semibold text-[var(--ink-primary)]"
                        : "text-[var(--ink-secondary)] hover:bg-black/[0.04] hover:text-[var(--ink-primary)]"
                    }`}
                  >
                    <span>{item.label}</span>
                    {item.tag ? (
                      <span className="font-mono text-[10px] text-[var(--ink-tertiary)]">
                        {item.tag}
                      </span>
                    ) : null}
                  </button>
                )
              })}
            </div>
          </div>

          {sidebarExtra}
        </aside>

        <main className="flex-1 overflow-y-auto p-6">{children}</main>

        {inspector ? (
          <aside
            aria-label="Inspector"
            className="flex w-76 shrink-0 flex-col gap-5 overflow-y-auto border-l border-[var(--border-hairline)] bg-[var(--bg-subtle)] p-4"
          >
            {inspector}
          </aside>
        ) : null}
      </div>
    </div>
  )
}
