import { useEffect, useMemo, useRef, useState } from 'react'
import { forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY } from 'd3-force'
import { select } from 'd3-selection'
import { zoom as d3zoom, zoomIdentity } from 'd3-zoom'
import { colorForType, HIDDEN_NODE_TYPES, titleCaseType, TYPE_COLORS } from '../graphColors'

const WIDTH = 760
const HEIGHT = 560
const TICKS = 400 // run the simulation to completion synchronously, then render a static
// result — matches the rest of this app's precomputed/static feel (the price chart has
// no live animation either, only hover), and avoids the jank risk of a live physics loop.
const SCALE_EXTENT = [0.25, 5]
const ZOOM_STEP = 1.3
const FIT_PADDING = 0.85 // leave a margin around the graph when fitting to view

// Label-fitting constants — kept in sync with .kg-node-label's actual
// font-size/weight in index.css. AVG_CHAR_WIDTH is a rough per-character
// width estimate for that font, used to size the text box conservatively
// (better to wrap/truncate a little early than to risk text touching the
// circle's edge).
const LABEL_LINE_HEIGHT = 11
const AVG_CHAR_WIDTH = 5.8
// Keeps the readable text box well inside the circle (a circle's inscribed
// square is already ~0.71r per side; using less than that leaves a visible
// border/margin of empty circle showing around the text on every side).
const LABEL_SAFE_FACTOR = 0.6
const MAX_LABEL_LINES = 4

function nodeRadius(node) {
  return 24 + Math.min(node.doc_count ?? 1, 5) * 7
}

// Splits a node's name into up to a few short lines guaranteed to fit
// inside its own circle with margin to spare, instead of one long
// truncated label below it (matching MarketFoundry's in-circle wrapped
// labels). Both the per-line character budget and the number of lines are
// derived from the circle's actual radius, not a fixed guess — bigger
// (more-cited) nodes get a bigger text box. Anything that still doesn't
// fit (a long name, or more lines than the box allows) gets a trailing
// ellipsis rather than overflowing the circle.
function wrapLabel(name, radius) {
  const safeHalf = radius * LABEL_SAFE_FACTOR // half-width/half-height of the readable box
  const maxChars = Math.max(3, Math.floor((2 * safeHalf) / AVG_CHAR_WIDTH))
  const maxLines = Math.min(MAX_LABEL_LINES, Math.max(1, Math.floor((2 * safeHalf) / LABEL_LINE_HEIGHT)))

  const words = (name || '').trim().split(/\s+/).filter(Boolean)
  const lines = []
  let current = ''
  for (const word of words) {
    if (lines.length >= maxLines) break
    const candidate = current ? `${current} ${word}` : word
    if (candidate.length > maxChars && current) {
      lines.push(current)
      current = word
    } else {
      current = candidate
    }
  }
  if (lines.length < maxLines && current) lines.push(current)

  const consumedWords = lines.join(' ').split(/\s+/).filter(Boolean).length
  const hasOverflow = consumedWords < words.length

  return lines.map((line, i) => {
    const isLast = i === lines.length - 1
    const mustEllipsize = line.length > maxChars || (isLast && hasOverflow)
    if (!mustEllipsize) return line
    return `${line.slice(0, Math.max(1, maxChars - 1))}…`
  })
}

// Finds connected components (union-find over shared edges) so each
// disconnected cluster (e.g. a person + their role, mentioned in only one
// document, with no link back to the main hub) can be checked for overlap
// against every other cluster and nudged apart afterward — see
// separateClusters below.
function findComponents(nodes, edges) {
  const parent = new Map(nodes.map((n) => [n.id, n.id]))
  const find = (x) => {
    while (parent.get(x) !== x) {
      parent.set(x, parent.get(parent.get(x)))
      x = parent.get(x)
    }
    return x
  }
  for (const e of edges) {
    if (!parent.has(e.source_id) || !parent.has(e.target_id)) continue
    const ra = find(e.source_id)
    const rb = find(e.target_id)
    if (ra !== rb) parent.set(ra, rb)
  }
  const groups = new Map()
  for (const n of nodes) {
    const root = find(n.id)
    if (!groups.has(root)) groups.set(root, [])
    groups.get(root).push(n.id)
  }
  return [...groups.values()].sort((a, b) => b.length - a.length)
}

// Minimum empty space kept between two different clusters' outer boundaries
// after separation — enough to read as clearly distinct groups without
// pushing them so far apart the graph feels sparse/unreadable.
const CLUSTER_GAP = 46

// After the physics settle, a disconnected cluster (no link path back to
// the main hub) can still land visually inside the main cluster's natural
// footprint purely by chance — a single shared weak centering force isn't
// enough to guarantee separation regardless of how many nodes are on each
// side. This does an explicit second pass: compute each connected
// component's bounding circle from its settled positions, then iteratively
// push any overlapping circles apart (largest/main cluster stays anchored,
// everything else moves just enough to clear it and every other cluster),
// and finally translate each cluster's member nodes by its net
// displacement. Guarantees a minimum visible gap between distinct clusters
// while keeping them as close to their natural layout as possible.
function separateClusters(nodes, links) {
  const components = findComponents(nodes, links)
  if (components.length <= 1) return

  const nodeById = new Map(nodes.map((n) => [n.id, n]))
  const circles = components.map((ids) => {
    const members = ids.map((id) => nodeById.get(id))
    const cx = members.reduce((sum, n) => sum + n.x, 0) / members.length
    const cy = members.reduce((sum, n) => sum + n.y, 0) / members.length
    let r = 0
    for (const n of members) {
      r = Math.max(r, Math.hypot(n.x - cx, n.y - cy) + nodeRadius(n))
    }
    return { ids, origCx: cx, origCy: cy, cx, cy, r }
  })

  for (let iter = 0; iter < 400; iter++) {
    let moved = false
    for (let i = 0; i < circles.length; i++) {
      for (let j = i + 1; j < circles.length; j++) {
        const a = circles[i]
        const b = circles[j]
        const dx = b.cx - a.cx
        const dy = b.cy - a.cy
        const dist = Math.hypot(dx, dy) || 0.001
        const minDist = a.r + b.r + CLUSTER_GAP
        if (dist < minDist) {
          moved = true
          const overlap = minDist - dist
          const ux = dx / dist
          const uy = dy / dist
          if (i === 0) {
            // Keep the largest component anchored; push the smaller one clear of it.
            b.cx += ux * overlap
            b.cy += uy * overlap
          } else {
            a.cx -= (ux * overlap) / 2
            a.cy -= (uy * overlap) / 2
            b.cx += (ux * overlap) / 2
            b.cy += (uy * overlap) / 2
          }
        }
      }
    }
    if (!moved) break
  }

  for (const c of circles) {
    const dx = c.cx - c.origCx
    const dy = c.cy - c.origCy
    if (dx === 0 && dy === 0) continue
    for (const id of c.ids) {
      const n = nodeById.get(id)
      n.x += dx
      n.y += dy
    }
  }
}

// Runs a one-shot force simulation (repel + link-spring + weak global
// centering + collision) and returns nodes/links with settled x/y
// positions. d3-force mutates link.source/target from string ids into the
// actual node objects once the simulation resolves them — that's expected,
// not a bug. A final separateClusters pass then guarantees disconnected
// clusters read as clearly distinct groups instead of relying on chance.
function layoutGraph(nodes, edges) {
  const simNodes = nodes.map((n) => ({ ...n }))
  const simLinks = edges.map((e) => ({ ...e, source: e.source_id, target: e.target_id }))

  const simulation = forceSimulation(simNodes)
    .force('charge', forceManyBody().strength(-260))
    .force(
      'link',
      forceLink(simLinks)
        .id((d) => d.id)
        .distance(115)
        .strength(0.5)
    )
    // Weak, uniform pull toward the canvas center — just enough to stop an
    // isolated component (or the whole graph) drifting off into infinity;
    // actual cluster-vs-cluster spacing is handled by separateClusters below.
    .force('x', forceX(WIDTH / 2).strength(0.05))
    .force('y', forceY(HEIGHT / 2).strength(0.05))
    .force('collide', forceCollide().radius((d) => nodeRadius(d) + 18))
    .stop()

  for (let i = 0; i < TICKS; i++) simulation.tick()

  separateClusters(simNodes, simLinks)

  return { nodes: simNodes, links: simLinks }
}

// Computes the d3-zoom transform that fits every node (plus its radius)
// inside the viewport, with a small margin — same job as MarketFoundry's
// "Fit view" button, also used once automatically on load/graph change so
// the graph never starts off-center or overflowing.
function fitTransform(nodes) {
  if (nodes.length === 0) return zoomIdentity
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
  for (const n of nodes) {
    const r = nodeRadius(n)
    minX = Math.min(minX, n.x - r)
    maxX = Math.max(maxX, n.x + r)
    minY = Math.min(minY, n.y - r)
    maxY = Math.max(maxY, n.y + r)
  }
  const graphWidth = Math.max(maxX - minX, 1)
  const graphHeight = Math.max(maxY - minY, 1)
  const scale = Math.min(
    SCALE_EXTENT[1],
    Math.max(SCALE_EXTENT[0], Math.min(WIDTH / graphWidth, HEIGHT / graphHeight) * FIT_PADDING)
  )
  const cx = (minX + maxX) / 2
  const cy = (minY + maxY) / 2
  return zoomIdentity.translate(WIDTH / 2 - scale * cx, HEIGHT / 2 - scale * cy).scale(scale)
}

// graph: {documents, nodes, edges} — one event's precomputed knowledge_graph
// (from /api/timeline, see backend/knowledge_graph.py). Selection (of either
// a node or an edge/relationship) is lifted up so the Selected
// Node/Relationship panel below can share it — only one of the two is ever
// active at a time, enforced by the parent (App.jsx).
export default function KnowledgeGraph({ graph, selectedNodeId, selectedEdgeId, onSelectNode, onSelectEdge }) {
  const svgRef = useRef(null)
  const zoomBehaviorRef = useRef(null)
  const [transform, setTransform] = useState(zoomIdentity)

  const visibleNodes = useMemo(
    () => (graph?.nodes || []).filter((n) => !HIDDEN_NODE_TYPES.has(n.type)),
    [graph]
  )
  const visibleIds = useMemo(() => new Set(visibleNodes.map((n) => n.id)), [visibleNodes])
  const visibleEdges = useMemo(
    () => (graph?.edges || []).filter((e) => visibleIds.has(e.source_id) && visibleIds.has(e.target_id)),
    [graph, visibleIds]
  )

  const { nodes: positioned, links } = useMemo(
    () => layoutGraph(visibleNodes, visibleEdges),
    [visibleNodes, visibleEdges]
  )

  // Wire up d3-zoom once per mount: wheel/trackpad-pinch to zoom, drag on
  // the background to pan, both centered correctly since the SVG's pixel
  // size and viewBox are identical (no CSS scaling to throw off d3-zoom's
  // pointer math).
  useEffect(() => {
    if (!svgRef.current) return
    const selection = select(svgRef.current)
    const behavior = d3zoom()
      .scaleExtent(SCALE_EXTENT)
      .on('zoom', (event) => setTransform(event.transform))
    selection.call(behavior)
    zoomBehaviorRef.current = behavior
    return () => selection.on('.zoom', null)
  }, [])

  // Auto-fit whenever a new/different graph loads, so it never opens
  // off-center or overflowing the viewport.
  useEffect(() => {
    if (!svgRef.current || !zoomBehaviorRef.current || positioned.length === 0) return
    const next = fitTransform(positioned)
    select(svgRef.current).call(zoomBehaviorRef.current.transform, next)
  }, [positioned])

  if (visibleNodes.length === 0) {
    return <p className="muted">No knowledge graph available for this event's documents.</p>
  }

  const zoomBy = (factor) => {
    if (!svgRef.current || !zoomBehaviorRef.current) return
    select(svgRef.current).call(zoomBehaviorRef.current.scaleBy, factor, [WIDTH / 2, HEIGHT / 2])
  }

  const fitView = () => {
    if (!svgRef.current || !zoomBehaviorRef.current) return
    select(svgRef.current).call(zoomBehaviorRef.current.transform, fitTransform(positioned))
  }

  return (
    <div className="kg-wrap">
      <div className="kg-toolbar">
        <button type="button" className="btn kg-zoom-btn" onClick={() => zoomBy(1 / ZOOM_STEP)} aria-label="Zoom out">
          −
        </button>
        <button type="button" className="btn kg-zoom-btn" onClick={() => zoomBy(ZOOM_STEP)} aria-label="Zoom in">
          +
        </button>
        <button type="button" className="btn" onClick={fitView}>
          Fit view
        </button>
      </div>

      <svg ref={svgRef} width={WIDTH} height={HEIGHT} viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="kg-svg">
        <g transform={`translate(${transform.x},${transform.y}) scale(${transform.k})`}>
          <g>
            {links.map((l) => {
              const focused =
                l.id === selectedEdgeId || l.source_id === selectedNodeId || l.target_id === selectedNodeId
              return (
                <g
                  key={l.id}
                  className="kg-edge-group"
                  onClick={(event) => {
                    event.stopPropagation()
                    onSelectEdge(l.id === selectedEdgeId ? null : l.id)
                  }}
                >
                  {/* Invisible wide hit-area — the visible line itself (1-1.5px) is too
                      thin a target to click reliably. */}
                  <line x1={l.source.x} y1={l.source.y} x2={l.target.x} y2={l.target.y} className="kg-edge-hit" />
                  <line
                    x1={l.source.x}
                    y1={l.source.y}
                    x2={l.target.x}
                    y2={l.target.y}
                    className={focused ? 'kg-edge kg-edge-focus' : 'kg-edge'}
                  />
                </g>
              )
            })}
          </g>
          <g>
            {positioned.map((n) => (
              <g
                key={n.id}
                transform={`translate(${n.x}, ${n.y})`}
                className="kg-node-group"
                onClick={(event) => {
                  event.stopPropagation()
                  onSelectNode(n.id === selectedNodeId ? null : n.id)
                }}
              >
                <circle
                  r={nodeRadius(n)}
                  fill={colorForType(n.type)}
                  className={n.id === selectedNodeId ? 'kg-node kg-node-selected' : 'kg-node'}
                />
                <text className="kg-node-label" textAnchor="middle">
                  {wrapLabel(n.name, nodeRadius(n)).map((line, i, arr) => (
                    <tspan key={i} x={0} y={(i - (arr.length - 1) / 2) * LABEL_LINE_HEIGHT}>
                      {line}
                    </tspan>
                  ))}
                </text>
              </g>
            ))}
          </g>
        </g>
      </svg>
      <KnowledgeGraphLegend />
    </div>
  )
}

function KnowledgeGraphLegend() {
  const entries = Object.entries(TYPE_COLORS).filter(([type]) => !HIDDEN_NODE_TYPES.has(type))
  return (
    <div className="kg-legend">
      {entries.map(([type, color]) => (
        <span key={type} className="kg-legend-item">
          <span className="kg-legend-dot" style={{ background: color }} />
          {titleCaseType(type)}
        </span>
      ))}
    </div>
  )
}
