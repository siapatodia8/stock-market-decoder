// month is "YYYY-MM" as returned by /api/timeline
export function formatMonth(month) {
  const [y, m] = month.split('-').map(Number)
  return new Date(y, m - 1, 1).toLocaleString('en-US', { month: 'short', year: 'numeric' })
}

export function formatPct(pct) {
  if (pct == null) return null
  const sign = pct > 0 ? '+' : ''
  return `${sign}${pct.toFixed(1)}%`
}
