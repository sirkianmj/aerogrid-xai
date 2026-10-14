/**
 * SatelliteSVG — an engineering-profile satellite.
 *
 * Real shapes: a central bus, two solar arrays extending left and
 * right with visible cell divisions, a parabolic dish antenna on the
 * nadir face, a small thruster nozzle on the opposite face, and two
 * attitude-control reaction wheels inset in the bus.
 *
 * Design grid: 100 x 60 units (width x height). The parent places
 * this with a <g transform="translate(x, y) scale(s)">.
 */

export type SatelliteVariant = "leo" | "geo" | "relay"

export type SatelliteSVGProps = {
  variant?: SatelliteVariant
}

export function SatelliteSVG({ variant = "leo" }: SatelliteSVGProps) {
  const bodyStroke = "var(--ink-primary)"
  const panelStroke = "var(--ink-secondary)"
  const fillBody = "var(--bg-surface)"
  const fillPanel = "var(--bg-subtle)"
  const accent = "var(--ink-primary)"

  // The relay variant has a second small dish on the top face and
  // two extra antenna whips; the geo variant uses a longer dish on a
  // boom. The leo variant is the base design.
  const hasSecondDish = variant === "relay"
  const hasBoom = variant === "geo"

  return (
    <g>
      {/* Left solar array */}
      <g>
        <rect
          x={2}
          y={24}
          width={28}
          height={12}
          rx={1}
          fill={fillPanel}
          stroke={panelStroke}
          strokeWidth={0.6}
        />
        <line x1={9} y1={24} x2={9} y2={36} stroke={panelStroke} strokeWidth={0.4} />
        <line x1={16} y1={24} x2={16} y2={36} stroke={panelStroke} strokeWidth={0.4} />
        <line x1={23} y1={24} x2={23} y2={36} stroke={panelStroke} strokeWidth={0.4} />
      </g>

      {/* Right solar array */}
      <g>
        <rect
          x={70}
          y={24}
          width={28}
          height={12}
          rx={1}
          fill={fillPanel}
          stroke={panelStroke}
          strokeWidth={0.6}
        />
        <line x1={77} y1={24} x2={77} y2={36} stroke={panelStroke} strokeWidth={0.4} />
        <line x1={84} y1={24} x2={84} y2={36} stroke={panelStroke} strokeWidth={0.4} />
        <line x1={91} y1={24} x2={91} y2={36} stroke={panelStroke} strokeWidth={0.4} />
      </g>

      {/* Left boom arm */}
      <line x1={30} y1={30} x2={34} y2={30} stroke={bodyStroke} strokeWidth={0.8} />
      {/* Right boom arm */}
      <line x1={66} y1={30} x2={70} y2={30} stroke={bodyStroke} strokeWidth={0.8} />

      {/* Central bus */}
      <rect
        x={34}
        y={18}
        width={32}
        height={24}
        rx={2}
        fill={fillBody}
        stroke={bodyStroke}
        strokeWidth={0.9}
      />

      {/* Reaction wheels */}
      <circle cx={40} cy={26} r={2.4} fill="none" stroke={panelStroke} strokeWidth={0.5} />
      <circle cx={60} cy={26} r={2.4} fill="none" stroke={panelStroke} strokeWidth={0.5} />

      {/* Bus panel detail */}
      <line x1={36} y1={34} x2={64} y2={34} stroke={panelStroke} strokeWidth={0.4} />
      <line x1={36} y1={37} x2={64} y2={37} stroke={panelStroke} strokeWidth={0.4} />

      {/* Nadir dish antenna (downward) */}
      <g>
        <line x1={50} y1={42} x2={50} y2={46} stroke={bodyStroke} strokeWidth={0.8} />
        <ellipse cx={50} cy={48} rx={6} ry={2.4} fill={fillBody} stroke={bodyStroke} strokeWidth={0.8} />
        <line x1={46} y1={47.4} x2={54} y2={47.4} stroke={panelStroke} strokeWidth={0.4} />
      </g>

      {/* Zenith boom + dish (geo variant) */}
      {hasBoom && (
        <g>
          <line x1={50} y1={18} x2={50} y2={10} stroke={bodyStroke} strokeWidth={0.8} />
          <ellipse cx={50} cy={8} rx={5} ry={2} fill={fillBody} stroke={bodyStroke} strokeWidth={0.8} />
        </g>
      )}

      {/* Relay extra: two small whip antennas on the top face */}
      {hasSecondDish && (
        <g>
          <line x1={40} y1={18} x2={36} y2={8} stroke={bodyStroke} strokeWidth={0.6} />
          <circle cx={36} cy={8} r={0.9} fill={accent} />
          <line x1={60} y1={18} x2={64} y2={8} stroke={bodyStroke} strokeWidth={0.6} />
          <circle cx={64} cy={8} r={0.9} fill={accent} />
        </g>
      )}

      {/* Thruster nozzle on the anti-nadir face (upward) */}
      <g>
        <line x1={50} y1={42} x2={50} y2={42} stroke={bodyStroke} strokeWidth={0} />
      </g>
      <g transform="translate(0, -2)">
        <polygon
          points="48,20 52,20 51,17 49,17"
          fill={fillBody}
          stroke={bodyStroke}
          strokeWidth={0.6}
        />
      </g>
    </g>
  )
}
