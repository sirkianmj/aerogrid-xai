/**
 * Continents — vector continent outlines on the unit sphere.
 *
 * Loads the bundled Natural Earth 1:110m land polygons (TopoJSON,
 * ~55 KB, public domain, committed under frontend/public/) and
 * renders each polygon ring as a polyline slightly above the sphere
 * surface. No runtime network access; the file is imported at build
 * time.
 *
 * This replaces the plain sphere-plus-wireframe as the geographic
 * reference for the Globe. The wireframe grid remains as a visual
 * guide at a lower radius.
 *
 * Coordinate convention matches geodetic.ts: the TopoJSON supplies
 * [lon, lat] pairs in degrees, which surfaceUnitVector maps to the
 * unit-sphere frame.
 */

import { useMemo } from "react"
import { Line } from "@react-three/drei"
import { feature } from "topojson-client"
import landTopo from "./data/land-110m.json"
import { surfaceUnitVector, type Vec3 } from "./geodetic"

// Slight radial lift so the lines do not z-fight with the sphere
// surface or the wireframe grid.
const LIFT = 1.006

type Ring = [number, number][]

function decodeSegments(): Vec3[][] {
  // The imported JSON has no types; narrow to the Topology shape the
  // topojson-client `feature` function expects.
  const topo = landTopo as unknown as {
    type: string
    objects: Record<string, unknown>
  }
  const landObj = topo.objects.land
  if (landObj === undefined) {
    return []
  }
  const f = feature(topo as never, landObj as never) as unknown

  const fc: { features: { geometry: { type: string; coordinates: unknown } }[] } =
    f !== null && typeof f === "object" && (f as { type?: string }).type === "FeatureCollection"
      ? (f as { features: { geometry: { type: string; coordinates: unknown } }[] })
      : {
          features: [
            f as { geometry: { type: string; coordinates: unknown } },
          ],
        }

  const out: Vec3[][] = []
  for (const feat of fc.features) {
    const g = feat.geometry
    if (g.type === "Polygon") {
      for (const ring of g.coordinates as Ring[]) {
        out.push(ring.map(([lon, lat]) => surfaceUnitVector(lat, lon)))
      }
    } else if (g.type === "MultiPolygon") {
      for (const poly of g.coordinates as Ring[][]) {
        for (const ring of poly) {
          out.push(ring.map(([lon, lat]) => surfaceUnitVector(lat, lon)))
        }
      }
    }
  }
  return out
}

export function Continents() {
  const lifted = useMemo<Vec3[][]>(
    () =>
      decodeSegments().map((pts) =>
        pts.map(([x, y, z]) => [x * LIFT, y * LIFT, z * LIFT] as Vec3),
      ),
    [],
  )
  return (
    <group>
      {lifted.map((pts, i) => (
        <Line
          key={i}
          points={pts}
          color="#3b82f6"
          lineWidth={0.6}
          transparent
          opacity={0.85}
        />
      ))}
    </group>
  )
}
