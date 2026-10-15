/**
 * Design tokens for the AeroGrid-XAI mission-control UI.
 *
 * Source of truth for the color palette used by TypeScript code.
 * The CSS custom properties in tokens.css mirror these values. The
 * contrast test in src/lib/contrast.test.ts verifies that the
 * foreground/background pairs meet WCAG 2.1 AA (>= 4.5:1) in both
 * themes.
 *
 * Palette is Apple's Human Interface Guidelines system colors. See
 * src/styles/tokens.css for the full vocabulary; this file exposes
 * only the values consumed by non-CSS code (the contrast test and
 * any inline style that cannot read a CSS variable).
 */

export const TOKENS = {
  /* Backgrounds — Apple systemGroupedBackground */
  bgDark: "#000000",
  bgLight: "#f2f2f7",

  /* Labels — Apple label colors */
  fgDark: "#ffffff",
  fgLight: "#1d1d1f",

  /* Accents — Apple system colors (light-appearance values). Used by
   * the epistemic badge band colors and any inline SVG that cannot
   * read a CSS variable. */
  accentTeal: "#5ac8fa",    /* sys-teal (light) */
  accentViolet: "#af52de",  /* sys-purple (light) */
  accentAmber: "#ff9500",   /* sys-orange (light) */
  accentSlate: "#8e8e93",   /* sys-gray (light) */
} as const

export type TokenName = keyof typeof TOKENS
