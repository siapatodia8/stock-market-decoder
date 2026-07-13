"""
Diagnostic-only script (not part of the production pipeline). Follow-up to
test_monthly_query.py's finding that metadata_filters returned zero results
for every attempt. Tests the leading hypothesis before logging this as a
HydraDB bug: our SDK ingest calls passed filing_date/doc_type/etc. through
the `document_metadata` parameter, which HydraDB's /query docs call out as a
"legacy alias" for the NESTED `additional_metadata` filter key — not the
top-level, schema-backed key we assumed.

Two parts:
  1. Pulls real chunks from an unfiltered query and prints their raw
     `metadata` / `additional_metadata` fields directly, so we can see with
     our own eyes which bucket filing_date/doc_type actually landed in,
     instead of guessing.
  2. Retests metadata_filters across 4 shape combinations (top-level vs.
     nested under additional_metadata, plain value vs. list-wrapped value)
     for both filing_date and doc_type, to isolate exactly which shape (if
     any) actually works, and whether this is filing_date-specific or a
     systemic filtering issue.

Reads HYDRA_DB_API_KEY / HYDRA_DB_TENANT_ID from .env. Run locally — the
sandbox can't reach api.hydradb.com.

Doesn't assume all 13 documents have finished re-indexing after the metadata
fix — checks status first and runs the diagnostic against whichever document
has actually completed, instead of a hardcoded month, so this can run against
partial completion instead of waiting for all 13.
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
DATA_DIR = REPO_ROOT / "data"
RESULTS_PATH = REPO_ROOT / "outputs" / "_metadata_filter_diagnostic_results.json"
INGEST_RESULTS_PATH = REPO_ROOT / "outputs" / "_ingestion_results_sdk.json"

# Import DOCUMENTS so we can look up each completed document's real
# filing_date/doc_type by our own tracking id, without hardcoding one.
# setup_and_ingest_sdk.py lives in scripts/, not this file's own directory
# (this file was moved into tests/ to separate diagnostics from setup/ingest
# utilities) — path inserted explicitly rather than assuming same-directory.
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from setup_and_ingest_sdk import DOCUMENTS  # noqa: E402


def log(msg):
    print(f"[test_metadata_filter_bucket] {msg}", flush=True)


def find_completed_document():
    """Checks live status for every document from the last ingest run and
    returns the manifest entry (from DOCUMENTS) for the first one that's
    actually indexing_status == "completed", or None if none are done yet."""
    if not INGEST_RESULTS_PATH.exists():
        sys.exit(f"{INGEST_RESULTS_PATH} not found — run --step ingest first.")
    with open(INGEST_RESULTS_PATH) as f:
        ingest_data = json.load(f)
    ingest_responses = ingest_data.get("ingest_responses_sdk")
    if not ingest_responses:
        sys.exit("No ingest_responses_sdk found in results file — run --step ingest first.")

    ids = []
    id_to_doc_key = {}
    for item in ingest_responses:
        real_id = item["response"]["data"]["results"][0]["id"]
        ids.append(real_id)
        id_to_doc_key[real_id] = item["doc_id"]

    log(f"Checking live status for {len(ids)} document(s)...")
    status = client.context.status(tenant_id=TENANT_ID, sub_tenant_id=SUB_TENANT_ID, ids=ids)
    completed_keys = []
    for s in status.data.statuses:
        doc_key = id_to_doc_key.get(s.id, s.id)
        log(f"  {doc_key}: {s.indexing_status}")
        if s.indexing_status in ("completed", "success"):
            completed_keys.append(doc_key)

    if not completed_keys:
        log("No documents have finished indexing yet.")
        return None

    chosen_key = completed_keys[0]
    doc = next((d for d in DOCUMENTS if d["id"] == chosen_key), None)
    log(f"Using completed document: {chosen_key!r} "
        f"(filing_date={doc['filing_date']!r}, doc_type={doc['doc_type']!r})")
    return doc


def inspect_raw_chunk_metadata(probe_query):
    """Part 1: run an unfiltered query and print exactly what's in each
    chunk's metadata / additional_metadata fields — the direct way to see
    which bucket filing_date/doc_type actually landed in."""
    log("=== PART 1: inspecting raw chunk metadata (unfiltered query) ===")
    result = client.query(
        tenant_id=TENANT_ID,
        sub_tenant_id=SUB_TENANT_ID,
        query=probe_query,
        mode="thinking",
        graph_context=False,  # don't need graph data for this, keep it minimal
        max_results=5,
    )
    chunks = result.data.chunks or []
    raw = []
    for c in chunks:
        entry = {
            "source_title": getattr(c, "source_title", None),
            "metadata": c.metadata.model_dump() if hasattr(c, "metadata") and hasattr(c.metadata, "model_dump")
                        else getattr(c, "metadata", None),
            "additional_metadata": c.additional_metadata.model_dump() if hasattr(c, "additional_metadata") and hasattr(c.additional_metadata, "model_dump")
                        else getattr(c, "additional_metadata", None),
        }
        raw.append(entry)
        log(f"  chunk source={entry['source_title']!r}")
        log(f"    metadata            = {entry['metadata']}")
        log(f"    additional_metadata = {entry['additional_metadata']}")
    return raw


def inspect_query_signature():
    """Print the SDK's own type signature for metadata_filters, in case the
    shape it expects differs from what the docs describe."""
    log("=== Inspecting client.query's metadata_filters parameter type ===")
    import inspect
    sig = inspect.signature(client.query)
    param = sig.parameters.get("metadata_filters")
    log(f"  metadata_filters annotation: {param.annotation if param else 'NOT FOUND'}")
    try:
        from hydra_db.types import SearchMetadataFilters
        log(f"  SearchMetadataFilters type: {SearchMetadataFilters}")
        if hasattr(SearchMetadataFilters, "model_fields"):
            log(f"  SearchMetadataFilters fields: {list(SearchMetadataFilters.model_fields.keys())}")
    except ImportError as e:
        log(f"  Could not import SearchMetadataFilters directly: {e}")


def try_filter(label, metadata_filters, probe_query):
    log(f"  [{label}] filters={metadata_filters}")
    try:
        result = client.query(
            tenant_id=TENANT_ID,
            sub_tenant_id=SUB_TENANT_ID,
            query=probe_query,
            mode="thinking",
            graph_context=False,
            max_results=10,
            metadata_filters=metadata_filters,
        )
    except Exception as e:
        log(f"    -> ERROR: {e}")
        return {"error": str(e)}
    n_chunks = len(result.data.chunks or [])
    sources = sorted({c.source_title for c in (result.data.chunks or [])})
    log(f"    -> n_chunks={n_chunks} sources={sources}")
    return {"n_chunks": n_chunks, "sources": sources}


def test_filter_shapes(known_filing_date, known_doc_type, probe_query):
    """Part 2: systematically test top-level vs. nested, plain vs.
    list-wrapped, for both filing_date and doc_type."""
    log("=== PART 2: testing metadata_filters shape combinations ===")
    results = {}

    # --- filing_date ---
    results["filing_date_top_level_plain"] = try_filter(
        "filing_date, top-level, plain value",
        {"filing_date": known_filing_date}, probe_query,
    )
    results["filing_date_top_level_list"] = try_filter(
        "filing_date, top-level, list-wrapped",
        {"filing_date": [known_filing_date]}, probe_query,
    )
    results["filing_date_nested_plain"] = try_filter(
        "filing_date, nested under additional_metadata, plain value",
        {"additional_metadata": {"filing_date": known_filing_date}}, probe_query,
    )
    results["filing_date_nested_list"] = try_filter(
        "filing_date, nested under additional_metadata, list-wrapped",
        {"additional_metadata": {"filing_date": [known_filing_date]}}, probe_query,
    )
    # 'document_metadata' is called out as a legacy alias for the nested key
    # in the docs — test it directly too, in case it behaves differently
    # from 'additional_metadata' despite being described as an alias.
    results["filing_date_document_metadata_alias_plain"] = try_filter(
        "filing_date, nested under document_metadata (legacy alias), plain value",
        {"document_metadata": {"filing_date": known_filing_date}}, probe_query,
    )

    # --- doc_type (systemic check: is this filing_date-specific or general?) ---
    results["doc_type_top_level_plain"] = try_filter(
        "doc_type, top-level, plain value", {"doc_type": known_doc_type}, probe_query,
    )
    results["doc_type_nested_plain"] = try_filter(
        "doc_type, nested under additional_metadata, plain value",
        {"additional_metadata": {"doc_type": known_doc_type}}, probe_query,
    )

    return results


def main():
    doc = find_completed_document()
    if doc is None:
        log("Nothing to test yet — re-run this script once at least one document "
            "shows indexing_status 'completed' (check with --step status).")
        return

    probe_query = f"What did Peloton disclose or announce around {doc['filing_date']}?"

    raw_metadata = inspect_raw_chunk_metadata(probe_query)
    inspect_query_signature()
    filter_results = test_filter_shapes(doc["filing_date"], doc["doc_type"], probe_query)

    RESULTS_PATH.parent.mkdir(exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump({
            "tested_document": doc["id"],
            "known_filing_date": doc["filing_date"],
            "known_doc_type": doc["doc_type"],
            "raw_chunk_metadata": raw_metadata,
            "filter_shape_results": filter_results,
        }, f, indent=2, default=str)
    log(f"Saved full results to {RESULTS_PATH}")
    log("Done. Share this file's contents back for analysis.")


if __name__ == "__main__":
    main()
