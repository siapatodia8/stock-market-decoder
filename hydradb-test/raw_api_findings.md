# HydraDB Raw API — Consolidated Test Findings

**Method:** 36 hand-run curl tests (no SDK) against `https://api.hydradb.com`, July 13–14 2026, on a fresh free-tier database (`sia-test-2`) with a 2-document synthetic corpus designed to test entity resolution and temporal reasoning: an RFC approving a migration (dated 2026-03-04) and meeting notes partially reversing it (2026-04-22), sharing 4 people, a project, and a superseded decision. Every test maps to a specific claim extracted from hydradb.com / docs.hydradb.com (crawled 2026-07-12). Full per-test log: `api_test_plan.md`; runnable cells with captured outputs: `test.ipynb`. This complements — and cross-checks — the earlier SDK-based testing done for the Stock Market Decoder build.

**Scorecard:** of the ~30 documented claims tested: **11 confirmed**, **9 contradicted outright**, ~6 partially wrong (right behavior, wrong code/shape/name), 2 untestable at this corpus size. Two SDK-era findings did **not** reproduce (one likely fixed); three reproduced exactly.

---

## 1. What genuinely works (worth saying first)

- **Cross-document entity resolution is real and good.** "Wallace Okafor" resolved to a single `entity_id` spanning both PDFs, with typed entities (PERSON/PROJECT/DOCUMENT/ORGANIZATION), namespaces, canonical vs raw predicates, and extracted `temporal_details` ("2026-05-15", "Q1 2026") — with zero manual tagging. The 4-cookbook auto-linking claim held. (T19)
- **Text/phrase search is precise and fast.** `query_by:"text"` + `operator:"phrase"` found exactly the right document at 62–66ms server-side — the only path that beats the sub-200ms claim. (T25, T26)
- **Instant read-path deletion.** Deleted docs vanish from `/query` and `/context/list` immediately, and their graph edges get pruned. (T32)
- **Deterministic ingest ids** (filename+tenant derived) confirmed at the raw layer, and delete→re-ingest of the same filename worked cleanly here — the SDK-era "silent failure on reused filename" (logged as Significant then) **did not reproduce**; possibly fixed. (T33)
- **Bounds validation is real** where it exists: `max_results` 51 → 400; `expiry_seconds` 59 → 400 with the exact valid range; `page_size` 101 → 400 *with a docs link* — the politest errors in the API. (T24, T27, T29)
- **`PATCH /context/sources/{id}/metadata` works and repairs the metadata trap** — after ingest silently accepted malformed metadata (below), PATCH restored it, verified via list. (T30)
- **The deprecation machinery exists and is informative** (`meta.deprecation[]` with field names, preferred replacements, "since 2.0.1") — the problem is the docs lag it (below). (T12, T13, T30)
- **Database provisioning is fast** (~5s to fully ready) and the status endpoint exposes a genuine partial-ready state (`knowledge:true, memories:false`). (T06)

## 2. Significant findings

### 2.1 Every 4xx error bypasses the documented response envelope
Docs promise `{success, data, error, meta}` with `meta.request_id` "even on errors." Reality: **every** error observed (auth, validation, conflict, not-found — T01, T04, T05b, T05c, T08, T10, T11a, T27b, T29a/b, T30a, T31b, T34) returns a FastAPI-style `{"detail": {success, message, error_code}}` with **no request_id** — making errors impossible to correlate with support. Compounding it:

- **Wrong status codes:** missing/invalid auth → **403 FORBIDDEN** (docs and HTTP convention say 401 UNAUTHORIZED); duplicate auth headers → 403 with `message: "unauthorized"` — code and message disagree about which auth concept applies. (T01, T04)
- **The documented error taxonomy doesn't match live codes.** "Already exists" is `TENANT_ALREADY_EXISTS` in docs, `DATABASE_ALREADY_EXISTS` on `/databases`, `INVALID_INPUT` on `/tenants`; "not found" is `TENANT_NOT_FOUND` in docs, `NOT_FOUND` live. One condition family, five names. (T05b, T05c, T34)
- **Internals leak through errors:** raw Go unmarshal text (`json: cannot unmarshal object into Go value of type []json.RawMessage`), the server-side field name `file_metadata` (docs call it `document_metadata`), and `milvus_sync_required` in a success response (the vector store is Milvus). (T11a, T30b)
- **Errors that blame the wrong thing:** JSON body to `/context/ingest` → "database is required" when the body *contained* database (the endpoint never parses JSON; it's multipart-only — and the documented status for this is 422, actual is 400). Wrong multipart field name → an error that itself calls the field `'files'` while rejecting a request that used `files=`. (T08, T10)

### 2.2 The API Reference systematically documents the naming migration backwards
The docs say `/query`, `/context/status`, `/context/inspect`, `/context/list`, `/context/relations` accept **only** `tenant_id` with "no `database` alias." Reality on every one of them: `database=` works fine, and it's `tenant_id` that triggers a formal deprecation notice ("deprecated since 2.0.1"). (T12, T13, T15, T27, T28, T29) Related:

- **`DELETE /context` is documented exactly inverted:** the docs' nested `{type, request:{...}}` shape → 400; the flat shape the docs warn against → works. (T31)
- **Two parallel create paths are both live** (`POST /databases` and `POST /tenants`) with different field names and different error codes for the same failure. (T05, T05c)
- **The SDK lags the raw API by a version:** the SDK-era finding that a deprecation notice pointed to "nonexistent" fields (`database_metadata`/`database_metadata_schema`) is resolved — those fields exist at the raw API; the installed SDK just doesn't expose them. (T30b)

### 2.3 The temporal/knowledge-update claims do not survive the raw layer
This corpus was built as a textbook knowledge-update case (confident decision → documented reversal). Results:

- Asking **"Is Postgres being decommissioned? What is the current plan?"** ranked the **outdated RFC above the reversal** (0.6657 vs 0.6608), with nothing anywhere in the response marking the March decision as superseded — even though the graph demonstrably extracted the dates. The LongMemEval Knowledge Update 97.43% story evidently lives in an LLM pipeline above this API, not in `/query`. (T20)
- **`recency_bias` had zero observable effect** (0.0 vs 0.9 → scores identical to 10 decimal places). Document-content dates are not used; if it keys off timestamp metadata, that dependency is undocumented. (T21)
- **`synthesis_context` gating matches docs** (thinking-only ✓) but its content is query *classification*, not synthesis — and in one case it claimed the justification "is not in the snippets" while chunk #1 of the same response contained it in full. (T17, T19, T20)

### 2.4 Silent traps that compound each other
- **Malformed `document_metadata` is silently accepted** (202, `success_count:1`) if it's valid JSON of the wrong shape, leaving metadata permanently empty — reconfirmed at raw layer, SDK finding reproduced. (T11b, visible in T16/T29)
- …which then makes **any `metadata_filters` query return zero results** — and this contradicts the docs' claim that undeclared filter keys are "silently ignored, not errored" (they filter, they don't ignore). The docs make two mutually exclusive claims here (silent-ignore vs correctness-first); reality follows correctness-first. (T22)
- **`ids=a,b` on `/context/status` is silently mis-parsed as one id** (→ `errored`/`FILE_NOT_FOUND`); only repeated `ids=a&ids=b` works. Encoding never documented. (T12)
- **No relevance floor:** "best chocolate cake recipes" returned the full corpus at 0.64 relevancy (on-topic ≈ 0.74). The documented zero-result behavior is practically unreachable, and score compression makes client-side thresholding hopeless. (T23)
- **Querying during indexing returns empty with zero signal** — confirmed exactly as the cookbooks self-admit ("looks like a bug but is not"). No "indexing in progress" hint exists in the response. (T13)

### 2.5 Business-tier claims
- **"Free plan is capped at 1 database (403 Plan limit reached)"** — false. A confirmed free-tier account held 4 databases and created a 5th without complaint. Either the docs are wrong or the limit isn't enforced (arguably worse for HydraDB). (T05)
- **Sub-200ms retrieval:** holds only for text-mode. Measured server-side `latency_ms`: text/phrase 62–66ms ✓; hybrid fast 376–489ms; `alpha:"auto"` 633ms; thinking 1,337–1,914ms. Wall clock adds ~300ms. (Phase 3)

## 3. Moderate findings

- **Dual-generation naming everywhere:** responses carry both `tenant_ids` AND `databases`, both `tenant_id` AND `database` in meta, `sub_tenant_ids` AND `collections` — duplication, not migration; message strings still say "tenant IDs"/"sub-tenant IDs." (T02, T07, T09)
- **BUG — `/context/list` reports the wrong scope:** every source shows `sub_tenant_id: "sia-test-2"` (the *tenant* name) while the same response's meta says the collection is `7qtkangrs6`. (T29)
- **"Default collection auto-provisioned at creation" is wrong as stated:** nothing is listed at creation; the auto-assigned collection has an opaque generated id (`7qtkangrs6`, not "default") and appears only after first write — matching the *competing* "grows organically" claim. (T07, T09)
- **Async status codes are inconsistent:** database create (async) → 200; ingest (async) → 202. (T05, T09)
- **`/context/inspect` `mode=content` returns `content: null`** with the actual payload in undocumented `content_base64`. (T27)
- **Graph data has two timestamp formats:** epoch floats in `/query` relations, ISO strings in `/context/relations`; relations also carry a `confidence` score only on one of the two endpoints. (T19, T28)
- **Docs' own contradiction resolved:** `query_forceful_relations` + `mode:"fast"` is a silent no-op (Knowledge/Query pages right; Memories page's "HTTP 422" wrong). (T18)
- **Transient `TENANT_NOT_FOUND` after creation** (documented as expected) did not occur even when polling immediately — docs describe a failure mode that seems fixed. (T06)
- **`ready_for_ingestion` exists** (docs' example right, their OpenAPI schema omits it) — schema/prose mismatches cut both ways. (T06)
- **Response shapes carry double `success` flags** (envelope + data level) and ~6–8 undocumented fields per endpoint. (T09, T16, T29)
- **No version echo:** omitting `API-Version` changes nothing observable, and no response field states which version served the request. (T03)

## 4. SDK-era findings, reconciled

| SDK finding (stock-market-decoder) | Raw-API result |
|---|---|
| Malformed metadata silently accepted, metadata permanently empty | **Reproduced** (T11b) — and PATCH is a working repair (T30) |
| `document_metadata` needs array-wrap; server calls it `file_metadata` | **Reproduced**, plus Go internals leak (T11a) |
| Deprecation notice references "nonexistent" `database_metadata` fields | **Explained** — fields exist at raw API; SDK lags (T30) |
| Re-ingest of just-deleted id silently never appears (Significant) | **Not reproduced** — clean reappearance in ~30–60s (T33); possibly fixed, keep both dated observations |
| Deterministic ids from filename+tenant | **Confirmed** (T33) |
| `synthesis_context` only in thinking mode | **Confirmed**, with new quality caveats (T17) |
| `_retrieval_source` undocumented key in `additional_metadata` | Not reproduced in this corpus (T16) |

## 5. The one-paragraph version (for the feedback write-up)

The graph layer is the real thing — cross-document entity resolution with typed, dated relations worked unassisted on a deliberately tricky corpus, and text search is fast and exact. But the raw API tells a story the docs don't: every error path bypasses the documented envelope with wrong status codes, five names for two error conditions, and leaked internals; the API Reference documents the tenant→database migration exactly backwards on at least five endpoints and documents a delete body the server rejects; and the temporal claims that headline the marketing (knowledge updates, recency, time-aware retrieval) produce no observable effect at the `/query` layer — the outdated document wins the "what's the current plan?" query on a corpus built to showcase exactly that strength.
