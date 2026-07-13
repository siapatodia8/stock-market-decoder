# Stock Market Decoder — Workflow Overview

An AI-powered stock event dashboard using HydraDB for retrieval and knowledge graph, and OpenAI for routing and answer synthesis. Grounds every answer about a company's key events in real SEC filings, never the model's own background knowledge.

This system has two distinct workflows: an offline ingestion/build workflow, run once to get HydraDB and the app ready, and an online chat workflow, run once per question.

---

## Ingestion & Build Workflow (offline, one-time)

Input: `data/*.md` (13 SEC filings) + `data/pton_price_history.csv`

| Step | Function | Uses HydraDB | Notes |
|---|---|---|---|
| 1. Create database | Creates the HydraDB tenant with our metadata schema | Yes | `client.databases.create()` — schema covers `doc_type`, `narrative_role`, `filing_date`, `doc_summary` |
| 2. Poll readiness | Waits for the database to be ready for ingestion | Yes | `client.databases.get()` — checks `graph_status` + `vectorstore_status` |
| 3. Ingest documents | Uploads all 13 filings as Knowledge | Yes | `client.context.ingest()`, one call per document. HydraDB internally chunks the text, embeds it (dense + sparse), and extracts entities/relationships into its knowledge graph |
| 4. Poll indexing status | Confirms every document finished indexing | Yes | `client.context.status()` — waits for `"completed"` per document |
| 5. Build event timeline | Builds the event catalog and per-event knowledge graph, cached locally | Yes | `timeline.py` — `client.query()` scoped by `filing_date` for a synthesized headline (our LLM over HydraDB's evidence), plus `client.context.relations()` for the graph. Merged with price history into `outputs/timeline_cache.json` |

Output: a fully indexed HydraDB database + `timeline_cache.json`, ready for live chat queries.

---

## Chat Workflow (online, per question)

Input: `user_question`

| Step | Function | Uses HydraDB | Notes |
|---|---|---|---|
| 1. Load event catalog | Loads the 5 events' `{event_id, dates, headline}` | No | Deterministic, reads from the cache built during setup |
| 2. Route question (Stage 1) | Scopes the question to the right event(s) | Yes | `route_via_retrieval()` — one unscoped `query()` across the whole tenant, then an LLM confirms `event_ids` from the real evidence. Stops here with "No timeline events matched" if nothing routes |
| 3. Compute price stats | Computes volatility, return, and drawdown for the matched window | No | Deterministic math over `data/pton_price_history.csv` — never from HydraDB |
| 4. Retrieve evidence (Stage 2) | Pulls the real filing text for the matched event(s) | Yes | `retrieve_for_events()` — scoped `query()` per event via `metadata_filters={filing_date}`. Stops here with "no evidence" if nothing returns |
| 5. Synthesize answer (Stage 3) | Generates the grounded, cited answer | No (LLM only) | `synthesize_answer()` — an OpenAI call over `chat_answer.yaml`, grounded in HydraDB's evidence plus the price context from step 3 |

Output: a grounded answer, cited sources, and price stats.

---
