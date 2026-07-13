import { useEffect, useMemo, useState } from 'react'
import { fetchTimeline } from './api'
import PriceChart from './components/PriceChart'
import KnowledgeGraph from './components/KnowledgeGraph'
import SelectedNodePanel from './components/SelectedNodePanel'
import DocumentViewer from './components/DocumentViewer'
import ChatPanel from './components/ChatPanel'
import Resizer from './components/Resizer'
import { formatMonth, formatPct } from './utils'
import { formatDocumentKind, formatDocumentLabel } from './documentLabels'

// Design 1d — "Decoder terminal": dark, dense; a chart spine + event ticker
// up top, then all three decoding stages (source doc, decoder chat,
// knowledge graph) visible at once side by side, instead of a stepper.
// Ported from the Claude Design prototype (Decoder Directions.dc.html,
// option #1d) onto this project's real backend and data model.

// An event can cite the same document across more than one evidence group
// (e.g. a chunk from the same 8-K backing two separate claims within the
// month) — dedupe by filename so it only ever appears once in the tab list.
function uniqueDocuments(evidence) {
  const seen = new Set()
  const docs = []
  for (const group of evidence || []) {
    for (const filename of group.documents || []) {
      if (!seen.has(filename)) {
        seen.add(filename)
        docs.push(filename)
      }
    }
  }
  return docs
}

function App() {
  const [months, setMonths] = useState(null)
  const [error, setError] = useState(null)
  const [selectedMonth, setSelectedMonth] = useState(null)
  const [selectedDocIndex, setSelectedDocIndex] = useState(0)
  const [graphSelection, setGraphSelection] = useState(null) // { type: 'node' | 'edge', id } | null

  // Every divider in the terminal is a draggable border — these track each
  // adjustable panel's size in px so the whole layout can be reshaped instead
  // of fixed to the design's original proportions.
  const [heroHeight, setHeroHeight] = useState(470) // chart + ticker + event header (headline + detail), above the panel row
  const [sourceWidth, setSourceWidth] = useState(330) // 01 · SOURCE column
  const [graphWidth, setGraphWidth] = useState(340) // 03 · GRAPH column (02 · DECODER fills what's left)
  const [graphDetailHeight, setGraphDetailHeight] = useState(170) // Selected node/relationship strip within the graph panel

  useEffect(() => {
    fetchTimeline()
      .then((data) => {
        setMonths(data.months)
        const firstEvent = data.months.find((m) => m.event)
        if (firstEvent) setSelectedMonth(firstEvent.month)
      })
      .catch((err) => setError(err.message))
  }, [])

  const selectedEntry = useMemo(
    () => months?.find((m) => m.month === selectedMonth) ?? null,
    [months, selectedMonth]
  )

  const eventMonths = useMemo(() => (months || []).filter((m) => m.event), [months])

  const lastPriced = useMemo(() => {
    if (!months) return null
    const priced = months.filter((m) => m.price)
    return priced.length > 0 ? priced[priced.length - 1] : null
  }, [months])

  function selectMonth(month) {
    setSelectedMonth(month)
    setSelectedDocIndex(0)
    setGraphSelection(null)
  }

  if (error) {
    return (
      <div className="term-page">
        <div className="term-boot-error">
          <p>Failed to fetch the timeline: {error}</p>
          <p className="muted">Make sure the backend is running: cd backend && uvicorn main:app --reload --port 8000</p>
        </div>
      </div>
    )
  }

  if (!months) {
    return (
      <div className="term-page">
        <div className="term-boot-error">
          <p>Booting decoder terminal…</p>
        </div>
      </div>
    )
  }

  const event = selectedEntry?.event ?? null
  const documents = event ? uniqueDocuments(event.evidence) : []
  const activeDoc = documents[selectedDocIndex] ?? documents[0] ?? null

  return (
    <div className="term-page">
      <div className="terminal">
        <header className="term-header">
          <div className="term-brand">
            <span className="term-logo">◆</span>
            <span className="term-title">DECODER TERMINAL</span>
            <span className="term-subtitle">/ PTON · PELOTON INTERACTIVE</span>
          </div>
          {lastPriced && (
            <div className="term-last">
              <span className="term-last-label">LAST</span>
              <span className="term-last-price">${lastPriced.price.close.toFixed(2)}</span>
              {lastPriced.price.pct_change != null && (
                <span className={lastPriced.price.pct_change >= 0 ? 'term-last-pct pos' : 'term-last-pct neg'}>
                  {lastPriced.price.pct_change >= 0 ? '▲' : '▼'} {Math.abs(lastPriced.price.pct_change).toFixed(1)}%
                </span>
              )}
            </div>
          )}
        </header>

        <div className="term-hero" style={{ height: heroHeight }}>
          <div className="term-chart">
            <PriceChart months={months} selectedMonth={selectedMonth} onSelectEvent={selectMonth} />
          </div>

          <div className="term-ticker">
            {eventMonths.map((m) => (
              <button
                key={m.month}
                type="button"
                className={m.month === selectedMonth ? 'term-tick term-tick-selected' : 'term-tick'}
                onClick={() => selectMonth(m.month)}
              >
                <span className="term-tick-date">{formatMonth(m.month)}</span>
                {m.price?.pct_change != null && (
                  <span className={m.price.pct_change >= 0 ? 'pct pct-pos' : 'pct pct-neg'}>
                    {formatPct(m.price.pct_change)}
                  </span>
                )}
              </button>
            ))}
          </div>

          {event && (
            <div className="term-event-header">
              <div className="term-event-meta">
                {formatMonth(selectedEntry.month)}
                {event.filing_dates?.length > 0 && ` · ${event.filing_dates.join(', ')}`}
                {selectedEntry.price?.close != null && ` · CLOSE $${selectedEntry.price.close.toFixed(2)}`}
              </div>
              <div className="term-event-headline">{event.headline}</div>
              {event.detail && <div className="term-event-detail">{event.detail}</div>}
            </div>
          )}
        </div>

        <Resizer axis="y" value={heroHeight} onChange={setHeroHeight} min={160} max={720} />

        {event ? (
          <div className="term-panels">
            <div className="term-panel" style={{ width: sourceWidth }}>
              <div className="term-panel-title">01 · SOURCE</div>
              {documents.length > 0 ? (
                <>
                  <div className="term-doc-tabs">
                    {documents.map((filename, i) => (
                      <button
                        key={filename}
                        type="button"
                        className={i === selectedDocIndex ? 'term-doc-tab term-doc-tab-active' : 'term-doc-tab'}
                        onClick={() => setSelectedDocIndex(i)}
                        title={formatDocumentLabel(filename)}
                      >
                        {formatDocumentKind(filename)}
                      </button>
                    ))}
                  </div>
                  <DocumentViewer filename={activeDoc} label={formatDocumentLabel(activeDoc)} />
                </>
              ) : (
                <p className="muted">No source documents for this event.</p>
              )}
            </div>

            <Resizer axis="x" value={sourceWidth} onChange={setSourceWidth} min={200} max={640} />

            <div className="term-panel term-panel-decoder">
              <div className="term-panel-title term-panel-title-accent">02 · DECODER</div>
              <ChatPanel />
            </div>

            <Resizer axis="x" value={graphWidth} onChange={setGraphWidth} min={220} max={640} invert />

            <div className="term-panel" style={{ width: graphWidth }}>
              <div className="term-panel-title">03 · GRAPH</div>
              {event.knowledge_graph?.nodes?.length > 0 ? (
                <>
                  <div className="term-graph-canvas">
                    <KnowledgeGraph
                      graph={event.knowledge_graph}
                      selectedNodeId={graphSelection?.type === 'node' ? graphSelection.id : null}
                      selectedEdgeId={graphSelection?.type === 'edge' ? graphSelection.id : null}
                      onSelectNode={(id) => setGraphSelection(id ? { type: 'node', id } : null)}
                      onSelectEdge={(id) => setGraphSelection(id ? { type: 'edge', id } : null)}
                    />
                  </div>

                  <Resizer axis="y" value={graphDetailHeight} onChange={setGraphDetailHeight} min={60} max={480} invert />

                  <div className="term-graph-detail" style={{ height: graphDetailHeight }}>
                    <SelectedNodePanel
                      graph={event.knowledge_graph}
                      selectedNodeId={graphSelection?.type === 'node' ? graphSelection.id : null}
                      selectedEdgeId={graphSelection?.type === 'edge' ? graphSelection.id : null}
                    />
                  </div>
                </>
              ) : (
                <p className="muted">No knowledge graph available for this event's documents.</p>
              )}
            </div>
          </div>
        ) : (
          <p className="muted term-no-event">Select a filing on the chart or ticker above to decode it.</p>
        )}
      </div>
    </div>
  )
}

export default App
