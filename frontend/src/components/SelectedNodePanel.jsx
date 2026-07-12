import { colorForType, titleCaseType } from '../graphColors'

// Mirrors MarketFoundry/HydraDB's own dashboard panel behavior: selecting a
// node shows a scrollable list of every relationship touching it as a plain
// subject -> predicate -> object line (no context sentence or date — just
// the triples, so the list stays scannable). Selecting a relationship
// (a line in the graph) instead shows that one relationship's full detail:
// the triple plus its evidence (context sentence + date, possibly more than
// one if the same fact was confirmed across multiple documents). Confidence
// score is deliberately not shown either way (matches HydraDB's own panel).
export default function SelectedNodePanel({ graph, selectedNodeId, selectedEdgeId }) {
  if (selectedEdgeId) {
    return <SelectedEdgeDetail graph={graph} edgeId={selectedEdgeId} />
  }
  if (selectedNodeId) {
    return <SelectedNodeDetail graph={graph} nodeId={selectedNodeId} />
  }
  return <p className="muted">Click a node, or a line connecting two nodes, to see its details.</p>
}

function SelectedNodeDetail({ graph, nodeId }) {
  const node = graph.nodes.find((n) => n.id === nodeId)
  if (!node) return null

  const nameById = Object.fromEntries(graph.nodes.map((n) => [n.id, n.name]))
  const relatedEdges = graph.edges.filter((e) => e.source_id === nodeId || e.target_id === nodeId)

  return (
    <div className="kg-detail">
      <div className="kg-detail-header">
        <span className="kg-detail-dot" style={{ background: colorForType(node.type) }} />
        <p className="kg-detail-name">{node.name}</p>
        <span className="kg-detail-type">{titleCaseType(node.type)}</span>
      </div>
      {node.identifier && <p className="kg-detail-identifier">{node.identifier}</p>}

      <p className="kg-detail-count">
        {relatedEdges.length} relationship{relatedEdges.length === 1 ? '' : 's'}
      </p>

      <div className="kg-relations kg-relations-scroll">
        {relatedEdges.map((edge) => (
          <p key={edge.id} className="kg-relation-triple">
            <span className={edge.source_id === nodeId ? 'kg-relation-focus' : ''}>
              {nameById[edge.source_id] || edge.source_id}
            </span>{' '}
            <span className="kg-relation-predicate">{edge.predicate}</span>{' '}
            <span className={edge.target_id === nodeId ? 'kg-relation-focus' : ''}>
              {nameById[edge.target_id] || edge.target_id}
            </span>
          </p>
        ))}
      </div>
    </div>
  )
}

function SelectedEdgeDetail({ graph, edgeId }) {
  const edge = graph.edges.find((e) => e.id === edgeId)
  if (!edge) return null

  const nameById = Object.fromEntries(graph.nodes.map((n) => [n.id, n.name]))

  return (
    <div className="kg-detail">
      <div className="kg-detail-header">
        <p className="kg-detail-name kg-detail-name-relation">
          <span className="kg-relation-focus">{nameById[edge.source_id] || edge.source_id}</span>{' '}
          <span className="kg-relation-predicate">{edge.predicate}</span>{' '}
          <span className="kg-relation-focus">{nameById[edge.target_id] || edge.target_id}</span>
        </p>
        <span className="kg-detail-type">Relationship</span>
      </div>

      <p className="kg-detail-count">
        {edge.evidence?.length || 0} supporting mention{edge.evidence?.length === 1 ? '' : 's'}
      </p>

      <div className="kg-relations kg-relations-scroll">
        {edge.evidence?.map((ev, i) => (
          <div key={i} className="kg-relation">
            {ev.context && <p className="kg-relation-context">{ev.context}</p>}
            {ev.temporal_details && <p className="kg-relation-date">{ev.temporal_details}</p>}
          </div>
        ))}
      </div>
    </div>
  )
}
