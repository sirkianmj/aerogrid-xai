import { render, screen, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { Globe } from "./Globe"
import type { SatelliteInfo, TrackResponse } from "./orbitalApi"

// jsdom has no WebGL. The r3f Canvas is mocked to a plain div so the
// surrounding state machine can be tested in the node environment. The
// 3D scene itself is not testable under jsdom and is exercised
// manually when the app runs with `npm run dev`.
vi.mock("@react-three/fiber", () => ({
  Canvas: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="r3f-canvas">{children}</div>
  ),
}))
vi.mock("@react-three/drei", () => ({
  OrbitControls: () => null,
  Line: () => null,
  Sphere: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

// The Globe reads the selected satellite and ground station from the
// mission context. Provide a fixed context so the test stays isolated
// from MissionProvider's own fetch behavior. The config below matches
// the CATALOG fixture (vanguard_r3 is present).
vi.mock("../MissionControl/missionContext", () => ({
  useMission: () => ({
    config: {
      satellite_key: "vanguard_r3",
      ground_lat_deg: 40.798,
      ground_lon_deg: -77.86,
      transmitter_power_w: 10000,
      n_uavs: 6,
      seed: 20261014,
      t_utc: null,
    },
    state: { status: "loading" as const },
    applyConfig: () => {},
    refresh: () => {},
    reset: () => {},
  }),
}))

const CATALOG: SatelliteInfo[] = [
  {
    key: "iss",
    name: "ISS (ZARYA)",
    epoch_utc: "2014-01-20T22:23:04Z",
    mean_motion_rev_per_day: 15.49,
    period_seconds: 5570.0,
    orbit_class: "LEO",
  },
  {
    key: "vanguard_r3",
    name: "VANGUARD 1",
    epoch_utc: "2000-06-28T18:47:56Z",
    mean_motion_rev_per_day: 10.82,
    period_seconds: 7975.0,
    orbit_class: "LEO",
  },
]

function makeTrack(key: string): TrackResponse {
  return {
    key,
    name: key === "vanguard_r3" ? "VANGUARD 1" : "ISS (ZARYA)",
    t_start: "2000-06-28T17:00:00Z",
    t_end: "2000-06-28T19:00:00Z",
    step_seconds: 30,
    n_points: 3,
    points: [
      { time_utc: "2000-06-28T17:00:00Z", lat_deg: 0, lon_deg: 0, alt_m: 650000, speed_km_s: 7.5, in_eclipse: false },
      { time_utc: "2000-06-28T17:00:30Z", lat_deg: 0.5, lon_deg: 0.5, alt_m: 650100, speed_km_s: 7.5, in_eclipse: false },
      { time_utc: "2000-06-28T17:01:00Z", lat_deg: 1.0, lon_deg: 1.0, alt_m: 650200, speed_km_s: 7.5, in_eclipse: true },
    ],
  }
}

function stubFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, _init?: RequestInit) => {
      if (url.includes("/orbital/satellites")) {
        return Promise.resolve({
          ok: true, status: 200, json: () => Promise.resolve({ satellites: CATALOG }),
        } as Response)
      }
      if (url.includes("/orbital/track")) {
        const params = new URLSearchParams(url.split("?")[1])
        const key = params.get("satellite") ?? "vanguard_r3"
        return Promise.resolve({
          ok: true, status: 200, json: () => Promise.resolve(makeTrack(key)),
        } as Response)
      }
      return Promise.reject(new Error("unexpected url: " + url))
    }),
  )
}

describe("Globe", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it("renders the panel heading and a loading message on mount", () => {
    stubFetch()
    render(<Globe />)
    expect(
      screen.getByRole("heading", { name: /globe/i, level: 2 }),
    ).toBeInTheDocument()
    expect(screen.getByText(/loading orbital data/i)).toBeInTheDocument()
  })

  it("loads the catalog and renders the default satellite track", async () => {
    stubFetch()
    render(<Globe />)
    await waitFor(() => {
      // "VANGUARD 1" appears in the header AND in the satellite picker
      // option list; both are correct. Assert at least one occurrence.
      expect(screen.getAllByText("VANGUARD 1").length).toBeGreaterThanOrEqual(1)
    })
    expect(screen.getByText("LEO")).toBeInTheDocument()
    expect(screen.getByText(/3 points @ 30s/)).toBeInTheDocument()
  })

  it("wraps the track in a Section 21 simulation_result badge", async () => {
    stubFetch()
    const { container } = render(<Globe />)
    await waitFor(() => {
      const badges = container.querySelectorAll(
        '[data-epistemic-tag="simulation_result"]',
      )
      expect(badges.length).toBeGreaterThanOrEqual(1)
    })
  })

  it("renders the track table with one row per point", async () => {
    stubFetch()
    render(<Globe />)
    await waitFor(() => {
      expect(screen.getByText(/track samples/i)).toBeInTheDocument()
    })
    // 3 rows in the table.
    const rows = document.querySelectorAll("tbody tr")
    expect(rows.length).toBe(3)
  })

  it("marks eclipse samples in the table", async () => {
    stubFetch()
    render(<Globe />)
    await waitFor(() => {
      expect(screen.getByText(/track samples/i)).toBeInTheDocument()
    })
    // Two "no" values and one "yes" in the in_eclipse column.
    const yes = screen.getAllByText("yes")
    expect(yes.length).toBe(1)
  })

  it("shows the artefact sub-label with the orbital track tag", async () => {
    stubFetch()
    render(<Globe />)
    await waitFor(() => {
      expect(screen.getByText(/artefact: orbital_track/i)).toBeInTheDocument()
    })
  })

  it("shows an error message when the catalog fetch fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("network failure"))),
    )
    render(<Globe />)
    await waitFor(() => {
      expect(screen.getByText(/network failure/i)).toBeInTheDocument()
    })
  })

  it("shows an OrbitalApiError with its status when the backend returns 500", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 500,
          json: () => Promise.resolve({ detail: "orbital service down" }),
        } as Response),
      ),
    )
    render(<Globe />)
    await waitFor(() => {
      expect(screen.getByText(/error \(500\): orbital service down/i)).toBeInTheDocument()
    })
  })
})
