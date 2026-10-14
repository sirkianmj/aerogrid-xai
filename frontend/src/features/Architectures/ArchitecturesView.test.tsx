import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { ArchitecturesView } from "./ArchitecturesView"

const { applyConfigMock } = vi.hoisted(() => ({ applyConfigMock: vi.fn() }))

vi.mock("../MissionControl/missionContext", () => ({
  useMission: () => ({
    config: {
      satellite_key: "iss",
      ground_lat_deg: 40.798,
      ground_lon_deg: -77.86,
      transmitter_power_w: 10000,
      n_uavs: 6,
      seed: 20261014,
      t_utc: null,
      visibility_km: 10.0,
      cloud_factor: 0.2,
      transmitter_aperture_m: 0.02,
      uav_alt_m: 1000.0,
      uav_receiver_aperture_m2: 0.5,
      uav_receiver_type: "laser_photovoltaic" as const,
      selected_architecture: null,
    },
    state: { status: "loading" as const },
    applyConfig: applyConfigMock,
    refresh: () => {},
    reset: () => {},
  }),
}))

const RESPONSE_BODY = {
  epistemic_tag: "simulation_result",
  population_size: 8,
  n_generations: 3,
  use_conflict_directed: true,
  generation_stats: [],
  hypervolume_history: [],
  conflict_prone_table: [],
  trace: [],
  trace_truncated: false,
  discovered: [
    {
      generation: 2,
      nodes: 3,
      links: 2,
      objectives: [0.7, 0.5, 0.6, 0.8, 0.4, 0.1],
      node_list: [
        { node_id: "n0", kind: "Satellite_LEO", params: {} },
        { node_id: "n1", kind: "UAV_Energy", params: {} },
        { node_id: "n2", kind: "Ground_Station", params: {} },
      ],
      link_list: [
        { link_id: "l0", kind: "Laser_Link", source_id: "n0", target_id: "n1" },
        { link_id: "l1", kind: "Laser_Link", source_id: "n1", target_id: "n2" },
      ],
    },
  ],
}

/** Stub fetch with an immediately-resolving response. */
function stubRun() {
  const fn = vi.fn(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve(RESPONSE_BODY),
    } as Response),
  )
  vi.stubGlobal("fetch", fn)
  return fn
}

/**
 * Stub fetch that never resolves until the test releases it. This is
 * the only way to observe the loading state: a promise that resolves
 * on the same microtask the click lives on is already done by the time
 * `userEvent.click` returns.
 */
function stubRunDeferred() {
  let release!: () => void
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  const fn = vi.fn(async () => {
    await gate
    return {
      ok: true,
      status: 200,
      json: () => Promise.resolve(RESPONSE_BODY),
    } as Response
  })
  vi.stubGlobal("fetch", fn)
  return { fn, release }
}

describe("ArchitecturesView", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it("renders the heading and an idle state on mount", () => {
    render(<ArchitecturesView />)
    expect(
      screen.getByRole("heading", { name: /Discovered architectures/i }),
    ).toBeInTheDocument()
    expect(screen.getByText(/No run yet/i)).toBeInTheDocument()
  })

  it("disables the button while the run is in flight", async () => {
    const { release } = stubRunDeferred()
    render(<ArchitecturesView />)
    const btn = screen.getByRole("button", { name: /Discover architectures/i })
    await userEvent.click(btn)
    // The deferred promise has not resolved, so the panel is still in
    // the loading state: the button label has changed and is disabled.
    const loading = screen.getByRole("button", { name: /Discovering/i })
    expect(loading).toBeDisabled()
    // Release the promise so the test does not leak a pending timer.
    release()
    await waitFor(() =>
      expect(screen.getByTestId("arch-card-0")).toBeInTheDocument(),
    )
  })

  it("renders one card per discovered architecture after the run", async () => {
    stubRun()
    render(<ArchitecturesView />)
    await userEvent.click(
      screen.getByRole("button", { name: /Discover architectures/i }),
    )
    await waitFor(() =>
      expect(screen.getByTestId("arch-card-0")).toBeInTheDocument(),
    )
    expect(screen.getByText(/3N 2L/)).toBeInTheDocument()
  })

  it("renders the objective values for each architecture", async () => {
    stubRun()
    render(<ArchitecturesView />)
    await userEvent.click(
      screen.getByRole("button", { name: /Discover architectures/i }),
    )
    await waitFor(() => expect(screen.getByTestId("arch-card-0")).toBeInTheDocument())
    // Spot check: the first objective value for C should appear.
    expect(screen.getByText("0.70")).toBeInTheDocument()
  })

  it("load button calls applyConfig with the selected architecture", async () => {
    applyConfigMock.mockClear()
    stubRun()
    render(<ArchitecturesView />)
    await userEvent.click(
      screen.getByRole("button", { name: /Discover architectures/i }),
    )
    await waitFor(() =>
      expect(screen.getByTestId("arch-card-0")).toBeInTheDocument(),
    )
    await userEvent.click(screen.getByTestId("load-arch-0"))
    expect(applyConfigMock).toHaveBeenCalledTimes(1)
    const call = applyConfigMock.mock.calls[0][0]
    expect(call).toHaveProperty("selected_architecture")
    expect(call.selected_architecture.node_list.length).toBeGreaterThan(0)
    expect(call.selected_architecture.link_list.length).toBeGreaterThan(0)
  })

})
