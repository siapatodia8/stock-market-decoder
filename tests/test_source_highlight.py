"""
Test harness for backend/highlight.py — locating a retrieved chunk's exact
span within its full source document (Tier 2 of the source-provenance UI
work; Tier 1, jumping to the right document via chunk.source_title, is
already live in the frontend).

Two layers, same split as test_orchestrator.py/test_retrieval.py:

  1. Deterministic checks — exercises all three match strategies
     (exact / whitespace-tolerant / fuzzy) directly with known strings. No
     network, run anywhere.
  2. Live cases — real HydraDB query, real chunk_content, matched against the
     real data/*.md file that chunk actually came from. Needs
     HYDRA_DB_API_KEY + network (run locally).

Run:
    cd backend && python ../tests/test_source_highlight.py
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

import highlight  # noqa: E402
import hydradb_client  # noqa: E402

DATA_DIR = REPO_ROOT / "data"

# (question, filing_date filter) — reuses real, already-ingested documents.
LIVE_CASES = [
    ("What did Peloton announce in December 2020?", "2020-12-21"),
    ("What was the restructuring plan?", "2022-02-08"),
]


def log(msg):
    print(f"[test_source_highlight] {msg}", flush=True)


def deterministic_checks() -> bool:
    print("=== Deterministic checks (no network) ===")
    ok = True

    # 1. Exact match.
    doc = "Peloton announced a deal today. The deal is worth $420 million."
    chunk = "The deal is worth $420 million."
    result = highlight.find_chunk_span(doc, chunk)
    passed = result is not None and result["method"] == "exact" and result["score"] == 1.0
    ok = ok and passed
    print(f"  [{'PASS' if passed else 'FAIL'}] exact match -> {result}")

    # 2. Whitespace-tolerant match: chunk has single spaces where the
    # "document" has been line-wrapped/reflowed with newlines.
    doc = "Peloton announced a deal today.\nThe deal is worth\n$420   million.\nMore text follows."
    chunk = "The deal is worth $420 million."
    result = highlight.find_chunk_span(doc, chunk)
    passed = result is not None and result["method"] == "whitespace_tolerant" and result["score"] == 1.0
    ok = ok and passed
    print(f"  [{'PASS' if passed else 'FAIL'}] whitespace-tolerant match -> {result}")

    # 3. Fuzzy fallback: chunk has a couple of words changed from the source
    # (simulates markdown emphasis markers stripped, or light rewording),
    # so neither exact nor whitespace-tolerant should succeed, but a long
    # contiguous matching block should still clear the fuzzy threshold.
    doc = "Peloton announced that Barry McCarthy will become CEO effective February 9, 2022."
    chunk = "that Barry McCarthy will become CEO effective February 9th 2022"
    result = highlight.find_chunk_span(doc, chunk)
    passed = result is not None and result["method"] == "fuzzy" and result["score"] >= 0.6
    ok = ok and passed
    print(f"  [{'PASS' if passed else 'FAIL'}] fuzzy fallback -> {result}")

    # 4. No reasonable match at all -> None, not a misleading low-confidence highlight.
    doc = "Peloton announced a deal today. The deal is worth $420 million."
    chunk = "Completely unrelated sentence about a totally different topic entirely."
    result = highlight.find_chunk_span(doc, chunk)
    passed = result is None
    ok = ok and passed
    print(f"  [{'PASS' if passed else 'FAIL'}] no-match case correctly returns None -> {result}")

    print()
    return ok


def live_cases() -> bool:
    print("=== Live cases (needs HYDRA_DB_API_KEY + network) ===")
    all_pass = True

    for question, filing_date in LIVE_CASES:
        log(f"[{filing_date}] query: {question!r}")
        try:
            data = hydradb_client.query(question, mode="thinking", max_results=20,
                                         metadata_filters={"filing_date": filing_date})
        except Exception as e:
            log(f"  SKIP/ERROR: {e}")
            all_pass = False
            continue

        chunks = data.chunks or []
        if not chunks:
            log("  No chunks returned for this filter — nothing to test.")
            all_pass = False
            continue

        for c in chunks:
            source_title = getattr(c, "source_title", None)
            chunk_content = getattr(c, "chunk_content", None)
            if not source_title or not chunk_content:
                continue

            doc_path = DATA_DIR / source_title
            if not doc_path.is_file():
                log(f"  SKIP: {source_title} not found in data/")
                continue

            document_text = doc_path.read_text()
            result = highlight.find_chunk_span(document_text, chunk_content)

            if result is None:
                passed = False
                log(f"  [FAIL] {source_title}: no match found for a real chunk of its own text")
            else:
                # Any real chunk of a document it was actually extracted from
                # should be exact or whitespace-tolerant — a real ingested
                # chunk being merely "fuzzy"-matched against its own source
                # would be a surprising, worth-investigating result.
                passed = result["method"] in ("exact", "whitespace_tolerant")
                preview = result["matched_text"][:80].replace("\n", " ")
                log(f"  [{'PASS' if passed else 'FLAG'}] {source_title}: "
                    f"method={result['method']} score={result['score']} "
                    f"span=({result['start']},{result['end']}) preview={preview!r}...")
            all_pass = all_pass and passed

    print()
    return all_pass


if __name__ == "__main__":
    det_ok = deterministic_checks()
    live_ok = live_cases()
    print("=== Summary ===")
    print(f"  deterministic: {'PASS' if det_ok else 'FAIL'}")
    print(f"  live: {'PASS' if live_ok else 'FAIL (or skipped — check key/network)'}")
