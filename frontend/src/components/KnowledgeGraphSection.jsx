import { useState } from 'react'
import KnowledgeGraph from './KnowledgeGraph'
import SelectedNodePanel from './SelectedNodePanel'

// graph: event.knowledge_graph from /api/timeline — combined across every
// document cited as evidence for this event (see backend/knowledge_graph.py).
// Two sections, per the MarketFoundry-style layout this was modeled on: the
// graph itself, and a separate Selected Node/Relationship panel below it.
// Selection is either a node or an edge, never both — picking one clears
// the other, matching a single-selection dashboard panel.
export default function KnowledgeGraphSection({ graph }) {
  const [selection, setSelection] = useState(null) // { type: 'node' | 'edge', id } | null

  if (!graph || graph.nodes?.length === 0) {
    return null
  }

  const selectedNodeId = selection?.type === 'node' ? selection.id : null
  const selectedEdgeId = selection?.type === 'edge' ? selection.id : null

  const handleSelectNode = (id) => setSelection(id ? { type: 'node', id } : null)
  const handleSelectEdge = (id) => setSelection(id ? { type: 'edge', id } : null)

  return (
    <div className="kg-section">
      <p className="section-label">Knowledge graph</p>
      <KnowledgeGraph
        graph={graph}
        selectedNodeId={selectedNodeId}
        selectedEdgeId={selectedEdgeId}
        onSelectNode={handleSelectNode}
        onSelectEdge={handleSelectEdge}
      />

      <p className="section-label kg-detail-label-spaced">Selected node / relationship</p>
      <SelectedNodePanel graph={graph} selectedNodeId={selectedNodeId} selectedEdgeId={selectedEdgeId} />
    </div>
  )
}
