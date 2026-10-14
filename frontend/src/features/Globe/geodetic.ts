/**
 * Geodetic-to-Cartesian conversion for the Globe renderer.
 *
 * The backend returns satellite and ground positions in the geodetic
 * frame: latitude, longitude, and altitude above the WGS-84 ellipsoid,
 * approximately. This module converts those coordinates to a Cartesian
 * frame that the Three.js scene can render.
 *
 * Coordinate convention
 * ---------------------
 *
 * The Globe uses a Y-up right-handed frame, matching Three.js defaults:
 *
 *     +Y is the north pole
 *     +X is the point (lat=0, lon=0)
 *     +Z is the point (lat=0, lon=+90E)
 *
 * Equivalently:
 *
 *     x = r * cos(lat) * cos(lon)
 *     y = r * sin(lat)
 *     z = r * cos(lat) * sin(lon)
 *
 * with lat and lon in radians and r the distance from Earth centre.
 *
 * Scale
 * -----
 *
 * The scene renders the Earth as a unit sphere. Positions returned by
 * geodeticToUnit are in the same unit: a point on the surface has
 * magnitude 1, a satellite at 500 km altitude has magnitude
 * (EARTH_RADIUS_M + 500_000) / EARTH_RADIUS_M = 1.0785.
 *
 * The Earth radius constant is 6_371_000 m, matching
 * backend/app/physics/geometry.py EARTH_RADIUS_M. The two must agree,
 * because the backend decides line of sight and pass geometry against
 * that sphere and the frontend must render the same sphere for the
 * scene to be visually consistent with the backend's claims.
 */

export const EARTH_RADIUS_M = 6_371_000.0

export type Vec3 = [number, number, number]

const DEG_TO_RAD = Math.PI / 180

function assertFinite(value: number, name: string): void {
  if (!Number.isFinite(value)) {
    throw new Error(`${name} must be finite; got ${value}`)
  }
}

/**
 * Convert a geodetic position to a unit-sphere-scaled Cartesian position.
 *
 * @param lat_deg Latitude in degrees, in [-90, 90].
 * @param lon_deg Longitude in degrees, any finite value.
 * @param alt_m Altitude above the Earth's surface, in metres. May be
 *              negative for points below the reference surface; the
 *              function does not clip.
 * @returns [x, y, z] with magnitude (EARTH_RADIUS_M + alt_m) / EARTH_RADIUS_M.
 */
export function geodeticToUnit(
  lat_deg: number,
  lon_deg: number,
  alt_m: number,
): Vec3 {
  assertFinite(lat_deg, "lat_deg")
  assertFinite(lon_deg, "lon_deg")
  assertFinite(alt_m, "alt_m")
  if (lat_deg < -90 || lat_deg > 90) {
    throw new Error(`lat_deg must be in [-90, 90]; got ${lat_deg}`)
  }
  const lat = lat_deg * DEG_TO_RAD
  const lon = lon_deg * DEG_TO_RAD
  const r = (EARTH_RADIUS_M + alt_m) / EARTH_RADIUS_M
  const cosLat = Math.cos(lat)
  return [
    r * cosLat * Math.cos(lon),
    r * Math.sin(lat),
    r * cosLat * Math.sin(lon),
  ]
}

/**
 * Return the unit vector (magnitude 1) pointing at a surface location.
 *
 * Equivalent to geodeticToUnit(lat, lon, 0). Kept as a separate name
 * because the Globe uses it for surface markers (ground sites) where
 * the altitude is always zero and the intent is clearer without the
 * third argument.
 */
export function surfaceUnitVector(lat_deg: number, lon_deg: number): Vec3 {
  return geodeticToUnit(lat_deg, lon_deg, 0)
}

/**
 * Return the Euclidean magnitude of a vector.
 */
export function magnitude(v: Vec3): number {
  return Math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
}

/**
 * Inverse of geodeticToUnit for any non-zero vector in the same frame.
 * Returns geodetic latitude and longitude in degrees; altitude is not
 * returned (callers who need it can recover it from the vector
 * magnitude).
 *
 * Throws on the zero vector.
 */
export function inverseGeodetic(p: Vec3): { lat_deg: number; lon_deg: number } {
  const [x, y, z] = p
  const r = Math.sqrt(x * x + y * y + z * z)
  if (r === 0) {
    throw new Error("cannot invert a zero-length vector")
  }
  const lat_deg = (Math.asin(y / r) * 180) / Math.PI
  const lon_deg = (Math.atan2(z, x) * 180) / Math.PI
  return { lat_deg, lon_deg }
}

/**
 * Interpolate between two unit-sphere points along the shorter great
 * circle. Fraction t in [0, 1] returns a point on the same sphere.
 *
 * Used by the Globe to draw arcs (link paths) between ground sites and
 * satellite positions without a separate spline library.
 */
export function greatCircleInterpolate(
  a: Vec3,
  b: Vec3,
  t: number,
  lift: number = 0,
): Vec3 {
  if (t < 0 || t > 1) {
    throw new Error(`t must be in [0, 1]; got ${t}`)
  }
  const na = magnitude(a)
  const nb = magnitude(b)
  if (na === 0 || nb === 0) {
    throw new Error("cannot interpolate a zero-length vector")
  }
  const ua: Vec3 = [a[0] / na, a[1] / na, a[2] / na]
  const ub: Vec3 = [b[0] / nb, b[1] / nb, b[2] / nb]
  const dot = Math.max(-1, Math.min(1, ua[0] * ub[0] + ua[1] * ub[1] + ua[2] * ub[2]))
  const omega = Math.acos(dot)
  let p: Vec3
  if (omega < 1e-9) {
    p = ua
  } else {
    const sinOmega = Math.sin(omega)
    const ca = Math.sin((1 - t) * omega) / sinOmega
    const cb = Math.sin(t * omega) / sinOmega
    p = [
      ca * ua[0] + cb * ub[0],
      ca * ua[1] + cb * ub[1],
      ca * ua[2] + cb * ub[2],
    ]
  }
  const bulge = 1 + lift * Math.sin(Math.PI * t)
  return [p[0] * bulge, p[1] * bulge, p[2] * bulge]
}
