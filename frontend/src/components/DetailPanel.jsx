import { useState } from 'react'
import DocumentViewer from './DocumentViewer'
import KnowledgeGraphSection from './KnowledgeGraphSection'
import { formatMonth, formatPct } from '../utils'
import { formatDocumentLabel } from '../documentLabels'

// monthEntry: one full entry from /api/timeline's months array, must have .event
// onAskAgent: (question:string) => void — opens the shared decoder chat with a
// scoped starter question (the stage-3 hand-off).
export default function DetailPanel({ monthEntry, onAskAgent }) {
  if (!monthEntry || !monthEntry.event) {
    return <p className="muted">Select a filing above to see what happened.</p>
  }

  const { event, price } = monthEntry
  const documents = uniqueDocuments(event.evidence)
  // Reference the headline so the orchestrator scopes to this event (the
  // headline carries the distinguishing terms, e.g. "CFO transition").
  const seedQuestion = `${event.headline} Explain what happened here and how the story changed.`

  return (
    <div className="detail-card">
      <p className="detail-meta">
        {formatMonth(monthEntry.month)}
        {event.filing_dates?.length > 0 && ` · ${event.filing_dates.join(', ')}`}
        {price?.pct_change != null && (
          <span className={price.pct_change >= 0 ? 'pct pct-pos' : 'pct pct-neg'}>
            {' '}
            {formatPct(price.pct_change)}
          </span>
        )}
      </p>
      <p className="detail-headline">{event.headline}</p>
      <p className="detail-body">{event.detail}</p>

      {documents.length > 0 && (
        <div className="evidence">
          <DecodePanel
            documents={documents}
            graph={event.knowledge_graph}
            onAskAgent={onAskAgent ? () => onAskAgent(seedQuestion) : null}
          />
        </div>
      )}
    </div>
  )
}

// An event can cite the same document across more than one evidence group
// (e.g. a chunk from the same 8-K backing two separate claims within the
// month) — dedupe by filename so it only ever appears once in the list.
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

// One decode control per event, regardless of how many documents or filing
// dates it cites. Starts collapsed — "Click to decode" reveals the source
// document(s). When there's more than one, a dropdown (labeled with the
// filing date so same-type documents filed days apart stay distinguishable)
// picks which one shows in the viewer below, one at a time, PDF-viewer style.
// The knowledge graph lives inside this same collapsed/expanded state too —
// it only renders once decoded, directly below the document viewer, instead
// of always showing regardless of whether the documents panel is open.
function DecodePanel({ documents, graph, onAskAgent }) {
  const [open, setOpen] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(0)

  return (
    <div className="evidence-group">
      <button type="button" className="decode-btn" onClick={() => setOpen((o) => !o)}>
        {open ? 'Hide' : 'Click to decode →'}
      </button>

      {open && (
        <div className="doc-window">
          <p className="decode-step-label">1 · Source document</p>
          {documents.length > 1 && (
            <select
              className="doc-select"
              value={selectedIndex}
              onChange={(e) => setSelectedIndex(Number(e.target.value))}
            >
              {documents.map((filename, i) => (
                <option key={filename} value={i}>
                  Document {i + 1}: {formatDocumentLabel(filename)}
                </option>
              ))}
            </select>
          )}
          <DocumentViewer
            filename={documents[selectedIndex]}
            label={formatDocumentLabel(documents[selectedIndex])}
          />

          <p className="decode-step-label">2 · Knowledge graph</p>
          <KnowledgeGraphSection graph={graph} />

          {onAskAgent && (
            <div className="decode-step3">
              <p className="decode-step-label">3 · Decode with the agent</p>
              <p className="muted decode-step3-hint">
                Hand this event to the decoder to explain it, connect it to the rest of the story,
                or compare it with other events.
              </p>
              <button type="button" className="btn btn-active decode-agent-btn" onClick={onAskAgent}>
                Decode with the agent →
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
