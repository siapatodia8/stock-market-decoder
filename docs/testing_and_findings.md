# Stock Market Decoder - Testing & Findings

Every finding below came from hands-on testing against the live HydraDB SDK, not from reading documentation alone. Surprising or inconsistent results were re-run until confirmed rather than logged from a single pass, and several were independently cross-checked against HydraDB's own dashboard, not just its API responses.

Separately from the SDK-based testing above, the raw HTTP API was also tested directly (no SDK, curl only) on smaller synthetic datasets to isolate backend behavior from SDK behavior - documented in [API Findings](findings/api_findings.md).

---

## Summary

| Severity | Count |
|---|---|
| Significant | 4 |
| Moderate | 6 |
| Minor | 2 |
| Informational | 1 |

Counts above cover the SDK-based findings docs. The raw-API pass is scored separately in [API Findings](findings/api_findings.md): of ~30 documented claims tested, 11 confirmed, 9 contradicted outright, ~6 partially wrong, plus a reconciliation of which SDK-era findings reproduced at the raw layer.

## Findings by Area

| Document | Description |
|---|---|
| [SDK & Ingestion Findings](findings/sdk_and_ingestion.md) | SDK behavior quirks and ingestion pipeline gotchas |
| [Documentation Accuracy Findings](findings/documentation_accuracy.md) | Where HydraDB's docs and actual behavior diverge |
| [Query & Retrieval Quality Findings](findings/query_and_retrieval_quality.md) | Retrieval reliability, reranking stability, and grounding quality |
| [Knowledge Graph Findings](findings/knowledge_graph.md) | What entity resolution and relationship extraction got right and wrong |
| [API Findings](findings/api_findings.md) | Raw HTTP API behavior vs documented claims - tested SDK-free on synthetic datasets, incl. an SDK-vs-raw reconciliation |

---
