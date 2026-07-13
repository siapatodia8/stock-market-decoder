# Stock Market Decoder - Testing & Findings

Every finding below came from hands-on testing against the live HydraDB SDK, not from reading documentation alone. Surprising or inconsistent results were re-run until confirmed rather than logged from a single pass, and several were independently cross-checked against HydraDB's own dashboard, not just its API responses.

---

## Summary

| Severity | Count |
|---|---|
| Significant | 5 |
| Moderate | 6 |
| Minor | 2 |
| Informational | 1 |

## Findings by Area

| Document | Description |
|---|---|
| [SDK & Ingestion Findings](findings/sdk_and_ingestion.md) | SDK behavior quirks and ingestion pipeline gotchas |
| [Documentation Accuracy Findings](findings/documentation_accuracy.md) | Where HydraDB's docs and actual behavior diverge |
| [Query & Retrieval Quality Findings](findings/query_and_retrieval_quality.md) | Retrieval reliability, reranking stability, and grounding quality |
| [Knowledge Graph Findings](findings/knowledge_graph.md) | What entity resolution and relationship extraction got right and wrong |

---
