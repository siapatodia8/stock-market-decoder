// Backend runs locally via `uvicorn main:app --reload --port 8000` (backend/).
// Called directly (not proxied through Vite), matching main.py's CORS allowlist
// for http://localhost:5173.
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
