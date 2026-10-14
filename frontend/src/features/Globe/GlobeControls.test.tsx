import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { GlobeControls, type GlobeControlsProps } from "./GlobeControls"
import type { SatelliteInfo } from "./orbitalApi"

const CATALOG: SatelliteInfo[] = [
  {
    key: "iss",
    name: "ISS (ZARYA)",
    epoch_utc: "2014-01-20T22:23:04+00:00",
    mean_motion_rev_per_day: 15.5,
    period_seconds: 5580,
    orbit_class: "LEO",
  },
  {
    key: "geo",
    name: "GEO-DEMO",
    epoch_utc: "2000-06-27T18:50:19+00:00",
    mean_motion_rev_per_day: 1.0,
    period_seconds: 86400,
    orbit_class: "GEO",
  },
  {
    key: "vanguard_r3",
    name: "VANGUARD 1",
    epoch_utc: "2000-06-27T18:50:19+00:00",
    mean_motion_rev_per_day: 10.824,
    period_seconds: 7982,
    orbit_class: "LEO",
  },
]

function makeProps(overrides: Partial<GlobeControlsProps> = {}): GlobeControlsProps {
  return {
    catalog: CATALOG,
    selected: "vanguard_r3",
    onSelect: vi.fn(),
    playheadIndex: 5,
    totalPoints: 241,
    onScrub: vi.fn(),
    isPlaying: false,
    onTogglePlay: vi.fn(),
    speed: 4,
    onSpeedChange: vi.fn(),
    onReset: vi.fn(),
    currentTimeIso: "2000-06-28T17:02:30Z",
    disabled: false,
    ...overrides,
  }
}

describe("GlobeControls", () => {
  it("renders the satellite picker with one option per catalog entry", () => {
    render(<GlobeControls {...makeProps()} />)
    const select = screen.getByLabelText(/satellite/i) as HTMLSelectElement
    const options = Array.from(select.options).map((o) => o.textContent)
    expect(options).toEqual(["ISS (ZARYA)", "GEO-DEMO", "VANGUARD 1"])
    expect(select.value).toBe("vanguard_r3")
  })

  it("calls onSelect when the user changes the satellite", async () => {
    const onSelect = vi.fn()
    const user = userEvent.setup()
    render(<GlobeControls {...makeProps({ onSelect })} />)
    await user.selectOptions(screen.getByLabelText(/satellite/i), "iss")
    expect(onSelect).toHaveBeenCalledWith("iss")
  })

  it("shows Play when not playing and Pause when playing", () => {
    const { rerender } = render(<GlobeControls {...makeProps({ isPlaying: false })} />)
    expect(screen.getByRole("button", { name: /play/i })).toBeInTheDocument()
    rerender(<GlobeControls {...makeProps({ isPlaying: true })} />)
    expect(screen.getByRole("button", { name: /pause/i })).toBeInTheDocument()
  })

  it("calls onTogglePlay when the play button is clicked", async () => {
    const onTogglePlay = vi.fn()
    const user = userEvent.setup()
    render(<GlobeControls {...makeProps({ onTogglePlay })} />)
    await user.click(screen.getByRole("button", { name: /play/i }))
    expect(onTogglePlay).toHaveBeenCalledTimes(1)
  })

  it("calls onReset when Reset is clicked", async () => {
    const onReset = vi.fn()
    const user = userEvent.setup()
    render(<GlobeControls {...makeProps({ onReset })} />)
    await user.click(screen.getByRole("button", { name: /reset/i }))
    expect(onReset).toHaveBeenCalledTimes(1)
  })

  it("scrubbing the time slider calls onScrub with the numeric index", async () => {
    const onScrub = vi.fn()
    const user = userEvent.setup()
    render(<GlobeControls {...makeProps({ onScrub })} />)
    // The range has max=240, value=5. Simulate user setting it to 100.
    const slider = screen.getByLabelText(/^time$/i) as HTMLInputElement
    expect(slider.value).toBe("5")
    // userEvent cannot "drag" a range; use fireEvent.change-equivalent
    await user.tripleClick(slider)
    // Setting value directly through the DOM and dispatching change
    // is what fireEvent.change does; the native range input handles it.
    // Use the standard approach from @testing-library.
    const { fireEvent } = await import("@testing-library/react")
    fireEvent.change(slider, { target: { value: "100" } })
    expect(onScrub).toHaveBeenCalledWith(100)
  })

  it("changing speed calls onSpeedChange", async () => {
    const onSpeedChange = vi.fn()
    const user = userEvent.setup()
    render(<GlobeControls {...makeProps({ onSpeedChange })} />)
    await user.selectOptions(screen.getByLabelText(/speed/i), "16")
    expect(onSpeedChange).toHaveBeenCalledWith(16)
  })

  it("disables play and reset when there are fewer than 2 points", () => {
    render(<GlobeControls {...makeProps({ totalPoints: 1 })} />)
    expect(screen.getByRole("button", { name: /play/i })).toBeDisabled()
    expect(screen.getByRole("button", { name: /reset/i })).toBeDisabled()
  })

  it("displays the current time", () => {
    render(<GlobeControls {...makeProps({ currentTimeIso: "2000-06-28T17:02:30Z" })} />)
    expect(screen.getByTestId("current-time")).toHaveTextContent("2000-06-28T17:02:30Z")
  })

  it("disables every control when the disabled prop is set", () => {
    render(<GlobeControls {...makeProps({ disabled: true })} />)
    expect(screen.getByLabelText(/satellite/i)).toBeDisabled()
    expect(screen.getByRole("button", { name: /play/i })).toBeDisabled()
    expect(screen.getByRole("button", { name: /reset/i })).toBeDisabled()
    expect(screen.getByLabelText(/^time$/i)).toBeDisabled()
    expect(screen.getByLabelText(/speed/i)).toBeDisabled()
  })

  it("speed selector offers 1x, 4x, 16x, 64x", () => {
    render(<GlobeControls {...makeProps()} />)
    const select = screen.getByLabelText(/speed/i) as HTMLSelectElement
    const options = Array.from(select.options).map((o) => o.textContent)
    expect(options).toEqual(["1×", "4×", "16×", "64×"])
  })
})
