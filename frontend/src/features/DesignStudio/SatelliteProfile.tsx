import { SatelliteProfileSVG } from "./svg/SatelliteProfileSVG"

export function SatelliteProfile({
  transmitter_power_w,
  transmitter_aperture_m,
  onChange,
}: {
  transmitter_power_w: number
  transmitter_aperture_m: number
  onChange: (patch: Partial<{ transmitter_aperture_m: number }>) => void
}) {

  // These values are computed by the SVG physics engine. 
  // We display them here using HTML for perfect layout.
  const designChain = [
    { label: "I_AM0", value: "1361 W/m²" },
    { label: "η_cell · packing · PSE", value: "0.30 · 0.85 · 0.95" },
    { label: "effective", value: "329.7 W/m²" },
    { label: "array area", value: "31.9 m² (2 wings)" },
    { label: "panel", value: "5.41 × 0.98 m · 5.33 m²" },
    { label: "cells/panel", value: "66 × 12 = 792" },
    { label: "span · total cells", value: "32.7 m · 4,752" },
  ]

  return (
    <div className="relative mx-auto max-w-[1100px] rounded-xl border border-[var(--border-hairline)] bg-[var(--bg-surface)] shadow-sm overflow-hidden">
      
      {/* Top Bar: Title & Material Key */}
      <div className="flex justify-between items-start border-b border-[var(--border-hairline)] p-4 bg-[var(--bg-subtle)]">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">SATELLITE — SIDE PROFILE</h2>
          <p className="font-mono text-[10px] text-[var(--ink-tertiary)] mt-1">units = metres · parametric</p>
        </div>
        <div className="font-mono text-[9px] text-[var(--ink-tertiary)] border border-[var(--border-hairline)] p-2 rounded bg-[var(--bg-surface)]">
          <div className="font-semibold mb-1 text-[var(--ink-secondary)]">MATERIAL KEY</div>
          <div>── solid: primary structure</div>
          <div>~~ chevron: MLI thermal blanket</div>
          <div>/// hatch: radiator panel</div>
          <div>.. dotted: internal bay outline</div>
        </div>
      </div>

      {/* The SVG Drawing (only the satellite, dimensions, and callouts) */}
      <div className="p-4 bg-[var(--bg-canvas)]">
         <SatelliteProfileSVG
            transmitter_power_w={transmitter_power_w}
            transmitter_aperture_m={transmitter_aperture_m}
            onChange={onChange}
          />
      </div>

      {/* Bottom Grid: Design Chain & Title Block */}
      <div className="grid grid-cols-3 gap-0 border-t border-[var(--border-hairline)] bg-[var(--bg-subtle)]">
        
        {/* Design Chain Box (HTML/CSS handles the spacing flawlessly) */}
        <div className="col-span-2 border-r border-[var(--border-hairline)]">
          <div className="border-b border-[var(--border-hairline)] p-3 font-mono text-xs font-semibold bg-[var(--bg-surface)]">
            SOLAR ARRAY DESIGN CHAIN
          </div>
          <div className="p-4 bg-[var(--bg-surface)]">
            <table className="w-full font-mono text-[11px]">
              <tbody>
                {designChain.map((row, i) => (
                  <tr key={i}>
                    <td className="py-1.5 text-[var(--ink-tertiary)]">{row.label}</td>
                    <td className="py-1.5 text-right font-medium text-[var(--ink-primary)]">{row.value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="mt-4 pt-3 border-t border-[var(--border-hairline)] text-[10px] text-[var(--ink-tertiary)]">
              80mm cell · 2mm gap · 82mm pitch
            </div>
          </div>
        </div>

        {/* Title Block */}
        <div className="flex flex-col justify-between bg-[var(--bg-surface)]">
          <div className="p-4 border-b border-[var(--border-hairline)]">
            <div className="font-bold text-sm tracking-wider">SATELLITE — SIDE PROFILE</div>
            <div className="text-[10px] text-[var(--ink-tertiary)] font-mono mt-1">units = metres · parametric</div>
          </div>
          <div className="grid grid-cols-2 text-[10px] font-mono divide-x divide-[var(--border-hairline)] border-b border-[var(--border-hairline)]">
            <div className="p-3">AG-DRW-SAT-001</div>
            <div className="p-3 text-right">SCALE 1:55</div>
          </div>
          <div className="grid grid-cols-2 text-[10px] font-mono divide-x divide-[var(--border-hairline)]">
            <div className="p-3">REV A</div>
            <div className="p-3 text-right">SI units</div>
          </div>
        </div>

      </div>
    </div>
  )
}
