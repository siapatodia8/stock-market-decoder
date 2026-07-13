"""
Originally written to test two changes together, since they interacted:
  1. retrieval_router.py wired in as the new stage 1 (replacing
     orchestrator.classify()).
  2. chat_answer.yaml's then-new wording, which had a distinct "not relevant"
     instruction for off-topic questions alongside "not in the available
     data" for on-topic-but-thin-detail.

What this test found: chat.py short-circuits BEFORE calling
synthesis.synthesize_answer() whenever stage 1 returns an empty event_ids
list (see chat.py: `if not scope["event_ids"]: ... return base`). Both
off-topic cases below (pizza, Nike) correctly short-circuited at stage 1, so
synthesis — and its "not relevant" wording — was never actually reached. The
UI showed chat.py's own generic warning string instead. Since that wording
branch was confirmed dead in practice, it was removed from chat_answer.yaml
afterward; the prompt now only carries the "not in the available data"
instruction. This test is kept as a regression check on the two things that
DO matter going forward: off-topic questions still short-circuit cleanly at
stage 1 (cases 1-2), and on-topic-but-undisclosed-detail questions still
reach synthesis and get the "not in the available data" phrasing rather than
a fabricated answer (case 3), alongside a normal control (case 4).

Run:
    cd backend && python ../tests/test_chat_answer_wording.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import chat

CASES = [
    {
        "q": "What's the best pizza topping?",
        "note": "Off-topic control. Confirmed short-circuits at stage 1 "
                "(warning='No timeline events matched...', answer=None) — the "
                "removed 'not relevant' wording was never reached here.",
    },
    {
        "q": "What is Nike's current stock price?",
        "note": "Harder off-topic case — finance-shaped question, wrong company. "
                "Same as above: confirms this also short-circuits, not just obvious non-sequiturs.",
    },
    {
        "q": "What was Peloton's advertising budget in December 2020?",
        "note": "On-topic, real event (2020-12), but this specific figure isn't "
                "disclosed in the actual 8-K/PR. Should reach synthesis and say "
                "plainly it's not in the available data, not invent a number.",
    },
    {
        "q": "What did Peloton announce in December 2020?",
        "note": "Control — normal, fully-answerable question. Should be unaffected.",
    },
]


def run_case(case):
    result = chat.run_chat(case["q"])
    print(f"  q: {case['q']}")
    print(f"     query_type={result['query_type']} event_ids={result['event_ids']}")
    print(f"     answer_source={result['answer_source']}")
    print(f"     warning={result['warning']!r}")
    if result["answer"]:
        print(f"     answer: {result['answer']}")
    print(f"     note: {case['note']}")
    print()


def main():
    print("=== chat_answer.yaml wording + retrieval_router interaction check ===\n")
    for case in CASES:
        run_case(case)


if __name__ == "__main__":
    main()
