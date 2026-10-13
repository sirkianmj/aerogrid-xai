import { afterEach, describe, expect, it, vi } from "vitest"
import {
  OrbitalApiError,
  fetchTrack,
  fetchVisibility,
  listSatellites,
  type SatelliteInfo,
  type TrackResponse,
  type VisibilityResponse,
} from "./orbitalApi"

const SAMPLE_SATS: SatelliteInfo[] = [
  {
    key: "iss",
    name: "ISS (ZARYA)",
    epoch_utc: "2014-01-20T22:23:04Z",
    mean_motion_rev_per_day: 15.49,
    period_seconds: 5570.0,
    orbit_class: "LEO",
  },
]

const SAMPLE_TRACK: TrackResponse = {
  key: "iss",
  name: "ISS (ZARYA)",
  t_start: "2014-01-20T22:00:00Z",
  t_end: "2014-01-20T23:00:00Z",
  step_seconds: 60,
  n_points: 2,
  points: [
    {
      time_utc: "2014-01-20T22:00:00Z",
      lat_deg: 1.0,
      lon_deg: 2.0,
      alt_m: 405000,
      speed_km_s: 7.66,
      in_eclipse: false,
    },
    {
      time_utc: "2014-01-20T22:01:00Z",
      lat_deg: 1.1,
      lon_deg: 2.1,
      alt_m: 405100,
      speed_km_s: 7.66,
      in_eclipse: false,
    },
  ],
}

const SAMPLE_VIS: VisibilityResponse = {
  key: "iss",
  name: "ISS (ZARYA)",
  ground: { name: "ground", lat_deg: 40, lon_deg: -75, alt_m: 0 },
  min_elevation_deg: 10,
  t_start: "2014-01-20T22:23:04Z",
  t_end: "2014-01-21T22:23:04Z",
  n_windows: 1,
  windows: [
    {
      start_utc: "2014-01-21T03:00:00Z",
      end_utc: "2014-01-21T03:08:00Z",
      duration_seconds: 480,
      peak_elevation_deg: 45.0,
      peak_time_utc: "2014-01-21T03:04:00Z",
    },
  ],
}

function stubFetch(body: unknown, ok = true, status = 200) {
  return vi.fn((_url: string, _init?: RequestInit) =>
    Promise.resolve({
      ok,
      status,
      json: () => Promise.resolve(body),
    } as Response),
  )
}

describe("listSatellites", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it("requests /api/orbital/satellites and unwraps the list", async () => {
    const fetchMock = stubFetch({ satellites: SAMPLE_SATS })
    vi.stubGlobal("fetch", fetchMock)
    const out = await listSatellites()
    expect(fetchMock.mock.calls[0]![0]).toBe("/api/orbital/satellites")
    expect(out).toEqual(SAMPLE_SATS)
  })

  it("raises OrbitalApiError with the backend detail on non-200", async () => {
    vi.stubGlobal(
      "fetch",
      stubFetch({ detail: "boom" }, false, 500),
    )
    await expect(listSatellites()).rejects.toMatchObject({
      name: "OrbitalApiError",
      status: 500,
      detail: "boom",
    })
  })

  it("falls back to an HTTP status message when the error body is not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 503,
          json: () => Promise.reject(new Error("not json")),
        } as Response),
      ),
    )
    try {
      await listSatellites()
      throw new Error("expected the call to reject")
    } catch (err) {
      expect(err).toBeInstanceOf(OrbitalApiError)
      expect((err as OrbitalApiError).status).toBe(503)
      expect((err as OrbitalApiError).detail).toBe("HTTP 503")
    }
  })
})

describe("fetchTrack", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it("builds the query string with all fields", async () => {
    const fetchMock = stubFetch(SAMPLE_TRACK)
    vi.stubGlobal("fetch", fetchMock)
    await fetchTrack({
      satellite: "iss",
      tStartIso: "2014-01-20T22:00:00Z",
      tEndIso: "2014-01-20T23:00:00Z",
      stepSeconds: 30,
    })
    const url = fetchMock.mock.calls[0]![0] as string
    expect(url.startsWith("/api/orbital/track?")).toBe(true)
    const params = new URLSearchParams(url.split("?")[1])
    expect(params.get("satellite")).toBe("iss")
    expect(params.get("t_start")).toBe("2014-01-20T22:00:00Z")
    expect(params.get("t_end")).toBe("2014-01-20T23:00:00Z")
    expect(params.get("step_seconds")).toBe("30")
  })

  it("defaults step_seconds to 60 when not provided", async () => {
    const fetchMock = stubFetch(SAMPLE_TRACK)
    vi.stubGlobal("fetch", fetchMock)
    await fetchTrack({
      satellite: "iss",
      tStartIso: "a",
      tEndIso: "b",
    })
    const url = fetchMock.mock.calls[0]![0] as string
    expect(new URLSearchParams(url.split("?")[1]).get("step_seconds")).toBe("60")
  })

  it("forwards the abort signal", async () => {
    const fetchMock = stubFetch(SAMPLE_TRACK)
    vi.stubGlobal("fetch", fetchMock)
    const ctrl = new AbortController()
    await fetchTrack({
      satellite: "iss",
      tStartIso: "a",
      tEndIso: "b",
      signal: ctrl.signal,
    })
    expect((fetchMock.mock.calls[0]![1] as RequestInit).signal).toBe(ctrl.signal)
  })
})

describe("fetchVisibility", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it("builds the query string with all fields", async () => {
    const fetchMock = stubFetch(SAMPLE_VIS)
    vi.stubGlobal("fetch", fetchMock)
    await fetchVisibility({
      satellite: "iss",
      groundLatDeg: 40,
      groundLonDeg: -75,
      groundAltM: 12,
      tStartIso: "a",
      tEndIso: "b",
      stepSeconds: 15,
      minElevationDeg: 12,
    })
    const url = fetchMock.mock.calls[0]![0] as string
    const params = new URLSearchParams(url.split("?")[1])
    expect(params.get("satellite")).toBe("iss")
    expect(params.get("ground_lat_deg")).toBe("40")
    expect(params.get("ground_lon_deg")).toBe("-75")
    expect(params.get("ground_alt_m")).toBe("12")
    expect(params.get("step_seconds")).toBe("15")
    expect(params.get("min_elevation_deg")).toBe("12")
  })

  it("defaults ground_alt_m to 0, step_seconds to 30, min_elevation_deg to 5", async () => {
    const fetchMock = stubFetch(SAMPLE_VIS)
    vi.stubGlobal("fetch", fetchMock)
    await fetchVisibility({
      satellite: "iss",
      groundLatDeg: 0,
      groundLonDeg: 0,
      tStartIso: "a",
      tEndIso: "b",
    })
    const url = fetchMock.mock.calls[0]![0] as string
    const params = new URLSearchParams(url.split("?")[1])
    expect(params.get("ground_alt_m")).toBe("0")
    expect(params.get("step_seconds")).toBe("30")
    expect(params.get("min_elevation_deg")).toBe("5")
  })
})
