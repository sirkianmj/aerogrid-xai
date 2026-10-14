/**
 * GlobeScene — the Three.js scene rendered inside the Globe panel.
 *
 * Renders a unit-sphere Earth, one marker per ground site, one marker
 * per satellite position along its track, and a line for the track
 * itself. The scene is static per render; it does not run an animation
 * loop because the track is a fixed time slice, not a live feed.
 *
 * Coordinate convention: see geodetic.ts. Positions are in the
 * unit-sphere frame with Y up.
 */

import { Line, Sphere } from "@react-three/drei"
import type { TrackPoint } from "./orbitalApi"
import {
  geodeticToUnit,
  surfaceUnitVector,
  type Vec3,
} from "./geodetic"

const EARTH_SEGMENTS = 48

export type GroundMarker = {
  name: string
  lat_deg: number
  lon_deg: number
}

export type GlobeSceneProps = {
  /** Track points in chronological order. */
  track: TrackPoint[]
  /** Ground sites to render as surface markers. */
  grounds: GroundMarker[]
  /** Optional link arcs between ground and satellite positions. */
  arcs?: [GroundMarker, TrackPoint][]
  /** The point the playhead is currently on. Rendered as a distinct
   *  marker so the user can see the satellite move along the track. */
  currentPoint?: TrackPoint | null
}

export function GlobeScene({
  track,
  grounds,
  arcs = [],
  currentPoint = null,
}: GlobeSceneProps) {
  return (
    <group>
      <ambientLight intensity={0.6} />
      <directionalLight position={[5, 5, 5]} intensity={0.9} />

      {/* Earth: unit sphere, translucent so far-side markers remain
          visible. Not a textured globe because no Earth texture is
          shipped with the repository. */}
      <Sphere args={[1, EARTH_SEGMENTS, EARTH_SEGMENTS]}>
        <meshStandardMaterial
          color="#0d2a4d"
          transparent
          opacity={0.85}
          roughness={0.9}
          metalness={0.1}
        />
      </Sphere>

      {/* Wireframe latitude/longitude grid at 30 degrees. */}
      <Sphere args={[1.001, 24, 24]}>
        <meshBasicMaterial color="#1e4a7a" wireframe transparent opacity={0.25} />
      </Sphere>

      {/* Ground markers. */}
      {grounds.map((g) => {
        const p = surfaceUnitVector(g.lat_deg, g.lon_deg)
        return (
          <mesh key={`ground-${g.name}`} position={p}>
            <sphereGeometry args={[0.02, 12, 12]} />
            <meshStandardMaterial color="#14b8a6" />
          </mesh>
        )
      })}

      {/* Track polyline. Skip if fewer than two points (a lone point
          does not define a line). */}
      {track.length >= 2 && (
        <Line
          points={track.map(
            (p) => geodeticToUnit(p.lat_deg, p.lon_deg, p.alt_m) as Vec3,
          )}
          color="#8b5cf6"
          lineWidth={2}
        />
      )}

      {/* Satellite markers along the track. Rendered for a subset of
          points (every step) so the scene does not become a solid tube
          when the track has hundreds of samples. */}
      {track.map((p, i) => {
        if (i % Math.max(1, Math.floor(track.length / 30)) !== 0 && i !== track.length - 1) {
          return null
        }
        const pos = geodeticToUnit(p.lat_deg, p.lon_deg, p.alt_m)
        const color = p.in_eclipse ? "#f59e0b" : "#e6e8eb"
        return (
          <mesh key={`sat-${i}`} position={pos}>
            <sphereGeometry args={[0.012, 10, 10]} />
            <meshStandardMaterial color={color} />
          </mesh>
        )
      })}

      {/* Current playhead position: a larger emissive marker so the
          animated satellite is visually distinct from the static
          track history. */}
      {currentPoint && (
        <mesh
          position={
            geodeticToUnit(
              currentPoint.lat_deg,
              currentPoint.lon_deg,
              currentPoint.alt_m,
            ) as Vec3
          }
        >
          <sphereGeometry args={[0.028, 16, 16]} />
          <meshStandardMaterial
            color="#f97316"
            emissive="#f97316"
            emissiveIntensity={0.8}
          />
        </mesh>
      )}

      {/* Link arcs from ground to satellite. Rendered as a two-segment
          lifted great-circle path, no spline library needed. */}
      {arcs.map(([ground, sat], i) => {
        const a = surfaceUnitVector(ground.lat_deg, ground.lon_deg)
        const b = geodeticToUnit(sat.lat_deg, sat.lon_deg, sat.alt_m)
        const N = 24
        const points: Vec3[] = []
        for (let k = 0; k <= N; k++) {
          const t = k / N
          points.push(interpolateWithLift(a, b, t, 0.15))
        }
        return (
          <Line
            key={`arc-${i}`}
            points={points}
            color="#f59e0b"
            lineWidth={1}
          />
        )
      })}
    </group>
  )
}

/**
 * Lift a great-circle arc above the sphere between two positions,
 * regardless of whether the endpoints are at the same radius. Used to
 * make link arcs visible above the Earth surface.
 */
function interpolateWithLift(a: Vec3, b: Vec3, t: number, lift: number): Vec3 {
  const ra = Math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])
  const rb = Math.sqrt(b[0] * b[0] + b[1] * b[1] + b[2] * b[2])
  const ua: Vec3 = [a[0] / ra, a[1] / ra, a[2] / ra]
  const ub: Vec3 = [b[0] / rb, b[1] / rb, b[2] / rb]
  const dot = Math.max(-1, Math.min(1, ua[0] * ub[0] + ua[1] * ub[1] + ua[2] * ub[2]))
  const omega = Math.acos(dot)
  let dir: Vec3
  if (omega < 1e-9) {
    dir = ua
  } else {
    const s = Math.sin(omega)
    const ca = Math.sin((1 - t) * omega) / s
    const cb = Math.sin(t * omega) / s
    dir = [
      ca * ua[0] + cb * ub[0],
      ca * ua[1] + cb * ub[1],
      ca * ua[2] + cb * ub[2],
    ]
  }
  const r = ra * (1 - t) + rb * t
  const bulge = 1 + lift * Math.sin(Math.PI * t)
  return [dir[0] * r * bulge, dir[1] * r * bulge, dir[2] * r * bulge]
}
