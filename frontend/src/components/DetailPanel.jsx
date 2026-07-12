import { useState } from 'react'
import DocumentViewer from './DocumentViewer'
import KnowledgeGraphSection from './KnowledgeGraphSection'
import { formatMonth, formatPct } from '../utils'
import { formatDocumentLabel } from '../documentLabels'

// monthEntry: one full entry from /api/timeline's months array, must have .event
export default function DetailPanel({ monthEntry }) {
  if (!monthEntry || !monthEntry.event) {
    return <p className="muted">Select a filing above to see what happened.</p>
  }

  const { event, price } = monthEntry
  const documents = uniqueDocuments(event.evidence)

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
          <DecodePanel documents={documents} />
        </div>
      )}

      <KnowledgeGraphSection graph={event.knowledge_graph} />
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
function DecodePanel({ documents }) {
  const [open, setOpen] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(0)

  return (
    <div className="evidence-group">
      <button type="button" className="decode-btn" onClick={() => setOpen((o) => !o)}>
        {open ? 'Hide' : 'Click to decode →'}
      </button>

      {open && (
        <div className="doc-window">
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
        </div>
      )}
    </div>
  )
}
