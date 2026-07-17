# Knowledge Graph Findings

How well HydraDB's automatic entity and relationship extraction merged the same real-world entity across multiple documents - independently cross-checked in the live dashboard, not just via the SDK.

---

## Entity Resolution Results

Pulled and merged the knowledge graph relations for all 5 documents behind one real, multi-document event (a CEO transition and restructuring announced across two 8-Ks, a board press release, a restructuring press release, and a shareholder letter), then reviewed every resulting entity by hand.

| Outcome | What Happened | Example |
|---|---|---|
| Correctly merged | Same-name mentions across different documents collapsed into one node, exactly as claimed | Barry McCarthy (3 documents), John Foley (4 documents), and 9 others in this one event alone - 11 entities total, each unified under a single node with edges from every document that mentioned it |
| Correctly kept separate | Different real-world entities that happen to share a word stayed distinct - good precision, not a resolution failure | "Peloton" (the company), "Peloton Board of Directors," "Peloton Guide" (a product), and "Peloton Output Park" (a facility) all stayed as separate nodes, matching what the live dashboard's own search returns |
| Should have merged, didn't | The same real-world entity, referred to by its formal legal name in one document and a shorthand in another, was extracted as two separate nodes with two different entity IDs | "peloton" and "peloton interactive, inc." - the hub of the entire event graph, so the hub's edges end up divided across two disconnected nodes: a traversal starting from either Peloton node cannot reach the relations attached to the other. The same pattern showed up for "netflix" / "netflix, inc." |

**Severity: Significant** - the failure hits the hub entity of the corpus, on the most predictable resolution case in SEC filings (formal legal name vs. shorthand), and there is no post-ingest repair available.

---

## No Source-Level Fix Available

The Python SDK's `context` client exposes exactly 7 methods, and none of them edit, merge, or alias a graph entity once it's been extracted - entity identity is assigned once, at ingestion time. The only documented levers are both re-ingestion-shaped, not post-ingest repairs: (a) normalizing entity names in the source documents and re-ingesting - i.e. caller-side data preprocessing, which is exactly the manual work automatic extraction exists to remove, and still not guaranteed to close a gap this consistent; or (b) replacing automatic extraction entirely with a caller-supplied graph via `graph_payload` (BYOG) - which is "replace, not augment" per the docs (fixing one bad merge means forfeiting all the correct automatic extraction), and whose relation-linking the docs themselves describe as having no reject floor.

Resolved in this app with an app-layer workaround: case-insensitive exact-name matching (free, already merges 11+ entities correctly per event on its own) plus a small manual alias table for the confirmed gaps above.

---
