"""
Test harness for the events orchestrator (backend/orchestrator.py).

Two layers, so you can debug in isolation:

  1. Deterministic checks — catalog loads from the real timeline_cache.json and
     the prompt builds. These need NO network and run anywhere.
  2. Classification cases — labeled example questions covering all four
     query_types. These call classify(), which needs OPENAI_API_KEY and network
     (run locally, same as timeline.py). Each case prints predicted vs expected
     so a misclassification is obvious at a glance.

Run:
    cd backend && python ../tests/test_orchestrator.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import orchestrator


# Each case: question, expected query_type, ids that MUST be in the result,
# and ids that must NOT be (to catch obviously-wrong scoping). required/forbidden
# are kept lenient on purpose — we assert the shape and the load-bearing events,
# not an exact set, since reasonable people disagree on edge inclusion.
CASES = [
    {
        "q": "What did Peloton announce in December 2020?",
        "type": "single",
        "required": {"2020-12"},
        "forbidden": {"2024-05"},
    },
    {
        "q": "How volatile was the stock in the period before the CFO transition?",
        "type": "range",
        "required": {"2020-12"},
        # boundary rule: "before the CFO transition" (2022-06) must exclude
        # 2022-06 itself, and must not reach the later refinancing.
        "forbidden": {"2022-06", "2024-05"},
    },
    {
        "q": "Compare Peloton's 2020 boom to the 2022 restructuring.",
        "type": "comparative",
        "required": {"2020-12", "2022-02"},
        "forbidden": set(),
    },
    {
        "q": "Tell me about the CFO change and the 2024 refinancing.",
        "type": "multi",
        "required": {"2022-06", "2024-05"},
        "forbidden": set(),
    },
    {
        "q": "What happened after the leadership overhaul?",
        "type": "range",
        "required": {"2024-05"},
        # boundary rule: "after the leadership overhaul" (2022-02) excludes 2022-02.
        "forbidden": {"2022-02"},
    },
    {
        "q": "Give me the whole Peloton story from start to finish.",
        "type": "range",
        "required": {"2020-12", "2024-05"},
        "forbidden": set(),
    },
    {
        # relevance gate: off-topic must return an empty scope, NOT all events.
        "q": "What's your favorite pizza topping?",
        "off_topic": True,
    },
]


def deterministic_checks() -> bool:
    print("=== Deterministic checks (no network) ===")
    catalog = orchestrator.load_event_catalog()
    ok = True

    if not catalog:
        print("  FAIL: catalog is empty")
        return False
    print(f"  OK: loaded {len(catalog)} events")

    for e in catalog:
        if not e["event_id"] or not e["headline"]:
            print(f"  FAIL: malformed catalog entry: {e}")
            ok = False
    print(f"  Event ids: {[e['event_id'] for e in catalog]}")

    prompt = orchestrator.build_classification_prompt("test question", catalog)
    if "test question" not in prompt or catalog[0]["event_id"] not in prompt:
        print("  FAIL: prompt did not embed question + catalog")
        ok = False
    else:
        print("  OK: prompt builds and embeds question + catalog")

    print()
    return ok


def classification_cases() -> bool:
    print("=== Classification cases (needs OPENAI_API_KEY + network) ===")
    catalog = orchestrator.load_event_catalog()
    all_pass = True

    for case in CASES:
        result = orchestrator.classify(case["q"], catalog=catalog)
        if result is None:
            print(f"  SKIP (no result / no key): {case['q']!r}")
            all_pass = False
            continue

        got_type = result["query_type"]
        got_ids = set(result["event_ids"])

        if case.get("off_topic"):
            passed = len(got_ids) == 0
            all_pass = all_pass and passed
            print(f"  [{'PASS' if passed else 'FAIL'}] {case['q']}  (off-topic)")
            print(f"       ids:  got={sorted(got_ids)} expected=[] "
                  f"{'ok' if passed else 'SHOULD BE EMPTY'}")
            print(f"       reasoning: {result['reasoning']}")
            continue

        type_ok = got_type == case["type"]
        req_ok = case["required"].issubset(got_ids)
        forbid_ok = not (case["forbidden"] & got_ids)
        passed = type_ok and req_ok and forbid_ok
        all_pass = all_pass and passed

        print(f"  [{'PASS' if passed else 'FAIL'}] {case['q']}")
        print(f"       type: got={got_type} expected={case['type']} "
              f"{'ok' if type_ok else 'MISMATCH'}")
        print(f"       ids:  got={sorted(got_ids)} "
              f"required={sorted(case['required'])} "
              f"{'ok' if req_ok else 'MISSING'}"
              f"{'' if forbid_ok else ' | FORBIDDEN PRESENT'}")
        print(f"       reasoning: {result['reasoning']}")

    print()
    return all_pass


if __name__ == "__main__":
    det_ok = deterministic_checks()
    cls_ok = classification_cases()
    print("=== Summary ===")
    print(f"  deterministic: {'PASS' if det_ok else 'FAIL'}")
    print(f"  classification: {'PASS' if cls_ok else 'FAIL (or skipped — check key/network)'}")
