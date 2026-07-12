import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { fetchDocument } from '../api'

// filename: e.g. "peloton_2020-12-21_8k.md" — fetches and renders the real
// full source document, not just the fragment(s) that were retrieved as
// evidence. Highlighting which part was actually used is deliberately not
// implemented yet — out of scope for this pass.
// label: human-readable display name (e.g. "Peloton – Form 8-K"); falls
// back to the raw filename if not given.
export default function DocumentViewer({ filename, label }) {
  const [content, setContent] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    setContent(null)
    setError(null)
    fetchDocument(filename)
      .then((data) => setContent(data.content))
      .catch((err) => setError(err.message))
  }, [filename])

  return (
    <div className="doc-viewer">
      <p className="doc-viewer-title">{label || filename}</p>
      <div className="snippet doc-viewer-scroll">
        {error && <p className="muted">Couldn't load this document: {error}</p>}
        {!error && content == null && <p className="muted">Loading...</p>}
        {content != null && <ReactMarkdown>{content}</ReactMarkdown>}
      </div>
    </div>
  )
}
