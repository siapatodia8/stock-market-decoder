"""
End-to-end test for the composed chat pipeline (backend/chat.py).

This is a live test — it runs all three stages (classify -> retrieve ->
synthesize), so it needs HYDRA_DB_API_KEY, OPENAI_API_KEY, and network. Run
locally:

    cd backend && python ../tests/test_chat.py

Each case prints the scope the orchestrator chose, the evidence counts, and the
synthesized answer, so you can eyeball whether the answer actually reflects the
right events. The last case checks the fallback path for an off-topic question.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import chat


# (question, expected query_type, required ids, forbidden ids, expect_price_stats).
# None type = we only care that the fallback triggers (no answer, a warning).
CASES = [
    ("What did Peloton announce in December 2020?", "single", {"2020-12"}, set(), False),
    ("Tell me about the CFO change and the 2024 refinancing.", "multi", {"2022-06", "2024-05"}, set(), True),
    # boundary rule: "leading up to the CFO transition" (2022-06) must scope to
    # the earlier overhaul and EXCLUDE 2022-06; a volatility range must carry price stats.
    ("How volatile was the stock leading up to the CFO transition?", "range", {"2022-02"}, {"2022-06"}, True),
    ("What's your favorite pizza topping?", None, set(), set(), False),  # off-topic -> fallback
]


def main() -> bool:
    all_ok = True
    for question, expected_type, required_ids, forbidden_ids, expect_price in CASES:
        print(f"=== {question} ===")
        result = chat.run_chat(question)

        got_type = result["query_type"]
        got_ids = set(result["event_ids"])
        print(f"  query_type: {got_type}  (expected {expected_type})")
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

        if expected_type is None:
            # off-topic: expect the fallback — no answer, a warning present
            passed = result["answer"] is None and result["warning"] is not None
        else:
            price_ok = (result["price_stats"] is not None) if expect_price else True
            passed = (got_type == expected_type
                      and required_ids.issubset(got_ids)
                      and not (forbidden_ids & got_ids)
                      and result["answer_source"] == "llm_synthesis"
                      and bool(result["answer"])
                      and price_ok)
        all_ok = all_ok and passed
        print(f"  [{'PASS' if passed else 'FAIL'}]\n")

    print("=== Summary ===")
    print(f"  chat pipeline: {'PASS' if all_ok else 'FAIL (or skipped — check keys/network)'}")
    return all_ok


if __name__ == "__main__":
    main()
