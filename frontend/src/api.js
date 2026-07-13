// Backend runs locally via `uvicorn main:app --reload --port 8000` (backend/).
// Called directly (not proxied through Vite), matching main.py's CORS allowlist
// for http://localhost:5173 (this app's dev port, Vite's default).
const API_BASE = 'http://localhost:8000'

export async function fetchTimeline() {
  const res = await fetch(`${API_BASE}/api/timeline`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export async function fetchDocument(filename) {
  const res = await fetch(`${API_BASE}/api/documents/${encodeURIComponent(filename)}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

// Sends one question to the scoped chat pipeline (orchestrator -> retrieval ->
// synthesis + price blend). Returns the full ChatResponse: answer, query_type,
// event_ids, filing_dates, reasoning, price_stats, chunks, warning, etc.
export async function sendChat(question) {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

// Locates chunk_text's span within filename's full document (backend/highlight.py
// — app-side text matching, no HydraDB call; see finding #16). Returns
// { match: { start, end, matched_text, score, method } | null }.
export async function fetchHighlight(filename, chunkText) {
  const res = await fetch(`${API_BASE}/api/highlight`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, chunk_text: chunkText }),
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}
