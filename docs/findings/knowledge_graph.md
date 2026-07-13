# Knowledge Graph Findings

How well HydraDB's automatic entity and relationship extraction merged the same real-world entity across multiple documents - tested against HydraDB's own claim, and independently cross-checked in the live dashboard, not just via the SDK.

---

## Entity Resolution Results

Pulled and merged the knowledge graph relations for all 5 documents behind one real, multi-document event (a CEO transition and restructuring announced across two 8-Ks, a board press release, a restructuring press release, and a shareholder letter), then reviewed every resulting entity by hand.

| Outcome | What Happened | Example |
|---|---|---|
| Correctly merged | Same-name mentions across different documents collapsed into one node, exactly as claimed | Barry McCarthy (3 documents), John Foley (4 documents), and 9 others in this one event alone - 11 entities total, each unified under a single node with edges from every document that mentioned it |
| Correctly kept separate | Different real-world entities that happen to share a word stayed distinct - good precision, not a resolution failure | "Peloton" (the company), "Peloton Board of Directors," "Peloton Guide" (a product), and "Peloton Output Park" (a facility) all stayed as separate nodes, matching what the live dashboard's own search returns |
| Should have merged, didn't | The same real-world entity, referred to by its formal legal name in one document and a shorthand in another, was extracted as two separate nodes with two different entity IDs | "peloton" and "peloton interactive, inc." - the hub of the entire event graph, so the split cuts the graph's connectivity roughly in half. The same pattern showed up for "netflix" / "netflix, inc." |

**Severity: Significant** - this is a direct counterexample to a specifically-tested claim, on the exact scenario (one real-world entity, referenced differently across documents) that claim's own pilot test was designed to validate.

---

## No Source-Level Fix Available

The `context` client exposes exactly 7 methods, and none of them edit, merge, or alias a graph entity once it's been extracted - entity identity is assigned once, at ingestion time, with no exposed way to correct it afterward. The only available lever would be re-ingesting source documents with more consistent naming, which carries its own risk (see SDK & Ingestion Findings) and isn't guaranteed to close a gap this consistent.

Resolved in this app with an app-layer workaround: case-insensitive exact-name matching (free, already merges 11+ entities correctly per event on its own) plus a small manual alias table for the confirmed gaps above.

---
