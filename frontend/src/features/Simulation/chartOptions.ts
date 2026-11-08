/**
 * ECharts option builders for the simulation panels.
 * Pure functions: no React. Read CSS custom properties at call time
 * so light/dark theme switches flow through.
 */

import type { EChartsOption } from "echarts"
import type { SimulationSample } from "./simulationApi"

const UAV_COLORS = [
  "#007aff", "#34c759", "#ff9500", "#ff3b30",
  "#5856d6", "#af52de", "#ff2d55", "#5ac8fa",
]

function uavColor(id: number): string {
  return UAV_COLORS[id % UAV_COLORS.length]
}

function readCssVar(name: string, fallback: string): string {
  if (typeof window === "undefined" || typeof document === "undefined") return fallback
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}

type Palette = {
  ink: string
  inkSecondary: string
  inkTertiary: string
  border: string
  surface: string
}

function palette(): Palette {
  return {
    ink: readCssVar("--ink-primary", "#1d1d1f"),
    inkSecondary: readCssVar("--ink-secondary", "#6e6e73"),
    inkTertiary: readCssVar("--ink-tertiary", "#86868b"),
    border: readCssVar("--border-hairline", "rgba(60,60,67,0.13)"),
    surface: readCssVar("--bg-surface", "#ffffff"),
  }
}

function axisCommon(name: string, p: Palette) {
  return {
    type: "value" as const,
    name,
    nameLocation: "middle" as const,
    nameGap: 24,
    nameTextStyle: { color: p.inkTertiary, fontSize: 10 },
    axisLine: { lineStyle: { color: p.border } },
    axisLabel: { color: p.inkTertiary, fontSize: 10 },
    splitLine: { lineStyle: { color: p.border, type: "dashed" as const } },
  }
}

function base(p: Palette): EChartsOption {
  return {
    backgroundColor: p.surface,
    textStyle: { fontFamily: "ui-sans-serif, -apple-system, system-ui", color: p.inkSecondary },
    grid: { left: 60, right: 24, top: 40, bottom: 40 },
    legend: {
      top: 8,
      textStyle: { color: p.inkSecondary, fontSize: 11 },
      icon: "roundRect",
      itemWidth: 10,
      itemHeight: 10,
    },
    tooltip: {
      trigger: "axis",
      backgroundColor: p.surface,
      borderColor: p.border,
      textStyle: { color: p.ink, fontSize: 11 },
    },
  }
}

export function perUavPowerOption(
  samples: SimulationSample[],
  field: "received_power_w" | "delivered_power_w",
  yAxisLabel: string,
): EChartsOption {
  const p = palette()
  const nUavs = samples[0]?.uavs.length ?? 0
  const series = Array.from({ length: nUavs }, (_, i) => ({
    name: `UAV-${i}`,
    type: "line" as const,
    smooth: true,
    showSymbol: false,
    lineStyle: { width: 1.5, color: uavColor(i) },
    itemStyle: { color: uavColor(i) },
    data: samples.map((s) => s.uavs[i]?.[field] ?? 0),
  }))
  return {
    ...base(p),
    xAxis: axisCommon("elapsed (s)", p),
    yAxis: axisCommon(yAxisLabel, p),
    series,
  }
}

export function aggregateOption(
  samples: SimulationSample[],
  field: "delivered_power_w" | "cumulative_energy_j" | "atmospheric_transmittance" | "satellite_elevation_deg",
  yAxisLabel: string,
  areaFill: boolean,
): EChartsOption {
  const p = palette()
  return {
    ...base(p),
    xAxis: axisCommon("elapsed (s)", p),
    yAxis: axisCommon(yAxisLabel, p),
    series: [
      {
        name: yAxisLabel,
        type: "line" as const,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: "#007aff" },
        itemStyle: { color: "#007aff" },
        areaStyle: areaFill ? { color: "rgba(0,122,255,0.15)" } : undefined,
        data: samples.map((s) => s[field]),
      },
    ],
  }
}


/**
 * Per-hop delivered power. Only meaningful when the simulation used a
 * multi-hop relay topology (at least one UAV has relay_hop_index >= 0).
 * X = hop index, Y = average delivered power across samples for that hop.
 * Returns null when no relay data is present, so the caller can skip the
 * chart entirely in direct mode.
 */
export function perHopPowerOption(
  samples: SimulationSample[],
): EChartsOption | null {
  const hopSum: Record<number, number> = {}
  const hopCount: Record<number, number> = {}
  for (const s of samples) {
    for (const u of s.uavs) {
      const h = u.relay_hop_index
      if (h < 0) continue
      hopSum[h] = (hopSum[h] ?? 0) + u.delivered_power_w
      hopCount[h] = (hopCount[h] ?? 0) + 1
    }
  }
  const hops = Object.keys(hopSum).map(Number).sort((a, b) => a - b)
  if (hops.length === 0) return null

  const p = palette()
  const ys = hops.map((h) => hopSum[h] / Math.max(1, hopCount[h]))
  return {
    ...base(p),
    xAxis: axisCommon("hop", p),
    yAxis: axisCommon("avg delivered (W)", p),
    series: [
      {
        name: "Delivered per hop",
        type: "line" as const,
        smooth: false,
        showSymbol: true,
        lineStyle: { width: 2, color: "#af52de" },
        itemStyle: { color: "#af52de" },
        data: ys,
      },
    ],
  }
}
