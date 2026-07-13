import { useEffect, useRef } from 'react'
import ChatPanel from './ChatPanel'

// Placement shell around the shared ChatPanel. `placement` selects the layout
// so we can trial all three ('sidebar', 'drawer', 'section') without touching
// the chat internals — ChatPanel is identical in every one.
//
// Hooks are declared unconditionally at the top so switching placement at
// runtime (the dev toggle) never changes the hook count.
export default function ChatDock({ open, onOpen, onClose, seed, placement = 'sidebar' }) {
  const sectionRef = useRef(null)

  // 'section' lives in the page flow at the bottom; opening it (CTA or FAB)
  // just scrolls it into view instead of sliding an overlay in.
  useEffect(() => {
    if (placement === 'section' && open) {
      sectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [open, seed?.key, placement])

  if (placement === 'section') {
    return (
      <>
        {!open && (
          <button type="button" className="chat-fab" onClick={onOpen}>
            Decoder ▾
          </button>
        )}
        <section className="chat-section" ref={sectionRef}>
          <div className="chat-dock-head">
            <span className="chat-dock-title">Decoder</span>
          </div>
          <ChatPanel seed={seed} />
        </section>
      </>
    )
  }

  // sidebar + drawer: fixed overlays that slide in.
  const containerClass = placement === 'sidebar' ? 'chat-sidebar' : 'chat-drawer'
  return (
    <>
      {!open && (
        <button type="button" className="chat-fab" onClick={onOpen}>
          Decoder {placement === 'drawer' ? '▴' : '▸'}
        </button>
      )}
      <aside className={`${containerClass} ${open ? 'open' : ''}`} aria-hidden={!open}>
        <div className="chat-dock-head">
          <span className="chat-dock-title">Decoder</span>
          <button type="button" className="chat-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <ChatPanel seed={seed} />
      </aside>
    </>
  )
}
