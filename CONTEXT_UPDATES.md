# Context Updates — Amendments to Original Proposal Docs

The original context package (`01_hydradb_product_and_claims.md`, `02_hackathon_task_brief.md`,
`03_project_stock_explainer.md`, `04_peloton_data_sources.md`) is stored read-only in Claude.ai
project knowledge and can't be edited directly. This file is the living addendum — only
corrections, confirmations, and process decisions made *after* those docs were written.
Treat this file as an update layer on top of the originals, not a replacement.

---

## Corrections to `01_hydradb_product_and_claims.md`

**Relationship type count**: original notes said five types (Entity, Temporal, Semantic,
Causal, World). Confirmed against the current live homepage architecture diagram
(hydradb.com) that there are only **four** relationship types: Entity, Temporal, Semantic,
Causal. "World" is not a relationship type — it's grouped separately with "Experience,
Opinion, Observation" as a *memory content* category. Still needs empirical confirmation
once real queries return `relation.canonical_predicate` values.

**Versioning claim — real tension found, not yet resolved**: marketing claims "Git-style
temporal versioning... append-only... not silently overwritten" (homepage + blog post
"Agents Are Just State Machines"). But the actual technical docs
(`docs.hydradb.com/essentials/v2/knowledge.md`) describe Knowledge mutability as "replaced
or deleted explicitly," and `POST /context/ingest`'s `upsert` parameter defaults to `true`
— replacing existing sources with the same ID, not versioning them. Setting `upsert: false`
doesn't add versioning either; it just errors on conflict. Also, HydraDB's own blog admits
"a SQL-like queryable interface for these axes [transaction time / valid time] isn't shown
in public docs." **Do not assume either claim is true — this needs direct hands-on testing
(task #17), not doc-reading.**

**Live REST field/endpoint names** (confirmed 2026-07-11 against
`docs.hydradb.com/api-reference/endpoint/*`, used throughout
`scripts/setup_and_ingest.py`): `tenant_id`/`sub_tenant_id` are the correct field
names — no `database`/`collection` alias exists on this REST surface. Create:
`POST /tenants/create`. `tenant_metadata_schema` is a **list** of field-definition
objects (`name`, `data_type`, `max_length`, `enable_match`,
`enable_dense_embedding`, `enable_sparse_embedding`, `nullable`), not a dict.
Readiness: `GET /tenants/infra/status` → `infra.scheduler_status` /
`infra.graph_status` (booleans) + `infra.vectorstore_status` (2-item array,
order corrected in findings log #2: `[0]`=Knowledge, `[1]`=Memories). Ingestion:
`POST /ingestion/upload_knowledge`, multipart fields `files` + `file_metadata`,
each metadata entry keyed `file_id`. Status: `POST /ingestion/verify_processing`
(POST with query params, no body) → `source_id`/`indexing_status`.

**SDK vs. REST are two structurally different interfaces**, not just differently-named
wrappers around one schema — different namespaces, param names, response field
names, and in one case a different response shape (`vectorstore_status` is an
array in REST vs. a named `{knowledge, memories}` object in the SDK). Full detail
in findings log #9. E6001 (see #4) was originally hoped to be REST-specific but
also occurred under SDK ingestion of the same tenant (findings #15/#17) — so
switching to the SDK fixed the retry-gets-stuck-forever failure mode (#11), not
E6001 itself, which resolves via patience regardless of client library.

**HydraDB MCP server — decided not to use it**: exists at `docs.hydradb.com/plugins/mcp.md`,
but all 7 of its tools are scoped to `/memories/*` endpoints only (store, search, list,
delete, fetch, ingest_conversation). No tool for creating a database, uploading Knowledge
documents, or running graph-aware `/query` with `type=knowledge`. Since this build is
Knowledge-only, the MCP doesn't cover what we need — using the SDK/API directly instead.

**v1→v2 method table exists** (`docs.hydradb.com/api-reference/v2/sdks`) — it's a pure
renaming map (e.g. `client.upload.knowledge()` → `client.context.ingest(type="knowledge")`),
not a bug-fix changelog. Useful for one thing: before logging anything to the findings log
as a "HydraDB bug," confirm we're calling the current v2 method/field names first — some of
the earlier-noted inconsistencies (two SDK package names, `tenant_id` vs `database`) may
just be v1/v2 naming coexistence, not real defects.

---

## Pipeline structure — how HydraDB's query flow actually works (confirmed via docs research)

Added after a deep-dive into `docs.hydradb.com` narrative docs (`essentials/v2/query.md`,
`essentials/v2/semantic-search.md`, `essentials/v2/context-graphs.md`,
`essentials/v2/api-results.md`), the raw OpenAPI spec embedded in
`api-reference/v2/endpoint/query.md`, and end-to-end reads of 3 official cookbooks
(AI Financial Analyst, Perplexity for Internal Knowledge, Cursor for Docs). This
directly informs/supersedes the informal architecture description in
`01_hydradb_product_and_claims.md` — HydraDB is retrieval + relationship infrastructure
only; it does not generate final answers. Everything past retrieval is our own backend's
job. Four stages:

**Stage 1 — Ingestion (write path)**
1. App calls `POST /context/ingest` (`client.context.ingest()`) with `tenant_id`,
   `sub_tenant_id`, `type` (`"knowledge"`/`"memory"`), the file(s), optional
   `document_metadata`.
2. HydraDB returns per-document `id`s with `status: "queued"` immediately — async, not
   synchronous.
3. Each doc moves through: Parsing (extract raw text) → Chunking (split into
   `chunk_content` units) → two parallel branches:
   - **Graph branch**: an LLM extracts entities/relationships per chunk, written as
     triplets (`source → relation → target`) to the graph store.
   - **Vectorisation branch**: each chunk is embedded and written to the vector store.
4. Both branches must finish before status flips to `"completed"` (queryable once it
   reaches at least `graph_creation`, per `query.md`'s common-mistakes table).
5. App polls `GET /context/status` (`client.context.status()`) with `tenant_id` +
   `sub_tenant_id` + `ids` until `indexing_status == "completed"` for every doc.
   **Must pass `sub_tenant_id` explicitly — omitting it silently misses real indexed
   docs (finding #14).**

**Stage 2 — Query / retrieval (read path)**
6. App calls `POST /query` (`client.query()`) with `query`, `type`
   (knowledge/memory/all), `query_by` (hybrid/text), `mode` (fast/thinking),
   `max_results`, `alpha`, `graph_context`. **`sub_tenant_id` must be passed explicitly
   here too — same silent-miss trap (finding #18).**
7. Retrieval runs: `query_by="hybrid"` blends semantic (embedding) + BM25 keyword search
   per the `alpha` weight (`1.0`=pure semantic, `0.0`=pure BM25, default `0.8`);
   `query_by="text"` is BM25-only, paired with `operator` (or/and/phrase).
8. Results return ranked by `relevancy_score` as `chunks[]` (retrieved text) and
   `sources[]` (deduplicated document-level info). Per `semantic-search.md`, verbatim:
   *"`POST /query` returns ranked chunks and source metadata, not an answer."*
9. If `graph_context: true` (default), HydraDB separately traverses the graph store for
   how retrieved chunks connect — to the query (`query_paths`) and to each other
   (`chunk_relations`) — each a structured triplet list with `relevancy_score` and a
   `combined_context` summary string. Empty arrays are normal, not an error, when no
   relationships exist for that result set.
10. If `mode="thinking"`: multi-query expansion (question broken into sub-queries) +
    reranking + `query_forceful_relations` (author-declared related sources) pulled into
    `additional_context`. `mode="fast"` (default) is single-pass, shallower graph slice,
    lower latency. **A third value, `mode="auto"`, exists in the Python SDK's type hint
    (`Literal['fast','thinking','auto']`) but is undocumented in both narrative docs and
    the OpenAPI `RetrieveMode` enum (only `fast`/`thinking` listed there); tested in
    `sia-test` and behaved identically to `"fast"` (`synthesis_context: None`).**
10a. **`max_results` is not just a token-budget knob under `mode="thinking"`.**
    `essentials/v2/api-results.md`'s practical-guidance section frames it purely as
    that — *"Start small on chunks... raise to 20 if you rerank downstream"* — but
    hands-on testing found `mode="thinking"`'s internal reranking step is genuinely
    non-deterministic near the `max_results` boundary: a correct, relevant chunk was
    present in only 2/8 identical repeated calls at `max_results=10`, vs. 8/8 at
    `max_results=20` or under `mode="fast"` (see finding #22). This caused a real
    wrong-date attribution in `timeline.py`'s output before being caught. Treat
    `max_results` as a correctness lever under `thinking` mode, not only a budget one.

11. Occasionally, when HydraDB's internal (non-configurable) classifier decides a query
    needed multi-step decomposition, `graph_context.synthesis_context` gets populated —
    per its OpenAPI field description: *"LLM-generated summary of how sub-query results
    connect, present only for multi-step queries with `requires_synthesis=True`."*
    `requires_synthesis` is not an exposed request parameter anywhere in the API. This
    field is not a supported "get an answer" mechanism — see finding #19 for the full
    empirical writeup (6 live test attempts) and the corrected framing below.
12. Full response returned: `chunks`, `sources`, `graph_context`, `additional_context`.
    This is the end of what HydraDB does — it has handed over evidence, not an answer.

**Stage 3 — App-layer synthesis (entirely our backend's job, not HydraDB's)**
13. Backend formats the raw JSON into an LLM-ready text block — via HydraDB's own
    `build_string()`/`buildString()` helper, or a custom formatter. **We use a custom
    formatter (`synthesis.get_context_snippets()`), not `build_string()`, by deliberate
    choice**: `build_string()` preserves server order and formats `chunks` and
    `graph_context` as separate sections, but our Aug-2021 fallback bug (a single weak
    `chunk_relations` snippet silently blocking a stronger fact sitting in a raw chunk —
    see synthesis.py's docstring) needed the two pools unioned and ranked together by
    `relevancy_score`. This is a knowing deviation from `api-results.md`'s stated common
    mistake ("re-sorting chunks client-side overrides HydraDB's ranking") — justified here
    because we're not re-sorting one HydraDB-ranked list, we're merging two differently-
    sourced pools (raw chunks + relation `combined_context` strings) that don't share one
    native order to begin with. Also confirmed (finding #23) that the SDK's chunk object
    exposes metadata as `.metadata`, not the `additional_metadata` name shown in that
    page's own JSON schema example.
14. Backend builds a prompt: grounding system instruction ("answer only from the
    provided context; say so if it isn't there") + formatted context + the question.
15. Backend calls its own LLM (every cookbook uses GPT-4o via
    `openai_client.chat.completions.create(...)`; could be any model).
16. The LLM writes the actual natural-language answer — this is the *only* point in the
    entire pipeline where an answer is generated, and it's the app's model doing it, not
    HydraDB's. Confirmed identically across all 3 cookbooks read end-to-end; one
    (Cursor for Docs) states this explicitly: *"HydraDB is the memory layer... GPT-4o is
    the reasoning layer... The two layers are intentionally separate."*
17. Backend returns the answer to the user.

**Stage 4 — Our project's added layer (not part of HydraDB's docs, our own design)**
18. Because the 4th dashboard component is a "show your work" chatbot, we don't just
    return the final answer from step 16 — we also return the evidence that produced it
    (retrieved chunks, graph triplets, query parameters used) so the UI can render
    retrieval → relationships → answer as one visible chain instead of a black box. This
    is exactly what `chunks`/`chunk_relations`/`query_paths`'s structured shape is built
    to support.

**Corrected framing on `synthesis_context` (supersedes the framing in finding #19 as
originally written)**: it is not a broken/failed feature — HydraDB never claims to
generate final answers, so nothing was promised and broken. The real, defensible
critique is discoverability: the field sits in the response schema next to
`chunk_relations`/`query_paths` with no signal it's a different category of thing (an
internal, non-requestable, best-effort byproduct vs. a reliable structured result). The
one sentence that would set correct expectations (`requires_synthesis=True`, multi-step
queries only, not developer-settable) exists in exactly one place across the whole
docs site — the raw OpenAPI schema block appended to the bottom of one reference page —
not in either narrative page that discusses the field. A developer reading the docs
top-to-bottom would never see it.

---

## Confirmed / reinforced from `03_project_stock_explainer.md` (no contradiction, added reasoning)

**Knowledge-only decision reinforced with deeper reasoning**: Memories' ingestion path only
accepts raw text or conversation pairs (no document/file parsing), and its `infer: true`
extraction is built to pull personal preference signals from raw behavioral input — not
structured facts from a legal filing. Using Memories for our filings would test the wrong
mechanism entirely, not just be unnecessary scope. Keeping it as the stated "growth path"
answer if asked (multi-user personalization), not part of the current build.

---

## Process decisions made this session (new, not in original docs)

**Data ingestion phasing** (narrower and more sequenced than the original "~15-20 docs at
once" framing):
- **Phase 1**: SEC 8-Ks + their bundled exhibits (press releases are Exhibit 99.1 within
  the same 8-K filing — no separate scraping needed, same pull).
- **Phase 2**: yfinance price series — included early (not deferred) specifically to test
  whether HydraDB's graph does anything meaningful with numeric time-series data, rather
  than assuming it's purely a frontend-only concern.
- **Phase 3**: Wikipedia page — sequenced last for build convenience, but explicitly
  flagged as not to be dropped if time runs short, since cross-style entity resolution
  (8-K vs. encyclopedia) is the single highest-priority "break it" test per the original
  proposal.

**Repo set up**: GitHub repo `siapatodia8/stock-market-decoder` created and cloned to
`/Users/siapatodia/Desktop/stock-market-decoder` (the actual project working folder,
doubling as the project name). On `main`, clean tree as of setup.

**HydraDB API key created**, named `sia-test` in the dashboard.

**Findings log started**: `hydradb_findings_log.md` in this repo. Policy — only log
confirmed hands-on findings from actual API testing; doc-research observations (the
corrections above) stay here in this file / in conversation until verified against the
real API, not logged as confirmed bugs prematurely.

**Task tracking**: full task checklist maintained via the task tool, covering setup →
data collection → ingestion → build → deliberate break-testing → polish → submission,
plus a standing task to keep this log updated throughout.

---

## Operating constraint: sandbox can't reach api.hydradb.com
The sandboxed shell's network proxy returns 403 on the CONNECT tunnel to
`api.hydradb.com` — not an allowlisted domain here — so any script that calls the
live HydraDB API (`scripts/setup_and_ingest.py`, `scripts/setup_and_ingest_sdk.py`)
must be run locally, not from the sandbox:
```
cd ~/Desktop/stock-market-decoder && pip install requests python-dotenv hydradb-sdk && python3 scripts/setup_and_ingest_sdk.py --step <step>
```
