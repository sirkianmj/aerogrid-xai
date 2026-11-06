import { describe, it, expect, vi } from "vitest"
import { render, waitFor, act } from "@testing-library/react"
import { MissionProvider } from "./MissionProvider"
import { useMission } from "./missionContext"

vi.mock("./missionApi", async () => {
  const actual = await vi.importActual<typeof import("./missionApi")>("./missionApi")
  const fake: unknown = {
    t_utc: "2026-01-01T00:00:00+00:00",
    seed: 1,
    satellite: {},
    ground_station: {},
    transmission: {},
    atmosphere: {},
    uavs: [],
    architecture: {},
    cleard: {},
    tier1: {},
    pipeline_stages: [],
    epistemic_tag: "simulation_result",
  }
  return {
    ...actual,
    fetchMissionState: vi.fn(async () => fake),
    postMissionState: vi.fn(async () => fake),
  }
})

function Probe({
  sink,
}: {
  sink: { current: ReturnType<typeof useMission> | null }
}) {
  sink.current = useMission()
  return null
}

async function renderProvider() {
  const sink: { current: ReturnType<typeof useMission> | null } = {
    current: null,
  }
  render(
    <MissionProvider>
      <Probe sink={sink} />
    </MissionProvider>,
  )
  await waitFor(() => expect(sink.current?.state.status).not.toBe("loading"))
  return sink
}

describe("StepOutputs", () => {
  it("setStepOutput stores data with step number and timestamp", async () => {
    const sink = await renderProvider()
    expect(sink.current?.stepOutputs).toEqual({})

    act(() => {
      sink.current!.setStepOutput(3, { foo: "bar" })
    })

    const entry = sink.current!.stepOutputs[3]
    expect(entry).toBeDefined()
    expect(entry.step).toBe(3)
    expect(entry.data).toEqual({ foo: "bar" })
    expect(typeof entry.at).toBe("number")
    expect(entry.at).toBeGreaterThan(0)
  })

  it("setStepOutput replaces data on re-set", async () => {
    const sink = await renderProvider()

    act(() => {
      sink.current!.setStepOutput(5, { run: 1 })
    })
    act(() => {
      sink.current!.setStepOutput(5, { run: 2 })
    })

    expect(sink.current!.stepOutputs[5].data).toEqual({ run: 2 })
    expect(sink.current!.stepOutputs[5].step).toBe(5)
  })

  it("setStepOutput keeps entries for different steps independent", async () => {
    const sink = await renderProvider()

    act(() => {
      sink.current!.setStepOutput(3, "discovery-result")
    })
    act(() => {
      sink.current!.setStepOutput(5, "simulation-result")
    })

    expect(sink.current!.stepOutputs[3].data).toBe("discovery-result")
    expect(sink.current!.stepOutputs[5].data).toBe("simulation-result")
  })

  it("clearStepOutput removes one entry, leaves others", async () => {
    const sink = await renderProvider()

    act(() => {
      sink.current!.setStepOutput(3, "a")
    })
    act(() => {
      sink.current!.setStepOutput(5, "b")
    })
    act(() => {
      sink.current!.clearStepOutput(3)
    })

    expect(sink.current!.stepOutputs[3]).toBeUndefined()
    expect(sink.current!.stepOutputs[5].data).toBe("b")
  })

  it("clearAllStepOutputs empties the map", async () => {
    const sink = await renderProvider()

    act(() => {
      sink.current!.setStepOutput(3, "a")
    })
    act(() => {
      sink.current!.setStepOutput(5, "b")
    })
    act(() => {
      sink.current!.clearAllStepOutputs()
    })

    expect(sink.current!.stepOutputs).toEqual({})
  })
})
