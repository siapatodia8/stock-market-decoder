"""
Empirical measurement of finding #12 (chunk/reranking non-determinism) through
the REAL production pipeline (chat.run_chat()), not an isolated SDK diagnostic.

Every prior look at this instability (test_chunk_retrieval_stability.py,
test_retrieval_determinism.py, and the live UI capex-question anomaly) was
either a single side-by-side comparison or a low-level query() probe. This
runs the same specific question 5 times each through the actual chat pipeline
and tallies how often the correct, checkable fact actually shows up in the
final synthesized answer — the same failure mode a real user would see.

Question selection, and why: per outputs/timeline_cache.json's own chunk_id
evidence (grepped directly, not assumed from word count), only two documents
in this corpus are both long AND genuinely split into multiple real chunks at
ingestion: peloton_2021-08-26_shareholder-letter_v2.md (4 chunks) and
peloton_2022-02-08_shareholder-letter.md (5 chunks). Everything else (8-Ks,
most press releases) is 1-2 chunks, effectively whole-document. Cases 1-4
below target facts confirmed (via the same chunk_id evidence) to live in the
LATE chunks of those two letters — chunk 4 of 5, and chunks 2-3 of 4 — the
scenario where "which chunk of this multi-chunk document got surfaced" is
itself an axis of instability, separate from whether the document was
retrieved at all. Case 5 is the original capex question, kept for direct
comparison with the live UI anomaly — its own fact sits in chunk 0 of a
2-chunk doc (confirmed by reading the raw file directly), so a miss there
points to corpus-wide top-K exclusion rather than within-document chunk
selection, a useful contrast against cases 1-4.

Each run is graded three ways, not just pass/fail:
  - correct: the expected figure appears in the answer.
  - refused: answer correctly-looking-but-empty, i.e. the "not in the
    available data" grounding response — a safe miss, not a fabrication.
  - wrong: neither of the above — the model answered something else, which
    would need a closer look (fabrication risk, not just instability).

Run:
    cd backend && python ../tests/test_chat_answer_stability.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import chat

RUNS_PER_QUESTION = 5

REFUSAL_MARKERS = ["not in the available data", "available data"]

CASES = [
    {
        "q": "What was Peloton's Connected Fitness segment revenue for the quarter ended December 31, 2021?",
        "expect_any": ["796.4"],
        "note": "peloton_2022-02-08_shareholder-letter.md, chunk 4 of 5 (deepest chunk).",
    },
    {
        "q": "How much cash and cash equivalents did Peloton report as of December 31, 2021?",
        "expect_any": ["1.6 billion", "$1.6 billion", "1,600", "1.6B"],
        "note": "peloton_2022-02-08_shareholder-letter.md, chunk 4 of 5 (deepest chunk).",
    },
    {
        "q": "What was Peloton's total revenue for the fiscal year ended June 30, 2021?",
        "expect_any": ["4,021.8", "4021.8"],
        "note": "peloton_2021-08-26_shareholder-letter_v2.md, chunk 2 of 4.",
    },
    {
        "q": "What was Peloton's net loss for fiscal year 2021?",
        "expect_any": ["189.0", "189"],
        "note": "peloton_2021-08-26_shareholder-letter_v2.md, chunk 3 of 4.",
    },
    {
        "q": "How much did Peloton cut its planned capital spending by in early 2022?",
        "expect_any": ["150 million", "$150 million", "150M"],
        "note": "peloton_2022-02-08_restructuring-pr.md, chunk 0 of 2 (the original live-UI anomaly's question) — "
                "kept for direct comparison, not testing deep-chunk selection like cases 1-4.",
    },
]


def grade(answer, expect_any):
    if answer is None:
        return "refused"  # stage 1/2 short-circuit before synthesis ever ran
    low = answer.lower()
    if any(fig.lower() in low for fig in expect_any):
        return "correct"
    if any(marker in low for marker in REFUSAL_MARKERS):
        return "refused"
    return "wrong"


def run_case(case):
    print(f"  q: {case['q']}")
    print(f"     note: {case['note']}")
    tallies = {"correct": 0, "refused": 0, "wrong": 0}
    for i in range(1, RUNS_PER_QUESTION + 1):
        result = chat.run_chat(case["q"])
        outcome = grade(result["answer"], case["expect_any"])
        tallies[outcome] += 1
        print(f"     run {i}: {outcome:8s} query_type={result['query_type']} event_ids={result['event_ids']}")
        if result["answer"]:
            print(f"              answer: {result['answer']}")
        elif result["warning"]:
            print(f"              warning: {result['warning']}")
    print(f"     tally: {tallies['correct']}/{RUNS_PER_QUESTION} correct, "
          f"{tallies['refused']}/{RUNS_PER_QUESTION} refused, "
          f"{tallies['wrong']}/{RUNS_PER_QUESTION} wrong")
    print()
    return tallies


def main():
    print(f"=== Chat answer stability — {RUNS_PER_QUESTION} runs x {len(CASES)} questions, real chat.run_chat() ===\n")
    all_tallies = []
    for case in CASES:
        all_tallies.append((case["q"], run_case(case)))

    print("=== Summary ===")
    for q, t in all_tallies:
        print(f"  {t['correct']}/{RUNS_PER_QUESTION} correct — {q}")


if __name__ == "__main__":
    main()
