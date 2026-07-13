"""
Diagnostic-only script (not part of the production pipeline). Follow-up to
findings log #20 — confirms `metadata_filters` works for a single filing_date
value, but doesn't yet answer whether a list of MULTIPLE DIFFERENT values for
one field matches "any of" them. Needed for timeline.py: February 2022 has
two real filing dates (2022-02-05 and 2022-02-08), so a per-month query has
to either filter on both at once or fall back to two separate calls merged
in code.

Tests, against the real Feb 2022 documents:
  1. filing_date filtered to 2022-02-05 alone (expect only that date's docs).
  2. filing_date filtered to 2022-02-08 alone (expect only that date's docs).
  3. filing_date filtered to BOTH dates in one list (does it return the
     union of both, just one, or neither?).

Reads HYDRA_DB_API_KEY / HYDRA_DB_TENANT_ID from .env. Run locally — the
sandbox can't reach api.hydradb.com.
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
RESULTS_PATH = REPO_ROOT / "outputs" / "_multivalue_filter_test_results.json"

PROBE_QUERY = "Based only on the provided documents, what did Peloton disclose or announce around this period?"
DATE_A = "2022-02-05"
DATE_B = "2022-02-08"


def log(msg):
    print(f"[test_multivalue_filter] {msg}", flush=True)


def run(label, metadata_filters):
    log(f"[{label}] filters={metadata_filters}")
    result = client.query(
        tenant_id=TENANT_ID,
        sub_tenant_id=SUB_TENANT_ID,
        query=PROBE_QUERY,
        mode="thinking",
        graph_context=False,
        max_results=10,
        metadata_filters=metadata_filters,
    )
    chunks = result.data.chunks or []
    sources = sorted({c.source_title for c in chunks})
    filing_dates_seen = sorted({
        (c.metadata or {}).get("filing_date") for c in chunks if c.metadata
    })
    log(f"  -> n_chunks={len(chunks)} sources={sources} filing_dates_seen={filing_dates_seen}")
    return {"n_chunks": len(chunks), "sources": sources, "filing_dates_seen": filing_dates_seen}


def main():
    results = {
        "single_date_A": run("single date A (02-05)", {"filing_date": DATE_A}),
        "single_date_B": run("single date B (02-08)", {"filing_date": DATE_B}),
        "both_dates_list": run("both dates, one list", {"filing_date": [DATE_A, DATE_B]}),
    }

    RESULTS_PATH.parent.mkdir(exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2, default=str)
    log(f"Saved results to {RESULTS_PATH}")

    both = results["both_dates_list"]
    a = results["single_date_A"]
    b = results["single_date_B"]
    if set(both["filing_dates_seen"]) == set(a["filing_dates_seen"]) | set(b["filing_dates_seen"]) and both["n_chunks"] > 0:
        log("CONCLUSION: multi-value list appears to work (OR semantics) — "
            "both dates' documents showed up in the combined call.")
    elif both["n_chunks"] == 0:
        log("CONCLUSION: multi-value list returned nothing — does NOT work, "
            "fall back to separate calls per date merged in code.")
    else:
        log("CONCLUSION: unclear/partial — compare the three results above manually.")


if __name__ == "__main__":
    main()
