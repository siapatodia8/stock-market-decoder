"""
Chat pipeline — composes the three stages into one call.

    run_chat(question)
        1. retrieval_router.route_via_retrieval -> {query_type, event_ids}
           (real HydraDB evidence + a lightweight LLM confirmation step)
        2. retrieval.retrieve_for_events -> scoped evidence bundle (HydraDB)
        3. synthesis.synthesize_answer   -> grounded answer      (our LLM)

This is the scoped replacement for /api/chat's old single unscoped
whole-tenant query (see docs/findings/query_and_retrieval_quality.md for the
reranking-instability finding this avoids). Scope is decided by stage 1 and
enforced by stage 2's metadata_filters — never by a blind tenant-wide retrieval.

Division of labour, to keep it honest: HydraDB stores/relates/retrieves
(stages 1 and 2 both touch it now). It does NOT generate the answer — stage
3, our own LLM over what HydraDB returned, does. Stage 1 used to be pure
app-layer routing over a headline-only catalog (orchestrator.classify(),
never touched HydraDB) — redesigned (see docs/workflow_overview.md):
headline-only routing couldn't ground on facts absent from the one-line
headline, so stage 1 now runs one unscoped
HydraDB query() first and has an LLM confirm event_ids/query_type from the
real retrieved excerpts. orchestrator.classify() is kept in the codebase as
the prior approach, not called here.

Fallbacks are explicit and never silently widen scope:
  - can't route (no key / empty question) -> no answer + warning
  - routed but no events matched           -> no answer + warning
  - evidence retrieved but synthesis empty  -> no answer + warning
Each returns a structured result with answer=None and answer_source="none",
so the caller/UI can show why nothing came back instead of a blank reply.
"""
from typing import Optional

import orchestrator
import price_stats
import retrieval
import retrieval_router
import synthesis


def run_chat(question: str, catalog: Optional[list] = None,
             mode: str = "thinking", max_results: int = retrieval.MAX_RESULTS) -> dict:
    """Runs the full scoped chat pipeline and returns:

        {
          "question": str,
          "query_type": str | None,     # single | multi | comparative | range
          "event_ids": [str],
          "filing_dates": [str],
          "reasoning": str,             # orchestrator's one-line scope rationale
          "answer": str | None,
          "answer_source": "llm_synthesis" | "none",
          "chunks": [...],              # raw SDK objects, merged + deduped
          "chunk_relations": [...],
          "query_paths": [...],
          "per_date": [...],            # per-event evidence, for provenance
          "warning": str | None,
        }
    """
    catalog = catalog if catalog is not None else orchestrator.load_event_catalog()

    base = {
        "question": question,
        "query_type": None,
        "event_ids": [],
        "filing_dates": [],
        "reasoning": "",
        "answer": None,
        "answer_source": "none",
        "chunks": [],
        "chunk_relations": [],
        "query_paths": [],
        "per_date": [],
        "price_window": None,   # (start_date, end_date) the price stat covers
        "price_stats": None,    # computed from the price CSV, not HydraDB
        "warning": None,
    }

    # Stage 1 — scope, via real retrieved evidence + LLM confirmation
    # (retrieval_router.py) — see chat.py's module docstring for why this
    # replaced the old headline-only orchestrator.classify().
    scope = retrieval_router.route_via_retrieval(question, catalog=catalog)
    if scope is None:
        base["warning"] = ("Couldn't interpret the question (or no OpenAI key set). "
                           "Try naming a company event or a time period.")
        return base

    base["query_type"] = scope["query_type"]
    base["event_ids"] = scope["event_ids"]
    base["reasoning"] = scope["reasoning"]

    if not scope["event_ids"]:
        base["warning"] = "No timeline events matched this question."
        return base

    # Price stats — independent of HydraDB. Derive a continuous window from the
    # scoped events (extending to the boundary event for "before/after X" ranges)
    # and compute volatility/return/drawdown from the price CSV. Attached
    # regardless of retrieval outcome; single-event windows yield None.
    window = price_stats.derive_price_window(
        scope["query_type"], scope["event_ids"], catalog
    )
    stats = price_stats.compute_stats(*window) if window else None
    base["price_window"] = list(window) if window else None
    base["price_stats"] = stats
    price_context = price_stats.describe(stats)

    # Stage 2 — scoped retrieval.
    bundle = retrieval.retrieve_for_events(
        question, scope["event_ids"], catalog=catalog,
        max_results=max_results, mode=mode,
    )
    base["filing_dates"] = bundle["filing_dates"]
    base["chunks"] = bundle["chunks"]
    base["chunk_relations"] = bundle["chunk_relations"]
    base["query_paths"] = bundle["query_paths"]
    base["per_date"] = bundle["per_date"]

    if not (bundle["chunks"] or bundle["chunk_relations"] or bundle["query_paths"]):
        base["warning"] = "The matched events returned no evidence from HydraDB."
        return base

    # Stage 3 — synthesis (our LLM over HydraDB's evidence + price context).
    answer = synthesis.synthesize_answer(
        question,
        chunks=bundle["chunks"],
        chunk_relations=bundle["chunk_relations"],
        query_paths=bundle["query_paths"],
        price_context=price_context,
    )
    if answer:
        base["answer"] = answer
        base["answer_source"] = "llm_synthesis"
    else:
        base["warning"] = "Evidence was retrieved but synthesis failed — check OPENAI_API_KEY."

    return base
