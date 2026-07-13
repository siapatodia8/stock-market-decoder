"""
Diagnostic-only script (not part of the production pipeline). Runs the same
filing_date-scoped query twice back to back, with metadata_filters unchanged
between calls, to check whether HydraDB's mode="thinking" retrieval is
deterministic — follow-up to two timeline.py runs returning different
evidence (Aug 2021 pulled Reg FD boilerplate one run, real Q4 content the
other; Feb 2022's reversal_marker snippet lost the CEO-transition fact on
one run) despite the query code being unchanged between them.

Imports hydradb_client/synthesis/timeline directly from backend/ so this
test exercises the exact same code path production uses, not a hand-rolled
duplicate. Reads HYDRA_DB_API_KEY / HYDRA_DB_TENANT_ID from .env. Run
locally — the sandbox can't reach api.hydradb.com.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

import hydradb_client  # noqa: E402
import synthesis  # noqa: E402
from timeline import GENERIC_QUESTION  # noqa: E402

RESULTS_PATH = REPO_ROOT / "outputs" / "_retrieval_determinism_test_results.json"

# Dates that showed different-looking evidence between two prior timeline.py runs.
TEST_DATES = ["2021-08-26", "2022-02-05"]


def log(msg):
    print(f"[test_retrieval_determinism] {msg}", flush=True)


def run_once(date: str) -> dict:
    data = hydradb_client.query(
        GENERIC_QUESTION,
        mode="thinking",
        metadata_filters={"filing_date": date},
    )
    chunks = data.chunks or []
    gc = data.graph_context
    relations = gc.chunk_relations if gc and gc.chunk_relations else []
    paths = gc.query_paths if gc and gc.query_paths else []
    snippets = synthesis.get_context_snippets(chunks=chunks, chunk_relations=relations, query_paths=paths)
    return {
        "n_chunks": len(chunks),
        "source_titles": sorted({getattr(c, "source_title", None) for c in chunks if getattr(c, "source_title", None)}),
        "snippets": snippets,
    }


def compare(run_a: dict, run_b: dict) -> dict:
    return {
        "same_chunk_count": run_a["n_chunks"] == run_b["n_chunks"],
        "same_source_titles": run_a["source_titles"] == run_b["source_titles"],
        "same_snippets": run_a["snippets"] == run_b["snippets"],
        "snippets_only_in_run_1": [s for s in run_a["snippets"] if s not in run_b["snippets"]],
        "snippets_only_in_run_2": [s for s in run_b["snippets"] if s not in run_a["snippets"]],
    }


def main():
    results = {}
    for date in TEST_DATES:
        log(f"[{date}] run 1...")
        run_a = run_once(date)
        log(f"  -> n_chunks={run_a['n_chunks']} sources={run_a['source_titles']}")

        log(f"[{date}] run 2...")
        run_b = run_once(date)
        log(f"  -> n_chunks={run_b['n_chunks']} sources={run_b['source_titles']}")

        diff = compare(run_a, run_b)
        results[date] = {"run_1": run_a, "run_2": run_b, "diff": diff}

        if diff["same_snippets"]:
            log(f"[{date}] CONCLUSION: identical snippets both runs — retrieval is stable for this date.")
        else:
            log(f"[{date}] CONCLUSION: snippets differ between runs — retrieval is NOT deterministic for this date.")
            if diff["snippets_only_in_run_1"]:
                log(f"    only in run 1: {diff['snippets_only_in_run_1']}")
            if diff["snippets_only_in_run_2"]:
                log(f"    only in run 2: {diff['snippets_only_in_run_2']}")

    RESULTS_PATH.parent.mkdir(exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2, default=str)
    log(f"Saved results to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
