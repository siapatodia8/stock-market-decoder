// Shared entity-type -> color mapping for the knowledge graph and the
// Selected Node/Relationship panel, so a node's color always matches
// between the graph and its own detail view. DOCUMENT is defined but not
// included in TYPE_LEGEND — those nodes are hidden by default (task #47)
// since they're structural (e.g. "Exhibit 99.1"), not story entities.
// Palette is "Option C" (brighter pastel) from the 3 candidates presented —
// light enough for black label text, distinct from the app's existing
// green/red (reserved for stock price direction).
export const TYPE_COLORS = {
  ORGANIZATION: '#a8c8ea',
  PERSON: '#f0b880',
  ROLE: '#c9a8dd',
  EVENT: '#8fd4c0',
  PROJECT: '#eaa0bc',
  CONCEPT: '#c9c98a',
  METRIC: '#f0d488',
  DOCUMENT: '#c7c7c7',
}

export const DEFAULT_NODE_COLOR = '#d3d1c7'

export const HIDDEN_NODE_TYPES = new Set(['DOCUMENT'])

export function colorForType(type) {
  return TYPE_COLORS[type] || DEFAULT_NODE_COLOR
}

export function titleCaseType(type) {
  if (!type) return 'Unknown'
  return type.charAt(0) + type.slice(1).toLowerCase()
}
