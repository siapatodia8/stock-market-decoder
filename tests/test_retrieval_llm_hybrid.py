"""
Regression test for the adopted orchestrator — calls the REAL
backend/retrieval_router.py module directly (retrieval_router.route_via_retrieval()),
not a local reimplementation.

This file originally duplicated retrieval_router's logic (unscoped query() ->
map chunks to events -> build evidence block -> LLM confirmation) because it
was written BEFORE that logic existed as a real backend module — back then
this test WAS the experiment. Now that backend/retrieval_router.py is wired
into chat.py and is the actual production stage 1, keeping a second, separate
copy of the same logic here would risk silent drift: a future change to the
real module (e.g. a different SNIPPETS_PER_EVENT, a fixed scoring bug) would
never be reflected here, and this test would keep passing/failing based on
stale logic while claiming to validate the real thing. Calling the real
module directly means this test always exercises whatever retrieval_router.py
currently does.

Why this exists (unchanged from the original experiment): pure retrieval over
one-line headline cards (test_retrieval_based_routing.py) failed on purely
numeric/non-thematic questions because the event card never contained that
detail — the real documents do. Retrieval also can't do boundary-exclusion or
off-topic rejection on its own. Per the relaxed grading adopted for the
redesign: boundary-exclusion and off-topic rejection are NOT required of
routing — chat_answer.yaml's grounding rule already makes synthesis say
"not in the available data" when retrieval over-includes, so over-inclusion
here is fine. The only thing graded is RECALL: does the required event show
up at all.

Run:
    cd backend && python ../tests/test_retrieval_llm_hybrid.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import orchestrator
import retrieval_router

CATALOG = orchestrator.load_event_catalog()


# Same question set as test_retrieval_based_routing.py / the original hybrid
# experiment. Grading is lenient (required-subset only, per the agreed
# relaxed criteria) — extra events and off-topic non-rejection are not
# failures here.
CASES = [
    {"q": "What did Peloton announce in December 2020?", "required": {"2020-12"},
     "classify_result": "single, ['2020-12'] — PASS"},
    {"q": "Compare Peloton's 2020 boom to the 2022 restructuring.", "required": {"2020-12", "2022-02"},
     "classify_result": "comparative, ['2020-12','2022-02'] — PASS"},
    {"q": "Tell me about the CFO change and the 2024 refinancing.", "required": {"2022-06", "2024-05"},
     "classify_result": "multi, ['2022-06','2024-05'] — PASS"},
    {"q": "How volatile was the stock in the period before the CFO transition?", "required": {"2020-12"},
     "note": "Boundary case — over-inclusion of 2022-06 is now acceptable, not graded against. "
             "Known, accepted gap — see docs/limitations_and_future_considerations.md.",
     "classify_result": "range, boundary correctly excludes 2022-06 — PASS"},
    {"q": "What's your favorite pizza topping?", "required": set(),
     "note": "Off-topic — not graded on rejection; observing what the router does with real off-topic retrieval.",
     "classify_result": "empty event_ids — PASS"},
    {"q": "What 40-year-old commercial fitness equipment company serving gyms and hotels did Peloton bring in-house in December 2020?",
     "required": {"2020-12"}, "classify_result": "single, ['2020-12'] — MATCHED (diagnostic)"},
    {"q": "Who became CEO of Precor after Peloton brought it into its commercial lineup?",
     "required": {"2020-12"},
     "note": "The real 8-K/PR text literally names Rob Barker as Precor's incoming CEO — "
             "should succeed here even though classify() (headline-only) returned empty.",
     "classify_result": "empty event_ids — EMPTY (diagnostic)"},
    {"q": "How much did Peloton cut its planned capital spending by in early 2022?",
     "required": {"2022-02"},
     "note": "The real restructuring PR literally states the $150M capex cut — "
             "the case that failed against headline-only cards; should succeed against real text.",
     "classify_result": "single, ['2022-02'] — MATCHED (diagnostic)"},
    {"q": "Tell me about the Precor acquisition, the CFO transition, and the 2024 refinancing.",
     "required": {"2020-12", "2022-06", "2024-05"},
     "note": "Explicit 3-item multi question — tests whether recall extends past 2 "
             "when the question genuinely names 3 things.",
     "classify_result": "not yet tested with classify() — new case"},
    {"q": "Compare the 2020 acquisition, the 2022 restructuring, and the 2024 refinancing.",
     "required": {"2020-12", "2022-02", "2024-05"},
     "note": "3-way comparative — tests query_type=comparative holding up with 3 "
             "named events instead of the 2 already tested above.",
     "classify_result": "not yet tested with classify() — new case"},
    {"q": "Give me the whole Peloton story from start to finish.",
     "required": {"2020-12", "2021-08", "2022-02", "2022-06", "2024-05"},
     "note": "All 5 events — the broadest possible case. classify() already handles "
             "this correctly (test_orchestrator.py); untested here until now.",
     "classify_result": "range, all 5 event ids — PASS (test_orchestrator.py)"},
]


def run_case(case):
    result = retrieval_router.route_via_retrieval(case["q"], catalog=CATALOG)
    if result is None:
        print(f"  SKIP (no result / no key): {case['q']!r}\n")
        return True  # can't grade without a key/network — don't fail the run for it

    got_ids = set(result["event_ids"])
    required_ok = case["required"].issubset(got_ids) if case["required"] else True

    print(f"  q: {case['q']}")
    print(f"     final: query_type={result['query_type']} event_ids={sorted(got_ids)} "
          f"required={sorted(case['required'])} {'ok' if required_ok else 'MISSING'}")
    print(f"     reasoning: {result['reasoning']}")
    print(f"     classify() reference result: {case['classify_result']}")
    if case.get("note"):
        print(f"     note: {case['note']}")
    print()
    return required_ok


def main():
    print("=== Hybrid routing regression test (via real backend/retrieval_router.py) ===\n")
    all_ok = True
    for case in CASES:
        all_ok = run_case(case) and all_ok

    print("=== Summary ===")
    print(f"  required-subset recall: {'PASS' if all_ok else 'FAIL'} (lenient grading — see notes above)")


if __name__ == "__main__":
    main()
