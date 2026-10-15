/**
 * AppShell — the macOS-style two-pane frame.
 *
 * Layout:
 *
 *     ┌──────────────┬─────────────────────────────────────────────┐
 *     │   sidebar    │              center canvas                  │
 *     │              │                                             │
 *     └──────────────┴─────────────────────────────────────────────┘
 *
 * Follows Apple's macOS application layout: a fixed source-list
 * sidebar carries identity (application name, version), navigation
 * (the workspace views), and secondary controls (theme, invariant
 * badges); the main pane carries content. The sidebar material is
 * lighter than the canvas in light mode and darker than the canvas
 * in dark mode, matching Finder, Mail, and Xcode.
 */

import { useState } from "react"
import type { ReactNode } from "react"
import {
  applyTheme,
  readThemePref,
  setThemePref,
  type ThemePref,
} from "../../lib/theme"

export type AppShellNavItem = {
  id: string
  label: string
  tag?: string
}

export type AppShellProps = {
  navItems: AppShellNavItem[]
  activeView: string
  onViewChange: (id: string) => void
  children: ReactNode
  sidebarExtra?: ReactNode
  inspector?: ReactNode
}

function InvariantBadge({ label, title }: { label: string; title: string }) {
  return (
    <span
      title={title}
      className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border-hairline)] bg-[var(--bg-surface)] px-2 py-1 text-[10px] font-mono text-[var(--ink-secondary)]"
    >
      <span
        aria-hidden="true"
        className="h-1.5 w-1.5 rounded-full bg-[var(--status-green)]"
      />
      <span>{label}</span>
    </span>
  )
}

function ThemeToggle() {
  const [pref, setPref] = useState<ThemePref>(() => readThemePref())
  const options: ThemePref[] = ["auto", "light", "dark"]

  function choose(next: ThemePref) {
    setThemePref(next)
    setPref(next)
  }

  return (
    <div
      role="radiogroup"
      aria-label="Theme"
      className="segmented-track w-full"
      data-testid="theme-toggle"
    >
      {options.map((opt) => {
        const active = pref === opt
        return (
          <button
            key={opt}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => choose(opt)}
            className={`segmented-item flex-1 !px-1 text-center !text-[10px] capitalize ${
              active ? "active" : ""
            }`}
          >
            {opt}
          </button>
        )
      })}
    </div>
  )
}

export function AppShell({
  navItems,
  activeView,
  onViewChange,
  children,
  sidebarExtra,
  inspector,
}: AppShellProps) {
  // applyTheme is called once at boot by main.tsx. Re-applying here on
  // every render is unnecessary; the ThemeToggle handles its own
  // changes.
  void applyTheme

  return (
    <div className="flex h-screen w-screen bg-[var(--bg-canvas)] text-[var(--ink-primary)]">
      <aside
        aria-label="Primary"
        className="flex w-[236px] shrink-0 flex-col overflow-y-auto border-r border-[var(--border-hairline)] bg-[var(--bg-sidebar)]"
      >
        {/* Identity block — Apple's "sidebar header". */}
        <div className="flex flex-col gap-0.5 px-4 pb-3 pt-4">
          <span
            className="text-[13px] font-semibold tracking-[-0.01em]"
            style={{ color: "var(--ink-primary)" }}
          >
            AeroGrid-XAI
          </span>
          <span className="font-mono text-[10px] text-[var(--ink-tertiary)]">
            Rev. 6 Unified Specification
          </span>
        </div>

        <nav
          aria-label="Workspace views"
          className="flex flex-col gap-0.5 px-2 py-2"
        >
          {navItems.map((item) => {
            const active = activeView === item.id
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onViewChange(item.id)}
                aria-current={active ? "page" : undefined}
                className="apple-sidebar-item"
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
        </nav>

        {sidebarExtra ? (
          <div className="flex flex-col gap-3 px-3 py-2">{sidebarExtra}</div>
        ) : null}

        <div className="mt-auto flex flex-col gap-2 p-3">
          <InvariantBadge
            label="Tier-2 Firewall Verified"
            title="The backend static analyzer (backend/app/control/static_analyzer.py) is a required CI gate: no Tier 2 function is reachable from the action interface without passing through Tier 1."
          />
          <InvariantBadge
            label="AGPL-3.0"
            title="Repository dual-license: AGPL-3.0 for community use, proprietary EULA for enterprise."
          />
          <ThemeToggle />
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto p-6">{children}</main>

      {inspector ? (
        <aside
          aria-label="Inspector"
          className="flex w-72 shrink-0 flex-col gap-5 overflow-y-auto border-l border-[var(--border-hairline)] bg-[var(--bg-subtle)] p-4"
        >
          {inspector}
        </aside>
      ) : null}
    </div>
  )
}
