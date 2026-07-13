# Topic 2 — Create Database

---

**Test ID**: T02.1
**Title**: Create `stock-decoder` database with metadata schema via SDK
**Date/Time**: 2026-07-13
**Topic**: 2 — Create database
**Already Handled?**: Yes — finding #2 in `hydradb_findings_log.md` (deprecation notice on this same call points at fields that don't exist in the SDK signature). Reconfirming it still happens on a fresh database, not re-investigating from scratch.
**Claim Reference**: n/a
**Environment**: `hydradb-sdk` (per `.venv`), Python (venv), macOS, target database `stock-decoder`, `.env` keys used: `HYDRA_DB_API_KEY`, `HYDRA_DB_TENANT_ID`
**Preconditions**: No existing `stock-decoder` database.
**Action / Command**:
```
python3 scripts/setup_and_ingest_sdk.py --step create
```
**Expected Result**: `202`-style accepted response per `api-reference/v2/endpoint/create-tenant.md` (`status: "accepted"`), with no `meta.deprecation` pointing at nonexistent fields (per `HydraDB_claims.md`, `database`/`tenant_metadata_schema` are the documented current parameters).
**Actual Result**:
```
data=TenantsTenantCreateAcceptedResponse(database='stock-decoder', message='Database creation started in the background. Use GET /databases/status?database=... to check progress.', status='accepted', tenant_id='stock-decoder')
error=None
meta=HandlerResponseMeta(collection=None, database=None, deprecation=[HandlerDeprecationNotice(deprecated=True, deprecated_field='tenant_metadata', deprecated_since='2.0.1', message='tenant_metadata and tenant_metadata_schema are deprecated; use database_metadata and database_metadata_schema instead', preferred_field='database_metadata')], latency_ms=165.8, request_id='88d6e886-8eb3-444d-aa81-c67f4f9d06d0', source_type=None, sub_tenant_id=None, tenant_id=None)
success=True
```
**Status**: Pass (core creation succeeded as expected) — with the known deprecation-notice issue reproduced.
**Error Details**: n/a (not an error — a `meta.deprecation` advisory on a successful response)
**Diagnosis / Root Cause**: Reconfirms finding #2 exactly: the SDK's own runtime response tells callers to migrate `tenant_metadata`/`tenant_metadata_schema` → `database_metadata`/`database_metadata_schema`, but `client.databases.create()`'s actual signature only accepts `tenant_metadata_schema` (confirmed via `inspect.signature` in the original finding). Following the notice today would raise a `TypeError` for an unknown kwarg. Reproduces identically on a brand-new tenant (`stock-decoder`), 2+ months after first observed — not a one-off fluke, still live.
**Files Changed**: none
**Fix / Workaround Applied**: none needed — kept calling with `tenant_metadata_schema` (the notice's advice is not actually followable).
**Retest Result**: n/a
**Reproducibility**: 1/1 this session (this is a deterministic response-shape issue, not a flaky one — no need to repeat runs to confirm it).
**Severity**: Moderate (unchanged from finding #2) — cosmetic today, but a forward-looking trap for anyone who trusts the deprecation notice and updates their code to match it.
**Category**: HydraDB-SDK-bug
**Cross-references**: `hydradb_findings_log.md` finding #2
**Follow-up / Open Questions**: none — same known issue, just reconfirmed under the new tenant.
