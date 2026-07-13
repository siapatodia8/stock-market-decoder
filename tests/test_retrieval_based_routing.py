"""
EXPERIMENT — does the "function routing via retrieval" pattern from HydraDB's
own cookbook (register callable functions as knowledge objects, then just
call query() and let ranking pick one — see the "AI Chief of Staff - Function
Routing" cookbook) work for OUR routing problem (deciding which timeline
event(s) a chat question concerns)?

This ingests each of our 5 catalog entries as its own tiny "event card"
document (same headline + dates text the classify() prompt already sees,
so it's an apples-to-apples comparison) into a SEPARATE, clearly-labeled
collection (EVENT_ROUTER_SUB_TENANT) inside the same tenant — never touches
"default", where the real 13 filings live. Then it calls the normal
client.query() (no classify(), no orchestrator prompt at all) and reads off
whichever event card(s) come back as the top match.

This is explicitly a fallback comparison, not a replacement in progress:
orchestrator.classify() (backend/orchestrator.py) is the current, working
approach. This file exists to answer "should we switch", not to switch.

Two things this CANNOT test for (by construction, not a bug in the test):
  - query_type (single/multi/comparative/range) — that's a question-SHAPE
    judgment, not a similarity signal. Not attempted here.
  - The BOUNDARY RULE (exclude the anchor event itself for "before X"/"after
    X") — that's date arithmetic, not textual similarity. One case below
    (CFO-transition boundary) is included specifically to observe this
    limitation directly, not because we expect it to pass.

Grading is a best-effort heuristic (top-1 or top-N event_id by
relevancy_score), not a strict pass/fail like test_orchestrator.py — there's
no clean way to turn a ranked list into a binary "matched" decision, so the
full ranked list + scores is printed for every case for manual inspection.

Run:
    cd backend && python ../tests/test_retrieval_based_routing.py
"""
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from dotenv import load_dotenv
load_dotenv()
import os

from hydra_db import HydraDB
import orchestrator

API_KEY = os.environ.get("HYDRA_DB_API_KEY")
TENANT_ID = os.environ.get("HYDRA_DB_TENANT_ID", "stock-market-decoder")
EVENT_ROUTER_SUB_TENANT = "event_router_experiment"  # isolated from "default"

client = HydraDB(token=API_KEY)


def event_card_filename(event_id: str) -> str:
    return f"event_card_{event_id}.md"


def ingest_event_cards(catalog: list):
    """One tiny document per catalog entry — same headline + dates text
    classify() already sees, nothing extra. upsert=true so reruns are safe."""
    ids = []
    for e in catalog:
        content = f"{e['headline']}\n\nFiling date(s): {', '.join(e['dates'])}"
        resp = client.context.ingest(
            tenant_id=TENANT_ID,
            sub_tenant_id=EVENT_ROUTER_SUB_TENANT,
            type="knowledge",
            upsert="true",
            documents=(event_card_filename(e["event_id"]), io.BytesIO(content.encode("utf-8")), "text/markdown"),
        )
        real_id = resp.data.results[0].id
        ids.append(real_id)
        print(f"  ingested {e['event_id']}: {content!r} -> id={real_id}")
    return ids


def wait_for_indexing(ids: list, timeout_s=120, interval_s=5):
    remaining = set(ids)
    start = time.time()
    while remaining and time.time() - start < timeout_s:
        status = client.context.status(tenant_id=TENANT_ID, sub_tenant_id=EVENT_ROUTER_SUB_TENANT, ids=list(remaining))
        for s in status.data.statuses:
            if s.indexing_status in ("completed", "success", "errored"):
                remaining.discard(s.id)
        if remaining:
            time.sleep(interval_s)
    if remaining:
        print(f"  WARNING: {len(remaining)} card(s) still indexing after {timeout_s}s — results below may be incomplete.")
    else:
        print("  All 5 event cards indexed.")


def route_via_retrieval(question: str, max_results: int = 5):
    """Returns a list of (event_id, relevancy_score) sorted descending, read
    off the event-card filename (event_card_<id>.md -> <id>)."""
    result = client.query(
        tenant_id=TENANT_ID,
        sub_tenant_id=EVENT_ROUTER_SUB_TENANT,
        query=question,
        mode="thinking",
        graph_context=False,  # 5 one-line cards — no graph reasoning needed
        max_results=max_results,
    )
    ranked = []
    for c in (result.data.chunks or []):
        title = c.source_title or ""
        if title.startswith("event_card_") and title.endswith(".md"):
            event_id = title[len("event_card_"):-len(".md")]
            ranked.append((event_id, c.relevancy_score or 0))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked


# Same real questions test_orchestrator.py and test_chat_e2e.py already used
# (for the classify()-based approach) and their known classify() results
# from the last live run, kept here purely as a reference to compare
# against — not a routing rule, just what to print alongside.
CASES = [
    {
        "q": "What did Peloton announce in December 2020?",
        "required": {"2020-12"},
        "classify_result": "single, ['2020-12'] — PASS",
    },
    {
        "q": "Compare Peloton's 2020 boom to the 2022 restructuring.",
        "required": {"2020-12", "2022-02"},
        "classify_result": "comparative, ['2020-12','2022-02'] — PASS",
    },
    {
        "q": "Tell me about the CFO change and the 2024 refinancing.",
        "required": {"2022-06", "2024-05"},
        "classify_result": "multi, ['2022-06','2024-05'] — PASS",
    },
    {
        "q": "How volatile was the stock in the period before the CFO transition?",
        "required": {"2020-12"},
        "forbidden": {"2022-06"},
        "note": "Boundary-exclusion case — retrieval has no date arithmetic, "
                "expected to NOT exclude 2022-06 the way classify()'s BOUNDARY "
                "RULE does. Included to observe this directly, not graded.",
        "classify_result": "range, boundary correctly excludes 2022-06 (after prompt fix) — PASS",
    },
    {
        "q": "What's your favorite pizza topping?",
        "required": set(),
        "note": "Off-topic relevance-gate case. classify() has an explicit "
                "instruction to return empty; retrieval has no native "
                "'nothing matches' signal — it always ranks all 5 cards by "
                "whatever similarity exists. Watch whether the top score "
                "here is clearly lower than a real question's top score.",
        "classify_result": "empty event_ids — PASS",
    },
    {
        "q": "What 40-year-old commercial fitness equipment company serving gyms and hotels did Peloton bring in-house in December 2020?",
        "required": {"2020-12"},
        "note": "Headline-distance case. classify() matched this one "
                "(background knowledge). Interesting to see if pure semantic "
                "similarity also matches it, given the event card's actual "
                "words are just the headline text (mentions manufacturing/"
                "R&D, not gyms/hotels/40-year-old).",
        "classify_result": "single, ['2020-12'] — MATCHED (diagnostic)",
    },
    {
        "q": "Who became CEO of Precor after Peloton brought it into its commercial lineup?",
        "required": {"2020-12"},
        "note": "classify() returned EMPTY for this one even with background "
                "knowledge available, since 'Rob Barker' has zero connection "
                "to the headline text. Retrieval has the same problem — "
                "'CEO of Precor' isn't semantically close to the headline's "
                "manufacturing/R&D framing either.",
        "classify_result": "empty event_ids — EMPTY (diagnostic)",
    },
    {
        "q": "How much did Peloton cut its planned capital spending by in early 2022?",
        "required": {"2022-02"},
        "note": "Headline-distance, purely numeric ($150M capex) — headline "
                "doesn't mention capex at all.",
        "classify_result": "single, ['2022-02'] — MATCHED (diagnostic)",
    },
]


def run_case(case):
    ranked = route_via_retrieval(case["q"])
    top_ids = {eid for eid, _ in ranked[: max(len(case["required"]), 1)]}
    required_ok = case["required"].issubset(top_ids) if case["required"] else True
    forbidden = case.get("forbidden", set())
    forbidden_ok = not (forbidden & {eid for eid, score in ranked[: len(case["required"]) or 1]})

    print(f"  q: {case['q']}")
    print(f"     ranked (event_id, score): {ranked}")
    print(f"     required={sorted(case['required'])} in top-N: {'ok' if required_ok else 'MISSING'}"
          + (f" | forbidden={sorted(forbidden)} excluded: {'ok' if forbidden_ok else 'PRESENT'}" if forbidden else ""))
    print(f"     classify() reference result: {case['classify_result']}")
    if case.get("note"):
        print(f"     note: {case['note']}")
    print()


def main():
    catalog = orchestrator.load_event_catalog()
    print(f"=== Ingesting {len(catalog)} event cards into sub_tenant={EVENT_ROUTER_SUB_TENANT!r} ===")
    ids = ingest_event_cards(catalog)
    wait_for_indexing(ids)

    print("\n=== Retrieval-based routing — same questions as the classify() tests ===\n")
    for case in CASES:
        run_case(case)


if __name__ == "__main__":
    main()
