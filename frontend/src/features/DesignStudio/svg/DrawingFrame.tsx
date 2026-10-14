/**
 * DrawingFrame — the border, datum markers, and title block that turn
 * a collection of shapes into a drawing.
 *
 * Real aerospace drawings have four components a reader uses to trust
 * the figure:
 *
 *   1. An outer heavy border and an inner hairline border, offset.
 *   2. Corner datum letters (A/B on the vertical edges, 1/2 on the
 *      horizontal) so features can be referenced by zone.
 *   3. Grid tick marks along the border at fixed intervals.
 *   4. A title block in the lower-right with title, drawing number,
 *      scale, revision, and any caller-supplied metadata line.
 *
 * The frame is drawn inside the caller's viewBox. Everything is
 * stroke-based and uses the app's existing token palette, so it
 * themes correctly in light and dark.
 *
 * The caller supplies the four content fields (title, drawing number,
 * scale label, revision) and an optional footnote (used to record the
 * one assumption that governs the drawing). All of it is text, not
 * icons, so no real satellite, aircraft, manufacturer, or programme
 * is named.
 */

import type { ReactElement, ReactNode } from "react"

export type DrawingFrameProps = {
  /** Total viewBox the frame spans. */
  x: number
  y: number
  width: number
  height: number
  /** Title line for the title block. */
  title: string
  /** Drawing number (e.g. "AG-DRW-001"). */
  drawingNumber: string
  /** Scale label (e.g. "scale 1:1000"). */
  scaleLabel: string
  /** Revision letter or number. */
  revision: string
  /** Optional note printed under the title (one line). */
  note?: string
  /** Optional footnote printed just above the title block. */
  footnote?: string
  /** Content children, in the same viewBox coordinate system. */
  children: ReactNode
}

export function DrawingFrame({
  x,
  y,
  width,
  height,
  title,
  drawingNumber,
  scaleLabel,
  revision,
  note,
  footnote,
  children,
}: DrawingFrameProps): ReactElement {
  // Frame strokes: heavy outer, hairline inner.
  const SW_OUTER = Math.max(width, height) * 0.0014
  const SW_INNER = SW_OUTER * 0.4
  const SW_TICK = SW_OUTER * 0.35
  const SW_HAIR = SW_OUTER * 0.22
  const FS_TITLE = Math.max(width, height) * 0.016
  const FS_SMALL = FS_TITLE * 0.68
  const FS_MICRO = FS_TITLE * 0.55

  const outerInset = Math.max(width, height) * 0.012
  const innerInset = outerInset * 2.2

  const ox = x + outerInset
  const oy = y + outerInset
  const ow = width - 2 * outerInset
  const oh = height - 2 * outerInset

  const ix = ox + (innerInset - outerInset)
  const iy = oy + (innerInset - outerInset)
  const iw = width - 2 * innerInset
  const ih = height - 2 * innerInset

  // Title block: 30% width, 22% height, bottom-right, inside inner border.
  const tbW = iw * 0.30
  const tbH = ih * 0.24
  const tbX = ix + iw - tbW
  const tbY = iy + ih - tbH

  // Grid ticks: number determined by the drawing size.
  const nTicksX = 8
  const nTicksY = 6
  const tickLen = SW_TICK * 4

  // Zone letters on the outer border.
  const zonesY = ["A", "B", "C", "D"]
  const zonesX = ["1", "2", "3", "4"]

  return (
    <g>
      <defs>
        <clipPath id={`frame-content-clip-${drawingNumber}`}>
          <rect x={ix} y={iy} width={iw} height={ih} />
        </clipPath>
      </defs>

      {/* Outer border */}
      <rect
        x={ox}
        y={oy}
        width={ow}
        height={oh}
        fill="none"
        stroke="var(--ink-primary)"
        strokeWidth={SW_OUTER}
      />
      {/* Inner border */}
      <rect
        x={ix}
        y={iy}
        width={iw}
        height={ih}
        fill="none"
        stroke="var(--ink-secondary)"
        strokeWidth={SW_INNER}
      />

      {/* Tick marks along the top and bottom */}
      {Array.from({ length: nTicksX - 1 }).map((_, i) => {
        const tx = ix + ((i + 1) * iw) / nTicksX
        return (
          <g key={`tx${i}`}>
            <line x1={tx} y1={oy} x2={tx} y2={oy + tickLen} stroke="var(--ink-secondary)" strokeWidth={SW_TICK} />
            <line
              x1={tx}
              y1={oy + oh - tickLen}
              x2={tx}
              y2={oy + oh}
              stroke="var(--ink-secondary)"
              strokeWidth={SW_TICK}
            />
          </g>
        )
      })}
      {/* Tick marks along the left and right */}
      {Array.from({ length: nTicksY - 1 }).map((_, i) => {
        const ty = iy + ((i + 1) * ih) / nTicksY
        return (
          <g key={`ty${i}`}>
            <line x1={ox} y1={ty} x2={ox + tickLen} y2={ty} stroke="var(--ink-secondary)" strokeWidth={SW_TICK} />
            <line
              x1={ox + ow - tickLen}
              y1={ty}
              x2={ox + ow}
              y2={ty}
              stroke="var(--ink-secondary)"
              strokeWidth={SW_TICK}
            />
          </g>
        )
      })}

      {/* Corner zone letters (vertical edges) */}
      {zonesY.map((z, i) => {
        const cy = iy + ((i + 0.5) * ih) / zonesY.length
        return (
          <g key={z}>
            <text
              x={ox + (innerInset - outerInset) * 0.5}
              y={cy}
              textAnchor="middle"
              dominantBaseline="middle"
              fontFamily="ui-monospace, monospace"
              fontSize={FS_SMALL}
              fill="var(--ink-tertiary)"
            >
              {z}
            </text>
            <text
              x={ox + ow - (innerInset - outerInset) * 0.5}
              y={cy}
              textAnchor="middle"
              dominantBaseline="middle"
              fontFamily="ui-monospace, monospace"
              fontSize={FS_SMALL}
              fill="var(--ink-tertiary)"
            >
              {z}
            </text>
          </g>
        )
      })}
      {/* Corner zone numbers (horizontal edges) */}
      {zonesX.map((z, i) => {
        const cx = ix + ((i + 0.5) * iw) / zonesX.length
        return (
          <g key={z}>
            <text
              x={cx}
              y={oy + (innerInset - outerInset) * 0.5 + FS_SMALL * 0.3}
              textAnchor="middle"
              fontFamily="ui-monospace, monospace"
              fontSize={FS_SMALL}
              fill="var(--ink-tertiary)"
            >
              {z}
            </text>
            <text
              x={cx}
              y={oy + oh - (innerInset - outerInset) * 0.5 + FS_SMALL * 0.3}
              textAnchor="middle"
              fontFamily="ui-monospace, monospace"
              fontSize={FS_SMALL}
              fill="var(--ink-tertiary)"
            >
              {z}
            </text>
          </g>
        )
      })}

      {/* Content, clipped to the inner frame */}
      <g clipPath={`url(#frame-content-clip-${drawingNumber})`}>{children}</g>

      {/* Title block (drawn last, on top of content) */}
      <g>
        <rect
          x={tbX}
          y={tbY}
          width={tbW}
          height={tbH}
          fill="var(--bg-surface)"
          stroke="var(--ink-primary)"
          strokeWidth={SW_INNER}
        />
        {/* Divider lines: three rows. Row 1 = title, row 2 = number + scale, row 3 = revision + date. */}
        <line
          x1={tbX}
          y1={tbY + tbH * 0.40}
          x2={tbX + tbW}
          y2={tbY + tbH * 0.40}
          stroke="var(--ink-secondary)"
          strokeWidth={SW_HAIR}
        />
        <line
          x1={tbX}
          y1={tbY + tbH * 0.72}
          x2={tbX + tbW}
          y2={tbY + tbH * 0.72}
          stroke="var(--ink-secondary)"
          strokeWidth={SW_HAIR}
        />
        <line
          x1={tbX + tbW * 0.55}
          y1={tbY + tbH * 0.40}
          x2={tbX + tbW * 0.55}
          y2={tbY + tbH}
          stroke="var(--ink-secondary)"
          strokeWidth={SW_HAIR}
        />

        <text
          x={tbX + tbW * 0.03}
          y={tbY + tbH * 0.22}
          fontFamily="ui-monospace, monospace"
          fontSize={FS_TITLE}
          fontWeight={600}
          fill="var(--ink-primary)"
        >
          {title}
        </text>
        {note && (
          <text
            x={tbX + tbW * 0.03}
            y={tbY + tbH * 0.35}
            fontFamily="ui-monospace, monospace"
            fontSize={FS_MICRO}
            fill="var(--ink-tertiary)"
          >
            {note}
          </text>
        )}

        <text
          x={tbX + tbW * 0.03}
          y={tbY + tbH * 0.57}
          fontFamily="ui-monospace, monospace"
          fontSize={FS_SMALL}
          fill="var(--ink-secondary)"
        >
          {drawingNumber}
        </text>
        <text
          x={tbX + tbW * 0.58}
          y={tbY + tbH * 0.57}
          fontFamily="ui-monospace, monospace"
          fontSize={FS_SMALL}
          fill="var(--ink-secondary)"
        >
          {scaleLabel}
        </text>

        <text
          x={tbX + tbW * 0.03}
          y={tbY + tbH * 0.90}
          fontFamily="ui-monospace, monospace"
          fontSize={FS_SMALL}
          fill="var(--ink-secondary)"
        >
          REV {revision}
        </text>
        <text
          x={tbX + tbW * 0.58}
          y={tbY + tbH * 0.90}
          fontFamily="ui-monospace, monospace"
          fontSize={FS_SMALL}
          fill="var(--ink-secondary)"
        >
          SI units
        </text>
      </g>

      {/* Footnote line just above the title block, left-aligned to inner frame */}
      {footnote && (
        <text
          x={ix + FS_MICRO * 0.6}
          y={tbY - FS_MICRO * 0.6}
          fontFamily="ui-monospace, monospace"
          fontSize={FS_MICRO}
          fill="var(--ink-tertiary)"
        >
          {footnote}
        </text>
      )}
    </g>
  )
}
