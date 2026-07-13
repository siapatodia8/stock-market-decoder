# Topic 6 — Poll Ingestion Status

---

**Test ID**: T06.1
**Title**: Ingestion/indexing speed observation — same 13-document corpus completed dramatically faster on this rerun than during the original build
**Date/Time**: 2026-07-13
**Topic**: 6 — Poll ingestion status
**Already Handled?**: Partially — finding #5 (E6001 transient Storage failure, self-resolving in minutes) and finding #7 (per-document Storage time variance, 4.1–27.5 min) cover *why individual documents were slow* in the original build, but neither covers a *cross-run trend* for the same repeat content getting faster. This angle is new.
**Claim Reference**: n/a — informational observation, not a specific documented claim.
**Environment**: `hydradb-sdk`, Python (venv), macOS, database `stock-decoder`, sub-tenant `default`.
**Preconditions**: All 13 documents just ingested (topic 5), same content as the original `stock-market-decoder` build.
**Action / Command**:
```
python3 scripts/setup_and_ingest_sdk.py --step status
```
(Timing cross-checked against `outputs/_ingestion_results_sdk.json`'s `status_results_sdk` key.)
**Expected Result**: Per finding #5/#7, some Storage-stage delay and possibly E6001 errors before all 13 reach `completed`.
**Actual Result**: Reported by the user: full ingestion+indexing completed in ~1 minute this run. Confirmed directly against `outputs/_ingestion_results_sdk.json`: all 13 documents show `"indexing_status": "completed"`, `"error_code": ""`, `"error_message": ""` — **zero E6001s or any other error this run**, across all 13 documents.
**Status**: Pass (nothing malfunctioned — if anything, this is a positive/faster-than-expected result)
**Error Details**: n/a — none occurred
**Diagnosis / Root Cause**: One thing is confirmed by real data, not speculation: **this run avoided the E6001 retry tax entirely** — `status_results_sdk` shows no error codes on any of the 13 documents, unlike the original build where finding #5 documented E6001 on most/all documents with multi-minute self-resolving delays. Since those delays were the dominant cost in the original ~25–40 min figures, simply not hitting E6001 this time plausibly accounts for most of the speed difference on its own.

Two further hypotheses remain unverified and are noted for awareness only, not confirmed:
- User's hypothesis: the original run's slowness may have been driven by heavier cross-document entity-resolution work when a large batch of documents sharing the same company identity (Peloton) are all being linked into the graph together — something a single-document comparison wouldn't isolate anyway, which is why a controlled single-file test was skipped as not actually comparable to the original scenario.
- General infra warm-up / reduced backend load at time of request — plausible, not tested.
**Files Changed**: none
**Fix / Workaround Applied**: n/a — not a defect
**Retest Result**: n/a
**Reproducibility**: 1/1 this session — not repeated, since isolating the cause further would require a full multi-document controlled test, judged not worth the overhead for what's ultimately a positive result (things got faster, not slower or broken).
**Severity**: n/a — not a defect
**Category**: Non-issue-as-expected (logged for awareness as an interesting operational observation, not a bug or docs mismatch)
**Cross-references**: `hydradb_findings_log.md` findings #5, #7
**Follow-up / Open Questions**: Unconfirmed — whether batch-size-dependent entity resolution cost or general infra load explains the remainder of the speed difference beyond the confirmed absence of E6001 this run. Not planned to be investigated further unless it recurs or becomes relevant later in the rerun.

---

**Note (process, not a finding)**: `outputs/_ingestion_results_sdk.json` also contains a `recall_response_sdk` key with real Peloton content already in it, despite topic 7 (verify retrieval) not having run yet in this rerun. This is stale leftover from an earlier session's `--step recall` call (the results file is merge-updated by `save_results()`, never reset between runs) — not new data, and not something to log. It'll be overwritten cleanly once we actually run `--step recall` in topic 7.
