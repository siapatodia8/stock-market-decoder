"""
End-to-end chat pipeline test — runs real questions through the FULL
backend.chat.run_chat() pipeline (retrieval_router.route_via_retrieval ->
scoped retrieval -> synthesis), not any single stage in isolation. Needs
OPENAI_API_KEY + network + a live HydraDB tenant, same as the other live
tests in this suite.

Run:
    cd backend && python ../tests/test_chat_e2e.py

Three groups of cases, each testing something distinct (see the comment
above each block in CASES for the full rationale):

  1. Graded cases (short-doc baseline, long-doc broad/narrow pairs, multi-doc
     single event, cross-event comparative, off-topic) — asserted PASS/FAIL
     on query_type / required event_ids / forbidden event_ids / at-least-one
     expected source, same lenient style as test_orchestrator.py. These count
     toward the overall pass/fail tally. NOTE: the `forbidden` checks
     predate the orchestrator redesign (see docs/CONTEXT_UPDATES.md) — the
     adopted stage 1 (retrieval_router.py) deliberately errs toward
     inclusion, so a `forbidden` failure here isn't necessarily a real bug;
     re-check against that design intent before treating one as a
     regression.

  2. The long-document broad/narrow pairs (2021-08 and 2022-02-08 shareholder
     letters) additionally print a chunk-length observation: the longest
     chunk_content length retrieved for the expected document, compared
     against that document's real full length (measured via `wc -c` on
     data/*.md). This is NOT graded pass/fail — there's no known-correct
     answer for whether specificity should shrink the chunk; that's the
     open question this test exists to observe.

  3. Headline-distance stress cases (group "headline_distance") — questions
     deliberately built from real document facts using none of the actual
     catalog headline's own vocabulary. ORIGINALLY written to stress-test
     orchestrator.classify()'s headline-only limitation (see
     docs/CONTEXT_UPDATES.md: "Chat scoping was headline-limited, not
     document-limited — since fixed"). That limitation no longer describes the pipeline
     actually running here — chat.py's stage 1 is now
     retrieval_router.route_via_retrieval() (see CONTEXT_UPDATES.md's
     "Orchestrator redesign" section), which sees real retrieved excerpts,
     not just a headline. This group is kept as an end-to-end confirmatory
     check (through the full chat.run_chat() pipeline, including price_stats
     and synthesis) that these cases still route correctly under the new
     stage 1 — routing behavior itself was already validated more directly
     in tests/test_retrieval_llm_hybrid.py. Diagnostic only, NOT counted in
     the pass/fail tally.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import chat


# Full byte length of each source file, from `wc -c` on data/*.md — the
# "no shrink possible" ceiling for the chunk-length observation below.
# NOTE: peloton_2021-08-26_shareholder-letter.md (no _v2) is NOT in this
# table on purpose — it's never referenced by scripts/setup_and_ingest_sdk.py
# and was therefore never ingested; only the _v2 file is real evidence.
DOC_LENGTHS = {
    "peloton_2022-02-08_8k.md": 938,
    "peloton_2021-08-26_8k.md": 1177,
    "peloton_2020-12-21_8k.md": 1621,
    "peloton_2024-05-20_8k.md": 1658,
    "peloton_2022-06-06_pr.md": 1847,
    "peloton_2024-05-20_pr.md": 2016,
    "peloton_2022-06-06_8k.md": 2029,
    "peloton_2022-02-05_8k.md": 2146,
    "peloton_2022-02-05_board-pr.md": 2211,
    "peloton_2020-12-21_pr.md": 2525,
    "peloton_2022-02-08_restructuring-pr.md": 2844,
    "peloton_2021-08-26_shareholder-letter_v2.md": 5596,
    "peloton_2022-02-08_shareholder-letter.md": 6400,
}

CASES = [
    # --- Group 1: short-document baseline. Confirms, through the REAL
    # pipeline (not the raw SDK test script used for Tier 2), that short
    # docs still come back as one whole-document chunk. Three different
    # events/topics so the result isn't an artifact of one document.
    {
        "group": "short_baseline",
        "q": "What did Peloton announce about the Precor acquisition in December 2020?",
        "type": "single",
        "required": {"2020-12"},
        "forbidden": {"2024-05"},
        "expected_sources": {"peloton_2020-12-21_8k.md", "peloton_2020-12-21_pr.md"},
    },
    {
        "group": "short_baseline",
        "q": "Why did Peloton's CFO change in June 2022?",
        "type": "single",
        "required": {"2022-06"},
        "forbidden": {"2020-12", "2024-05"},
        "expected_sources": {"peloton_2022-06-06_8k.md", "peloton_2022-06-06_pr.md"},
    },
    {
        "group": "short_baseline",
        "q": "What is Peloton's global refinancing plan announced in 2024?",
        "type": "single",
        "required": {"2024-05"},
        "forbidden": {"2020-12"},
        "expected_sources": {"peloton_2024-05-20_8k.md", "peloton_2024-05-20_pr.md"},
    },

    # --- Group 2: long-document broad/narrow pairs. The actual chunk-shrink
    # test — same document, broad question vs. a narrow one targeting a
    # single fact. "pair" groups them for the post-run chunk-length table.
    {
        "group": "long_pair", "pair": "2021-08-letter", "role": "broad",
        "q": "What did Peloton's August 2021 shareholder letter say about its business?",
        "type": "single",
        "required": {"2021-08"},
        "expected_sources": {"peloton_2021-08-26_shareholder-letter_v2.md"},
    },
    {
        "group": "long_pair", "pair": "2021-08-letter", "role": "narrow",
        "q": "What specific internal control weakness did Peloton disclose in its August 2021 shareholder letter?",
        "type": "single",
        "required": {"2021-08"},
        "expected_sources": {"peloton_2021-08-26_shareholder-letter_v2.md"},
    },
    {
        "group": "long_pair", "pair": "2022-02-letter", "role": "broad",
        "q": "What did Peloton's leadership say in the February 2022 shareholder letter?",
        "type": "single",
        "required": {"2022-02"},
        "expected_sources": {"peloton_2022-02-08_shareholder-letter.md"},
    },
    {
        "group": "long_pair", "pair": "2022-02-letter", "role": "narrow",
        "q": "What exact severance or cost figures did Peloton disclose in its February 2022 shareholder letter restructuring section?",
        "type": "single",
        "required": {"2022-02"},
        "expected_sources": {"peloton_2022-02-08_shareholder-letter.md"},
    },

    # --- Group 3: multi-document single event (2022-02 has 3 documents: 8-K,
    # board-pr, shareholder-letter). Tests whether specificity narrows which
    # DOCUMENTS surface, not just chunk size within one document. Doc-count
    # comparison is printed, not graded — same "discovery, not known-correct
    # answer" reasoning as the chunk-length observation above.
    {
        "group": "multi_doc_event", "pair": "2022-02-docs", "role": "broad",
        "q": "What happened to Peloton in February 2022?",
        "type": "single",
        "required": {"2022-02"},
    },
    {
        "group": "multi_doc_event", "pair": "2022-02-docs", "role": "narrow",
        "q": "Who replaced John Foley as CEO in February 2022?",
        "type": "single",
        "required": {"2022-02"},
    },

    # --- Group 4: cross-event comparative. Checks chunk merging/dedup across
    # events end-to-end (test_orchestrator.py already covers classification
    # for this question; this checks the actual retrieved chunks/sources too).
    {
        "group": "cross_event",
        "q": "Compare Peloton's 2020 acquisition boom to the 2022 restructuring.",
        "type": "comparative",
        "required": {"2020-12", "2022-02"},
        "forbidden": set(),
    },

    # --- Group 5: negative path. Confirms run_chat() returns cleanly with a
    # warning and no chunks/answer, through the real pipeline, no crash.
    {
        "group": "off_topic",
        "q": "What's the best pizza topping?",
        "off_topic": True,
    },

    # --- Group 6: headline-distance stress tests. See module docstring —
    # diagnostic only, not graded. Built from real document facts (verified
    # against data/*.md) that deliberately avoid the catalog headline's own
    # vocabulary. Originally testing classify()'s headline-only limitation;
    # now an end-to-end confirmatory check that retrieval_router.py (the
    # current stage 1) still routes these correctly through the full
    # chat.run_chat() pipeline.
    {
        "group": "headline_distance",
        "q": "What 40-year-old commercial fitness equipment company serving gyms and hotels did Peloton bring in-house in December 2020?",
        "expected_event": "2020-12",
        "note": "Zero headline-vocabulary overlap (no 'acquisition', '$420 million', or 'Precor') — hardest case.",
    },
    {
        "group": "headline_distance",
        "q": "Who became CEO of Precor after Peloton brought it into its commercial lineup?",
        "expected_event": "2020-12",
        "note": "Named-entity-only (Rob Barker), no event-type language.",
    },
    {
        "group": "headline_distance",
        "q": "Why did Peloton wind down its POP manufacturing plant and cut about 2,800 jobs in early 2022?",
        "expected_event": "2022-02",
        "note": "Real facts from restructuring PR body, avoids 'leadership changes'/'restructuring plan' phrasing.",
    },
    {
        "group": "headline_distance",
        "q": "What happened to Jill Woodworth after mid-2022?",
        "expected_event": "2022-06",
        "note": "Named-entity-only (outgoing CFO), no 'CFO transition' language.",
    },
    {
        "group": "headline_distance",
        "q": "How much did Peloton cut its planned capital spending by in early 2022?",
        "expected_event": "2022-02",
        "note": "Routes purely off a number ($150M capex cut), no headline words at all.",
    },
]


def _chunk_sources(result):
    return {c.source_title for c in result["chunks"] if getattr(c, "source_title", None)}


def _max_chunk_len(result, filename):
    lens = [len(c.chunk_content) for c in result["chunks"]
            if getattr(c, "source_title", None) == filename and c.chunk_content]
    return max(lens) if lens else None


def _grade_once(case, result):
    if case.get("off_topic"):
        passed = result["answer"] is None and len(result["chunks"]) == 0
        detail = (f"answer={result['answer']!r} chunks={len(result['chunks'])} "
                  f"{'ok' if passed else 'SHOULD BE EMPTY'}")
        return passed, detail

    got_type = result["query_type"]
    got_ids = set(result["event_ids"])
    got_sources = _chunk_sources(result)

    type_ok = case.get("type") is None or got_type == case["type"]
    req_ok = case["required"].issubset(got_ids)
    forbid_ok = not (case.get("forbidden", set()) & got_ids)
    expected_sources = case.get("expected_sources")
    src_ok = not expected_sources or bool(expected_sources & got_sources)
    answer_ok = result["answer_source"] == "llm_synthesis"

    passed = type_ok and req_ok and forbid_ok and src_ok and answer_ok
    detail = (
        f"type: got={got_type} expected={case.get('type')} {'ok' if type_ok else 'MISMATCH'} | "
        f"ids: got={sorted(got_ids)} required={sorted(case['required'])} {'ok' if req_ok else 'MISSING'}"
        f"{'' if forbid_ok else ' | FORBIDDEN PRESENT'} | "
        f"sources: got={sorted(got_sources)} {'ok' if src_ok else 'MISSING EXPECTED'} | "
        f"answer_source={result['answer_source']} {'ok' if answer_ok else 'NO ANSWER'}"
    )
    return passed, detail


def run_graded_case(case):
    result = chat.run_chat(case["q"])
    passed, detail = _grade_once(case, result)
    label = "PASS" if passed else "FAIL"
    print(f"  [{label}] ({case['group']}) {case['q']}")
    print(f"       {detail}")
    if result.get("warning"):
        print(f"       warning: {result['warning']}")
    return passed, result


def run_diagnostic_case(case):
    result = chat.run_chat(case["q"])
    got_ids = set(result["event_ids"])
    matched = case["expected_event"] in got_ids
    print(f"  [{'MATCHED' if matched else 'NO MATCH'}] {case['q']}")
    print(f"       expected_event={case['expected_event']} got_ids={sorted(got_ids)} "
          f"query_type={result['query_type']}")
    print(f"       reasoning: {result['reasoning']}")
    print(f"       note: {case['note']}")
    return result


def main():
    print("=== End-to-end chat.run_chat() test suite ===\n")

    all_pass = True
    long_pair_results = {}   # pair -> {role: result}
    multi_doc_results = {}   # pair -> {role: result}

    print("--- Graded cases ---")
    for case in CASES:
        if case["group"] == "headline_distance":
            continue
        passed, result = run_graded_case(case)
        all_pass = all_pass and passed
        if case["group"] == "long_pair":
            long_pair_results.setdefault(case["pair"], {})[case["role"]] = result
        if case["group"] == "multi_doc_event":
            multi_doc_results.setdefault(case["pair"], {})[case["role"]] = result

    print("\n--- Headline-distance stress tests (diagnostic, not graded) ---")
    for case in CASES:
        if case["group"] == "headline_distance":
            run_diagnostic_case(case)

    print("\n--- Chunk-length observation: broad vs. narrow on the same long document ---")
    for pair, roles in long_pair_results.items():
        broad, narrow = roles.get("broad"), roles.get("narrow")
        if not broad or not narrow:
            continue
        case = next(c for c in CASES if c.get("pair") == pair and c["group"] == "long_pair")
        filename = next(iter(case["expected_sources"]))
        full_len = DOC_LENGTHS.get(filename)
        broad_len = _max_chunk_len(broad, filename)
        narrow_len = _max_chunk_len(narrow, filename)
        print(f"  {pair} ({filename}, full doc = {full_len} chars):")
        print(f"    broad question  -> max chunk length = {broad_len}"
              f"{' (whole document)' if broad_len == full_len else ''}")
        print(f"    narrow question -> max chunk length = {narrow_len}"
              f"{' (whole document)' if narrow_len == full_len else ''}")
        if broad_len is not None and narrow_len is not None:
            print(f"    shrink observed: {'YES' if narrow_len < broad_len else 'NO'}")

    print("\n--- Doc-count observation: broad vs. narrow on the same multi-doc event ---")
    for pair, roles in multi_doc_results.items():
        broad, narrow = roles.get("broad"), roles.get("narrow")
        if not broad or not narrow:
            continue
        broad_srcs, narrow_srcs = _chunk_sources(broad), _chunk_sources(narrow)
        print(f"  {pair}:")
        print(f"    broad question  -> {len(broad_srcs)} source doc(s): {sorted(broad_srcs)}")
        print(f"    narrow question -> {len(narrow_srcs)} source doc(s): {sorted(narrow_srcs)}")

    print("\n=== Summary ===")
    print(f"  graded cases: {'PASS' if all_pass else 'FAIL'}")
    print("  headline-distance stress tests: see MATCHED/NO MATCH above (informational only)")
    print("  chunk-length / doc-count tables: see observations above (no known-correct answer)")


if __name__ == "__main__":
    main()
