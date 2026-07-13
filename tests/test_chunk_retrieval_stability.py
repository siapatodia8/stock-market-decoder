"""
Diagnostic-only script (not part of the production pipeline). Repeatedly
queries filing_date=2022-02-05 to measure how often peloton_2022-02-05_8k.md
comes back. Across recent timeline.py runs this chunk was present 3 times
then missing 2 times in a row, always leaving only peloton_2022-02-05_board-pr.md
behind — since that press release's own byline reads "February 8, 2022" (even
though the events it describes happened Feb 5-7), its absence causes
timeline.py to mislabel Feb 5-7 facts as Feb 8.

Tests two theories against each other:
  1. Ranking-boundary: does raising max_results (10 -> 20) recover it?
  2. Thinking-mode reranking: is it more stable under mode="fast" (no query
     expansion/reranking) than mode="thinking"?

Imports hydradb_client/timeline directly from backend/ so this exercises the
exact same call shape production uses. Reads HYDRA_DB_API_KEY /
HYDRA_DB_TENANT_ID from .env. Run locally — the sandbox can't reach
api.hydradb.com.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

import hydradb_client  # noqa: E402
from timeline import GENERIC_QUESTION  # noqa: E402

RESULTS_PATH = REPO_ROOT / "outputs" / "_chunk_retrieval_stability_results.json"
TARGET_DATE = "2022-02-05"
TARGET_DOC = "peloton_2022-02-05_8k.md"
N_REPEATS = 8


def log(msg):
    print(f"[test_chunk_retrieval_stability] {msg}", flush=True)


def run_once(mode: str, max_results: int) -> dict:
    data = hydradb_client.query(
        GENERIC_QUESTION,
        mode=mode,
        max_results=max_results,
        metadata_filters={"filing_date": TARGET_DATE},
    )
    chunks = data.chunks or []
    titles = [getattr(c, "source_title", None) for c in chunks]
    target_present = TARGET_DOC in titles
    target_rank = titles.index(TARGET_DOC) + 1 if target_present else None
    target_score = None
    if target_present:
        for c in chunks:
            if getattr(c, "source_title", None) == TARGET_DOC:
                target_score = getattr(c, "relevancy_score", None)
                break
    return {
        "n_chunks": len(chunks),
        "source_titles": titles,
        "target_present": target_present,
        "target_rank": target_rank,
        "target_relevancy_score": target_score,
    }


def main():
    results = {"thinking_max10": [], "thinking_max20": [], "fast_max10": []}

    log(f"Running {N_REPEATS}x mode=thinking, max_results=10 (matches timeline.py's current call)...")
    for i in range(N_REPEATS):
        r = run_once("thinking", 10)
        results["thinking_max10"].append(r)
        log(f"  [{i+1}/{N_REPEATS}] target_present={r['target_present']} rank={r['target_rank']} n_chunks={r['n_chunks']}")

    log(f"Running {N_REPEATS}x mode=thinking, max_results=20 (tests ranking-boundary theory)...")
    for i in range(N_REPEATS):
        r = run_once("thinking", 20)
        results["thinking_max20"].append(r)
        log(f"  [{i+1}/{N_REPEATS}] target_present={r['target_present']} rank={r['target_rank']} n_chunks={r['n_chunks']}")

    log(f"Running {N_REPEATS}x mode=fast, max_results=10 (tests thinking-mode-reranking theory)...")
    for i in range(N_REPEATS):
        r = run_once("fast", 10)
        results["fast_max10"].append(r)
        log(f"  [{i+1}/{N_REPEATS}] target_present={r['target_present']} rank={r['target_rank']} n_chunks={r['n_chunks']}")

    RESULTS_PATH.parent.mkdir(exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2, default=str)

    for label, runs in results.items():
        hits = sum(1 for r in runs if r["target_present"])
        log(f"CONCLUSION [{label}]: target present in {hits}/{len(runs)} runs.")

    log(f"Saved results to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
