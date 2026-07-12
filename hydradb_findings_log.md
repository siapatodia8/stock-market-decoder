# HydraDB Findings Log — Errors, Inconsistencies, Gaps

Running log of confirmed, hands-on findings from actual API testing. Feeds the
"brutal, honest feedback" write-up. Doc-research-only observations (not
independently tested against the live API) belong in `CONTEXT_UPDATES.md`, not
here.

Format per entry: **Method** (REST / SDK / both / dashboard) → **Claimed** →
**Found** → **Where** → **Severity** → **Assumption**

---

### 1. "Get started" checklist doesn't reflect actual account state
- **Method**: Dashboard UI
- **Claimed**: Checklist marks "create a database" complete once a database exists.
- **Found**: Showed incomplete despite `sia-test` already existing and visible on the Databases page.
- **Where**: dashboard.hydradb.com/get-started vs. /databases.
- **Severity**: Minor/cosmetic.
- **Assumption**: Checklist likely tracks the dashboard's own "Create database" button flow, not actual account state — `sia-test` was created via API/SDK, not the UI.

### 2. Vectorstore readiness array order is reversed from what docs state
- **Method**: REST
- **Claimed**: `api-reference/endpoint/infra-status` and `essentials/knowledge` both state `vectorstore_status` is `[0]=Memories, [1]=Knowledge`.
- **Found**: Array read `[true, false]`. `POST /memories/add_memory` failed with `404`, "vectorstore collection has not been provisioned yet" — proving Memory's collection specifically was unprovisioned. Since that's the `false` entry at index 1, the real order is `[0]=Knowledge, [1]=Memories` — reverse of both docs.
- **Where**: `GET /tenants/infra/status`, `POST /memories/add_memory`, `GET /tenants/monitor`, tenant `stock-market-decoder`.
- **Severity**: Significant — two independent doc pages agree with each other but are both wrong on a basic, load-bearing field. Ingestion itself isn't gated on this flag (accepted regardless of its state).
- **Assumption**: Likely intentional async design (accept immediately, process in background), not a bug in itself — but the flag is a real, actionable signal, not a formality.

### 3. Docs self-contradict on whether `graph_creation`-stage content is searchable
- **Method**: REST
- **Claimed**: `api-reference/endpoint/verify-processing` says content in `graph_creation` is already searchable via vector recall.
- **Found**: `essentials/knowledge` says the opposite — not searchable until `indexing_status` is `completed` — and its own "common mistakes" table lists querying too early as an expected user error, not a bug.
- **Where**: Two HydraDB doc pages, directly compared.
- **Severity**: Moderate — direct self-contradiction on core behavior.

### 4. Ingestion silently failed for hours before reporting an error (E6001)
- **Method**: REST (original occurrence; also recurred under SDK ingestion of the same tenant — see findings #15/#17, so this is not REST-specific)
- **Claimed**: Docs state documents fully process in 1–5 minutes; `errored` is a documented terminal status, implying failures surface on a similar timescale.
- **Found**: All 13 documents sat at `indexing_status: "graph_creation"` for 20+ minutes, then for hours beyond that. Re-checked hours later — all 13 had flipped to `errored`, `error_code: "E6001"`, `"We couldn't save your indexed content."` The dashboard's Databases page showed accurate document/chunk counts throughout, suggesting a document/chunk catalog layer succeeded while a separate searchable-vector-index layer failed — consistent with the error's specific wording ("indexed content," not "document").
- **Where**: `POST /ingestion/verify_processing`, `GET /tenants/monitor`, dashboard, tenant `stock-market-decoder`.
- **Severity**: Significant, two dimensions: (1) a genuine save failure in the vector-index layer; (2) the multi-hour delay before the failure surfaced — any integration polling with a reasonable timeout would give up long before HydraDB reports the real terminal state.
- **Assumption**: Transient backend failure during the final content-save step. Confirmed unrelated to sub-tenant naming (a fresh sub-tenant hit the identical pattern) or client library choice (server-side error, not request-formation). See finding #15 — the actual fix was patience (retries), not a schema change.

### 5. `graph_context: false` is not honored in `thinking` mode
- **Method**: REST
- **Claimed**: `api-reference/endpoint/full-recall` — `graph_context` fields return empty unless the request sets `graph_context: true`.
- **Found**: Same query, `graph_context: false`: `mode="fast"` correctly returned empty graph context; `mode="thinking"` returned populated `query_paths` anyway.
- **Where**: `POST /recall/full_recall`, tenant `stock-market-decoder`.
- **Severity**: Moderate — flag isn't respected consistently across modes.

### 6. `/memories/add_memory` returns a misleading "tenant does not exist" error
- **Method**: REST
- **Claimed**: `api-reference/endpoint/add-memory` documents `404 TENANT_NOT_FOUND` for a tenant that doesn't exist.
- **Found**: Called against `stock-market-decoder` — a tenant that unambiguously exists — and got `404`, `"Tenant does not exist. The vectorstore collection has not been provisioned yet."` The real condition is narrower: only Memory's collection was unprovisioned, not the tenant. Error body also included unrelated "migrate to v2" boilerplate despite the call already using the current endpoint.
- **Where**: `POST /memories/add_memory`, tenant `stock-market-decoder`.
- **Severity**: Moderate — the message would send a developer chasing the wrong cause (tenant_id typo) instead of the real one (an unprovisioned sub-store).

### 7. `/tenants/monitor` response field name doesn't match docs
- **Method**: REST
- **Claimed**: Docs' example response uses `normal_collection` for the Knowledge collection field.
- **Found**: Actual response uses `knowledge_collection`.
- **Where**: `GET /tenants/monitor`, tenant `stock-market-decoder`.
- **Severity**: Minor doc inaccuracy.

### 8. Upload success returns 202, docs only document 200
- **Method**: REST
- **Claimed**: `api-reference/endpoint/upload-knowledge` response table lists only `200`.
- **Found**: Actual successful response is `202 Accepted`.
- **Where**: `POST /ingestion/upload_knowledge`.
- **Severity**: Minor — a strict `status_code == 200` check would mishandle a genuinely successful call.

### 9. Python SDK is not a thin wrapper over the REST API — different namespaces, params, and response shapes for the same operations
- **Method**: REST vs. SDK, direct comparison
- **Claimed**: Implicit claim of any official SDK — that it's a convenience wrapper matching the documented REST endpoints.
- **Found**: Ran `test.ipynb` (SDK, tenant `sia-test`) side by side with the REST script (`scripts/setup_and_ingest.py`). They diverge structurally:
  - Namespace: SDK is `client.databases`/`.context`/`.query`; REST uses `/tenants`/`/ingestion`/`/recall`/`/memories`. No `client.tenants` exists at all (`AttributeError`).
  - `client.databases.create` accepts both `database=` and `tenant_id=` kwargs — REST has no such alias.
  - Ingestion: SDK is `client.context.ingest(documents=, document_metadata=)`, one file per call. REST is `POST /ingestion/upload_knowledge`, multipart `files`/`file_metadata`, batched.
  - Response field naming for the same concept: SDK uses `id`; REST's upload response uses `source_id`; REST's status response uses `file_id`.
  - `vectorstore_status` shape: SDK returns a named object (`.knowledge`/`.memories`); REST returns a positional 2-item array (finding #2).
- **Where**: `test.ipynb` (tenant `sia-test`) vs. `scripts/setup_and_ingest.py` (tenant `stock-market-decoder`).
- **Severity**: Significant — code written against the REST reference and code written against the SDK for the identical task look unrelated.
- **Assumption**: SDK likely generated from a different internal schema version than this REST surface.

### 10. `synthesis_context` is only populated in `mode="thinking"` — `fast` and `auto` return `None` even with `graph_context=True`
- **Method**: SDK
- **Claimed**: `graph_context: true` is documented as the flag controlling whether graph context is returned; `mode` is documented as a recall-strategy selector, not a field-population gate.
- **Found**: Same tenant/query/`graph_context=True`, only `mode` varied: `"fast"` → `None`; `"auto"` → `None`; `"thinking"` → real text. Ruled out result-count truncation (`max_results=20` gave the same result).
- **Where**: `test.ipynb`, tenant `sia-test`.
- **Severity**: Moderate. `mode="thinking"` being necessary doesn't mean it's sufficient — see finding #19.

### 11. Retrying REST ingestion produced a different failure mode than the original attempt
- **Method**: REST
- **Claimed**: N/A — reproducibility check on finding #4. Retrying with `upsert: true` (default) is the error's own suggested recovery.
- **Found**: Re-ran ingest + status against the same 13 documents. Every document stayed at `indexing_status: "queued"` for the full 1200s poll — never advanced, never reached `errored` like the original attempt did. Not observed under SDK ingestion — SDK documents always showed visible pipeline progress (Parsing/Chunking/Graph/Embedding attempts advancing), never a frozen `queued` state, even when they later hit E6001.
- **Where**: `scripts/setup_and_ingest.py --step ingest`/`--step status`, tenant `stock-market-decoder`.
- **Severity**: Significant — two retries against the same tenant produced two different failure signatures. Decision made to stop retrying REST and switch to the SDK path (`scripts/setup_and_ingest_sdk.py`).

### 12. Deprecation notice on `client.databases.create` points at fields that don't exist in the current SDK signature
- **Method**: SDK
- **Found**: `client.databases.create(...)` succeeded but returned `meta.deprecation` telling callers to migrate from `tenant_metadata`/`tenant_metadata_schema` to `database_metadata`/`database_metadata_schema` — neither of which exists in the method's actual signature (`inspect.signature` confirmed).
- **Where**: `client.databases.create` response `meta.deprecation`, tenant `stock-market-decoder`.
- **Severity**: Moderate — cosmetic today, but a forward-looking trap: complying with the notice right now would raise a `TypeError` for an unknown kwarg.

### 13. SDK's `document_metadata` requires a JSON array even for a single-document call; error reveals the field is really called `file_metadata` server-side
- **Method**: SDK
- **Found**: `client.context.ingest(..., document_metadata=json.dumps({...}))` (single object) failed: `400 INVALID_INPUT`, `"cannot unmarshal object into Go value of type []json.RawMessage"`. Wrapping in a list (`json.dumps([{...}])`) is required even though the call only ever ingests one document.
- **Where**: `client.context.ingest`, tenant `stock-market-decoder`.
- **Severity**: Moderate — unintuitive given the singular `documents` param; only discoverable via a Go-level error naming an undocumented field. Fixed by wrapping in `[...]`.

### 14. `client.context.status` silently returns `FILE_NOT_FOUND` for real, indexed documents unless `sub_tenant_id` is passed explicitly
- **Method**: SDK
- **Found**: `client.context.status(tenant_id=..., ids=[...])` with no `sub_tenant_id` returned `FILE_NOT_FOUND` for all 13 real, indexed document ids (verified against the dashboard). Adding `sub_tenant_id="default"` (matching ingest-time value) immediately found them.
- **Where**: `client.context.status`, tenant `stock-market-decoder`.
- **Severity**: Significant — an optional param defaulting to `None` behaves as "search an empty scope," not "use the default sub-tenant." Not confirmed whether REST's equivalent (`verify_processing`) has the same gap — our REST script always passed `sub_tenant_id` explicitly, so this was never tested there.

### 15. Revising findings #4/#12: `nullable: true` on `doc_summary` is very likely NOT the actual fix for E6001 — a transient, self-resolving retry issue instead
- **Method**: SDK (observed during SDK-based ingestion of `stock-market-decoder`)
- **Found**: Schema was never changed, yet 12 of 13 documents that hit the E6001/`doc_summary` error on Storage succeeded anyway, purely via HydraDB's own automatic retries over several minutes. Confirms E6001 is not REST-specific — the same error and self-resolving pattern recurred here under SDK ingestion of the same tenant.
- **Where**: Dashboard Pipeline tab, tenant `stock-market-decoder`.
- **Severity**: Changes the read on #4/#12 — if a schema gap were the true cause, no document could succeed without fixing it, but nearly all did unmodified. More consistent explanation: an async propagation race condition between document metadata write and chunk-level vector insert. Recommendation: treat E6001 on Storage as something to tolerate with patience (retries measured in minutes), not something requiring a schema change.

### 16. Correcting finding #9: SDK ingest ids are deterministic (filename + tenant/sub-tenant), not random per call
- **Method**: SDK
- **Found**: A removed document, re-ingested as a fresh call, returned the byte-for-byte identical `id` it had before removal. A random/server-generated id could not reproduce this by chance.
- **Where**: `scripts/setup_and_ingest_sdk.py --step ingest --doc-id ...`, tenant `stock-market-decoder`.
- **Severity**: There is an effective upsert key — implicit (derived from filename/tenant/sub-tenant), not an explicit param like REST's `file_id`.

### 17. Re-ingesting under the same (deterministic) id shortly after deleting the original silently fails to materialize — distinct from the E6001 pattern
- **Method**: SDK
- **Found**: Re-ingesting a just-deleted document under its original filename returned `success: true` with the same id as before, but never appeared in the dashboard's Context list, even after several minutes. Re-ingesting the same content under a new filename (new deterministic id) worked normally — appeared within ~6.5s, then went through the same E6001/Vectorisation pattern as the other 12 documents, eventually succeeding.
- **Where**: `scripts/setup_and_ingest_sdk.py`, tenant `stock-market-decoder`.
- **Severity**: Significant — worse failure mode than E6001 since there's no visible error, just a document that never shows up. Workaround: never reuse a just-deleted document's filename/id.
- **Note**: Across all 13 documents, observed time-to-successful-Storage (via automatic retries, no manual fix) ranged ~4.1 to 27.5 minutes. The same document was the slowest case twice in a row, under two different ids — suggests some documents are consistently slower to embed/store, not pure random variance.

### 18. `client.query` also silently returns nothing without explicit `sub_tenant_id` — same trap as #14, in a second SDK method
- **Method**: SDK
- **Found**: `client.query(tenant_id=..., query=..., mode="thinking", graph_context=True)` with no `sub_tenant_id` returned `chunks: []`, `sources: []`, `query_paths: []`, despite the relevant documents confirmed `indexing_status: "completed"`.
- **Where**: `client.query`, tenant `stock-market-decoder`.
- **Severity**: Significant, same reasoning as #14. Not confirmed whether REST's equivalent (`full_recall`) has the same gap — our REST script always passed `sub_tenant_id` explicitly.
- **Resolved**: Adding `sub_tenant_id="default"` fixed it — 13 relevant chunks returned, correctly ranked, plus populated `chunk_relations`/`query_paths`.

### 19. `mode="thinking"`'s `synthesis_context` field does not reliably produce a real answer on this tenant's data
- **Method**: SDK
- **Found**: Across 6 live query attempts (3 distinct phrasings — compound, single-part date-scoped, direct factual with no date/filter language), `synthesis_context` never once produced a grounded answer: 4/6 returned a stub describing the query instead of answering it (e.g. *"The query asks for two distinct types of information... requiring a search filtered by date."*), 2/6 returned a clean `None`. This happened even with strong retrieval (up to 18 `graph_paths`, 11–13 accurate chunks) and even though `chunk_relations`/`query_paths`'s own `combined_context` fields held correct, well-grounded summaries of the same content. A separate cross-check on `sia-test` (2 clean synthetic documents, single narrative) showed the same pattern: one phrasing produced real (if incomplete — it omitted the actual causal fact present in the graph) synthesized text; a differently-worded question against the identical two documents produced the same query-paraphrase stub.
- **Where**: `client.query`, tenant `stock-market-decoder` (`data/_ingestion_results_sdk.json`) and tenant `sia-test` (`test.ipynb`).
- **Severity**: Real and reproducible, but not a broken promise — HydraDB's docs never claim `/query` returns a final answer; every official cookbook generates the answer via the caller's own LLM call over `chunks`/`graph_context`, not via `synthesis_context`. The actual issue is discoverability: `synthesis_context` sits in the response schema indistinguishable from `chunk_relations`/`query_paths`, but per its own OpenAPI field description, it's only populated for "multi-step queries with `requires_synthesis=True`" — a flag that isn't exposed as a request parameter anywhere in the public API. Full pipeline/architecture writeup in `CONTEXT_UPDATES.md`.
- **Assumption**: Our own build should not treat `synthesis_context` as the answer source. Detect null/stub and construct the answer from `chunk_relations`/`query_paths`'s `combined_context`, or — matching every official cookbook's pattern — call our own LLM over the formatted retrieval context.

### 20. `document_metadata` silently accepts the wrong shape with no validation error, resulting in permanently empty chunk metadata
- **Method**: SDK
- **Claimed**: N/A — self-diagnosed after `metadata_filters` returned zero results for every shape tried, before assuming it was a HydraDB bug.
- **Found**: Our own SDK ingestion sent `document_metadata` as a flat object (`{"doc_type": ..., "filing_date": ..., ...}`) with no `"id"`/`"metadata"` wrapper — the documented shape (`api-reference/v2/endpoint/ingest-context.md`) requires `[{"id": ..., "metadata": {...fields...}}]`. Ingestion returned `success: true` with no error or warning for the malformed shape, but every chunk's `metadata`/`additional_metadata` came back completely empty at query time — confirmed by inspecting raw chunk fields directly.
- **Where**: `client.context.ingest`, tenant `stock-market-decoder`.
- **Severity**: Moderate on HydraDB's side — a structurally-wrong-but-valid-JSON payload silently discards the metadata instead of failing validation or warning. Was Significant on our side until diagnosed, since it made every `metadata_filters` attempt look broken.
- **Resolved**: fixed the shape, re-ingested. `metadata_filters` now works exactly as documented — top-level plain key-value pairs matching `tenant_metadata_schema` (e.g. `{"filing_date": "2020-12-21"}`), confirmed for both `filing_date` and `doc_type`. A single value wrapped in a list also works (e.g. `{"filing_date": ["2020-12-21"]}`). A list of multiple *different* values does not — tested `{"filing_date": ["2022-02-05", "2022-02-08"]}` (two real dates, each individually confirmed working) and got zero chunks, vs. 4 and 3 chunks respectively for the same two dates queried separately. No "any of" / IN semantics — exact single-value match only. `timeline.py` needs one filtered call per date, merged in code, for any period with more than one real filing date.

### 21. Supplying an explicit `id` in `document_metadata` for a filename previously ingested without one creates a duplicate instead of upserting over it
- **Method**: SDK
- **Claimed**: Implicit — `upsert: true` plus deterministic filename-based ids (finding #16) should mean re-ingesting the same filename always updates the same record.
- **Found**: After fixing finding #20's metadata shape (which added an `"id"` field to `document_metadata` for the first time), re-ingesting all 13 documents did not update the existing records — it created 13 new ones, confirmed via the dashboard (26 of 26 files). The two copies of the same filename had unrelated ids: the original had an auto-assigned hash id (e.g. `fbedf8ab5ec47eba63b752842cb05d5e`), the new one had the caller-supplied id (e.g. `peloton_2022-02-08_8k`). Supplying an id sets the document's identity directly rather than being matched against whatever identity that filename already had.
- **Where**: `client.context.ingest` / `client.context.list`, tenant `stock-market-decoder`.
- **Severity**: Significant — a real trap for anyone incrementally adopting the documented `document_metadata` shape on an already-ingested tenant: correctly adding `"id"` for the first time causes silent duplication, not an update, with no error to react to.
- **Resolved**: identified and removed the 13 stale, empty-metadata copies via `client.context.list` + `client.context.delete`, keeping the 13 correctly-metadata'd ones. Not an ongoing risk going forward — now that `id` is supplied consistently every time, future re-ingestion should upsert correctly.

### 22. `mode="thinking"`'s internal reranking is measurably non-deterministic near the `max_results` boundary — a correct, relevant chunk can silently vanish across identical repeated calls
- **Method**: SDK
- **Claimed**: `essentials/v2/api-results.md`'s practical-guidance section frames `max_results` purely as a token-budget/downstream-reranking knob — *"Start small on chunks. `max_results: 10` is a reasonable default... raise to 20 if you rerank downstream."* No mention of a correctness or stability risk at low values.
- **Found**: Ran the identical `mode="thinking", max_results=10` call (`metadata_filters={"filing_date": "2022-02-05"}`) 8 times in a row. The correct source document (`peloton_2022-02-05_8k.md`) was present in only 2/8 runs, and its `relevancy_score` swung wildly across those hits (0.044 and 0.881 — not close values, a 20x spread). Raising only `max_results` to 20 (same `mode="thinking"` call, nothing else changed) fixed it 8/8, with the score stabilizing in a tight band (~0.847–0.881). Separately, switching to `mode="fast"` at the original `max_results=10` was also 8/8 stable, with the *identical* `relevancy_score` every single run (`1.4244978427886963`). This isolates the cause specifically to `thinking` mode's internal reranking step, not the underlying retrieval/embedding step, which is itself perfectly deterministic.
- **Where**: `scripts/test_chunk_retrieval_stability.py`, `data/_chunk_retrieval_stability_results.json`, tenant `stock-market-decoder`.
- **Severity**: Significant, and not merely theoretical — this caused a real, silently-wrong production output. Two consecutive `timeline.py` runs mislabeled Feb 5–7 disclosures as "February 8" because the correct 8-K vanished from the result set and only a press release (whose own byline reads "February 8, 2022" despite describing earlier events) survived. This is a correctness failure, not a token-budget inconvenience — the docs' framing of `max_results` doesn't warn a developer this could happen.
- **Assumption/resolution**: fixed via `max_results=20` for `timeline.py`'s per-date queries specifically. Not proven this fully generalizes past this dataset's scale (13 documents, single tenant) — larger corpora may need a higher threshold, or may still see boundary effects at 20. Flagging as an open risk rather than a closed one.

### 23. Chunk-level metadata field is exposed as `.metadata` on the SDK's Python object but named `additional_metadata` in the docs' own JSON schema example for the identical field
- **Method**: SDK, cross-checked against `docs.hydradb.com/essentials/v2/api-results.md`
- **Claimed**: That page's response-shape example, and its "Full flow without SDK" reference implementation, both name this field `additional_metadata` on each chunk (e.g. `chunk.get("chunk_content", "")` / `additional_metadata: {"author": "Support Team"}` in the schema sample).
- **Found**: `backend/synthesis.py` accesses the same field via `getattr(chunk, "metadata", None)` — and it works, producing correct, chunk-specific values in production (`data/timeline_cache.json`'s `doc_summaries`, e.g. *"Peloton announces agreement to acquire Precor for $420M to establish U.S. manufacturing capacity"* correctly paired with the 8-K chunk, and a distinct summary correctly paired with the press-release chunk). This confirms the SDK's Python chunk object genuinely exposes the field as `.metadata`, not `.additional_metadata` — diverging from the docs' own schema example for that same field.
- **Where**: `backend/synthesis.py` (`get_context_snippets`/`doc_summaries` logic), tenant `stock-market-decoder`.
- **Severity**: Minor — same pattern as finding #7 (`normal_collection` vs. `knowledge_collection`), and consistent with finding #9's broader point that the SDK's object shape doesn't always mirror the raw JSON shown in docs, even on the same docs page that documents the SDK usage.
