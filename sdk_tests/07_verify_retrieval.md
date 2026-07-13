# Topic 7 — Verify Retrieval

---

**Test ID**: T07.1
**Title**: Re-test of finding #9 — is `mode="thinking"`'s `synthesis_context` reliable for this query, on this rerun?
**Date/Time**: 2026-07-13
**Topic**: 7 — Verify retrieval
**Already Handled?**: Yes — finding #9 already investigated this exact behavior (6 attempts, 3 phrasings, on the original `stock-market-decoder` tenant: 4/6 stubs, 2/6 `None`). Re-testing because the very first run here got a real, grounded answer — a result finding #9 characterized as uncommon — so per the reproducibility protocol this needed repeat runs before concluding anything, rather than being dismissed as a fluke or silently accepted as "now fixed."
**Claim Reference**: `HydraDB_claims.md` — `synthesis_context` / multi-step query synthesis behavior.
**Environment**: `hydradb-sdk`, Python (venv), macOS, database `stock-decoder`, sub-tenant `default`.
**Preconditions**: All 13 documents ingested and `completed`.
**Action / Command**:
```
python3 scripts/setup_and_ingest_sdk.py --step recall --mode thinking
```
(same `DEFAULT_RECALL_QUERY` — the compound "leadership changes vs. financial guidance cuts/restructuring" question — run 4 times total)
**Expected Result**: Per finding #9, expect stub/paraphrase text or `None` most of the time for this compound-question phrasing.
**Actual Result**: 4/4 runs produced a real, correctly-grounded, non-stub answer — e.g. *"Peloton's leadership transitions in early 2022 occurred simultaneously with a significant decline in financial performance, characterized by a $439.4 million net loss and reduced sales guidance... restructuring program on February 8, 2022..."* Chunk count (11) and `graph_paths` count (10) were identical across all 4 runs.
**Status**: Pass (for this specific query/phrasing, on this rerun)
**Error Details**: n/a
**Diagnosis / Root Cause**: This refines, not contradicts, finding #9 — that finding tested 3 different phrasings and didn't break down which specific phrasing succeeded vs. stubbed; it's plausible this particular compound phrasing was always relatively reliable and the other 2 (single-part date-scoped, direct factual) were the weaker performers. Not re-tested here since scope was kept to reconfirming/repeating the one query already in the script rather than expanding to new phrasings (keeping this check short, per policy). Cannot conclude from this alone whether `synthesis_context` has generally improved since finding #9, only that this specific query is reliable across 4 consecutive runs on a fresh database.
**Files Changed**: none
**Fix / Workaround Applied**: n/a
**Retest Result**: n/a (this test entry already reflects 4 repeat runs)
**Reproducibility**: 7/7 consistent (4 initial runs + 3 more via `test_recall_not_cached.py`, real, grounded, non-stub answers every time)
**Severity**: n/a
**Category**: Non-issue-as-expected
**Cross-references**: `hydradb_findings_log.md` finding #9 (refines, does not overturn — scope limited to one phrasing)
**Follow-up / Open Questions**: Whether the other 2 phrasings from finding #9 (single-part date-scoped, direct factual) are now also more reliable is untested here — would need its own short check if this matters later, e.g. before relying on `synthesis_context` as a primary answer path anywhere in the app (current app design already doesn't — see `synthesis.py`'s custom formatter, per `CONTEXT_UPDATES.md` stage 3).

**Addendum — confirmed these are genuine live calls, not cached**: a reasonable question came up mid-testing (does `outputs/_ingestion_results_sdk.json`'s persisted/merged results mean recall is silently reading a cached response instead of hitting the live API?). Checked the code first — `save_results()` only writes after a call returns, never reads to short-circuit one. Then confirmed empirically via `sdk_tests/test_recall_not_cached.py`: 3 more calls returned 3 distinct, server-assigned `meta.request_id`s (`402bac5b...`, `fdbc6b9c...`, `a1eb309d...`) with realistic latencies (2932–3293ms, consistent with a genuine LLM-backed synthesis call, not an instant cache hit). No caching involved.
