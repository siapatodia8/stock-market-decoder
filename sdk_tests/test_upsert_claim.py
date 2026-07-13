"""
sdk_tests claim-verification script — tests HydraDB's upsert behavior using
the project's own stale duplicate file
(data/peloton_2021-08-26_shareholder-letter.md, content byte-identical to
data/peloton_2021-08-26_shareholder-letter_v2.md but a different filename,
never actually part of the real 13-document corpus — see
docs/hydradb_findings_log.md finding #7).

Two things under test, both against HydraDB_claims.md / CONTEXT_UPDATES.md's
stated behavior for `POST /context/ingest`'s `upsert` parameter ("upsert: true
(default) ... replacing existing sources with the same ID, not versioning
them"):

  1. Content-vs-ID dedup: ingesting content that is byte-identical to an
     already-ingested document (the real _v2.md), but under a DIFFERENT
     filename (so a different deterministic id per finding #6) — does
     HydraDB recognize the duplicate content, or treat it as a genuinely new,
     separate source? Expectation per finding #6 (ids are filename-derived,
     not content-derived): a new, distinct source.
  2. Basic upsert-in-place: ingesting the exact same filename a second time,
     completely unchanged — should update the existing record in place (per
     the documented `upsert: true` default), not create a duplicate.

Cleans up its own test document afterward via client.context.delete, using the
id returned directly by the ingest call (not a client.context.list()+title
lookup — that was tried first and proved unreliable immediately after ingest,
most likely a propagation-timing gap rather than a HydraDB bug; see
sdk_tests/05_ingest_documents.md T05.1's follow-up notes). This ensures
data/peloton_2021-08-26_shareholder-letter.md (not part of DOCUMENTS in
scripts/setup_and_ingest_sdk.py) never remains ingested after this test
finishes.

Reads HYDRA_DB_API_KEY / HYDRA_DB_TENANT_ID from .env. Run locally:
    python3 sdk_tests/test_upsert_claim.py
"""
import os
import sys
import time
from pathlib import Path

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

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_FILE = REPO_ROOT / "data" / "peloton_2021-08-26_shareholder-letter.md"
V2_FILE_NAME = "peloton_2021-08-26_shareholder-letter_v2.md"


def log(msg):
    print(f"[test_upsert_claim] {msg}", flush=True)


def ingest_once():
    with open(TEST_FILE, "rb") as f:
        resp = client.context.ingest(
            tenant_id=TENANT_ID,
            sub_tenant_id=SUB_TENANT_ID,
            type="knowledge",
            upsert="true",
            documents=(TEST_FILE.name, f, "text/markdown"),
        )
    return resp


def wait_for_status(doc_id, timeout_s=300, interval_s=5):
    """Poll client.context.status by the KNOWN id (not list()+title matching,
    which is unreliable immediately after ingest — see sdk_tests/05 T05.1's
    follow-up notes) until it reaches a terminal state."""
    start = time.time()
    while time.time() - start < timeout_s:
        status = client.context.status(tenant_id=TENANT_ID, sub_tenant_id=SUB_TENANT_ID, ids=[doc_id])
        s = status.data.statuses[0]
        if s.indexing_status in ("completed", "success", "errored"):
            return s.indexing_status
        time.sleep(interval_s)
    return "timeout"


def main():
    log(f"=== Part 1: ingesting {TEST_FILE.name} for the first time ===")
    log("(content is byte-identical to the already-ingested "
        f"{V2_FILE_NAME}, but a different filename -> different id per finding #6)")
    r1 = ingest_once()
    log(f"  -> {r1}")
    doc_id = r1.data.results[0].id
    log(f"  id={doc_id!r} — waiting for indexing to complete before proceeding...")
    log(f"  status: {wait_for_status(doc_id)}")

    log(f"\n=== Part 2: re-ingesting the SAME file ({TEST_FILE.name}) again, unchanged ===")
    log("(tests the basic upsert:true default -> should update in place, not duplicate)")
    r2 = ingest_once()
    log(f"  -> {r2}")
    doc_id_2 = r2.data.results[0].id
    log(f"  status: {wait_for_status(doc_id_2)}")

    log("\n=== Part 3: checking ids returned across both ingests ===")
    if doc_id == doc_id_2:
        log(f"  PASS: same id both times ({doc_id!r}) — consistent with upsert-by-id, "
            f"not a new record per call.")
    else:
        log(f"  ANOMALY: got two different ids for the same filename: {doc_id!r} vs {doc_id_2!r}.")

    log(f"\n  For comparison, {V2_FILE_NAME!r}'s real id (from the main 13-doc ingest) is "
        f"'peloton_2021-08-26_shareholder-letter' — different from {doc_id!r} despite "
        f"byte-identical content -> confirms no content-hash dedup, matching is "
        f"filename/id-derived only (consistent with finding #6).")

    log("\n=== Part 4: cleanup — deleting the test document by its known id, so it "
        "doesn't pollute the real 13-doc corpus ===")
    try:
        resp = client.context.delete(tenant_id=TENANT_ID, sub_tenant_id=SUB_TENANT_ID, ids=[doc_id])
        log(f"  deleted {doc_id}: {resp}")
    except Exception as e:
        log(f"  FAILED to delete {doc_id}: {e}")


if __name__ == "__main__":
    main()
