"""
Builds the full monthly timeline (Dec 2020 - May 2024): every month gets a
real price % change, and any month with a real filing_date also gets a
synthesized event summary from HydraDB. Writes the result to
data/timeline_cache.json. Run standalone to (re)build the cache; the
/api/timeline endpoint just reads the cached file.
"""
import json
from pathlib import Path

import hydradb_client
import price_data
import synthesis

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = REPO_ROOT / "data" / "timeline_cache.json"

START_MONTH = "2020-12"
END_MONTH = "2024-05"

# Fixed and generic — never event-specific, so the question itself doesn't
# presuppose what happened. Scoping to the right month/document is entirely
# done via metadata_filters, not by naming the event in the query text.
GENERIC_QUESTION = (
    "Based only on the provided documents, what did Peloton disclose, "
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
            "snippets": snippets,
        })
        all_chunks += chunks

    all_chunks = _dedupe(all_chunks)
    result = synthesis.synthesize_timeline_event(GENERIC_QUESTION, date_groups)

    source_titles = sorted({getattr(c, "source_title", None) for c in all_chunks if getattr(c, "source_title", None)})
    doc_summaries = sorted({
        (getattr(c, "metadata", None) or {}).get("doc_summary")
        for c in all_chunks
        if (getattr(c, "metadata", None) or {}).get("doc_summary")
    })

    return {
        "filing_dates": sorted(dates_with_roles),
        "question": GENERIC_QUESTION,
        "headline": result.get("headline") if result else None,
        "detail": result.get("detail") if result else None,
        "source_titles": source_titles,
        "doc_summaries": doc_summaries,
        "chunk_count": len(all_chunks),
        "evidence": date_groups,
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
