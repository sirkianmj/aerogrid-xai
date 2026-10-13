import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { ParallelCoordinates } from "./ParallelCoordinates"
import type { ParetoPoint } from "./tradeSpaceApi"

const LABELS = ["C", "R", "E", "N", "T", "U"]

const POINTS: ParetoPoint[] = [
  { objectives: [0.8, 0.5, 0.1, 0.9, 0.5, 0.3], generation: 2, node_count: 5, link_count: 3 },
  { objectives: [0.6, 0.7, 0.2, 0.8, 0.6, 0.2], generation: 2, node_count: 7, link_count: 4 },
  { objectives: [0.5, 0.6, 0.3, 0.7, 0.4, 0.1], generation: 2, node_count: 6, link_count: 3 },
]

describe("ParallelCoordinates", () => {
  it("renders an SVG with a role=img and default aria-label", () => {
    render(
      <ParallelCoordinates points={POINTS} labels={LABELS} negativeObjectives={[5]} />,
    )
    const svg = screen.getByRole("img", { name: /pareto front parallel coordinates/i })
    expect(svg.tagName.toLowerCase()).toBe("svg")
  })

  it("accepts a custom aria-label", () => {
    render(
      <ParallelCoordinates
        points={POINTS}
        labels={LABELS}
        negativeObjectives={[5]}
        ariaLabel="my front"
      />,
    )
    expect(screen.getByRole("img", { name: "my front" })).toBeInTheDocument()
  })

  it("renders one polyline per Pareto point", () => {
    const { container } = render(
      <ParallelCoordinates points={POINTS} labels={LABELS} negativeObjectives={[5]} />,
    )
    expect(container.querySelectorAll("polyline").length).toBe(POINTS.length)
  })

  it("renders one axis label per objective, plus min/max tag per axis", () => {
    render(
      <ParallelCoordinates points={POINTS} labels={LABELS} negativeObjectives={[5]} />,
    )
    for (const label of LABELS) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
    // U is the minimized axis.
    expect(screen.getByText("min")).toBeInTheDocument()
    // The other five are maximized.
    expect(screen.getAllByText("max").length).toBe(5)
  })

  it("shows a fallback when there are no points", () => {
    render(
      <ParallelCoordinates points={[]} labels={LABELS} negativeObjectives={[5]} />,
    )
    expect(screen.getByText(/no pareto points to plot/i)).toBeInTheDocument()
  })

  it("shows a fallback when there are no labels", () => {
    render(
      <ParallelCoordinates points={POINTS} labels={[]} negativeObjectives={[]} />,
    )
    expect(screen.getByText(/no pareto points to plot/i)).toBeInTheDocument()
  })

  it("warns on an arity mismatch between objectives and labels", () => {
    const bad: ParetoPoint[] = [
      { objectives: [0.5, 0.5], generation: 0, node_count: 3, link_count: 2 },
    ]
    render(<ParallelCoordinates points={bad} labels={LABELS} negativeObjectives={[5]} />)
    expect(screen.getByText(/Pareto point has 2 objectives; expected 6/i)).toBeInTheDocument()
  })

  it("counts the Pareto points in the legend text", () => {
    render(
      <ParallelCoordinates points={POINTS} labels={LABELS} negativeObjectives={[5]} />,
    )
    expect(screen.getByText(/3 Pareto points/)).toBeInTheDocument()
  })

  it("uses the singular form in the legend for one point", () => {
    render(
      <ParallelCoordinates points={[POINTS[0]!]} labels={LABELS} negativeObjectives={[5]} />,
    )
    expect(screen.getByText(/1 Pareto point /)).toBeInTheDocument()
  })

  it("inverts the U axis so lower-U points sit higher on screen", () => {
    // Construct two points identical in every objective except U. The
    // one with the smaller U should have its polyline endpoint on the
    // last axis higher on screen (smaller y in SVG coordinates).
    const twoPoints: ParetoPoint[] = [
      { objectives: [0.5, 0.5, 0.5, 0.5, 0.5, 0.2], generation: 0, node_count: 3, link_count: 2 },
      { objectives: [0.5, 0.5, 0.5, 0.5, 0.5, 0.8], generation: 0, node_count: 3, link_count: 2 },
    ]
    const { container } = render(
      <ParallelCoordinates points={twoPoints} labels={LABELS} negativeObjectives={[5]} />,
    )
    const lines = container.querySelectorAll("polyline")
    // Each polyline ends with "x,y". Extract the last y of each.
    const lastY = (s: string): number => {
      const segments = s.trim().split(/\s+/)
      const last = segments[segments.length - 1]!
      return Number(last.split(",")[1])
    }
    const y_lowU = lastY(lines[0]!.getAttribute("points") ?? "")
    const y_highU = lastY(lines[1]!.getAttribute("points") ?? "")
    // Lower U (0.2) should have smaller y (higher on screen).
    expect(y_lowU).toBeLessThan(y_highU)
  })
})
