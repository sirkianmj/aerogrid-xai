import { describe, expect, it } from "vitest"
import { TOKENS } from "../styles/tokens"
import { contrast_ratio, relative_luminance, srgb_to_linear } from "./contrast"

describe("srgb_to_linear", () => {
  it("linearizes black to zero", () => {
    expect(srgb_to_linear(0)).toBe(0)
  })

  it("linearizes white to one", () => {
    expect(srgb_to_linear(1)).toBeCloseTo(1, 10)
  })

  it("uses the linear segment for very dark values", () => {
    expect(srgb_to_linear(0.03928)).toBeCloseTo(0.03928 / 12.92, 10)
  })
})

describe("relative_luminance", () => {
  it("returns 0 for black", () => {
    expect(relative_luminance("#000000")).toBe(0)
  })

  it("returns 1 for white", () => {
    expect(relative_luminance("#ffffff")).toBeCloseTo(1, 10)
  })

  it("rejects invalid hex", () => {
    expect(() => relative_luminance("#fff")).toThrow()
    expect(() => relative_luminance("nope")).toThrow()
  })
})

describe("contrast_ratio", () => {
  it("black on white is 21:1", () => {
    expect(contrast_ratio("#000000", "#ffffff")).toBeCloseTo(21, 5)
  })

  it("identical colors are 1:1", () => {
    expect(contrast_ratio("#123456", "#123456")).toBe(1)
  })

  it("is symmetric", () => {
    expect(contrast_ratio("#abcdef", "#123456")).toBeCloseTo(
      contrast_ratio("#123456", "#abcdef"),
      10,
    )
  })
})

describe("design-token palette meets WCAG 2.1 AA", () => {
  it("dark theme: foreground on background >= 4.5:1", () => {
    expect(contrast_ratio(TOKENS.fgDark, TOKENS.bgDark)).toBeGreaterThanOrEqual(4.5)
  })

  it("light theme: foreground on background >= 4.5:1", () => {
    expect(contrast_ratio(TOKENS.fgLight, TOKENS.bgLight)).toBeGreaterThanOrEqual(4.5)
  })
})
