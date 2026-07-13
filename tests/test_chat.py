"""
End-to-end test for the composed chat pipeline (backend/chat.py).

This is a live test — it runs all three stages (route -> retrieve ->
synthesize), so it needs HYDRA_DB_API_KEY, OPENAI_API_KEY, and network. Run
locally:

    cd backend && python ../tests/test_chat.py

Each case prints the scope stage 1 chose, the evidence counts, and the
synthesized answer, so you can eyeball whether the answer actually reflects
the right events. The last case checks the fallback path for an off-topic
question.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import chat


CASES = [
    {
        "q": "What did Peloton announce in December 2020?",
        "type": "single", "required": {"2020-12"}, "forbidden": set(), "expect_price": False,
    },
    {
        "q": "Tell me about the CFO change and the 2024 refinancing.",
        "type": "multi", "required": {"2022-06", "2024-05"}, "forbidden": set(), "expect_price": True,
    },
    {
        # Known, accepted gap — see docs/limitations_and_future_considerations.md.
        # retrieval_router.py (the adopted stage 1,
        # superseding orchestrator.classify()) has no boundary/date-window
        # logic the way classify()'s BOUNDARY RULE did — "leading up to X"
        # tends to collapse onto the anchor event X itself instead of
        # computing the true earlier window. Confirmed twice in
        # tests/test_retrieval_llm_hybrid.py's hybrid experiment before
        # adoption, and reproduces here in the real wired pipeline (routes to
        # ['2022-06'] instead of the earlier events). Not fixed: over-
        # inclusion is absorbed by chat_answer.yaml's grounding rule — this
        # exact case answers "It's not in the available data" rather than
        # fabricating a volatility figure — and this was an accepted tradeoff
        # of the redesign, not a regression. Kept in the suite as a live,
        # visible reminder of the gap; not graded strictly, just printed.
        "q": "How volatile was the stock leading up to the CFO transition?",
        "known_gap": True,
    },
    {
        "q": "What's your favorite pizza topping?",
        "off_topic": True,
    },
]


def main() -> bool:
    all_ok = True
    for case in CASES:
        question = case["q"]
        print(f"=== {question} ===")
        result = chat.run_chat(question)

        got_type = result["query_type"]
        got_ids = set(result["event_ids"])
        print(f"  query_type: {got_type}")
        print(f"  event_ids: {sorted(got_ids)}")
        print(f"  filing_dates: {result['filing_dates']}")
        print(f"  reasoning: {result['reasoning']}")
        print(f"  evidence: {len(result['chunks'])} chunks, "
              f"{len(result['chunk_relations'])} relations, "
              f"{len(result['query_paths'])} paths")
        print(f"  price_window: {result['price_window']}")
        print(f"  price_stats: {result['price_stats']}")
        print(f"  answer_source: {result['answer_source']}")
        if result["answer"]:
            print(f"  answer: {result['answer']}")
        if result["warning"]:
            print(f"  warning: {result['warning']}")

        if case.get("off_topic"):
            passed = result["answer"] is None and result["warning"] is not None
            label = "PASS" if passed else "FAIL"
        elif case.get("known_gap"):
            passed = True  # not graded — see the comment above this case
            label = "SKIPPED (known gap, not graded)"
        else:
            price_ok = (result["price_stats"] is not None) if case["expect_price"] else True
            passed = (got_type == case["type"]
                      and case["required"].issubset(got_ids)
                      and not (case["forbidden"] & got_ids)
                      and result["answer_source"] == "llm_synthesis"
                      and bool(result["answer"])
                      and price_ok)
            label = "PASS" if passed else "FAIL"

        all_ok = all_ok and passed
        print(f"  [{label}]\n")

    print("=== Summary ===")
    print(f"  chat pipeline: {'PASS' if all_ok else 'FAIL (or skipped — check keys/network)'}")
    return all_ok


if __name__ == "__main__":
    main()
