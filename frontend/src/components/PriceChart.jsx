import { useRef, useState } from 'react'
import { formatMonth, formatPct } from '../utils'

// Area chart — line + soft gradient fill, log-scaled y-axis. PTON went from
// $149 to under $10 and stayed there for years; on a linear axis that whole
// stretch (3 of our 5 events) compresses into a sliver near the bottom. Log
// scale makes equal percentage moves look equally significant regardless of
// the price level they happened at.
const W = 900
const H = 450
const PAD_L = 50
const PAD_R = 12
const PAD_T = 16
const PAD_B = 34

const INNER_W = W - PAD_L - PAD_R
const INNER_H = H - PAD_T - PAD_B
const BASELINE_Y = PAD_T + INNER_H

// Approx rendered height (px) of .chart-tooltip, plus its 10px gap off the
// point — if the hovered point sits closer to the top of the chart than
// this, the default above-point placement would push the tooltip past the
// container edge and get clipped, so we flip it below the point instead.
const TOOLTIP_FLIP_MARGIN_PX = 72

// "1-2-5" tick sequence, the standard pattern for log-scale axes — roughly
// even spacing in log space, round-looking numbers. Returns ticks strictly
// between min/max; the exact min/max are labeled separately.
function logTicks(min, max) {
  const ticks = []
  const magStart = Math.floor(Math.log10(min))
  const magEnd = Math.ceil(Math.log10(max))
  for (let mag = magStart; mag <= magEnd; mag++) {
    for (const mult of [1, 2, 5]) {
      const v = mult * 10 ** mag
      if (v > min && v < max) ticks.push(v)
    }
  }
  return ticks
}

// Evenly spaced month indices for x-axis ticks, always including the first
// and last month regardless of how the spacing lands.
function xTickIndices(n, target = 7) {
  if (n <= 1) return [0]
  const step = Math.max(1, Math.round((n - 1) / (target - 1)))
  const indices = []
  for (let i = 0; i < n; i += step) indices.push(i)
  if (indices[indices.length - 1] !== n - 1) indices.push(n - 1)
  return indices
}

// months: full /api/timeline months array (already range-sliced by the caller)
// selectedMonth: "YYYY-MM" of the currently open event, or null
// onSelectEvent: (month) => void — only called for months that have an event
export default function PriceChart({ months, selectedMonth, onSelectEvent }) {
  const svgRef = useRef(null)
  const [hoverIndex, setHoverIndex] = useState(null)
  const [containerH, setContainerH] = useState(0)

  const priced = months.filter((m) => m.price)
  if (priced.length === 0) {
    return <p className="muted">No price data in this range.</p>
  }

  const closes = priced.map((m) => m.price.close)
  const minP = Math.min(...closes)
  const maxP = Math.max(...closes)
  const logMin = Math.log(minP)
  const logMax = Math.log(maxP)
  const midTicks = logMin < logMax ? logTicks(minP, maxP) : []

  const slot = INNER_W / priced.length
  const xFor = (i) => PAD_L + slot * i + slot / 2
  const yFor = (p) => (logMax > logMin ? BASELINE_Y - ((Math.log(p) - logMin) / (logMax - logMin)) * INNER_H : BASELINE_Y - INNER_H / 2)

  const xTicks = xTickIndices(priced.length)
  const linePoints = priced.map((m, i) => `${xFor(i)},${yFor(m.price.close)}`)
  const areaPath =
    `M ${linePoints[0]} L ${linePoints.join(' L ')} ` +
    `L ${xFor(priced.length - 1)},${BASELINE_Y} L ${xFor(0)},${BASELINE_Y} Z`

  // Continuous cursor tracking, snapped to the nearest real month — this is
  // monthly data, so interpolating a value "between" two points would be
  // fabricated. getBoundingClientRect + preserveAspectRatio="none" on the svg
  // keeps this linear regardless of the svg's fluid rendered width.
  function handleMouseMove(e) {
    const rect = svgRef.current.getBoundingClientRect()
    const svgX = ((e.clientX - rect.left) / rect.width) * W
    const idx = Math.min(priced.length - 1, Math.max(0, Math.floor((svgX - PAD_L) / slot)))
    setHoverIndex(idx)
    setContainerH(rect.height)
  }

  function handleMouseLeave() {
    setHoverIndex(null)
  }

  const hovered = hoverIndex != null ? priced[hoverIndex] : null
  const hoverX = hovered ? xFor(hoverIndex) : null
  const hoverY = hovered ? yFor(hovered.price.close) : null
  const hoverPxFromTop = hovered && containerH ? (hoverY / H) * containerH : null
  const flipTooltipBelow = hoverPxFromTop != null && hoverPxFromTop < TOOLTIP_FLIP_MARGIN_PX

  return (
    <div className="chart-wrap">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        className="price-chart"
        role="img"
        aria-label="Peloton monthly closing price on a log scale, with filing events marked"
      >
        <defs>
          <linearGradient id="areaGradient" gradientUnits="userSpaceOnUse" x1="0" y1={PAD_T} x2="0" y2={BASELINE_Y}>
            <stop offset="0%" stopColor="#8fd4c0" stopOpacity="0.28" />
            <stop offset="100%" stopColor="#8fd4c0" stopOpacity="0" />
          </linearGradient>
        </defs>

        {midTicks.map((t) => (
          <line key={t} x1={PAD_L} y1={yFor(t)} x2={PAD_L + INNER_W} y2={yFor(t)} className="gridline" />
        ))}

        <line x1={PAD_L} y1={PAD_T} x2={PAD_L} y2={BASELINE_Y} className="axis-line" />
        <line x1={PAD_L} y1={BASELINE_Y} x2={PAD_L + INNER_W} y2={BASELINE_Y} className="axis-line" />

        {/* invisible full-height hit target */}
        <rect x={PAD_L} y={PAD_T} width={INNER_W} height={INNER_H} fill="transparent" onMouseMove={handleMouseMove} onMouseLeave={handleMouseLeave} />

        <path d={areaPath} className="area-fill" />
        <polyline points={linePoints.join(' ')} className="price-line" />

        {/* Hover always shows real direction (green/red) regardless of the
            static blue "this is a filing event" styling underneath it — for
            a non-event month there's no dot at all until you hover it. */}
        {hoverX != null && !hovered.event && (
          <>
            <line x1={hoverX} y1={PAD_T} x2={hoverX} y2={BASELINE_Y} className="crosshair-line" />
            <circle
              cx={hoverX}
              cy={hoverY}
              r={4}
              className={hovered.price.pct_change == null ? 'hover-dot' : hovered.price.pct_change >= 0 ? 'hover-dot-pos' : 'hover-dot-neg'}
            />
          </>
        )}
        {hoverX != null && hovered.event && <line x1={hoverX} y1={PAD_T} x2={hoverX} y2={BASELINE_Y} className="crosshair-line" />}

        {priced.map((m, i) => {
          if (!m.event) return null
          const isHovered = i === hoverIndex
          const isSelected = m.month === selectedMonth
          let cls = 'event-dot'
          if (isHovered && m.price.pct_change != null) cls = m.price.pct_change >= 0 ? 'event-dot-pos' : 'event-dot-neg'
          else if (isSelected) cls = 'event-dot event-dot-selected'
          return (
            <circle
              key={m.month}
              cx={xFor(i)}
              cy={yFor(m.price.close)}
              r={isSelected ? 7 : isHovered ? 6 : 5}
              className={cls}
              onMouseMove={handleMouseMove}
              onMouseLeave={handleMouseLeave}
              onClick={() => onSelectEvent(m.month)}
            >
              <title>{formatMonth(m.month)}</title>
            </circle>
          )
        })}
      </svg>

      {/* Real HTML text, positioned at the same %-based coordinates as the
          SVG plot — see the .chart-axis-labels CSS comment for why these
          aren't <text> elements inside the (non-uniformly scaled) SVG. */}
      <div className="chart-axis-labels">
        {midTicks.map((t) => (
          <span key={t} className="chart-axis-label chart-axis-label-y" style={{ top: `${(yFor(t) / H) * 100}%` }}>
            ${t}
          </span>
        ))}
        <span className="chart-axis-label chart-axis-label-y-top" style={{ top: `${(PAD_T / H) * 100}%` }}>
          ${Math.round(maxP)}
        </span>
        <span className="chart-axis-label chart-axis-label-y-bottom" style={{ top: `${(BASELINE_Y / H) * 100}%` }}>
          ${Math.round(minP)}
        </span>

        {xTicks.map((i, idx) => {
          const isFirst = idx === 0
          const isLast = idx === xTicks.length - 1
          const anchorCls = isLast ? 'chart-axis-label-x-end' : isFirst ? 'chart-axis-label-x-start' : 'chart-axis-label-x-middle'
          return (
            <span
              key={priced[i].month}
              className={`chart-axis-label ${anchorCls}`}
              style={{ left: `${(xFor(i) / W) * 100}%` }}
            >
              {formatMonth(priced[i].month)}
            </span>
          )
        })}
      </div>

      {hovered && (
        <div
          className={flipTooltipBelow ? 'chart-tooltip chart-tooltip-below' : 'chart-tooltip'}
          style={{ left: `${(hoverX / W) * 100}%`, top: `${(hoverY / H) * 100}%` }}
        >
          <p className="tooltip-month">{formatMonth(hovered.month)}</p>
          <p className="tooltip-price">${hovered.price.close.toFixed(2)}</p>
          {hovered.price.pct_change != null && (
            <p className={hovered.price.pct_change >= 0 ? 'pct pct-pos' : 'pct pct-neg'}>
              {formatPct(hovered.price.pct_change)}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
