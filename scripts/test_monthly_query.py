"""
Diagnostic-only script (not part of the production pipeline). Tests different
ways of framing the timeline's per-month "what happened" query before we build
it into the backend, so the query design in backend/timeline.py is based on
real results instead of a guess.

The question being tested: what's the best way to retrieve a given month's
real content from HydraDB without the query itself presupposing what happened
(see conversation — a query can't already name "the CEO change" or it's us
injecting knowledge, not HydraDB retrieving it)?

Tests 3 months against tenant `stock-market-decoder`:
  - 2022-02: two known filing_date values (2022-02-05, 2022-02-08) — richest
    case, and tests whether metadata_filters supports multiple exact-match
    values for one field or only a single value.
  - 2021-08: one known filing_date value (2021-08-26) — single-filing case.
  - 2021-03: zero filings — the null case. Tests whether the system correctly
    returns "nothing here" rather than retrieving unrelated content and
    the LLM hallucinating an event that didn't happen that month.

For each month (where applicable), runs 4 query variants and logs full raw
results side by side:
  A. Generic template question (no date/period language at all) +
     metadata_filters scoped to the month's known filing_date(s).
  B. Generic template question WITH the month/year named in the question text
     + the same metadata_filters.
  C. Date-scoped natural-language question, NO metadata_filters — relies on
     retrieval alone to find the right period.
  D. Generic template question, NO metadata_filters, NO date language at all
     — baseline, to show what happens with no scoping whatsoever.

Also runs mode="thinking" vs mode="fast" on variant B for the 2022-02 case,
to check whether built-in multi-query expansion is already good enough or
whether we'd need our own LLM pre-processing step before calling HydraDB.

Reads HYDRA_DB_API_KEY / HYDRA_DB_TENANT_ID from .env, same as the other
scripts. Run locally — the sandbox can't reach api.hydradb.com.
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

try:
    from hydra_db import HydraDB
except ImportError:
    sys.exit("hydra_db SDK not installed. Run: pip install hydradb-sdk")

API_KEY = os.environ.get("HYDRA_DB_API_KEY")
TENANT_ID = os.environ.get("HYDRA_DB_TENANT_ID", "stock-market-decoder")
SUB_TENANT_ID = "default"

if not API_KEY:
    sys.exit("HYDRA_DB_API_KEY not set in .env")

client = HydraDB(token=API_KEY)

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_PATH = REPO_ROOT / "data" / "_monthly_query_test_results.json"

GENERIC_TEMPLATE = (
    "Based only on the provided documents, what did Peloton disclose or "
    "announce around this period?"
)

# month -> known filing_date values, from the ingestion manifest (structural
# routing info, not narrative content).
TEST_MONTHS = {
    "2022-02": {"label": "February 2022", "dates": ["2022-02-05", "2022-02-08"]},
    "2021-08": {"label": "August 2021", "dates": ["2021-08-26"]},
    "2021-03": {"label": "March 2021", "dates": []},
}


def log(msg):
    print(f"[test_monthly_query] {msg}", flush=True)


def summarize(result):
    """Condense a raw query response down to the fields we actually need to
    compare across variants."""
    data = result.data
    gc = data.graph_context
    return {
        "n_chunks": len(data.chunks or []),
        "chunk_sources": sorted({c.source_title for c in (data.chunks or [])}),
        "n_query_paths": len(gc.query_paths or []) if gc else 0,
        "n_chunk_relations": len(gc.chunk_relations or []) if gc else 0,
        "synthesis_context": gc.synthesis_context if gc else None,
        "top_combined_contexts": [
            p.combined_context for p in ((gc.query_paths or [])[:3] if gc else [])
        ],
    }


def run_variant(label, query_text, metadata_filters=None, mode="thinking"):
    log(f"  [{label}] mode={mode} filters={metadata_filters} query={query_text!r}")
    kwargs = dict(
        tenant_id=TENANT_ID,
        sub_tenant_id=SUB_TENANT_ID,
        query=query_text,
        mode=mode,
        graph_context=True,
        max_results=10,
    )
    if metadata_filters is not None:
        kwargs["metadata_filters"] = metadata_filters
    try:
        result = client.query(**kwargs)
    except Exception as e:
        log(f"    -> ERROR: {e}")
        return {"error": str(e)}
    summary = summarize(result)
    log(f"    -> chunks={summary['n_chunks']} query_paths={summary['n_query_paths']} "
        f"synthesis={'yes' if summary['synthesis_context'] else 'no'}")
    return summary


def test_month(month_key, info):
    label = info["label"]
    dates = info["dates"]
    log(f"=== {label} ({month_key}) — known filing_date(s): {dates or 'NONE'} ===")

    results = {}

    # Variant A: generic template, no date language, filtered to known dates
    if dates:
        filters_single = {"filing_date": dates[0]}
        results["A_generic_filtered_single_date"] = run_variant(
            "A (single date filter)", GENERIC_TEMPLATE, metadata_filters=filters_single
        )
        if len(dates) > 1:
            # Test whether metadata_filters accepts a list for multi-value exact match.
            filters_list = {"filing_date": dates}
            results["A2_generic_filtered_list_of_dates"] = run_variant(
                "A2 (list-of-dates filter, testing multi-value support)",
                GENERIC_TEMPLATE, metadata_filters=filters_list,
            )

    # Variant B: generic template WITH month/year named, same filters
    dated_query = f"{GENERIC_TEMPLATE} (period: {label})"
    if dates:
        results["B_generic_with_period_filtered"] = run_variant(
            "B (period named + filter)", dated_query, metadata_filters={"filing_date": dates[0]}
        )
        # Also run mode="fast" on this same variant, to compare against "thinking".
        results["B_fast_mode_comparison"] = run_variant(
            "B (period named + filter, mode=fast)", dated_query,
            metadata_filters={"filing_date": dates[0]}, mode="fast",
        )

    # Variant C: date-scoped natural language, NO metadata_filters
    natural_query = f"What did Peloton disclose or announce in {label}?"
    results["C_natural_language_dated_no_filter"] = run_variant(
        "C (natural language date, no filter)", natural_query
    )

    # Variant D: generic template, no filters, no date language — baseline
    results["D_generic_no_filter_no_date"] = run_variant(
        "D (no scoping at all — baseline)", GENERIC_TEMPLATE
    )

    return results


def main():
    all_results = {}
    for month_key, info in TEST_MONTHS.items():
        all_results[month_key] = test_month(month_key, info)

    RESULTS_PATH.parent.mkdir(exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    log(f"Saved full results to {RESULTS_PATH}")
    log("Done. Share this file's contents back for analysis.")


if __name__ == "__main__":
    main()
