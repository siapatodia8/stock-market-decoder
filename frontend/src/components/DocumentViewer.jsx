import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { fetchDocument, fetchHighlight } from '../api'

// filename: e.g. "peloton_2020-12-21_8k.md" — fetches and renders the real
// full source document, not just the fragment(s) that were retrieved as
// evidence.
// label: human-readable display name (e.g. "Peloton – Form 8-K"); falls
// back to the raw filename if not given.
// highlightChunkText (optional): the specific retrieved chunk's raw text to
// locate and visually mark within the full document, via backend/highlight.py
// (app-side text matching — no HydraDB call, see finding #16). When set, the
// document renders as three pieces (before/highlighted/after the matched
// span) and auto-scrolls the highlighted piece into view. When absent,
// renders as one plain ReactMarkdown block, same as before.
export default function DocumentViewer({ filename, label, highlightChunkText }) {
  const [content, setContent] = useState(null)
  const [error, setError] = useState(null)
  const [highlightSpan, setHighlightSpan] = useState(null) // { start, end } | null
  const highlightRef = useRef(null)

  useEffect(() => {
    setContent(null)
    setError(null)
    setHighlightSpan(null)
    fetchDocument(filename)
      .then((data) => setContent(data.content))
      .catch((err) => setError(err.message))
  }, [filename])

  useEffect(() => {
    if (!filename || !highlightChunkText) {
      setHighlightSpan(null)
      return
    }
    let cancelled = false
    fetchHighlight(filename, highlightChunkText)
      .then((data) => {
        if (!cancelled) setHighlightSpan(data.match ? { start: data.match.start, end: data.match.end } : null)
      })
      .catch(() => {
        if (!cancelled) setHighlightSpan(null)
      })
    return () => {
      cancelled = true
    }
  }, [filename, highlightChunkText])

  // Once the highlighted piece is in the DOM, scroll it into view.
  useEffect(() => {
    if (highlightSpan) {
      highlightRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [highlightSpan, content])

  return (
    <div className="doc-viewer">
      <p className="doc-viewer-title">{label || filename}</p>
      <div className="snippet doc-viewer-scroll">
        {error && <p className="muted">Couldn't load this document: {error}</p>}
        {!error && content == null && <p className="muted">Loading...</p>}
        {content != null && (
          highlightSpan ? (
            <>
              <ReactMarkdown>{content.slice(0, highlightSpan.start)}</ReactMarkdown>
              <div className="doc-viewer-highlight" ref={highlightRef}>
                <ReactMarkdown>{content.slice(highlightSpan.start, highlightSpan.end)}</ReactMarkdown>
              </div>
              <ReactMarkdown>{content.slice(highlightSpan.end)}</ReactMarkdown>
            </>
          ) : (
            <ReactMarkdown>{content}</ReactMarkdown>
          )
        )}
      </div>
    </div>
  )
}
