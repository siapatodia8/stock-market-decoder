"""
Builds the full monthly timeline (Dec 2020 - May 2024): every month gets a
real price % change, and any month with a real filing_date also gets a
synthesized event summary from HydraDB. Writes the result to
outputs/timeline_cache.json. Run standalone to (re)build the cache; the
/api/timeline endpoint just reads the cached file.
"""
import json
from pathlib import Path

import hydradb_client
import knowledge_graph
import price_data
import synthesis

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = REPO_ROOT / "outputs" / "timeline_cache.json"

START_MONTH = "2020-12"
END_MONTH = "2024-05"

# Single source of truth for this dataset's company/industry — used in the
# retrieval question and passed into synthesis so the prompt itself never
# hardcodes a company name. Change these two lines to point the whole
# pipeline at a different company's filings.
COMPANY_NAME = "Peloton Interactive"
COMPANY_INDUSTRY = "connected fitness"

# Fixed and generic — never event-specific, so the question itself doesn't
# presuppose what happened. Scoping to the right month/document is entirely
# done via metadata_filters, not by naming the event in the query text.
GENERIC_QUESTION = (
    f"Based only on the provided documents, what did {COMPANY_NAME} disclose, "
    "announce, or report during this period?"
)


def _month_range(start: str, end: str) -> list:
    y, m = (int(x) for x in start.split("-"))
    ey, em = (int(x) for x in end.split("-"))
    months = []
    while (y, m) <= (ey, em):
        months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def _dump(obj):
    return obj.model_dump() if hasattr(obj, "model_dump") else obj


def _dedupe(items: list) -> list:
    seen = set()
    unique = []
    for item in items:
        key = json.dumps(_dump(item), sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _build_event(dates_with_roles: dict) -> dict:
    """One metadata_filters call per date (multi-value lists don't work —
    finding #20), kept separate per date-cluster (not merged) so synthesis
    can anchor the headline on the reversal_marker fact and order the detail
    sentence chronologically instead of by raw retrieval ranking."""
    date_groups = []
    all_chunks = []
    for date in sorted(dates_with_roles):
        data = hydradb_client.query(
            GENERIC_QUESTION,
            mode="thinking",
            max_results=20,  # default (10) missed real chunks near the ranking
            # boundary under thinking-mode's rerank volatility — confirmed via
            # tests/test_chunk_retrieval_stability.py (2/8 hits at 10 vs 8/8 at 20)
            metadata_filters={"filing_date": date},
        )
        chunks = data.chunks or []
        gc = data.graph_context
        relations = gc.chunk_relations if gc and gc.chunk_relations else []
        paths = gc.query_paths if gc and gc.query_paths else []
        snippets = synthesis.get_context_snippets(chunks=chunks, chunk_relations=relations, query_paths=paths)
        date_groups.append({
            "date": date,
            "narrative_role": dates_with_roles[date],
            "snippets": snippets,  # [{"text", "source_title"}, ...] — see synthesis.get_context_snippets
        })
        all_chunks += chunks

    all_chunks = _dedupe(all_chunks)
    result = synthesis.synthesize_timeline_event(
        GENERIC_QUESTION, date_groups, company=COMPANY_NAME, industry=COMPANY_INDUSTRY
    )

    # Document-wise evidence, not snippet-wise: group each date's snippets by
    # their real source document instead of showing raw chunk fragments.
    # Relation-derived snippets (source_title=None, HydraDB's own graph-LLM
    # summary text, not a verbatim quote) aren't attributable to one document
    # — kept as separate, unattributed relation_notes instead of dropped.
    evidence = []
    for g in date_groups:
        documents = sorted({s["source_title"] for s in g["snippets"] if s["source_title"]})
        relation_notes = [s["text"] for s in g["snippets"] if not s["source_title"]]
        evidence.append({
            "date": g["date"],
            "narrative_role": g["narrative_role"],
            "documents": documents,
            "relation_notes": relation_notes,
        })

    # Derived from the same snippets actually used for synthesis, not from
    # every raw chunk retrieved — a raw chunk that got outranked and never
    # made it into get_context_snippets() shouldn't be listed as "shown".
    source_titles = sorted({d for e in evidence for d in e["documents"]})
    doc_summaries = sorted({
        (getattr(c, "metadata", None) or {}).get("doc_summary")
        for c in all_chunks
        if getattr(c, "source_title", None) in source_titles and (getattr(c, "metadata", None) or {}).get("doc_summary")
    })

    # Precomputed here (not fetched live by the frontend) for the same
    # reason evidence/doc_summaries are: it's per-event, not too large to
    # cache, and this keeps the event view instant like the rest of the
    # app. Built from source_titles — the same deduplicated document list
    # already used for the evidence panel's decode dropdown, so the graph
    # always covers exactly the documents a user can already open. See
    # knowledge_graph.py and finding #24 (hydradb_findings_log.md) for the
    # entity-alias step this goes through.
    graph = knowledge_graph.build_graph(source_titles) if source_titles else {
        "documents": [], "skipped_documents": [], "nodes": [], "edges": []
    }

    return {
        "filing_dates": sorted(dates_with_roles),
        "question": GENERIC_QUESTION,
        "headline": result.get("headline") if result else None,
        "detail": result.get("detail") if result else None,
        "source_titles": source_titles,
        "doc_summaries": doc_summaries,
        "chunk_count": len(all_chunks),
        "evidence": evidence,
        "knowledge_graph": graph,
    }


def build_timeline() -> list:
    month_to_dates = hydradb_client.list_filing_dates()
    price_by_month = price_data.get_monthly_price_data()

    timeline = []
    for month in _month_range(START_MONTH, END_MONTH):
        entry = {
            "month": month,
            "price": price_by_month.get(month),
            "event": None,
        }
        dates_with_roles = month_to_dates.get(month)
        if dates_with_roles:
            entry["event"] = _build_event(dates_with_roles)
        timeline.append(entry)
    return timeline


def save_cache(timeline: list):
    CACHE_PATH.parent.mkdir(exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(timeline, f, indent=2, default=str)


def load_cache() -> list:
    with open(CACHE_PATH) as f:
        return json.load(f)


if __name__ == "__main__":
    timeline = build_timeline()
    save_cache(timeline)
    n_events = sum(1 for e in timeline if e["event"])
    print(f"Built {len(timeline)} months, {n_events} with events. Saved to {CACHE_PATH}")
