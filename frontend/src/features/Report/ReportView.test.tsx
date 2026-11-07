import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

vi.mock("../MissionControl/missionContext", () => ({
  useMission: () => ({
    config: { seed: 1, satellite_key: "iss", n_uavs: 3 },
    state: { status: "ok", data: { t_utc: "2026-01-01T00:00:00Z" } },
    stepOutputs: {
      3: { step: 3, data: { population_size: 8 }, at: 1 },
      5: { step: 5, data: { n_samples: 11 }, at: 2 },
    },
    completedSteps: new Set<number>(),
    markStepComplete: vi.fn(),
  }),
}))

vi.mock("./reportApi", async () => {
  const actual = await vi.importActual<typeof import("./reportApi")>("./reportApi")
  return {
    ...actual,
    generateReport: vi.fn(),
    // In tests there is no pywebview bridge; the polling helper would
    // otherwise wait out its full timeout before falling through to the
    // browser download path, which exceeds testing-library's default
    // waitFor window.
    waitForPywebview: vi.fn().mockResolvedValue(null),
  }
})

beforeEach(() => {
  Object.defineProperty(URL, "createObjectURL", {
    value: vi.fn(() => "blob:mock"),
    configurable: true,
  })
  Object.defineProperty(URL, "revokeObjectURL", {
    value: vi.fn(),
    configurable: true,
  })
})

import { ReportView } from "./ReportView"
import { generateReport } from "./reportApi"

const mockedGenerate = vi.mocked(generateReport)

describe("ReportView", () => {
  beforeEach(() => {
    mockedGenerate.mockReset()
  })

  it("renders header and generate button in idle state", () => {
    render(<ReportView />)
    expect(screen.getByText("6 · Report")).toBeInTheDocument()
    expect(
      screen.getByRole("button", { name: /generate pdf report/i }),
    ).toBeInTheDocument()
  })

  it("shows section status table with executed/not-executed rows", () => {
    render(<ReportView />)
    expect(screen.getByText(/Step 3 · Discovery/)).toBeInTheDocument()
    expect(screen.getAllByText(/executed/i).length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText("not executed")).toBeInTheDocument()
  })

  it("calls generateReport on click", async () => {
    mockedGenerate.mockResolvedValueOnce(new Blob(["%PDF-mock"], { type: "application/pdf" }))
    const user = userEvent.setup()
    render(<ReportView />)
    await user.click(screen.getByRole("button", { name: /generate pdf report/i }))
    await waitFor(() => expect(mockedGenerate).toHaveBeenCalledOnce())
  })

  it("passes config, step_outputs and mission_state to generateReport", async () => {
    mockedGenerate.mockResolvedValueOnce(new Blob(["%PDF"], { type: "application/pdf" }))
    const user = userEvent.setup()
    render(<ReportView />)
    await user.click(screen.getByRole("button", { name: /generate pdf report/i }))
    await waitFor(() => expect(mockedGenerate).toHaveBeenCalledOnce())
    const req = mockedGenerate.mock.calls[0][0]
    expect(req.mission_config).toMatchObject({ seed: 1, satellite_key: "iss" })
    expect(req.step_outputs).toHaveProperty("3")
    expect(req.step_outputs).toHaveProperty("5")
    expect(req.mission_state).not.toBeNull()
  })

  it("shows download confirmation on success", async () => {
    mockedGenerate.mockResolvedValueOnce(new Blob(["%PDF"], { type: "application/pdf" }))
    const user = userEvent.setup()
    render(<ReportView />)
    await user.click(screen.getByRole("button", { name: /generate pdf report/i }))
    await waitFor(() => expect(screen.getByText(/Downloaded aerogrid-report-/)).toBeInTheDocument())
  })

  it("shows error message on failure", async () => {
    mockedGenerate.mockRejectedValueOnce(new Error("backend said no"))
    const user = userEvent.setup()
    render(<ReportView />)
    await user.click(screen.getByRole("button", { name: /generate pdf report/i }))
    await waitFor(() => expect(screen.getByText(/backend said no/)).toBeInTheDocument())
  })
})
