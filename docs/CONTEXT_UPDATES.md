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

**REST-specific notes and the REST-vs-SDK comparison removed (2026-07-13)**: this
project only builds and tests against the HydraDB Python SDK.
`scripts/setup_and_ingest.py` (the REST setup script) was deleted, and the
REST-only findings/comparison that depended on it were removed from
`hydradb_findings_log.md` — most turned out to be mistakes in how the REST
calls were formed on our side, not confirmed HydraDB defects, and a
REST-vs-SDK comparison isn't in scope for this build. See that file's header
note for the old→new finding-number mapping if cross-referencing an older copy
of either doc.

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
   docs (finding #4).**

**Stage 2 — Query / retrieval (read path)**
6. App calls `POST /query` (`client.query()`) with `query`, `type`
   (knowledge/memory/all), `query_by` (hybrid/text), `mode` (fast/thinking),
   `max_results`, `alpha`, `graph_context`. **`sub_tenant_id` must be passed explicitly
   here too — same silent-miss trap (finding #8).**
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
    `max_results=20` or under `mode="fast"` (see finding #12). This caused a real
    wrong-date attribution in `timeline.py`'s output before being caught. Treat
    `max_results` as a correctness lever under `thinking` mode, not only a budget one.

11. Occasionally, when HydraDB's internal (non-configurable) classifier decides a query
    needed multi-step decomposition, `graph_context.synthesis_context` gets populated —
    per its OpenAPI field description: *"LLM-generated summary of how sub-query results
    connect, present only for multi-step queries with `requires_synthesis=True`."*
    `requires_synthesis` is not an exposed request parameter anywhere in the API. This
    field is not a supported "get an answer" mechanism — see finding #9 for the full
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
    native order to begin with. Also confirmed (finding #13) that the SDK's chunk object
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

**Corrected framing on `synthesis_context` (supersedes the framing in finding #9 as
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

## Known limitations / future considerations (not fixed now, noted for later)

**Chat scoping was headline-limited, not document-limited — since fixed.**
This limitation described the original stage 1, `orchestrator.classify()`:
its whole view of "what happened when" was `load_event_catalog()`'s compact
`{event_id, dates, headline}` list, never full document content, so a
question with no vocabulary overlap against any headline risked routing to
the wrong event (or none) even when the correct event's documents actually
contained the answer. This surfaced directly during this rerun's
boundary-ambiguity investigation (`tests/test_orchestrator.py`'s "leadership
changes" case). It is no longer the current behavior — see "Orchestrator
redesign" below: `chat.py`'s stage 1 now calls `retrieval_router.
route_via_retrieval()`, which routes from real retrieved document excerpts,
not headlines. `orchestrator.classify()` still exists and is still
independently tested, but only as a kept-for-reference fallback, not what the
live app calls. Left here for historical context on why the redesign
happened, not as a description of present-day behavior.

**`query_by`/`alpha`/`operator` are entirely untested in this project.** Confirmed via
a repo-wide grep — every `client.query()` call this whole project (this rerun and the
original build) only ever sets `tenant_id`/`database`, `sub_tenant_id`, `query`, `mode`,
`graph_context`, `max_results`, `metadata_filters`. `query_by` (`hybrid`/`text`),
`alpha` (semantic/BM25 blend weight), and `operator` (`or`/`and`/`phrase`, `text` mode
only) have never been explicitly set anywhere, so every query has run on whatever
HydraDB defaults to when those fields are omitted entirely (docs claim `hybrid`,
`alpha=0.8` — never independently verified, since no response field echoes back which
values the server actually used). Not pursued as a fix for anything — every answer
fact-checked this rerun has been accurate, and the one known retrieval instability
(finding #12) traces to `mode="thinking"`'s reranking step, a separate mechanism these
params don't touch. Documented as a genuine open testing-coverage gap, not an active
problem.

---

## Orchestrator redesign — retrieval-grounded hybrid routing adopted, replacing headline-only classify()

Follow-up to the "Chat scoping is headline-limited" limitation noted above. Two
experiments (both app-layer investigations — not HydraDB bugs, not logged to
`hydradb_findings_log.md`/`_index.csv` per this project's logging policy of
HydraDB-attributable findings only) tested whether HydraDB's own "function
routing via retrieval" pattern (register candidates as knowledge objects,
route by calling `query()` and reading off the top match — see the cookbook
"AI Chief of Staff - Function Routing") could replace or improve on
`orchestrator.classify()`.

**Experiment 1 — pure retrieval over headline-only "event cards"**
(`tests/test_retrieval_based_routing.py`): ingested each catalog entry's
headline + dates as its own tiny document in an isolated collection, routed
by `query()` ranking alone, no LLM classification at all.
- Clean on straightforward on-topic questions (single/multi/comparative) —
  real score margins between the correct match and the runner-up.
- Cannot do boundary/exclusion logic. "Before the CFO transition" scored the
  CFO-transition event itself *highest* (most semantically similar to its own
  name), not lowest — a structural mismatch between similarity ranking and
  date-window exclusion, not a prompting/tuning problem.
- No native off-topic rejection. Retrieval always ranks all candidates;
  off-topic questions showed a much tighter score spread (within 0.009 across
  all 5 cards) and a lower absolute top score than any real question — a
  usable heuristic threshold, but hand-tuned, not a clean instruction the way
  `classify()`'s relevance gate is.
- Failed on purely numeric/non-thematic questions (e.g. "how much was the
  capex cut by") — later shown to be an artifact of the headline-only proxy
  lacking the fact at all, not a retrieval limitation (see experiment 2).
- Embeddings themselves carry real-world/background knowledge: a question
  describing Precor by its actual business (commercial fitness equipment,
  gyms, hotels) matched the Dec-2020 card cleanly despite zero lexical
  overlap with its headline text. Switching to retrieval doesn't eliminate
  reliance on outside/background knowledge — it just relocates where that
  knowledge lives, from the LLM's weights to the embedding model's.

**Experiment 2 — hybrid: real full-corpus retrieval + LLM confirmation over
actual excerpts** (`tests/test_retrieval_llm_hybrid.py`,
`backend/prompts/retrieval_router.yaml`): one unscoped `query()` per question
across the real 13-document corpus (no `metadata_filters`, `max_results=20`),
chunks mapped back to event_id via their real `filing_date`, grouped into a
compact evidence block, then a lightweight LLM step confirms `event_ids` +
`query_type` from the real excerpts instead of a bare headline.
- Fixed both real-content failures from experiment 1: the CEO-name question
  (the real 8-K/PR literally names Rob Barker) and the capex question (the
  real restructuring PR literally states the $150M figure) both now route
  correctly.
- At this corpus's scale (13 documents), unscoped retrieval doesn't actually
  filter anything — every question's candidate list was all 5 events, every
  time. All real discrimination happens in the LLM step reading the top-2
  excerpts per event, not in retrieval's own ranking/exclusion. This
  experiment can't speak to retrieval's filtering power at a larger corpus
  scale.
- No cap on how many events can be returned — confirmed via 3 added cases
  (an explicit 3-item multi question, a 3-way comparative, and the "whole
  story" 5-event case), all passed cleanly.
- Boundary/range logic still fails without explicit rules, and this is a
  real recall miss, not harmless over-inclusion: "before the CFO transition"
  returned `['2022-02', '2022-06']`, missing `2020-12` — the anchor's own
  reasoning shows why ("...indicated by the events in June 2022 and February
  2022"), i.e. it narrowed to the events adjacent to the anchor instead of
  computing the true earlier window. Decided not to fix now (see decision
  below) — left as a known, documented gap.
- Final tally: 10/11 cases pass; the one fail is the boundary case above.

**Decision**: the hybrid approach (real-corpus retrieval + LLM confirmation
over actual excerpts) is adopted as this project's orchestrator, superseding
pure headline-only `classify()`. This is defensible specifically because
`chat_answer.yaml`'s synthesis-stage grounding rule ("if the context doesn't
contain enough information, say so plainly") already absorbs the routing
stage's imprecision — over-inclusion at the routing stage costs nothing once
synthesis is disciplined about what it will and won't answer from. The
known boundary/range gap is accepted as-is, not fixed, per the same
reasoning: over-inclusion there is tolerable, and the one observed failure
was under-inclusion on a case type (range/before-after) that's explicitly
not a hard requirement for this redesign.

**Wired in and validated.** `backend/retrieval_router.py` (new module) implements
`route_via_retrieval()` — one unscoped `query()` across the real tenant,
chunks mapped to event_id via a new live lookup
(`hydradb_client.filename_to_filing_date()`, same `context.list()`-based
pattern as the existing `source_id_map()`), evidence grouped and fed to
`retrieval_router.yaml`. `backend/chat.py`'s stage 1 now calls this instead
of `orchestrator.classify()`; `orchestrator.py` is untouched and kept as the
prior approach (its own docstring now says so explicitly), still independently
tested by `tests/test_orchestrator.py` and `tests/test_prompt_grounding.py`.

`chat_answer.yaml` went through one more round after the initial rewrite:
reverted to the original, simpler wording (it "worked well," per direct
feedback) plus exactly one addition — a `{company}`/`{industry}`-templated
grounding line matching `timeline_event.yaml`'s existing style (`synthesis.py`
gained `COMPANY_NAME`/`COMPANY_INDUSTRY` constants, same values `timeline.py`
already uses, to fill it). A further split into "not relevant" (off-topic) vs.
"not in the available data" (on-topic-but-thin) was added, then the "not
relevant" half was removed again after `tests/test_chat_answer_wording.py`
proved it was dead code: `chat.py` short-circuits before synthesis ever runs
whenever stage 1 returns empty `event_ids`, so an off-topic question always
surfaces `chat.py`'s own hardcoded warning string, never that branch of the
LLM prompt. Final prompt carries only the "not in the available data"
instruction.

Every test file touching either change was re-validated or fixed:
`tests/test_orchestrator.py` (boundary-rule regression from de-hardcoding,
fixed by replacing the deleted worked example with an abstract step-by-step
procedure — 8/8 clean); `tests/test_prompt_grounding.py` (Section B's
`REFUSAL_MARKERS` list didn't include the new "not in the available data"
wording — a real bug, silently would have reported correct refusals as
failures — fixed); `tests/test_retrieval_llm_hybrid.py` (refactored to import
and call the real `retrieval_router.route_via_retrieval()` instead of a
pre-wiring local reimplementation, removing a silent-drift risk — re-run
confirmed identical 10/11 result, same known boundary gap); `tests/test_chat.py`
(one case reclassified `known_gap`, not graded strictly, for the same
boundary limitation surfacing through the real pipeline); `tests/test_chat_e2e.py`
(docstring/comments corrected to describe `retrieval_router` instead of
`classify()`; re-run confirmed all `forbidden` assertions still hold under
the new pipeline — no relaxation needed after all).

**Live UI validation, one open anomaly, and an empirical stability check.**
5 prompts tested live in the built UI: on-topic single-event, cross-event
comparative (with price stats and merged sources), off-topic rejection, and
an undisclosed-detail refusal all behaved exactly as expected. One anomaly:
"How much did Peloton cut its planned capital spending by in early 2022?"
answered "It's not in the available data" on first ask, even though the
correct source document was listed among the retrieved sources and the same
fact had just been correctly cited in the preceding comparative answer;
re-asking the identical question moments later answered it correctly. Same
question, same code, two different outcomes on consecutive runs — a
live, user-facing repro of finding #12 (`mode="thinking"` reranking
non-determinism) via the real production path, not just an isolated
diagnostic. To measure this more rigorously, `tests/
test_chat_answer_stability.py` ran 5 questions × 5 runs each (25 total
`chat.run_chat()` calls) — 4 targeting facts confirmed (via
`outputs/timeline_cache.json`'s own chunk_id evidence) to live in the late
chunks of the two genuinely multi-chunk long documents in this corpus (the
two shareholder letters), plus the original capex question for direct
comparison. Result: 25/25 correct, zero refusals, zero fabrications. This is
explained, not contradicted, by finding #12: both HydraDB-touching stages of
the real pipeline (`retrieval.py`'s stage 2, `retrieval_router.py`'s stage 1)
already call `query()` at `max_results=20`, the value finding #12's own
diagnostic (`test_chunk_retrieval_stability.py`) showed eliminates the
instability that's present at the smaller default of 10. So this confirms
the app's existing mitigation holds under real load — it does not prove the
live anomaly can't recur; a lower-probability instability could still post a
clean batch by chance, and the dataset here is small (13 documents). A
larger corpus with more documents and longer documents would be expected to
make this instability more evident, not less — worth stating plainly in the
final findings write-up rather than treating 25/25 as closing the question.

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
live HydraDB API (`scripts/setup_and_ingest_sdk.py`)
must be run locally, not from the sandbox:
```
cd ~/Desktop/stock-market-decoder && pip install requests python-dotenv hydradb-sdk && python3 scripts/setup_and_ingest_sdk.py --step <step>
```

## Operating constraint: sandbox can't reach registry.npmjs.org either
Same shape of restriction as the HydraDB one above — `npm create vite@latest` /
`npm install` inside the sandbox both 403 (`blocked-by-allowlist`). `frontend/`'s
scaffold files (`package.json`, `vite.config.js`, `index.html`, `src/*.jsx`) were
therefore hand-written directly rather than generated via `npm create vite`. Run
locally to actually install and start it:
```
cd frontend && npm install && npm run dev
```
The frontend also needs the backend running locally at the same time (separate
terminal, `cd backend && uvicorn main:app --reload --port 8000`) — `App.jsx` calls
`http://localhost:8000` directly, matching `main.py`'s CORS allowlist for
`http://localhost:5173` (Vite's default port).
