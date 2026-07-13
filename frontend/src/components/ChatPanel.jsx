import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { sendChat } from '../api'

// Placement-agnostic chat core. The same component is dropped into whichever
// shell (sidebar / drawer / bottom section) — it owns all the chat behaviour,
// the shells only own layout.
//
// Each turn is one Q&A pair (the backend pipeline is stateless per question:
// classify -> scoped retrieval -> synthesis + price blend), rendered with its
// scope, price stat, and an expandable "how we found this" provenance block.
//
// seed: { question, key } — when `key` changes (an event's "Decode with the
// agent" CTA), the question is auto-sent, so the hand-off from an event's
// evidence into the shared decoder feels like a real continuation.

const EXAMPLES = [
  'What did Peloton announce in December 2020?',
  "Compare Peloton's 2020 boom to the 2022 restructuring.",
  'How volatile was the stock leading up to the CFO transition?',
]

export default function ChatPanel({ seed }) {
  const [input, setInput] = useState('')
  const [turns, setTurns] = useState([]) // [{ question, loading, result?, error? }]
  const [pending, setPending] = useState(false)
  const scrollRef = useRef(null)

  async function ask(question) {
    const q = (question ?? input).trim()
    if (!q || pending) return
    setInput('')
    setPending(true)
    setTurns((t) => [...t, { question: q, loading: true }])
    try {
      const result = await sendChat(q)
      setTurns((t) => t.map((turn, i) => (i === t.length - 1 ? { ...turn, loading: false, result } : turn)))
    } catch (err) {
      setTurns((t) => t.map((turn, i) => (i === t.length - 1 ? { ...turn, loading: false, error: err.message } : turn)))
    } finally {
      setPending(false)
    }
  }

  // Auto-send a seeded question from an event's stage-3 CTA.
  useEffect(() => {
    if (seed?.question) ask(seed.question)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seed?.key])

  // Keep the newest turn in view.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [turns])

  return (
    <div className="chat-panel">
      <div className="chat-scroll" ref={scrollRef}>
        {turns.length === 0 && (
          <div className="chat-empty">
            <p className="chat-empty-title">Ask the decoder</p>
            <p className="muted">
              Ask about one event, compare two, or ask across a whole period — it figures out
              the scope from your question.
            </p>
            <div className="chat-examples">
              {EXAMPLES.map((ex) => (
                <button key={ex} type="button" className="chat-example" onClick={() => ask(ex)}>
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        {turns.map((turn, i) => (
          <ChatTurn key={i} turn={turn} />
        ))}
      </div>

      <form
        className="chat-input-row"
        onSubmit={(e) => {
          e.preventDefault()
          ask()
        }}
      >
        <input
          className="chat-input"
          value={input}
          placeholder="Ask about the story…"
          onChange={(e) => setInput(e.target.value)}
          disabled={pending}
        />
        <button type="submit" className="btn btn-active" disabled={pending || !input.trim()}>
          {pending ? '…' : 'Ask'}
        </button>
      </form>
    </div>
  )
}

function ChatTurn({ turn }) {
  const { question, loading, result, error } = turn
  return (
    <div className="chat-turn">
      <p className="chat-q">{question}</p>

      {loading && <p className="muted chat-a">Decoding…</p>}
      {error && <p className="muted chat-a">Couldn't reach the decoder: {error}</p>}

      {result && (
        <div className="chat-a">
          {result.answer ? (
            <div className="chat-answer">
              <ReactMarkdown>{result.answer}</ReactMarkdown>
            </div>
          ) : (
            <p className="muted">{result.warning || 'No answer.'}</p>
          )}

          {result.price_stats && <PriceChip stats={result.price_stats} />}

          {result.event_ids?.length > 0 && <Provenance result={result} />}
        </div>
      )}
    </div>
  )
}

function PriceChip({ stats }) {
  const ret = stats.total_return_pct
  const sign = ret >= 0 ? '+' : ''
  return (
    <div className="chat-price">
      <span className={ret >= 0 ? 'pct pct-pos' : 'pct pct-neg'}>
        {sign}
        {ret}%
      </span>
      <span className="muted">
        {' '}
        · vol {stats.volatility_pct}% · max drawdown {stats.max_drawdown_pct}% · {stats.weeks}w (
        {stats.start_date} → {stats.end_date})
      </span>
    </div>
  )
}

function Provenance({ result }) {
  const [open, setOpen] = useState(false)
  const sources = uniqueSources(result.chunks)
  return (
    <div className="chat-prov">
      <button type="button" className="decode-btn" onClick={() => setOpen((o) => !o)}>
        {open ? 'Hide how we found this' : 'How we found this →'}
      </button>
      {open && (
        <div className="chat-prov-body">
          <p className="chat-prov-line">
            <span className="chat-tag">{result.query_type}</span>
            {' '}scope: {result.event_ids.join(', ')}
          </p>
          {result.reasoning && <p className="muted">Why these: {result.reasoning}</p>}
          {result.filing_dates?.length > 0 && (
            <p className="muted">Filings queried: {result.filing_dates.join(', ')}</p>
          )}
          <p className="muted">
            Evidence: {result.chunks?.length || 0} chunks, {result.chunk_relations?.length || 0} graph
            relationships
          </p>
          {sources.length > 0 && (
            <p className="muted">Sources: {sources.join(', ')}</p>
          )}
        </div>
      )}
    </div>
  )
}

function uniqueSources(chunks) {
  const seen = new Set()
  for (const c of chunks || []) {
    const t = c?.source_title
    if (t) seen.add(t)
  }
  return [...seen]
}
