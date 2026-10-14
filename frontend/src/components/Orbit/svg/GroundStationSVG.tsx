/**
 * GroundStationSVG — a tracking ground station.
 *
 * Shapes: parabolic dish on a two-axis mount, pedestal, small
 * electronics enclosure beside it, and a ground plane line.
 *
 * Design grid: 60 x 60 units.
 */

export function GroundStationSVG() {
  const stroke = "var(--ink-primary)"
  const fill = "var(--bg-surface)"

  return (
    <g>
      {/* Ground plane */}
      <line x1={0} y1={56} x2={60} y2={56} stroke={stroke} strokeWidth={0.8} />
      <line
        x1={4}
        y1={58}
        x2={56}
        y2={58}
        stroke="var(--ink-tertiary)"
        strokeWidth={0.4}
        strokeDasharray="2 2"
      />

      {/* Pedestal base */}
      <polygon points="22,56 38,56 35,46 25,46" fill={fill} stroke={stroke} strokeWidth={0.8} />
      <line x1={26} y1={50} x2={34} y2={50} stroke="var(--ink-secondary)" strokeWidth={0.4} />

      {/* Az/el mount arm */}
      <line x1={30} y1={46} x2={30} y2={36} stroke={stroke} strokeWidth={0.9} />

      {/* Parabolic dish — tilted */}
      <g transform="translate(30, 30) rotate(-30)">
        <ellipse cx={0} cy={0} rx={12} ry={4} fill={fill} stroke={stroke} strokeWidth={0.9} />
        <ellipse cx={0} cy={0} rx={6} ry={2} fill="none" stroke="var(--ink-secondary)" strokeWidth={0.4} />
        <ellipse cx={0} cy={0} rx={2} ry={0.8} fill="none" stroke="var(--ink-secondary)" strokeWidth={0.4} />
        {/* Feed horn */}
        <line x1={0} y1={0} x2={10} y2={0} stroke={stroke} strokeWidth={0.6} />
        <circle cx={10} cy={0} r={1.1} fill={stroke} />
      </g>

      {/* Electronics enclosure */}
      <rect x={40} y={50} width={10} height={6} rx={1} fill={fill} stroke={stroke} strokeWidth={0.7} />
      <line x1={42} y1={53} x2={48} y2={53} stroke="var(--ink-secondary)" strokeWidth={0.4} />
    </g>
  )
}
