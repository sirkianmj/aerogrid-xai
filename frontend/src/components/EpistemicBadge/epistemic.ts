/**
 * Section 21 epistemic hierarchy definitions.
 *
 * Split out of EpistemicBadge.tsx so that the component file exports
 * only components. The React Fast Refresh plugin treats a component
 * module that also exports constants as ineligible for hot refresh, so
 * separating the data from the rendering is a development-ergonomics
 * requirement, not only a lint one.
 *
 * The seven categories are the specification's Rev. 6, Section 21
 * list, ordered from strongest to weakest evidentiary status:
 *
 *   1. physical_measurement           real hardware test result
 *   2. validated_physical_model       model fit to measurements
 *   3. estimated_model                first-principles, not validated
 *   4. simulation_result              Digital Twin output
 *   5. ai_prediction                  Tier 2 surrogate, with uncertainty
 *   6. formal_verification_result     SAT/UNSAT against PWL encoding
 *   7. hypothetical_scenario          user what-if, no real-world claim
 *
 * The tag type is a literal union, so the TypeScript compiler rejects
 * an unknown tag at the call site.
 */

export type EpistemicTag =
  | "physical_measurement"
  | "validated_physical_model"
  | "estimated_model"
  | "simulation_result"
  | "ai_prediction"
  | "formal_verification_result"
  | "hypothetical_scenario"

export type EpistemicBand =
  | "verified"
  | "modelled"
  | "predicted"
  | "hypothetical"

export type TagInfo = {
  level: number
  label: string
  band: EpistemicBand
}

export const EPISTEMIC_TAGS: Record<EpistemicTag, TagInfo> = {
  physical_measurement: {
    level: 1,
    label: "Physical measurement",
    band: "verified",
  },
  validated_physical_model: {
    level: 2,
    label: "Validated physical model",
    band: "verified",
  },
  estimated_model: {
    level: 3,
    label: "Estimated model",
    band: "modelled",
  },
  simulation_result: {
    level: 4,
    label: "Simulation result",
    band: "modelled",
  },
  ai_prediction: {
    level: 5,
    label: "AI prediction",
    band: "predicted",
  },
  formal_verification_result: {
    level: 6,
    label: "Formal verification result",
    band: "predicted",
  },
  hypothetical_scenario: {
    level: 7,
    label: "Hypothetical scenario",
    band: "hypothetical",
  },
}

export const ALL_TAGS: EpistemicTag[] = Object.keys(
  EPISTEMIC_TAGS,
) as EpistemicTag[]

export const BAND_COLOR_VAR: Record<EpistemicBand, string> = {
  verified: "var(--color-accent-teal)",
  modelled: "var(--color-accent-violet)",
  predicted: "var(--color-accent-amber)",
  hypothetical: "var(--color-accent-slate)",
}
