# Topic 10 — Backend Build & Run

---

**Test ID**: T10.1
**Title**: Undocumented `_retrieval_source` field surfaces in chunk `additional_metadata`, even with `graph_context=False`
**Date/Time**: 2026-07-13
**Topic**: 10 — Backend build & run
**Already Handled?**: No — not previously observed or logged anywhere in this project (checked `hydradb_findings_log.md`, `CONTEXT_UPDATES.md`, `HydraDB_claims.md`; no prior mention of `_retrieval_source`).
**Claim Reference**: `docs.hydradb.com/essentials/v2/api-results.md` — chunk response-shape schema (same page finding #13 already flagged for a `.metadata`/`additional_metadata` naming mismatch). That schema's `additional_metadata` example only shows caller-supplied fields (e.g. `{"author": "Support Team"}"`), no internal/reserved fields.
**Environment**: `hydradb-sdk`, Python (venv), macOS, database `stock-decoder`, sub-tenant `default`.
**Preconditions**: All 13 documents ingested and `completed`.
**Action / Command**:
```
python ../tests/test_metadata_filter_bucket.py
```
(Part 1 — unfiltered `client.query(..., mode="thinking", graph_context=False, max_results=5)` against the probe query for the Dec-2020 document; raw `metadata`/`additional_metadata` printed per chunk.)
**Expected Result**: Per the docs' schema example, `additional_metadata` should be `null` unless the caller supplied custom fields at ingest time (this project's ingest calls never set any `additional_metadata`).
**Actual Result**: 6 of 8 returned chunks had `additional_metadata: null` as expected. The 2 chunks sourced from `peloton_2021-08-26_shareholder-letter_v2.md` instead had `additional_metadata: {"_retrieval_source": "graph"}` — a field never supplied by this project's ingestion code, and never documented anywhere in the public schema. Notably, this happened with `graph_context=False` on the call, meaning some internal graph-based retrieval path contributed to (or tagged) these chunks regardless of the caller-facing `graph_context` flag.
**Status**: Fail (docs-completeness gap — undocumented internal field)
**Error Details**: n/a — not an error, an undocumented field
**Diagnosis / Root Cause**: Unknown from the outside — the SDK/API appears to internally tag some chunks with their retrieval path (vector vs. graph-assisted) via a reserved `_`-prefixed key injected into the same `additional_metadata` bucket callers use for their own custom fields, without documenting the key, its possible values, or that `graph_context=False` doesn't fully suppress graph-path involvement.
**Files Changed**: none
**Fix / Workaround Applied**: n/a — purely observational; doesn't block anything in this project (nothing reads `additional_metadata` in production code paths, per finding #13's `.metadata`-only usage in `synthesis.py`).
**Retest Result**: n/a
**Reproducibility**: Observed on 1 run so far (2/8 chunks, same 2 chunks both times they appeared in the raw dump — not re-run repeatedly since this is a low-stakes documentation gap, not a correctness-critical behavior; not spending extra cycles per the "keep tests short" policy).
**Severity**: Minor
**Category**: HydraDB-Docs-mismatch
**Cross-references**: `hydradb_findings_log.md` finding #13 (same docs page, same `additional_metadata` object, different gap)
**Follow-up / Open Questions**: What other reserved `_`-prefixed keys might exist in `additional_metadata`? Does `graph_context=False` ever fully suppress graph-path retrieval, or does it only control whether `synthesis_context`/`graph_paths` are returned to the caller while the underlying retrieval strategy can still involve the graph? Not pursued further here — flagging for the findings write-up rather than expanding this test.
**Provenance note**: not new behavior. `git show e2eb109:outputs/_metadata_filter_diagnostic_results.json` confirms the original build's run of this exact diagnostic already captured `{"_retrieval_source": "graph"}` on 2 chunks back then too (the Feb 2022 shareholder letter and board press release — different chunks than this rerun's, since the underlying data/database differs, but the same field/mechanism). The original `hydradb_findings_log.md` (last committed at `ea6824c`, before this rerun) never mentions it — the raw evidence was already sitting in that output file, just never examined closely enough to notice. So this reproduces across two independent builds; it's newly *documented* here, not newly *occurring*.
