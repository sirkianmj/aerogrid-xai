/**
 * WCAG 2.1 contrast-ratio computation.
 *
 * Implements the relative-luminance and contrast-ratio formulas from
 * the Web Content Accessibility Guidelines 2.1, section 1.4.3
 * (contrast minimum) and the defined algorithm:
 *
 *   L = 0.2126 R + 0.7152 G + 0.0722 B
 *
 * where R, G, B are linearized channel values:
 *
 *   C_linear = C_srgb / 12.92                  if C_srgb <= 0.03928
 *   C_linear = ((C_srgb + 0.055) / 1.055)^2.4  otherwise
 *
 *   contrast = (L_lighter + 0.05) / (L_darker + 0.05)
 *
 * Ratios are dimensionless. WCAG AA requires >= 4.5 for body text and
 * >= 3.0 for large text (18 pt or 14 pt bold).
 */

export function srgb_to_linear(channel: number): number {
  if (channel <= 0.03928) return channel / 12.92
  return Math.pow((channel + 0.055) / 1.055, 2.4)
}

export function relative_luminance(hex: string): number {
  const h = hex.replace(/^#/, "")
  if (h.length !== 6) {
    throw new Error(`expected a 6-digit hex color, got ${hex}`)
  }
  const r = parseInt(h.slice(0, 2), 16) / 255
  const g = parseInt(h.slice(2, 4), 16) / 255
  const b = parseInt(h.slice(4, 6), 16) / 255
  return (
    0.2126 * srgb_to_linear(r) +
    0.7152 * srgb_to_linear(g) +
    0.0722 * srgb_to_linear(b)
  )
}

export function contrast_ratio(hex_a: string, hex_b: string): number {
  const la = relative_luminance(hex_a)
  const lb = relative_luminance(hex_b)
  const lighter = Math.max(la, lb)
  const darker = Math.min(la, lb)
  return (lighter + 0.05) / (darker + 0.05)
}
