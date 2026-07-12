"""
Diagnostic + cleanup script (not part of the production pipeline).

Root cause (confirmed in the dashboard): the original SDK ingestion, before
the document_metadata shape fix, never supplied an explicit "id" field, so
HydraDB auto-assigned its own hash-style id per document (e.g.
"fbedf8ab5ec47eba63b752842cb05d5e"). The corrected ingestion now supplies
"id": doc["id"] (e.g. "peloton_2022-02-08_8k") explicitly in
document_metadata — HydraDB treated that as the new document's own id rather
than matching it against the filename's existing hash id, so upsert:true had
nothing to match and created a second document per filename instead of
updating the first. All 13 documents now exist twice: once under the old
hash id (empty metadata), once under the new slug id (correct metadata).

This script:
  1. Lists everything in the tenant/sub-tenant via client.context.list().
  2. Groups entries by filename. For any filename with more than one entry,
     prints both records' id/metadata/timestamp side by side.
  3. Without --execute (default): dry run only — prints which records WOULD
     be deleted (the old, empty-metadata, non-matching-id copies) and does
     nothing else.
  4. With --execute: actually deletes the confirmed-old copies.

Reads HYDRA_DB_API_KEY / HYDRA_DB_TENANT_ID from .env. Run locally — the
sandbox can't reach api.hydradb.com.
"""
import inspect
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from setup_and_ingest_sdk import DOCUMENTS  # noqa: E402

KNOWN_IDS = {d["id"] for d in DOCUMENTS}


def log(msg):
    print(f"[cleanup_duplicate_ingest] {msg}", flush=True)


def has_real_metadata(entry_metadata):
    """True if this entry's metadata actually has our fields in it, not just
    an empty dict."""
    if not entry_metadata:
        return False
    if hasattr(entry_metadata, "model_dump"):
        entry_metadata = entry_metadata.model_dump()
    return bool(entry_metadata)


def list_all_documents():
    log("Inspecting client.context.list signature...")
    log(f"  {inspect.signature(client.context.list)}")
    log("Calling client.context.list(...)")
    result = client.context.list(
        tenant_id=TENANT_ID,
        sub_tenant_id=SUB_TENANT_ID,
        type="knowledge",
    )
    data = result.data
    log(f"  response.data type: {type(data).__name__}")

    # Don't guess the field name blindly a second time — try the common
    # conventions we've seen elsewhere in this SDK, and if none hit, dump
    # everything so the real field name is visible instead of erroring again.
    items = None
    for field_name in ("sources", "items", "results", "documents", "data"):
        candidate = getattr(data, field_name, None)
        if isinstance(candidate, list):
            items = candidate
            log(f"  Found list under '.{field_name}' ({len(items)} item(s))")
            break

    if items is None:
        log("  Could not find a list field automatically. Available fields: "
            f"{[f for f in dir(data) if not f.startswith('_')]}")
        log(f"  Full dump: {data.model_dump() if hasattr(data, 'model_dump') else data}")
        sys.exit("See the dump above and tell me the correct field name — "
                  "update list_all_documents() accordingly.")

    # Print one real item's actual shape before anything downstream guesses
    # at field names again — last run silently guessed wrong on every field
    # (source_title/id/metadata) and would have flagged all 26 for deletion.
    if items:
        sample = items[0]
        log(f"  Sample item fields: {[f for f in dir(sample) if not f.startswith('_')]}")
        log(f"  Sample item dump: {sample.model_dump() if hasattr(sample, 'model_dump') else sample}")

    return items


def group_by_filename(items):
    # items are plain dicts (confirmed via the sample dump), not objects with
    # attribute access — filename is under "title", e.g. "peloton_..._8k.md".
    groups = {}
    for item in items:
        title = item.get("title")
        groups.setdefault(title, []).append(item)
    return groups


def main():
    execute = "--execute" in sys.argv

    log("Inspecting client.context.delete signature...")
    log(f"  {inspect.signature(client.context.delete)}")

    items = list_all_documents()
    groups = group_by_filename(items)

    duplicates = {title: entries for title, entries in groups.items() if len(entries) > 1}
    if not duplicates:
        log("No duplicate filenames found — nothing to clean up.")
        return

    to_delete = []
    for title, entries in duplicates.items():
        log(f"=== {title} — {len(entries)} copies ===")
        for e in entries:
            doc_id = e.get("id")
            meta = e.get("metadata")
            is_new = doc_id in KNOWN_IDS
            is_populated = has_real_metadata(meta)
            log(f"  id={doc_id!r} metadata_populated={is_populated} "
                f"matches_known_manifest_id={is_new}")
            # Old/stale = hash-style id (not one of our own manifest ids) AND
            # empty metadata. Only delete if BOTH signals agree — if they
            # disagree, leave it alone and flag it for manual review instead
            # of guessing.
            if not is_new and not is_populated:
                to_delete.append((title, doc_id))
            elif is_new and is_populated:
                pass  # the correct, new copy — keep
            else:
                log(f"    -> AMBIGUOUS, not auto-deleting. Review manually.")

    log(f"\n{len(to_delete)} record(s) identified as safe to delete "
        f"(old hash id + empty metadata, on a filename with a confirmed "
        f"good replacement):")
    for title, doc_id in to_delete:
        log(f"  {title} -> {doc_id}")

    # Hard guardrail: we expect ~13 stale duplicates out of ~26 total. If the
    # heuristic ever flags more than half of everything (e.g. from a silent
    # field-extraction failure like the one this script already hit once),
    # refuse to proceed rather than risk deleting good records.
    if len(to_delete) > len(items) / 2:
        sys.exit(f"\nSAFETY ABORT: {len(to_delete)} of {len(items)} records flagged for "
                  f"deletion — that's more than half. This almost certainly means the "
                  f"id/metadata/title extraction is wrong again, not that half the tenant "
                  f"is actually stale. Not proceeding. Check the sample item dump above.")

    if not execute:
        log("\nDry run only — nothing deleted. Re-run with --execute to actually delete these.")
        return

    log("\n--execute passed — deleting now...")
    for title, doc_id in to_delete:
        try:
            resp = client.context.delete(tenant_id=TENANT_ID, sub_tenant_id=SUB_TENANT_ID, ids=[doc_id])
            log(f"  deleted {doc_id} ({title}) -> {resp}")
        except Exception as e:
            log(f"  FAILED to delete {doc_id} ({title}): {e}")


if __name__ == "__main__":
    main()
