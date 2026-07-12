import DetailPanel from './DetailPanel'

// months: full /api/timeline array — renders every event month, in order,
// with no chart at all. Read-the-narrative mode.
export default function StoryView({ months }) {
  const eventMonths = months.filter((m) => m.event)

  if (eventMonths.length === 0) {
    return <p className="muted">No filing events found.</p>
  }

  return (
    <div className="story-list">
      {eventMonths.map((m) => (
        <DetailPanel key={m.month} monthEntry={m} />
      ))}
    </div>
  )
}
