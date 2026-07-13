"""
Isolated tests for the two rewritten prompts (backend/prompts/orchestrator.yaml
and backend/prompts/chat_answer.yaml), run BEFORE the full end-to-end suite so
any adjustment need shows up against one stage at a time, not tangled up with
retrieval variability.

  Section A — classify() alone, re-running the 5 headline-distance questions
  from test_chat_e2e.py's diagnostic group. Needs OPENAI_API_KEY + network,
  no HydraDB call. Informational: prints MATCHED/EMPTY/OTHER and the
  reasoning text, so we can see whether the new GROUNDING rule actually
  changes routing behavior (it may not — an LLM's own next-token weights can
  still associate "Precor" with Peloton regardless of an instruction not to
  use that association; instruction-following isn't perfect).

  Section B — synthesize_answer() alone, with a FABRICATED chunk (no HydraDB
  call at all) that intentionally does not contain a well-known real-world
  fact about Peloton (its 2012 founding year). Tests whether the new
  GROUNDING rule in chat_answer.yaml actually stops the model from filling
  that gap from its own training knowledge. Graded PASS/FAIL by substring
  checks (a real grading rubric isn't possible for free-text, so this checks
  for the presence of the fabricated fact and the absence of the outside
  fact / presence of refusal language).

Run:
    cd backend && python ../tests/test_prompt_grounding.py
"""
import sys
from types import SimpleNamespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import orchestrator
import synthesis


# --- Section A ---------------------------------------------------------

HEADLINE_DISTANCE_CASES = [
    {
        "q": "What 40-year-old commercial fitness equipment company serving gyms and hotels did Peloton bring in-house in December 2020?",
        "note": "Zero headline-vocabulary overlap (no 'acquisition', '$420 million', or 'Precor').",
    },
    {
        "q": "Who became CEO of Precor after Peloton brought it into its commercial lineup?",
        "note": "Named-entity-only (Rob Barker), no event-type language.",
    },
    {
        "q": "Why did Peloton wind down its POP manufacturing plant and cut about 2,800 jobs in early 2022?",
        "note": "Real facts from restructuring PR body, avoids 'leadership changes'/'restructuring plan' phrasing.",
    },
    {
        "q": "What happened to Jill Woodworth after mid-2022?",
        "note": "Named-entity-only (outgoing CFO), no 'CFO transition' language.",
    },
    {
        "q": "How much did Peloton cut its planned capital spending by in early 2022?",
        "note": "Routes purely off a number ($150M capex cut), no headline words at all.",
    },
]


def section_a():
    print("=== Section A: classify() alone on headline-distance questions ===\n")
    catalog = orchestrator.load_event_catalog()
    for case in HEADLINE_DISTANCE_CASES:
        result = orchestrator.classify(case["q"], catalog=catalog)
        if result is None:
            print(f"  SKIP (no result / no key): {case['q']!r}")
            continue
        ids = result["event_ids"]
        label = "EMPTY" if not ids else "MATCHED"
        print(f"  [{label}] {case['q']}")
        print(f"       event_ids={ids} query_type={result['query_type']}")
        print(f"       reasoning: {result['reasoning']}")
        print(f"       note: {case['note']}")
    print()


# --- Section B ---------------------------------------------------------

# One fabricated chunk, never sent to HydraDB. Deliberately contains a
# specific, checkable fact (a $12M supply agreement) and deliberately omits
# a real, well-known Peloton fact (its 2012 founding year) that the model
# almost certainly "knows" from training — this is the actual grounding test.
FAKE_CHUNK = SimpleNamespace(
    chunk_content=(
        "On March 3, 2019, Peloton signed a supply agreement valued at "
        "$12 million with an unnamed logistics partner to support regional "
        "delivery capacity."
    ),
    relevancy_score=0.9,
    source_title="fabricated_test_chunk.md",
)

REFUSAL_MARKERS = ["doesn't", "does not", "not mention", "not provided",
                   "not stated", "no information", "isn't in the context",
                   "not in the context", "context doesn't", "unable to",
                   "not specified", "doesn't say", "does not say", "cannot answer",
                   "not in the available data", "available data"]  # current chat_answer.yaml wording


def _has_refusal(answer: str) -> bool:
    a = answer.lower()
    return any(m in a for m in REFUSAL_MARKERS)


GROUNDING_CASES = [
    {
        "name": "positive control — answerable from the fabricated chunk",
        "q": "What was the supply agreement Peloton signed in March 2019 about, and how much was it worth?",
        "expect_fact": True,
        "expect_outside_fact": False,
        "expect_refusal": False,
    },
    {
        "name": "partial — one answerable part, one only-from-memory part",
        "q": "What year was Peloton founded, and what was the March 2019 supply agreement about?",
        "expect_fact": True,
        "expect_outside_fact": False,
        "expect_refusal": True,  # should flag the founding-year part as not in context
    },
    {
        "name": "full refusal — purely a fact only in training knowledge",
        "q": "What year was Peloton founded?",
        "expect_fact": False,
        "expect_outside_fact": False,
        "expect_refusal": True,
    },
]


def section_b():
    print("=== Section B: synthesize_answer() alone, fabricated chunk ===\n")
    all_pass = True
    for case in GROUNDING_CASES:
        answer = synthesis.synthesize_answer(case["q"], chunks=[FAKE_CHUNK])
        if answer is None:
            print(f"  SKIP (no answer / no key): {case['q']!r}")
            continue

        has_fact = "12" in answer and ("march" in answer.lower() or "2019" in answer)
        has_outside_fact = "2012" in answer
        has_refusal = _has_refusal(answer)

        passed = (has_fact == case["expect_fact"]
                  and has_outside_fact == case["expect_outside_fact"]
                  and (not case["expect_refusal"] or has_refusal))
        all_pass = all_pass and passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {case['name']}")
        print(f"       q: {case['q']}")
        print(f"       has_fabricated_fact={has_fact} (expected {case['expect_fact']}) | "
              f"has_2012_outside_fact={has_outside_fact} (expected {case['expect_outside_fact']}) | "
              f"has_refusal_language={has_refusal} (expected>= {case['expect_refusal']})")
        print(f"       answer: {answer}\n")

    print(f"  Section B: {'PASS' if all_pass else 'FAIL'}\n")
    return all_pass


if __name__ == "__main__":
    section_a()
    section_b()
