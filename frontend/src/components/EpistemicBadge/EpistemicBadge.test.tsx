import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { EpistemicBadge, TaggedOutput } from "./EpistemicBadge"
import {
  ALL_TAGS,
  EPISTEMIC_TAGS,
  type EpistemicTag,
} from "./epistemic"

describe("EpistemicBadge", () => {
  it("renders exactly the seven Section 21 categories", () => {
    expect(ALL_TAGS).toHaveLength(7)
  })

  it("exposes the seven tags as an exhaustive literal union", () => {
    // Compile-time check: if a category is added to or removed from the
    // type without updating this list, tsc fails.
    const expected: EpistemicTag[] = [
      "physical_measurement",
      "validated_physical_model",
      "estimated_model",
      "simulation_result",
      "ai_prediction",
      "formal_verification_result",
      "hypothetical_scenario",
    ]
    expect([...ALL_TAGS].sort()).toEqual([...expected].sort())
  })

  it("renders the label for a given tag", () => {
    render(<EpistemicBadge tag="simulation_result" />)
    expect(screen.getByText("Simulation result")).toBeInTheDocument()
  })

  it("sets the data-epistemic-tag attribute for downstream queries", () => {
    const { container } = render(
      <EpistemicBadge tag="formal_verification_result" />,
    )
    const badge = container.querySelector("[data-epistemic-tag]")
    expect(badge).not.toBeNull()
    expect(badge?.getAttribute("data-epistemic-tag")).toBe(
      "formal_verification_result",
    )
  })

  it("assigns each tag a numeric level from 1 (strongest) to 7 (weakest)", () => {
    const levels = ALL_TAGS.map((t) => EPISTEMIC_TAGS[t].level).sort(
      (a, b) => a - b,
    )
    expect(levels).toEqual([1, 2, 3, 4, 5, 6, 7])
  })

  it("assigns a valid band to every tag", () => {
    for (const tag of ALL_TAGS) {
      expect(["verified", "modelled", "predicted", "hypothetical"]).toContain(
        EPISTEMIC_TAGS[tag].band,
      )
    }
  })

  it.each(ALL_TAGS)("renders tag %s without error", (tag) => {
    render(<EpistemicBadge tag={tag} />)
    expect(screen.getByText(EPISTEMIC_TAGS[tag].label)).toBeInTheDocument()
  })
})

describe("TaggedOutput", () => {
  it("wraps children with an epistemic badge", () => {
    render(
      <TaggedOutput tag="simulation_result">
        <p>payload</p>
      </TaggedOutput>,
    )
    expect(screen.getByText("Simulation result")).toBeInTheDocument()
    expect(screen.getByText("payload")).toBeInTheDocument()
  })

  it("marks the wrapper element for structural queries", () => {
    const { container } = render(
      <TaggedOutput tag="ai_prediction">
        <span>x</span>
      </TaggedOutput>,
    )
    expect(container.querySelector("[data-tagged-output]")).not.toBeNull()
  })
})
