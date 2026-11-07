import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

const mockResetMission = vi.fn()
const mockApplyConfig = vi.fn()

vi.mock("../MissionControl/missionContext", () => ({
  useMission: () => ({
    resetMission: mockResetMission,
    applyConfig: mockApplyConfig,
  }),
}))

import { Launcher } from "./Launcher"
import { TEMPLATES } from "./templates"

describe("Launcher", () => {
  beforeEach(() => {
    mockResetMission.mockReset()
    mockApplyConfig.mockReset()
  })

  it("renders the app title and New Project card", () => {
    render(<Launcher onNavigateToWorkflow={vi.fn()} />)
    expect(screen.getByText("AeroGrid-XAI")).toBeInTheDocument()
    expect(screen.getByTestId("launcher-new-project")).toBeInTheDocument()
  })

  it("renders every template card", () => {
    render(<Launcher onNavigateToWorkflow={vi.fn()} />)
    for (const t of TEMPLATES) {
      expect(screen.getByTestId(`launcher-template-${t.id}`)).toBeInTheDocument()
      expect(screen.getByText(t.name)).toBeInTheDocument()
    }
  })

  it("New Project resets mission and navigates to design", async () => {
    const onNav = vi.fn()
    const user = userEvent.setup()
    render(<Launcher onNavigateToWorkflow={onNav} />)
    await user.click(screen.getByTestId("launcher-new-project"))
    expect(mockResetMission).toHaveBeenCalledOnce()
    expect(mockApplyConfig).not.toHaveBeenCalled()
    expect(onNav).toHaveBeenCalledWith("design")
  })

  it("clicking a template applies config, resets mission, and navigates to design", async () => {
    const onNav = vi.fn()
    const user = userEvent.setup()
    render(<Launcher onNavigateToWorkflow={onNav} />)
    const quickstart = TEMPLATES.find((t) => t.id === "quickstart")!
    await user.click(screen.getByTestId(`launcher-template-${quickstart.id}`))
    expect(mockResetMission).toHaveBeenCalledOnce()
    expect(mockApplyConfig).toHaveBeenCalledOnce()
    expect(mockApplyConfig).toHaveBeenCalledWith(quickstart.configPatch)
    expect(onNav).toHaveBeenCalledWith("design")
  })

  it("Fixed-Wing template carries uav_hardware_list in its patch", () => {
    const fixed = TEMPLATES.find((t) => t.id === "fixed-wing-endurance")!
    expect(fixed.configPatch.uav_hardware_list).toBeDefined()
    expect(fixed.configPatch.uav_hardware_list).toHaveLength(3)
    for (const hw of fixed.configPatch.uav_hardware_list!) {
      expect(hw.airframe).toBe("fixed_wing")
    }
  })
})
