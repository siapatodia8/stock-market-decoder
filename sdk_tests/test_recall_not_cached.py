"""
sdk_tests verification script — directly proves that repeated client.query()
calls are live server round-trips, not served from a local/client-side cache.

Prompted by a reasonable question during the rerun: since
outputs/_ingestion_results_sdk.json persists and merges results across runs
(scripts/setup_and_ingest_sdk.py's save_results()), is it possible recall/query
results are actually being read from that file instead of hitting the live
API each time?

Short answer, confirmed by reading the code: no — save_results() only WRITES
to that file after a live call already returned; nothing in step_recall()
reads from it to short-circuit a call. This script adds direct, wire-level
proof: each client.query() call returns a distinct, server-assigned
meta.request_id and a real meta.latency_ms — values a cache could not
fabricate as different every time.

Run: python3 sdk_tests/test_recall_not_cached.py
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv()

try:
    from hydra_db import HydraDB
except ImportError:
    sys.exit("hydra_db SDK not installed. Run: pip install hydradb-sdk")

API_KEY = os.environ.get("HYDRA_DB_API_KEY")
TENANT_ID = os.environ.get("HYDRA_DB_TENANT_ID", "stock-decoder")
SUB_TENANT_ID = "default"

if not API_KEY:
    sys.exit("HYDRA_DB_API_KEY not set in .env")

client = HydraDB(token=API_KEY)

QUERY = (
    "How did Peloton's leadership changes in 2022 relate to its financial guidance "
    "cuts and restructuring around the same time?"
)


def log(msg):
    print(f"[test_recall_not_cached] {msg}", flush=True)


def main():
    request_ids = []
    for i in range(3):
        result = client.query(
            tenant_id=TENANT_ID,
            sub_tenant_id=SUB_TENANT_ID,
            query=QUERY,
            mode="thinking",
            graph_context=True,
            max_results=10,
        )
        rid = result.meta.request_id
        latency = result.meta.latency_ms
        gc = result.data.graph_context
        synthesis = gc.synthesis_context if gc else None
        request_ids.append(rid)
        preview = (synthesis or "")[:90]
        log(f"Call {i + 1}: request_id={rid!r} latency_ms={latency} "
            f"synthesis_context_preview={preview!r}...")

    log(f"\nAll request_ids: {request_ids}")
    if len(set(request_ids)) == len(request_ids):
        log("CONFIRMED: all request_ids are distinct -> each call was a genuine, "
            "separate live round-trip to the API, not served from a cache.")
    else:
        log("UNEXPECTED: duplicate request_ids found -- would need investigation.")


if __name__ == "__main__":
    main()
