"""
Chat stage 2 — scoped retrieval.

Takes the event_ids the orchestrator (stage 1) selected and pulls the evidence
for exactly those events from HydraDB — one metadata_filters-scoped query per
filing_date — then merges the results into a single bundle for synthesis.

This reuses timeline.py's proven per-date fan-out pattern instead of the
unscoped whole-tenant query the current /api/chat still uses (that unscoped
shape is the instability documented as finding #12).

Constraints this respects, both already established in the findings log:
  - metadata_filters is exact-match on a single filing_date (finding #10), so
    we fan out one query per date and merge — never one range query.
  - max_results=20, not the default 10: thinking-mode reranking drops real
    chunks near the ranking boundary at 10 (test_chunk_retrieval_stability.py
    saw 2/8 hits at 10 vs 8/8 at 20).

Difference from timeline.py: the query text here is the USER'S actual question,
so ranking within each scoped document set reflects what they asked. Scope
still comes only from metadata_filters — never from naming events in the query
text.

HydraDB retrieves; it does not answer. The returned bundle (merged chunks +
graph relations) is what synthesis.py turns into an answer downstream.
"""
import json
from typing import Optional

import hydradb_client
import orchestrator

MAX_RESULTS = 20  # see module docstring / test_chunk_retrieval_stability.py


def _dump(obj):
    return obj.model_dump() if hasattr(obj, "model_dump") else obj


def _dedupe(items: list) -> list:
    """Same content-hash dedupe timeline.py uses, so a chunk retrieved under
    two different date-scoped queries isn't double-counted after merge."""
    seen = set()
    unique = []
    for item in items:
        key = json.dumps(_dump(item), sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def event_dates(event_ids: list, catalog: Optional[list] = None) -> list:
    """Maps orchestrator event_ids to the sorted, de-duplicated list of
    filing_dates to actually query. Deterministic — no network. An unknown
    event_id contributes no dates (it's silently skipped, since the
    orchestrator already validates ids against the catalog)."""
    catalog = catalog if catalog is not None else orchestrator.load_event_catalog()
    by_id = {e["event_id"]: e["dates"] for e in catalog}
    dates = set()
    for eid in event_ids:
        dates.update(by_id.get(eid, []))
    return sorted(dates)


def retrieve_for_events(question: str, event_ids: list,
                        catalog: Optional[list] = None,
                        max_results: int = MAX_RESULTS,
                        mode: str = "thinking") -> dict:
    """Runs one scoped HydraDB query per filing_date behind the given events
    and merges the evidence.

    Returns a bundle:
        {
          "question": str,
          "event_ids": [str],
          "filing_dates": [str],
          "per_date": [ {"date", "chunks", "chunk_relations", "query_paths"} ],
          "chunks": [merged, deduped],          # raw SDK chunk objects
          "chunk_relations": [merged],          # raw SDK relation objects
          "query_paths": [merged],              # raw SDK path objects
        }

    per_date keeps each date's evidence separate (useful for provenance and
    for anchoring synthesis chronologically); the flat merged lists plug
    straight into synthesis.synthesize_answer(). Empty event_ids yields an
    empty bundle — the caller decides the fallback (e.g. ask the user to
    rephrase), this module does not silently widen the scope."""
    dates = event_dates(event_ids, catalog=catalog)

    per_date = []
    all_chunks, all_relations, all_paths = [], [], []
    for date in dates:
        data = hydradb_client.query(
            question,
            mode=mode,
            max_results=max_results,
            metadata_filters={"filing_date": date},
        )
        chunks = data.chunks or []
        gc = data.graph_context
        relations = gc.chunk_relations if gc and gc.chunk_relations else []
        paths = gc.query_paths if gc and gc.query_paths else []

        per_date.append({
            "date": date,
            "chunks": chunks,
            "chunk_relations": relations,
            "query_paths": paths,
        })
        all_chunks += chunks
        all_relations += relations
        all_paths += paths

    return {
        "question": question,
        "event_ids": list(event_ids),
        "filing_dates": dates,
        "per_date": per_date,
        "chunks": _dedupe(all_chunks),
        "chunk_relations": _dedupe(all_relations),
        "query_paths": _dedupe(all_paths),
    }
