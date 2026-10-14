import { describe, expect, it } from "vitest"
import { EARTH_RADIUS_M, geodeticToUnit, greatCircleInterpolate, inverseGeodetic, magnitude, surfaceUnitVector, type Vec3 } from "./geodetic"

describe("EARTH_RADIUS_M", () => {
  it("matches the backend spherical Earth radius", () => {
    // backend/app/physics/geometry.py EARTH_RADIUS_M = 6_371_000.0
    expect(EARTH_RADIUS_M).toBe(6_371_000.0)
  })
})

describe("geodeticToUnit: cardinal points", () => {
  it("(0, 0, 0) is +X", () => {
    const [x, y, z] = geodeticToUnit(0, 0, 0)
    expect(x).toBeCloseTo(1, 12)
    expect(y).toBeCloseTo(0, 12)
    expect(z).toBeCloseTo(0, 12)
  })

  it("(90, any, 0) is +Y (north pole)", () => {
    const [x, y, z] = geodeticToUnit(90, 123, 0)
    expect(x).toBeCloseTo(0, 12)
    expect(y).toBeCloseTo(1, 12)
    expect(z).toBeCloseTo(0, 12)
  })

  it("(-90, any, 0) is -Y (south pole)", () => {
    const [x, y, z] = geodeticToUnit(-90, -7, 0)
    expect(x).toBeCloseTo(0, 12)
    expect(y).toBeCloseTo(-1, 12)
    expect(z).toBeCloseTo(0, 12)
  })

  it("(0, 90, 0) is +Z", () => {
    const [x, y, z] = geodeticToUnit(0, 90, 0)
    expect(x).toBeCloseTo(0, 12)
    expect(y).toBeCloseTo(0, 12)
    expect(z).toBeCloseTo(1, 12)
  })

  it("(0, -90, 0) is -Z", () => {
    const [x, y, z] = geodeticToUnit(0, -90, 0)
    expect(x).toBeCloseTo(0, 12)
    expect(y).toBeCloseTo(0, 12)
    expect(z).toBeCloseTo(-1, 12)
  })
})

describe("geodeticToUnit: altitude scaling", () => {
  it("surface altitude 0 has magnitude 1", () => {
    expect(magnitude(geodeticToUnit(45, 45, 0))).toBeCloseTo(1, 12)
  })

  it("altitude increases magnitude proportionally", () => {
    const alt = 500_000
    const expected = (EARTH_RADIUS_M + alt) / EARTH_RADIUS_M
    expect(magnitude(geodeticToUnit(0, 0, alt))).toBeCloseTo(expected, 12)
  })

  it("altitude ratio is preserved at every latitude", () => {
    const alt = 35_786_000
    const expected = (EARTH_RADIUS_M + alt) / EARTH_RADIUS_M
    for (const lat of [-90, -45, 0, 45, 90]) {
      expect(magnitude(geodeticToUnit(lat, 0, alt))).toBeCloseTo(expected, 12)
    }
  })

  it("negative altitude is allowed and reduces magnitude", () => {
    const alt = -1_000
    const expected = (EARTH_RADIUS_M + alt) / EARTH_RADIUS_M
    expect(magnitude(geodeticToUnit(0, 0, alt))).toBeCloseTo(expected, 12)
  })
})

describe("geodeticToUnit: validation", () => {
  it("rejects latitude outside [-90, 90]", () => {
    expect(() => geodeticToUnit(91, 0, 0)).toThrow()
    expect(() => geodeticToUnit(-91, 0, 0)).toThrow()
  })

  it("accepts latitude exactly at the poles", () => {
    expect(() => geodeticToUnit(90, 0, 0)).not.toThrow()
    expect(() => geodeticToUnit(-90, 0, 0)).not.toThrow()
  })

  it("accepts any finite longitude", () => {
    expect(() => geodeticToUnit(0, 540, 0)).not.toThrow()
    expect(() => geodeticToUnit(0, -540, 0)).not.toThrow()
  })

  it("rejects NaN and infinities", () => {
    expect(() => geodeticToUnit(NaN, 0, 0)).toThrow()
    expect(() => geodeticToUnit(0, Infinity, 0)).toThrow()
    expect(() => geodeticToUnit(0, 0, -Infinity)).toThrow()
  })
})

describe("surfaceUnitVector", () => {
  it("equals geodeticToUnit with zero altitude", () => {
    const a = surfaceUnitVector(30, 60)
    const b = geodeticToUnit(30, 60, 0)
    expect(a[0]).toBeCloseTo(b[0], 15)
    expect(a[1]).toBeCloseTo(b[1], 15)
    expect(a[2]).toBeCloseTo(b[2], 15)
  })
})

describe("greatCircleInterpolate", () => {
  const a: Vec3 = surfaceUnitVector(0, 0)
  const b: Vec3 = surfaceUnitVector(0, 90)

  it("returns the start point at t=0", () => {
    const p = greatCircleInterpolate(a, b, 0)
    expect(p[0]).toBeCloseTo(a[0], 12)
    expect(p[1]).toBeCloseTo(a[1], 12)
    expect(p[2]).toBeCloseTo(a[2], 12)
  })

  it("returns the end point at t=1", () => {
    const p = greatCircleInterpolate(a, b, 1)
    expect(p[0]).toBeCloseTo(b[0], 12)
    expect(p[1]).toBeCloseTo(b[1], 12)
    expect(p[2]).toBeCloseTo(b[2], 12)
  })

  it("returns the midpoint between (0,0) and (0,90) at t=0.5", () => {
    // The great circle midpoint should be on the equator at lon=45.
    const expected = surfaceUnitVector(0, 45)
    const p = greatCircleInterpolate(a, b, 0.5)
    expect(p[0]).toBeCloseTo(expected[0], 12)
    expect(p[1]).toBeCloseTo(expected[1], 12)
    expect(p[2]).toBeCloseTo(expected[2], 12)
  })

  it("returns points of magnitude 1 when lift is zero", () => {
    for (const t of [0.1, 0.25, 0.5, 0.75, 0.9]) {
      expect(magnitude(greatCircleInterpolate(a, b, t))).toBeCloseTo(1, 12)
    }
  })

  it("bulges above the sphere when lift > 0", () => {
    const peak = greatCircleInterpolate(a, b, 0.5, 0.2)
    expect(magnitude(peak)).toBeCloseTo(1.2, 12)
  })

  it("rejects t outside [0, 1]", () => {
    expect(() => greatCircleInterpolate(a, b, -0.1)).toThrow()
    expect(() => greatCircleInterpolate(a, b, 1.1)).toThrow()
  })

  it("rejects a zero-length input", () => {
    const zero: Vec3 = [0, 0, 0]
    expect(() => greatCircleInterpolate(zero, b, 0.5)).toThrow()
  })
})

describe("geodeticToUnit: agreement with backend positions", () => {
  // The backend's physics.geometry.node_position_from_params_m returns
  // metres in a Z-up frame:
  //   x = r cos(lat) cos(lon)
  //   y = r cos(lat) sin(lon)
  //   z = r sin(lat)
  // The Globe uses a Y-up frame. The two differ only by the swap of the
  // y and z coordinates. Verify that relationship explicitly, so a
  // silent drift between backend and frontend is caught here.

  it("y and z axes are swapped relative to the backend z-up frame", () => {
    const lat = 30
    const lon = 60
    const alt = 500_000
    const lat_rad = (lat * Math.PI) / 180
    const lon_rad = (lon * Math.PI) / 180
    const r = EARTH_RADIUS_M + alt
    // Backend z-up:
    const bx = r * Math.cos(lat_rad) * Math.cos(lon_rad)
    const by = r * Math.cos(lat_rad) * Math.sin(lon_rad)
    const bz = r * Math.sin(lat_rad)
    // Frontend y-up, normalized to a unit sphere:
    const [fx, fy, fz] = geodeticToUnit(lat, lon, alt)
    expect(fx).toBeCloseTo(bx / EARTH_RADIUS_M, 12)
    expect(fy).toBeCloseTo(bz / EARTH_RADIUS_M, 12)
    expect(fz).toBeCloseTo(by / EARTH_RADIUS_M, 12)
  })
})

describe("inverseGeodetic", () => {
  it("round-trips through geodeticToUnit", () => {
    const cases: [number, number][] = [
      [0, 0],
      [45, 90],
      [-30, -120],
      [89.9, 179.9],
      [-89.9, -179.9],
      [40.798, -77.86],
    ]
    for (const [lat, lon] of cases) {
      const v = geodeticToUnit(lat, lon, 0)
      const back = inverseGeodetic(v)
      expect(back.lat_deg).toBeCloseTo(lat, 4)
      expect(back.lon_deg).toBeCloseTo(lon, 4)
    }
  })

  it("throws on the zero vector", () => {
    expect(() => inverseGeodetic([0, 0, 0])).toThrow()
  })
})
