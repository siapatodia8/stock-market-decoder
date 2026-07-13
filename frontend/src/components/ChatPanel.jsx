import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { sendChat } from '../api'

// Placement-agnostic chat core, styled for the terminal's "02 · DECODER"
// panel. Each turn is one Q&A pair (the backend pipeline is stateless per
// question: classify -> scoped retrieval -> synthesis + price blend),
// rendered with its price stat and an expandable "how we found this"
// provenance block.

const EXAMPLES = [
  'What did Peloton announce in December 2020?',
  "Compare Peloton's 2020 boom to the 2022 restructuring.",
]

export default function ChatPanel() {
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

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      ask()
    }
  }

  // Keep the newest turn in view.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [turns])

  return (
    <div className="term-chat">
      <div className="term-chat-scroll" ref={scrollRef}>
        {turns.length === 0 && (
          <div className="term-chat-empty">
            <p>Hand this event to the decoder — explain it, or compare across the timeline.</p>
            <div className="term-chat-examples">
              {EXAMPLES.map((ex) => (
                <button key={ex} type="button" className="term-chat-example" onClick={() => ask(ex)}>
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

      <div className="term-chat-input-row">
        <input
          className="term-chat-input"
          value={input}
          placeholder="> ask the decoder…"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={pending}
        />
        <button type="button" className="term-chat-send" onClick={() => ask()} disabled={pending || !input.trim()}>
          RUN
        </button>
      </div>
    </div>
  )
}

function ChatTurn({ turn }) {
  const { question, loading, result, error } = turn
  return (
    <div className="term-chat-turn">
      <p className="term-chat-q">{question}</p>

      {loading && <p className="term-chat-thinking">decoding<span className="dd1">.</span><span className="dd2">.</span><span className="dd3">.</span></p>}
      {error && <p className="muted">Couldn't reach the decoder: {error}</p>}

      {result && (
        <div className="term-chat-a">
          {result.answer ? (
            <div className="term-chat-answer">
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
    <div className="term-chat-price">
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
    <div className="term-chat-prov">
      <button type="button" className="term-decode-btn" onClick={() => setOpen((o) => !o)}>
        {open ? 'hide how we found this' : 'how we found this →'}
      </button>
      {open && (
        <div className="term-chat-prov-body">
          <p className="term-chat-prov-line">
            <span className="term-chat-tag">{result.query_type}</span>
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
          {sources.length > 0 && <p className="muted">Sources: {sources.join(', ')}</p>}
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
