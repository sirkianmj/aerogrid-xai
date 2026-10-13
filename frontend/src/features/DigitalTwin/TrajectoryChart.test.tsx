import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { TrajectoryChart } from "./TrajectoryChart"

const TWO_SAMPLES = [
  { time_s: 0, t_plc_k: 298.15, t_te_k: 298.15 },
  { time_s: 600, t_plc_k: 360.0, t_te_k: 330.0 },
]

const MANY_SAMPLES = Array.from({ length: 50 }, (_, i) => ({
  time_s: i * 10,
  t_plc_k: 298.15 + i * 1.5,
  t_te_k: 298.15 + i * 0.5,
}))

describe("TrajectoryChart", () => {
  it("renders an SVG with a role=img and an aria-label", () => {
    render(<TrajectoryChart samples={TWO_SAMPLES} label="transient" />)
    const svg = screen.getByRole("img", { name: "transient" })
    expect(svg.tagName.toLowerCase()).toBe("svg")
  })

  it("renders two polylines, one per series", () => {
    const { container } = render(<TrajectoryChart samples={MANY_SAMPLES} />)
    const lines = container.querySelectorAll("polyline")
    expect(lines.length).toBe(2)
    expect(lines[0]!.getAttribute("stroke")).toBe("#f59e0b")
    expect(lines[1]!.getAttribute("stroke")).toBe("#14b8a6")
  })

  it("shows a hint when there are fewer than two samples", () => {
    render(<TrajectoryChart samples={[TWO_SAMPLES[0]!]} />)
    expect(screen.getByText(/fewer than two samples/i)).toBeInTheDocument()
  })

  it("draws one point per sample in the PLC polyline", () => {
    const { container } = render(<TrajectoryChart samples={MANY_SAMPLES} />)
    const plc = container.querySelectorAll("polyline")[0]!
    const points = (plc.getAttribute("points") ?? "").trim().split(/\s+/)
    expect(points.length).toBe(MANY_SAMPLES.length)
  })

  it("labels the x-axis as time in seconds and the y-axis as temperature in Celsius", () => {
    render(<TrajectoryChart samples={MANY_SAMPLES} />)
    expect(screen.getByText(/time \(s\)/)).toBeInTheDocument()
    expect(screen.getByText(/temperature \(C\)/)).toBeInTheDocument()
  })

  it("renders a legend with both series names", () => {
    render(<TrajectoryChart samples={MANY_SAMPLES} />)
    expect(screen.getByText("PLC")).toBeInTheDocument()
    expect(screen.getByText("TE")).toBeInTheDocument()
  })
})
