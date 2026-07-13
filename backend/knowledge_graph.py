"""
Stage 4: builds one merged, deduplicated knowledge graph across every
document cited as evidence for a timeline event. Pulls each document's full
relation set via hydradb_client.get_relations_for_source() — independent of
any query or relevance ranking, unlike synthesis.py's query()-based evidence
— and merges them into one {nodes, edges} graph.

The alias/dedup step below exists because HydraDB's own cross-document
entity resolution (a claimed Tier 4 feature) does not reliably merge the
same real-world entity when documents refer to it differently (e.g. "Peloton"
vs. "Peloton Interactive, Inc."), confirmed via both the SDK and the live
dashboard's own Graph view. Full writeup: docs/findings/knowledge_graph.md.
There is no HydraDB API to fix this at the source
(checked — see the same doc), so it's handled here, at render time,
scoped only to this feature. Does not touch synthesis.py/timeline.py.
"""
import hydradb_client

# Confirmed gaps from finding #14 — same real-world entity, different raw
# name per document, not merged by HydraDB's own entity resolution. Keys and
# values are lowercased; a key collapses into its value. Exact-string match
# only (case-insensitive) — no fuzzy/embedding matching, to avoid
# false-merging genuinely different entities (e.g. "Peloton Guide" the
# product must NOT collapse into "Peloton" the company).
ENTITY_ALIASES = {
    "peloton": "peloton interactive, inc.",
    "netflix": "netflix, inc.",
    "executive chair of the board of directors": "executive chair",
    "executive chairman of the board": "executive chair",
    "co-founder and chair": "executive chair",
}


def _canonical_key(name: str) -> str:
    """Lowercases and applies the alias table — this becomes the node's
    stable id, replacing HydraDB's own per-document entity_id (which is
    exactly what fails to merge across documents in the first place)."""
    lowered = name.strip().lower()
    return ENTITY_ALIASES.get(lowered, lowered)


def _better_display_name(a: str, b: str) -> str:
    """When two raw names collapse into one node, prefer the longer/more
    formal-looking one as the display name (e.g. "Peloton Interactive, Inc."
    over "Peloton") — reads better in a graph built from SEC filings."""
    return a if len(a) >= len(b) else b


def _register_node(nodes: dict, entity, filename: str) -> str:
    """Adds/updates a node from a GraphEntity (source or target of a
    triplet), applying the alias table, and returns its canonical key."""
    key = _canonical_key(entity.name)
    node = nodes.get(key)
    if node is None:
        node = {
            "id": key,
            "name": entity.name,
            "type": entity.type,
            "identifier": entity.identifier,
            "documents": [],
        }
        nodes[key] = node
    else:
        node["name"] = _better_display_name(node["name"], entity.name)
        node["identifier"] = node["identifier"] or entity.identifier
    if filename not in node["documents"]:
        node["documents"].append(filename)
    return key


def build_graph(documents: list) -> dict:
    """documents: list of filenames — the same deduplicated list already
    shown in the frontend's "Click to decode" dropdown for one event.
    Returns {"documents": [...], "nodes": [...], "edges": [...]}. Node
    "id" is the alias-normalized key, not HydraDB's raw entity_id. Edges
    with the same (source, predicate, target) across multiple documents
    merge into one edge with multiple "evidence" entries — one edge = one
    fact, matching the document-wise (not snippet-wise) evidence panel
    already built for this app. DOCUMENT-type nodes (e.g. "Exhibit 99.1")
    are included here, not filtered — hiding them by default is a frontend
    rendering choice, so the data stays complete."""
    id_map = hydradb_client.source_id_map()

    nodes = {}  # canonical_key -> node dict
    edges = {}  # (source_key, predicate, target_key) -> edge dict
    skipped_documents = []

    for filename in documents:
        source_id = id_map.get(filename)
        if not source_id:
            # Document not found in the tenant (shouldn't happen in
            # practice — these filenames come from the same evidence list
            # that already round-tripped through HydraDB) — skip rather
            # than fail the whole graph for one bad filename.
            skipped_documents.append(filename)
            continue

        triplets = hydradb_client.get_relations_for_source(source_id)
        for triplet in triplets:
            source_entity = triplet.source
            target_entity = triplet.target
            if not source_entity or not target_entity:
                continue

            source_key = _register_node(nodes, source_entity, filename)
            target_key = _register_node(nodes, target_entity, filename)

            for relation in (triplet.relations or []):
                predicate = relation.canonical_predicate or relation.raw_predicate
                if not predicate:
                    continue
                edge_key = (source_key, predicate, target_key)
                edge = edges.get(edge_key)
                if edge is None:
                    edge = {
                        "id": f"{source_key}|{predicate}|{target_key}",
                        "source_id": source_key,
                        "target_id": target_key,
                        "predicate": predicate,
                        "evidence": [],
                    }
                    edges[edge_key] = edge
                edge["evidence"].append({
                    "context": relation.context,
                    "document": filename,
                    "temporal_details": relation.temporal_details,
                    "confidence": relation.confidence,  # not shown in UI, kept for completeness
                    "chunk_id": relation.chunk_id,
                })

    for node in nodes.values():
        node["documents"].sort()
        node["doc_count"] = len(node["documents"])

    return {
        "documents": documents,
        "skipped_documents": skipped_documents,
        "nodes": sorted(nodes.values(), key=lambda n: (-n["doc_count"], n["name"])),
        "edges": sorted(edges.values(), key=lambda e: (e["source_id"], e["predicate"], e["target_id"])),
    }
