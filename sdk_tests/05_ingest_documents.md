# Topic 5 — Ingest Knowledge Documents

---

**Test ID**: T05.1
**Title**: Claim check — does HydraDB dedupe identical content ingested under different filenames, or only match by filename/id?
**Date/Time**: 2026-07-13
**Topic**: 5 — Ingest knowledge documents
**Already Handled?**: No — new. Findings #6/#7/#11 established filename-derived deterministic ids and various upsert edge cases, but never directly tested identical content under two different filenames side by side.
**Claim Reference**: `HydraDB_claims.md` / `CONTEXT_UPDATES.md` — "`upsert: true` (default) ... replacing existing sources with the same ID, not versioning them."
**Environment**: `hydradb-sdk`, Python (venv), macOS, database `stock-decoder`, sub-tenant `default`.
**Preconditions**: All 13 real documents already ingested and `completed` (topic 5/6), including `peloton_2021-08-26_shareholder-letter_v2.md` (id: `peloton_2021-08-26_shareholder-letter`).
**Action / Command**:
```
python3 sdk_tests/test_upsert_claim.py
```
(Ingests `data/peloton_2021-08-26_shareholder-letter.md` — content byte-identical to the already-ingested `_v2.md` — twice in a row, no explicit id supplied.)
**Expected Result**: If ids are filename-derived (finding #6), expect a new, distinct id from `_v2.md`'s id, and the same id returned both times this file is ingested.
**Actual Result**:
- 1st ingest: `id='fb111e7e5c93d37534b06cacedb8fedf'`
- 2nd ingest (same file, unchanged): `id='fb111e7e5c93d37534b06cacedb8fedf'` — identical to the 1st.
- `_v2.md`'s real id (from topic 5's main ingest): `peloton_2021-08-26_shareholder-letter` — different from the above, despite byte-identical content.
**Status**: Pass — claim holds, as expected given finding #6.
**Error Details**: n/a
**Diagnosis / Root Cause**: Confirms there is no content-hash-based deduplication — HydraDB does not recognize that this file and `_v2.md` are byte-identical. Matching/upsert is purely filename(+tenant/sub-tenant)-derived, consistent with finding #6. Same filename ingested twice → same id both times (consistent with upsert-by-id). Not independently verified via row-count (see note below) — that check failed due to a flaw in the test script's timing/design, not a HydraDB behavior.
**Files Changed**: none
**Fix / Workaround Applied**: n/a
**Retest Result**: n/a
**Reproducibility**: 1/1 — the id match across two ingests is a deterministic, non-flaky result (not the kind of thing that needs repeat runs).
**Severity**: n/a (Non-issue-as-expected)
**Category**: Non-issue-as-expected
**Cross-references**: `hydradb_findings_log.md` finding #6
**Follow-up / Open Questions**: Resolved. The script's original Part 3 (`client.context.list()` check) returned 0 matches — a test-script timing issue (checked immediately post-ingest with no wait, searched by title instead of the known id), not a HydraDB finding. Fixed the script to wait for `indexing_status: "completed"` via `client.context.status()` before proceeding, and to delete via the known id directly. Re-ran clean: both ingests reached `completed`, same id both times, and `client.context.delete()` succeeded (`deleted_count=1`) — see T05.2 for a new observation surfaced by that delete call.

---

**Test ID**: T05.2
**Title**: Deprecation-notice coverage is inconsistent across endpoints for the same deprecated `tenant_id`/`sub_tenant_id` parameters
**Date/Time**: 2026-07-13
**Topic**: 5 — Ingest knowledge documents (surfaced via `test_upsert_claim.py`'s cleanup/delete step)
**Already Handled?**: No — new. Finding #2 covers a *different* deprecation notice (on `create()`, about `tenant_metadata`/`tenant_metadata_schema` field naming). This is about `tenant_id`/`sub_tenant_id` param naming, on a different endpoint.
**Claim Reference**: n/a
**Environment**: `hydradb-sdk`, Python (venv), macOS, database `stock-decoder`, sub-tenant `default`.
**Preconditions**: n/a
**Action / Command**: Same `python3 sdk_tests/test_upsert_claim.py` run as T05.1 — specifically its `client.context.delete(tenant_id=..., sub_tenant_id=..., ids=[...])` call.
**Expected Result**: If `tenant_id`/`sub_tenant_id` are deprecated in favor of `database`/`collection`, a reasonable developer would expect that flagged consistently on every call using those param names.
**Actual Result**: The `delete()` call's response included `meta.deprecation=[HandlerDeprecationNotice(deprecated=True, deprecated_field=None, deprecated_since='2.0.1', message='The tenant_id and sub_tenant_id fields are deprecated. Migrate to the database and collection fields.', preferred_field=None)]`. The 13 real `ingest()` calls earlier in this same session (topic 5 main ingest), using the identical `tenant_id`/`sub_tenant_id` params, all returned `meta.deprecation=None` — no notice at all.
**Status**: Fail (inconsistent, not a hard functional break)
**Error Details**: n/a — not an error, a missing/inconsistent advisory
**Diagnosis / Root Cause**: The deprecation-notice mechanism appears to be implemented per-endpoint rather than centrally for the deprecated param names — `delete()` flags `tenant_id`/`sub_tenant_id` usage, `ingest()` doesn't, and `create()` flags a third, unrelated field pair (`tenant_metadata`/`tenant_metadata_schema`) instead. A developer who only ever calls `ingest()` (the most common operation) would never learn `tenant_id`/`sub_tenant_id` are deprecated at all.
**Files Changed**: none
**Fix / Workaround Applied**: n/a — nothing to fix on our side; we still pass `tenant_id`/`sub_tenant_id` since aliases are documented as working either way.
**Retest Result**: n/a
**Reproducibility**: 1/1 this session for `delete()`; consistent absence across all 13 `ingest()` calls (13/13, not a fluke).
**Severity**: Minor — cosmetic/discoverability gap, not a functional break; same family of issue as finding #2 (deprecation-notice mechanism has rough edges) but a distinct instance.
**Category**: HydraDB-SDK-bug
**Cross-references**: `hydradb_findings_log.md` finding #2
**Follow-up / Open Questions**: Not tested here whether `client.context.status()`/`client.query()` also carry this same `tenant_id`/`sub_tenant_id` deprecation notice or stay silent like `ingest()` — would need a dedicated check if this pattern matters more later.
