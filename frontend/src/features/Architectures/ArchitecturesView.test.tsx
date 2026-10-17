import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { ArchitecturesView } from "./ArchitecturesView"

const { applyConfigMock, lastRunRef } = vi.hoisted(() => ({
  applyConfigMock: vi.fn(),
  lastRunRef: { current: null as null | { kind: string; data: unknown; at: number } },
}))

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
    lastDiscoveryRun: lastRunRef.current,
    setLastDiscoveryRun: () => {},
    markStepComplete: () => {},
    clearLastDiscoveryRun: () => {},
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

function withRun(data: unknown) {
  lastRunRef.current = { kind: "discovery_run", data, at: Date.now() }
}

function withNoRun() {
  lastRunRef.current = null
}

describe("ArchitecturesView", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    applyConfigMock.mockClear()
    lastRunRef.current = null
  })

  it("renders the heading and an idle state when no CLEAR-D run exists", () => {
    withNoRun()
    render(<ArchitecturesView />)
    expect(
      screen.getByRole("heading", { name: /Discovered architectures/i }),
    ).toBeInTheDocument()
    expect(screen.getByText(/No CLEAR-D run yet/i)).toBeInTheDocument()
  })

  it("renders a card per discovered architecture from the shared run", () => {
    withRun(RESPONSE_BODY)
    render(<ArchitecturesView />)
    expect(screen.getByTestId("arch-card-0")).toBeInTheDocument()
    expect(screen.getByText(/3N 2L/)).toBeInTheDocument()
  })

  it("renders the objective values for each architecture", () => {
    withRun(RESPONSE_BODY)
    render(<ArchitecturesView />)
    expect(screen.getByText("0.70")).toBeInTheDocument()
  })

  it("shows the feasible-count and seed for a successful run", () => {
    withRun(RESPONSE_BODY)
    render(<ArchitecturesView />)
    expect(screen.getByText(/1 feasible/)).toBeInTheDocument()
    expect(screen.getByText(/seed 20261014/)).toBeInTheDocument()
  })

  it("load button calls applyConfig with the selected architecture", async () => {
    withRun(RESPONSE_BODY)
    render(<ArchitecturesView />)
    await userEvent.click(screen.getByTestId("load-arch-0"))
    expect(applyConfigMock).toHaveBeenCalledTimes(1)
    const call = applyConfigMock.mock.calls[0][0]
    expect(call).toHaveProperty("selected_architecture")
    expect(call.selected_architecture.node_list.length).toBeGreaterThan(0)
    expect(call.selected_architecture.link_list.length).toBeGreaterThan(0)
  })

  it("shows the empty state when the shared run discovered nothing", () => {
    withRun({ ...RESPONSE_BODY, discovered: [] })
    render(<ArchitecturesView />)
    expect(
      screen.getByText(/no feasible architectures with/i),
    ).toBeInTheDocument()
  })
})
