/**
 * ArchitectureSketch — a compact SVG rendering of one discovered
 * architecture's topology.
 *
 * Layout follows the same layering used by the FANET panel: satellite
 * nodes on the top row, UAV nodes on the middle row, ground nodes on
 * the bottom row. Nodes are drawn as small circles with the layer's
 * accent color; links are drawn as straight lines behind them. There
 * is no interaction: the sketch is a thumbnail, not a graph editor.
 */

import type { DiscoveredNode, DiscoveredLink } from "../ClearDDashboard/clearDApi"

const W = 320
const H = 180
const LAYER_Y = { satellite: 28, uav: 90, ground: 152 } as const

const NODE_COLOR: Record<string, string> = {
  Satellite_LEO: "var(--plot-primary)",
  Satellite_GEO: "var(--plot-primary)",
  UAV_Energy: "var(--plot-secondary)",
  UAV_Compute: "var(--plot-warning)",
  Ground_Station: "var(--plot-muted)",
}

function layerOf(kind: string): keyof typeof LAYER_Y {
  if (kind.startsWith("Satellite_")) return "satellite"
  if (kind.startsWith("UAV_")) return "uav"
  return "ground"
}

type PositionedNode = { node: DiscoveredNode; x: number; y: number }

function layout(nodes: DiscoveredNode[]): Record<string, PositionedNode> {
  const buckets: Record<keyof typeof LAYER_Y, DiscoveredNode[]> = {
    satellite: [],
    uav: [],
    ground: [],
  }
  for (const n of nodes) buckets[layerOf(n.kind)].push(n)
  const out: Record<string, PositionedNode> = {}
  for (const layer of ["satellite", "uav", "ground"] as const) {
    const list = buckets[layer]
    const n = list.length
    const y = LAYER_Y[layer]
    for (let i = 0; i < n; i++) {
      const x = ((i + 1) / (n + 1)) * W
      out[list[i].node_id] = { node: list[i], x, y }
    }
  }
  return out
}

export type ArchitectureSketchProps = {
  nodes: DiscoveredNode[]
  links: DiscoveredLink[]
}

export function ArchitectureSketch({ nodes, links }: ArchitectureSketchProps) {
  const positions = layout(nodes)
  const r = (kind: string) =>
    kind.startsWith("Satellite_") ? 5 : kind.startsWith("Ground_") ? 5 : 4

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="Architecture topology sketch"
      className="w-full"
      style={{ maxHeight: 180 }}
    >
      {/* Edges first so nodes are drawn above. */}
      <g stroke="var(--ink-tertiary)" strokeWidth={0.8} opacity={0.6}>
        {links.map((ln) => {
          const a = positions[ln.source_id]
          const b = positions[ln.target_id]
          if (!a || !b) return null
          return (
            <line
              key={ln.link_id}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
            />
          )
        })}
      </g>

      {/* Layer labels. */}
      <g
        fontFamily="ui-monospace, monospace"
        fontSize={8}
        fill="var(--ink-tertiary)"
        opacity={0.6}
      >
        <text x={4} y={LAYER_Y.satellite - 12}>SAT</text>
        <text x={4} y={LAYER_Y.uav - 12}>UAV</text>
        <text x={4} y={LAYER_Y.ground - 12}>GND</text>
      </g>

      {/* Nodes. */}
      {Object.values(positions).map(({ node, x, y }) => (
        <circle
          key={node.node_id}
          cx={x}
          cy={y}
          r={r(node.kind)}
          fill={NODE_COLOR[node.kind] ?? "var(--ink-tertiary)"}
          opacity={0.9}
        />
      ))}
    </svg>
  )
}
