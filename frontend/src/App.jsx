import { useEffect, useMemo, useState } from 'react'
import { fetchTimeline } from './api'
import PriceChart from './components/PriceChart'
import EventPills from './components/EventPills'
import DetailPanel from './components/DetailPanel'
import StoryView from './components/StoryView'

const RANGES = [
  { key: '1', label: '1Y' },
  { key: '2', label: '2Y' },
  { key: '3', label: '3Y' },
  { key: 'all', label: 'All' },
]

function App() {
  const [months, setMonths] = useState(null)
  const [error, setError] = useState(null)
  const [view, setView] = useState('chart')
  const [range, setRange] = useState('all')
  const [selectedMonth, setSelectedMonth] = useState(null)

  useEffect(() => {
    fetchTimeline()
      .then((data) => {
        setMonths(data.months)
        const firstEvent = data.months.find((m) => m.event)
        if (firstEvent) setSelectedMonth(firstEvent.month)
      })
      .catch((err) => setError(err.message))
  }, [])

  const visibleMonths = useMemo(() => {
    if (!months) return []
    if (range === 'all') return months
    const n = Number(range) * 12
    return months.slice(-n)
  }, [months, range])

  const selectedEntry = useMemo(
    () => months?.find((m) => m.month === selectedMonth) ?? null,
    [months, selectedMonth]
  )

  if (error) {
    return (
      <div className="page">
        <p>Failed to fetch the timeline: {error}</p>
        <p className="muted">Make sure the backend is running: cd backend && uvicorn main:app --reload --port 8000</p>
      </div>
    )
  }

  if (!months) {
    return <div className="page"><p>Loading timeline...</p></div>
  }

  return (
    <div className="page">
      <h1>Stock Market Decoder</h1>

      <div className="toggle-row">
        <div className="toggle-group">
          <button type="button" className={view === 'chart' ? 'btn btn-active' : 'btn'} onClick={() => setView('chart')}>
            Chart view
          </button>
          <button type="button" className={view === 'story' ? 'btn btn-active' : 'btn'} onClick={() => setView('story')}>
            Story view
          </button>
        </div>
        {view === 'chart' && (
          <div className="toggle-group">
            {RANGES.map((r) => (
              <button
                key={r.key}
                type="button"
                className={range === r.key ? 'btn btn-active' : 'btn'}
                onClick={() => setRange(r.key)}
              >
                {r.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {view === 'chart' ? (
        <>
          <PriceChart months={visibleMonths} selectedMonth={selectedMonth} onSelectEvent={setSelectedMonth} />
          <p className="legend">
            <span><span className="legend-dot legend-dot-muted" />monthly close</span>
            <span><span className="legend-dot legend-dot-accent" />filing event</span>
          </p>
          <p className="section-label">Jump to filing</p>
          <EventPills months={months} selectedMonth={selectedMonth} onSelect={setSelectedMonth} />
          <DetailPanel monthEntry={selectedEntry} />
        </>
      ) : (
        <StoryView months={months} />
      )}
    </div>
  )
}

export default App
