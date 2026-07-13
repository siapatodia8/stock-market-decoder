// Draggable divider that adjusts a numeric px value by mouse delta along one
// axis. axis="x" is a vertical bar (col-resize, drag left/right to change a
// width); axis="y" is a horizontal bar (row-resize, drag up/down to change a
// height). `invert` flips which drag direction grows the value, for a handle
// that sits on the trailing edge of the panel it controls (e.g. the divider
// between the decoder and the graph panel shrinks the graph as you drag
// right, not grow it).
export default function Resizer({ axis, value, onChange, min, max, invert = false }) {
  function onMouseDown(e) {
    e.preventDefault()
    const start = axis === 'x' ? e.clientX : e.clientY
    const startValue = value
    const cursorClass = axis === 'x' ? 'resizing-col' : 'resizing-row'
    document.body.classList.add(cursorClass)

    function onMove(ev) {
      const pos = axis === 'x' ? ev.clientX : ev.clientY
      const delta = (pos - start) * (invert ? -1 : 1)
      onChange(Math.min(max, Math.max(min, startValue + delta)))
    }
    function onUp() {
      document.body.classList.remove(cursorClass)
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  return (
    <div
      className={axis === 'x' ? 'resize-handle-v' : 'resize-handle-h'}
      onMouseDown={onMouseDown}
    />
  )
}
