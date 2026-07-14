# API Findings

Raw HTTP API behavior verified against HydraDB's documented claims - no SDK in the loop. This was a separate test pass from the SDK-based findings in this folder: every call was hand-run with `curl` against `https://api.hydradb.com` on a fresh free-tier database, using a small synthetic two-document corpus purpose-built to probe entity resolution and temporal reasoning - an RFC approving an infrastructure migration (dated 2026-03-04) and meeting notes partially reversing that decision after a security incident (2026-04-22), sharing four people, one project, and a superseded decision.

Each test targeted a specific claim from hydradb.com or docs.hydradb.com (site and docs crawled). Where an SDK-era finding could be re-checked at the raw layer, it was - see the reconciliation table at the end.

**Scorecard:** of ~30 documented claims tested, **11 confirmed**, **9 contradicted outright**, ~6 partially wrong (right behavior, wrong status code / shape / error name), and 2 untestable at this corpus size. Three SDK-era findings reproduced exactly; two did not reproduce (one likely fixed since).

---

## What genuinely works

- **Cross-document entity resolution is real and good.** The same person mentioned in both documents resolved to a single `entity_id`, with typed entities (PERSON / PROJECT / DOCUMENT / ORGANIZATION), namespaces, canonical vs raw predicates, and extracted `temporal_details` ("2026-05-15", "Q1 2026") - with zero manual tagging. The auto-linking claim repeated across four cookbooks held up.
- **Text/phrase search is precise and fast.** `query_by:"text"` + `operator:"phrase"` found exactly the right document at 62-66ms server-side - the only query path that beats the sub-200ms claim.
- **Instant read-path deletion.** Deleted documents vanish from `/query` and `/context/list` immediately, as documented, and their graph edges are pruned.
- **Deterministic ingest ids** (derived from filename + tenant) confirmed at the raw layer - and delete-then-re-ingest of the same filename worked cleanly here (see reconciliation table; this had failed silently in SDK-era testing).
- **Bounds validation is real where it exists:** `max_results: 51` → 400; `expiry_seconds: 59` → 400 with the exact valid range; `page_size: 101` → 400 *with a docs link in the error* - the politest errors in the API.
- **`PATCH /context/sources/{id}/metadata` works and repairs the metadata trap** - after ingest silently accepted malformed metadata (below), PATCH restored it, verified via `/context/list`.
- **The deprecation machinery exists and is informative** (`meta.deprecation[]` with field names, preferred replacements, "deprecated since 2.0.1") - the problem is the docs lag behind it.
- **Database provisioning is fast** (~5s to fully ready), and `/databases/status` exposes a genuine partial-ready state (`knowledge: true, memories: false`) before `ready_for_ingestion` flips.

## Significant findings

### 1. Every 4xx error bypasses the documented response envelope

Docs promise `{success, data, error, meta}` with `meta.request_id` "even on errors." In practice **every** error observed - auth, validation, conflict, not-found - returned a FastAPI-style `{"detail": {success, message, error_code}}` with **no request_id**, making errors impossible to correlate with support. Compounding it:

- **Wrong status codes:** missing/invalid auth → **403 FORBIDDEN** (docs and HTTP convention say 401 UNAUTHORIZED); duplicate `Authorization` headers → 403 with `message: "unauthorized"` - the code and message disagree about which auth concept applies.
- **The documented error taxonomy doesn't match live codes.** "Already exists" is `TENANT_ALREADY_EXISTS` in the docs, `DATABASE_ALREADY_EXISTS` on `POST /databases`, and `INVALID_INPUT` on `POST /tenants`; "not found" is `TENANT_NOT_FOUND` in the docs but `NOT_FOUND` live. One condition family, five names.
- **Internals leak through responses:** raw Go unmarshal text (`json: cannot unmarshal object into Go value of type []json.RawMessage`), the server-side field name `file_metadata` (docs call it `document_metadata`), and `milvus_sync_required` in a success payload (revealing the vector store).
- **Errors that blame the wrong thing:** a JSON body to `/context/ingest` → "database is required" even when the body contained `database` (the endpoint never parses JSON - it is multipart-only; docs claim this case returns 422, actual is 400). A wrong multipart field name (`files=`) → an error message that *itself calls the field 'files'* while rejecting it; the real field is `documents`.

### 2. The API Reference documents the naming migration backwards

The docs state that `/query`, `/context/status`, `/context/inspect`, `/context/list`, and `/context/relations` accept **only** `tenant_id`, with "no `database` alias." On every one of them, the reality is inverted: `database=` works fine, and it is `tenant_id` that triggers a formal deprecation notice. Related:

- **`DELETE /context` is documented exactly inverted:** the docs' nested `{type, request:{...}}` body → 400 "database is required"; the flat body the docs warn against → works, with correct per-id results.
- **Two parallel create paths are both live** (`POST /databases` and `POST /tenants`) with different field names and different error codes for the same failure.
- **The SDK lags the raw API by a version:** an SDK-era finding flagged a deprecation notice pointing to "nonexistent" `database_metadata` fields - those fields exist at the raw API; the installed SDK simply doesn't expose them.

### 3. The temporal/knowledge-update claims do not survive at the raw layer

The corpus was built as a textbook knowledge-update case (confident decision → documented reversal):

- Asking **"is X being decommissioned - what is the current plan?"** ranked the **outdated RFC above the reversal** (0.6657 vs 0.6608), with nothing in the response marking the earlier decision as superseded - even though the graph demonstrably extracted both documents' dates. The LongMemEval Knowledge Update (97.43%) story evidently lives in an LLM pipeline above this API, not in `/query`.
- **`recency_bias` had zero observable effect** (0.0 vs 0.9 → scores identical to 10 decimal places). Document-content dates are not used; if the feature keys off timestamp metadata, that dependency is undocumented.
- **`synthesis_context` gating matches the docs** (populated in `mode:"thinking"` only), but its content reads as query *classification*, not synthesis - and in one case it claimed the justification "is not in the snippets" while the top chunk of the same response contained it in full.

### 4. Silent traps that compound each other

- **Malformed `document_metadata` is silently accepted** (202, `success_count: 1`) when it is valid JSON of the wrong shape, leaving metadata permanently empty - the SDK-era finding reproduced exactly at the raw layer.
- ...which then makes **any `metadata_filters` query return zero results** - contradicting the docs' claim that undeclared filter keys are "silently ignored, not errored" (they filter; they don't ignore). The docs make two mutually exclusive claims here (silent-ignore vs correctness-first); the implementation follows correctness-first.
- **`ids=a,b` on `/context/status` is silently mis-parsed as a single id** (→ `errored` / `FILE_NOT_FOUND`); only repeated `ids=a&ids=b` works. The encoding is documented nowhere.
- **No relevance floor:** a deliberately absurd query returned the full corpus at 0.64 relevancy (on-topic queries score ~0.74). The documented zero-result behavior is practically unreachable on a non-empty corpus, and the score compression makes client-side thresholding hopeless.
- **Querying during indexing returns empty with zero signal** - exactly as the cookbooks self-admit ("looks like a bug but is not"). No "indexing in progress" hint exists anywhere in the response.

### 5. Business-tier claims

- **"Free plan is capped at 1 database (403 Plan limit reached)"** - false. A confirmed free-tier account held four databases and created a fifth without complaint. Either the docs are wrong or the limit isn't enforced.
- **"Sub-200ms retrieval"** holds only for text-mode. Measured server-side `latency_ms`: text/phrase 62-66ms ✓; hybrid fast 376-489ms; `alpha:"auto"` 633ms; thinking mode 1,337-1,914ms. Wall-clock adds ~300ms of network on top.

## Moderate findings

- **Dual-generation naming everywhere:** responses carry both `tenant_ids` AND `databases`, both `tenant_id` AND `database` in `meta`, both `sub_tenant_ids` AND `collections` - duplication rather than migration, with message strings still reading "tenant IDs" / "sub-tenant IDs."
- **Bug - `/context/list` reports the wrong scope:** every listed source shows `sub_tenant_id` equal to the *tenant* name, while the same response's `meta` shows the actual collection id.
- **"A default collection is auto-provisioned at database creation" is wrong as stated:** nothing is listed at creation; the auto-assigned collection has an opaque generated id (not "default") and appears in `/databases/collections` only after first write - matching the docs' *competing* "grows organically on first write" claim.
- **Async status codes are inconsistent:** database creation (async) returns 200; ingestion (async) returns 202.
- **`/context/inspect` with `mode=content` returns `content: null`** and puts the actual payload in an undocumented `content_base64` field.
- **The graph has two timestamp formats:** epoch floats in `/query` relations vs ISO strings in `/context/relations`; relations also carry a `confidence` score on only one of the two endpoints.
- **A docs self-contradiction, resolved empirically:** `query_forceful_relations` + `mode:"fast"` is a silent no-op (the Knowledge and Query pages are right; the Memories page's claim of "HTTP 422" is wrong).
- **The documented transient `TENANT_NOT_FOUND` right after database creation did not occur** even when polling immediately - the docs describe a failure mode that appears fixed.
- **`ready_for_ingestion` exists** - the docs' example is right and their own OpenAPI schema omits it; schema/prose mismatches cut both ways.
- **Response shapes carry double `success` flags** (envelope level + data level) and roughly 6-8 undocumented fields per endpoint.
- **No version echo:** omitting the `API-Version` header changes nothing observable, and no response field states which API version served the request.

## SDK-era findings, reconciled at the raw layer

| SDK-based finding (this repo) | Raw-API result |
|---|---|
| Malformed metadata silently accepted, chunk metadata permanently empty ([SDK & Ingestion](sdk_and_ingestion.md)) | **Reproduced** - and `PATCH /context/sources/{id}/metadata` is a working repair |
| `document_metadata` requires array-wrapping; server-side name `file_metadata` leaks in errors ([SDK & Ingestion](sdk_and_ingestion.md)) | **Reproduced**, plus raw Go unmarshal internals leak |
| Deprecation notice references "nonexistent" `database_metadata` fields ([SDK & Ingestion](sdk_and_ingestion.md)) | **Explained** - the fields exist at the raw API; the SDK lags them |
| Re-ingesting a just-deleted id silently never appears ([SDK & Ingestion](sdk_and_ingestion.md), logged Significant) | **Not reproduced** - clean reappearance with the same deterministic id in ~30-60s; possibly fixed since (both observations kept, with dates) |
| Ingest ids are deterministic ([SDK & Ingestion](sdk_and_ingestion.md)) | **Confirmed** |
| `synthesis_context` only populated in thinking mode ([Documentation Accuracy](documentation_accuracy.md)) | **Confirmed**, with new content-quality caveats (reads as query classification, not synthesis) |
| Undocumented `_retrieval_source` key in `additional_metadata` ([Documentation Accuracy](documentation_accuracy.md)) | Not reproduced on this corpus |
