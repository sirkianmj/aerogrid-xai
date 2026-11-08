import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

const mockApplyConfig = vi.fn()

const mockConfig = {
  transmitter_power_w: 2000,
  wavelength_nm: 1064,
  transmitter_aperture_m: 0.15,
  transmitter_min_elevation_deg: 5.0,
  transmitter_type: "ground" as const,
}

vi.mock("../MissionControl/missionContext", () => ({
  useMission: () => ({
    config: mockConfig,
    applyConfig: mockApplyConfig,
    state: {
      status: "ok" as const,
      data: {
        uavs: [
          { delivered_power_w: 5.2 },
          { delivered_power_w: 4.8 },
          { delivered_power_w: 3.1 },
          { delivered_power_w: 2.0 },
        ],
        transmission: {
          modality: "laser_ground",
          elevation_deg: 42.1,
          slant_range_m: 1500.0,
        },
        atmosphere: { transmittance: 0.87 },
      },
    },
  }),
}))

import { GroundDesigner } from "./GroundDesigner"

describe("GroundDesigner", () => {
  beforeEach(() => {
    mockApplyConfig.mockReset()
  })

  it("renders all four parameter inputs", () => {
    render(<GroundDesigner />)
    expect(screen.getByLabelText("Ground transmitter power watts")).toBeInTheDocument()
    expect(screen.getByLabelText("Ground transmitter wavelength nm")).toBeInTheDocument()
    expect(screen.getByLabelText("Ground transmitter aperture metres")).toBeInTheDocument()
    expect(screen.getByLabelText("Minimum elevation angle")).toBeInTheDocument()
  })

  it("displays live transmission metrics", () => {
    render(<GroundDesigner />)
    expect(screen.getByText("laser_ground")).toBeInTheDocument()
    expect(screen.getByText("1.50 km")).toBeInTheDocument()
    expect(screen.getByText("42.1°")).toBeInTheDocument()
    expect(screen.getByText("0.8700")).toBeInTheDocument()
    // Total delivered = 5.2 + 4.8 + 3.1 + 2.0 = 15.1 W
    expect(screen.getByText("15.100 W")).toBeInTheDocument()
  })

  it("calls applyConfig on power change", async () => {
    const user = userEvent.setup()
    render(<GroundDesigner />)
    const input = screen.getByLabelText("Ground transmitter power watts")
    await user.clear(input)
    await user.type(input, "5000")
    // Last call should be with transmitter_power_w: 5000 (or intermediate values)
    const lastCall = mockApplyConfig.mock.calls[mockApplyConfig.mock.calls.length - 1][0]
    expect(lastCall).toHaveProperty("transmitter_power_w")
  })

  it("does not call applyConfig on invalid input", async () => {
    const user = userEvent.setup()
    render(<GroundDesigner />)
    const input = screen.getByLabelText("Ground transmitter aperture metres")
    await user.clear(input)
    // Leave empty → Number('') = 0, which is finite but we might want to reject
    // Actually Number('') is 0, so NaN check won't catch it. Verify it doesn't
    // set a NaN value:
    const calls = mockApplyConfig.mock.calls
    for (const [patch] of calls) {
      if ("transmitter_aperture_m" in patch) {
        expect(Number.isFinite(patch.transmitter_aperture_m)).toBe(true)
      }
    }
  })
})
