"""
Test harness for scoped retrieval (backend/retrieval.py).

Two layers, same split as test_orchestrator.py:

  1. Deterministic checks — event_id -> filing_date mapping against the real
     timeline_cache.json. No network, run anywhere.
  2. Live retrieval cases — actually query HydraDB for a single event and a
     multi-event set. Needs HYDRA_DB_API_KEY + network (run locally). Asserts
     the right dates were queried and that real evidence came back.

Run:
    cd backend && python ../tests/test_retrieval.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import retrieval
import orchestrator


# event_ids -> the exact filing_dates we expect to query.
MAPPING_CASES = [
    ({"2020-12"}, ["2020-12-21"]),
    ({"2022-02"}, ["2022-02-05", "2022-02-08"]),
    ({"2022-06", "2024-05"}, ["2022-06-06", "2024-05-20"]),
    ({"nonexistent-id"}, []),
]

# Live retrieval cases: (question, event_ids, expected dates).
LIVE_CASES = [
    ("What did Peloton announce in December 2020?", ["2020-12"], ["2020-12-21"]),
    ("Tell me about the CFO change and the refinancing.",
     ["2022-06", "2024-05"], ["2022-06-06", "2024-05-20"]),
]


def deterministic_checks() -> bool:
    print("=== Deterministic checks (no network) ===")
    catalog = orchestrator.load_event_catalog()
    ok = True
    for event_ids, expected in MAPPING_CASES:
        got = retrieval.event_dates(list(event_ids), catalog=catalog)
        passed = got == expected
        ok = ok and passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {sorted(event_ids)} -> {got} "
              f"(expected {expected})")
    print()
    return ok


def live_cases() -> bool:
    print("=== Live retrieval cases (needs HYDRA_DB_API_KEY + network) ===")
    catalog = orchestrator.load_event_catalog()
    all_pass = True
    for question, event_ids, expected_dates in LIVE_CASES:
        try:
            bundle = retrieval.retrieve_for_events(question, event_ids, catalog=catalog)
        except Exception as e:
            print(f"  SKIP/ERROR for {event_ids}: {e}")
            all_pass = False
            continue

        dates_ok = bundle["filing_dates"] == expected_dates
        per_date_ok = len(bundle["per_date"]) == len(expected_dates)
        has_evidence = bool(bundle["chunks"] or bundle["chunk_relations"] or bundle["query_paths"])
        passed = dates_ok and per_date_ok and has_evidence
        all_pass = all_pass and passed

        print(f"  [{'PASS' if passed else 'FAIL'}] {question}")
        print(f"       dates queried: {bundle['filing_dates']} "
              f"(expected {expected_dates}) {'ok' if dates_ok else 'MISMATCH'}")
        print(f"       merged: {len(bundle['chunks'])} chunks, "
              f"{len(bundle['chunk_relations'])} chunk_relations, "
              f"{len(bundle['query_paths'])} query_paths "
              f"{'ok' if has_evidence else 'NO EVIDENCE'}")
        for pd in bundle["per_date"]:
            print(f"         {pd['date']}: {len(pd['chunks'])} chunks, "
                  f"{len(pd['chunk_relations'])} relations, {len(pd['query_paths'])} paths")
    print()
    return all_pass


if __name__ == "__main__":
    det_ok = deterministic_checks()
    live_ok = live_cases()
    print("=== Summary ===")
    print(f"  deterministic: {'PASS' if det_ok else 'FAIL'}")
    print(f"  live retrieval: {'PASS' if live_ok else 'FAIL (or skipped — check key/network)'}")
