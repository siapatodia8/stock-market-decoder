import { formatMonth, formatPct } from '../utils'

// months: full /api/timeline array — filters to event months itself, so the
// pill list always reflects everything available regardless of chart range.
export default function EventPills({ months, selectedMonth, onSelect }) {
  const eventMonths = months.filter((m) => m.event)

  if (eventMonths.length === 0) {
    return <p className="muted">No filing events found.</p>
  }

  return (
    <div className="pill-row">
      {eventMonths.map((m) => (
        <button
          key={m.month}
          type="button"
          className={m.month === selectedMonth ? 'pill pill-active' : 'pill'}
          onClick={() => onSelect(m.month)}
        >
          {formatMonth(m.month)}
          {m.price?.pct_change != null && (
            <span className={m.price.pct_change >= 0 ? 'pct pct-pos' : 'pct pct-neg'}>
              {' '}
              {formatPct(m.price.pct_change)}
            </span>
          )}
        </button>
      ))}
    </div>
  )
}
