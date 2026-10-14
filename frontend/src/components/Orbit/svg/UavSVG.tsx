/**
 * UavSVG — drone silhouettes with rotor/propeller detail.
 *
 * Two variants:
 *
 *   "quad"      quadcopter with four rotor arms and rotor discs
 *   "fixed"     fixed-wing with wings, tail plane, and propeller
 *
 * Design grid: 60 x 40 units.
 */

export type UavVariant = "quad" | "fixed"

export type UavSVGProps = {
  variant?: UavVariant
}

export function UavSVG({ variant = "quad" }: UavSVGProps) {
  const stroke = "var(--ink-primary)"
  const fill = "var(--bg-surface)"

  if (variant === "fixed") {
    return (
      <g>
        {/* Fuselage */}
        <ellipse
          cx={30}
          cy={20}
          rx={14}
          ry={3.2}
          fill={fill}
          stroke={stroke}
          strokeWidth={0.9}
        />
        {/* Main wings */}
        <polygon
          points="14,20 30,20 46,20 40,8 30,8 20,8"
          fill={fill}
          stroke={stroke}
          strokeWidth={0.7}
        />
        {/* Tail plane */}
        <polygon
          points="44,20 50,20 50,16 46,16"
          fill={fill}
          stroke={stroke}
          strokeWidth={0.7}
        />
        {/* Horizontal stabiliser */}
        <line x1={46} y1={20} x2={46} y2={24} stroke={stroke} strokeWidth={0.6} />
        <line x1={43} y1={24} x2={49} y2={24} stroke={stroke} strokeWidth={0.6} />
        {/* Propeller */}
        <g>
          <line x1={12} y1={16} x2={12} y2={24} stroke={stroke} strokeWidth={0.7} />
          <circle cx={12} cy={20} r={2.2} fill="none" stroke={stroke} strokeWidth={0.6} />
        </g>
        {/* Cockpit dot */}
        <circle cx={22} cy={20} r={0.9} fill={stroke} />
      </g>
    )
  }

  // quad variant
  return (
    <g>
      {/* Arms (X configuration) */}
      <line x1={30} y1={20} x2={12} y2={10} stroke={stroke} strokeWidth={0.9} />
      <line x1={30} y1={20} x2={48} y2={10} stroke={stroke} strokeWidth={0.9} />
      <line x1={30} y1={20} x2={12} y2={30} stroke={stroke} strokeWidth={0.9} />
      <line x1={30} y1={20} x2={48} y2={30} stroke={stroke} strokeWidth={0.9} />

      {/* Central body */}
      <ellipse
        cx={30}
        cy={20}
        rx={7}
        ry={4}
        fill={fill}
        stroke={stroke}
        strokeWidth={0.9}
      />
      <ellipse
        cx={30}
        cy={20}
        rx={3}
        ry={1.6}
        fill="none"
        stroke={stroke}
        strokeWidth={0.5}
      />

      {/* Rotor discs */}
      <g fill="none" stroke={stroke} strokeWidth={0.5}>
        <circle cx={12} cy={10} r={4} />
        <circle cx={48} cy={10} r={4} />
        <circle cx={12} cy={30} r={4} />
        <circle cx={48} cy={30} r={4} />
      </g>
      {/* Hub dots */}
      <g fill={stroke}>
        <circle cx={12} cy={10} r={0.8} />
        <circle cx={48} cy={10} r={0.8} />
        <circle cx={12} cy={30} r={0.8} />
        <circle cx={48} cy={30} r={0.8} />
      </g>
    </g>
  )
}
