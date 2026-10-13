/**
 * Design tokens for the AeroGrid-XAI mission-control UI.
 *
 * These are the source of truth for the color palette. The CSS custom
 * properties in tokens.css mirror these values. The contrast test in
 * src/lib/contrast.test.ts verifies that the foreground/background
 * pairs meet WCAG 2.1 AA (>= 4.5:1) in both themes.
 *
 * The palette is aerospace-oriented: a deep near-black background for
 * dark mode, a near-white background for light mode, and accent colors
 * used only for epistemic-band dots. Text always uses the foreground
 * token, which is what the contrast test verifies.
 */

export const TOKENS = {
  bgDark: "#0a0e14",
  bgLight: "#f5f7fa",
  fgDark: "#e6e8eb",
  fgLight: "#0f1419",
  accentTeal: "#14b8a6",
  accentViolet: "#8b5cf6",
  accentAmber: "#f59e0b",
  accentSlate: "#94a3b8",
} as const

export type TokenName = keyof typeof TOKENS
