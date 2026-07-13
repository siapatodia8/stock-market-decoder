# Topic 8 — Verify Knowledge Graph Relations

---

**Test ID**: T08.1
**Title**: Re-test of finding #14 — does cross-document entity resolution still fail to merge `peloton`/`peloton interactive, inc.` and `netflix`/`netflix, inc.` on a fresh database?
**Date/Time**: 2026-07-13
**Topic**: 8 — Verify knowledge graph relations
**Already Handled?**: Yes — finding #14 documented this exact gap on the original `stock-market-decoder` tenant (confirmed both via SDK and the live dashboard graph view). Re-testing on a completely fresh database + fresh ingestion, to check whether this is a corpus/run-specific fluke or a systematic HydraDB behavior.
**Claim Reference**: `HydraDB_claims.md` — entity resolution / cross-document entity merging claim (Tier 4).
**Environment**: `hydradb-sdk`, Python (venv), macOS, database `stock-decoder`, sub-tenant `default`.
**Preconditions**: All 13 documents ingested and `completed`.
**Action / Command**:
```
cd backend && python ../tests/test_knowledge_graph_relations.py
```
Full results saved to `outputs/_knowledge_graph_relations_test_results.json`.
**Expected Result**: Per finding #14, expect `peloton`/`peloton interactive, inc.` and `netflix`/`netflix, inc.` to remain separate, unmerged entity nodes.
**Actual Result**: Confirmed via `task_43_multi_doc_merge.full_node_registry` in the saved results:
- `'peloton interactive, inc.'` — ORGANIZATION, appears in 4 documents (`peloton_2022-02-05_8k.md`, `peloton_2022-02-05_board-pr.md`, `peloton_2022-02-08_8k.md`, `peloton_2022-02-08_restructuring-pr.md`)
- `'peloton'` (bare) — ORGANIZATION, appears in 1 document (`peloton_2022-02-08_shareholder-letter.md`) — a **separate** node, not merged into the above
- `'netflix'` — ORGANIZATION, 1 document (`peloton_2022-02-08_shareholder-letter.md`)
- `'netflix, inc.'` — ORGANIZATION, 1 document (`peloton_2022-02-05_8k.md`) — again, a **separate** node from `'netflix'`

Also confirmed clean on this rerun: 71 total triplets across 5 Feb-2022 documents, 64 unique nodes, zero inconsistent-casing variants, and determinism (same document queried twice → identical 26 triplets both times).
**Status**: Fail (reproduces finding #14; not our own mistake — this is HydraDB's entity extraction behavior)
**Error Details**: n/a — not an error, an entity-resolution gap
**Diagnosis / Root Cause**: Same root cause as finding #14: entity identity is assigned per-document at extraction time with no cross-document legal-name-vs-shorthand normalization. This rerun is a cleaner reproduction in one sense (a totally fresh database, fresh ingestion, different point in time) and a slightly different shape in another: in the original finding, `peloton`/`peloton interactive, inc.` were both heavily-connected hub nodes across many documents; here `peloton interactive, inc.` is the 4-document hub but bare `peloton` only surfaced in 1 document this time (likely just which of the 5 Feb-2022 docs happened to use the shorthand vs. legal name) — so the connectivity impact is smaller this run, but the underlying resolution gap is identical.
**Files Changed**: none
**Fix / Workaround Applied**: n/a — this project's existing app-layer alias table (`backend/knowledge_graph.py`'s `ENTITY_ALIASES`) already handles exactly this pair, unchanged from the original build.
**Retest Result**: n/a
**Reproducibility**: Reproduces cleanly on a fresh database/ingestion — strengthens finding #14's credibility as a systematic behavior rather than a one-off artifact of the original corpus.
**Severity**: Significant (unchanged from finding #14 — same reasoning: direct counterexample to a specifically-claimed feature, on real filings, not synthetic data)
**Category**: HydraDB-SDK-bug
**Cross-references**: `hydradb_findings_log.md` finding #14
**Follow-up / Open Questions**: none — this confirms finding #14 rather than opening anything new.
