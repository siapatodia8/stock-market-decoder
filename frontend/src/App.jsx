import { useEffect, useState } from 'react'

// Backend runs locally via `uvicorn main:app --reload --port 8000` (backend/).
// Not proxied through Vite — called directly, matching main.py's CORS allowlist
// for http://localhost:5173.
const API_BASE = 'http://localhost:8000'

function App() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch(`${API_BASE}/api/timeline`)
      .then((res) => {
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
        return res.json()
      })
      .then(setData)
      .catch((err) => setError(err.message))
  }, [])

  if (error) {
    return (
      <div style={{ padding: '2rem', fontFamily: 'monospace' }}>
        <p>Failed to fetch {API_BASE}/api/timeline</p>
        <p>{error}</p>
        <p>Make sure the backend is running: cd backend && uvicorn main:app --reload --port 8000</p>
      </div>
    )
  }

  if (!data) {
    return <p style={{ padding: '2rem' }}>Loading timeline...</p>
  }

  return (
    <div style={{ padding: '2rem' }}>
      <h1>Timeline sanity check — {data.months.length} months loaded</h1>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </div>
  )
}

export default App
