"""
Creates the HydraDB tenant (`stock-market-decoder`) with our metadata schema,
waits for it to be ready, then ingests the 13 Peloton documents as Knowledge via
the Python SDK. Alternative to scripts/setup_and_ingest.py (REST) — use this path
when REST ingestion is stuck or failing.

SDK namespaces are `.databases`, `.context`, `.query` (not `.tenants`). Ingests
one document per call, unlike REST's batch upload. Ingest ids are deterministic
(derived from filename + tenant/sub-tenant), so re-ingesting the same filename
safely updates the existing record.

Reads HYDRA_DB_API_KEY / HYDRA_DB_TENANT_ID from .env, same as the REST script.
Does NOT delete any existing tenant — delete `stock-market-decoder` via the
dashboard (dashboard.hydradb.com/databases) first if starting fresh.
"""
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

try:
    from hydra_db import HydraDB
except ImportError:
    sys.exit("hydra_db SDK not installed. Run: pip install hydradb-sdk "
              "(import stays `from hydra_db import HydraDB`).")

API_KEY = os.environ.get("HYDRA_DB_API_KEY")
TENANT_ID = os.environ.get("HYDRA_DB_TENANT_ID", "stock-market-decoder")
SUB_TENANT_ID = "default"

if not API_KEY:
    sys.exit("HYDRA_DB_API_KEY not set in .env")

client = HydraDB(token=API_KEY)

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
RESULTS_PATH = REPO_ROOT / "outputs" / "_ingestion_results_sdk.json"

# Same 13 documents/metadata as setup_and_ingest.py — kept in sync manually since
# this is a hedge script, not the primary path.
DOCUMENTS = [
    {"id": "peloton_2020-12-21_8k", "file": "peloton_2020-12-21_8k.md", "doc_type": "8-K", "narrative_role": "claim", "filing_date": "2020-12-21",
     "doc_summary": "Peloton announces agreement to acquire Precor for $420M to establish U.S. manufacturing capacity"},
    {"id": "peloton_2020-12-21_pr", "file": "peloton_2020-12-21_pr.md", "doc_type": "press_release", "narrative_role": "claim", "filing_date": "2020-12-21",
     "doc_summary": "Press release detailing the Precor acquisition — U.S. manufacturing, R&D, and commercial-market expansion plans"},
    {"id": "peloton_2021-08-26_8k", "file": "peloton_2021-08-26_8k.md", "doc_type": "8-K", "narrative_role": "claim", "filing_date": "2021-08-26",
     "doc_summary": "8-K cover filing referencing FY2021 Q4 results and attached shareholder letter"},
    # Note: file is _v2 — original filename's id got stuck after a delete+
    # re-ingest cycle (findings log #17); re-ingested under a new filename
    # instead. Our own "id" stays the same since it's just our tracking key.
    {"id": "peloton_2021-08-26_shareholder-letter", "file": "peloton_2021-08-26_shareholder-letter_v2.md", "doc_type": "shareholder_letter", "narrative_role": "claim", "filing_date": "2021-08-26",
     "doc_summary": "Confident Q4 FY21 letter: announces new Peloton Output Park factory, sets aggressive FY2022 guidance ($5.4B revenue, 3.63M subscriptions)"},
    {"id": "peloton_2022-02-05_8k", "file": "peloton_2022-02-05_8k.md", "doc_type": "8-K", "narrative_role": "reversal_marker", "filing_date": "2022-02-05",
     "doc_summary": "8-K detailing board changes and CEO transition, Foley to McCarthy, effective Feb 9 2022"},
    {"id": "peloton_2022-02-05_board-pr", "file": "peloton_2022-02-05_board-pr.md", "doc_type": "press_release", "narrative_role": "reversal_marker", "filing_date": "2022-02-05",
     "doc_summary": "Press release announcing new board directors; Barry McCarthy named CEO; John Foley becomes Executive Chair"},
    {"id": "peloton_2022-02-08_8k", "file": "peloton_2022-02-08_8k.md", "doc_type": "8-K", "narrative_role": "reversal_content", "filing_date": "2022-02-08",
     "doc_summary": "8-K cover referencing Q2 FY22 earnings and the restructuring press release"},
    {"id": "peloton_2022-02-08_shareholder-letter", "file": "peloton_2022-02-08_shareholder-letter.md", "doc_type": "shareholder_letter", "narrative_role": "reversal_content", "filing_date": "2022-02-08",
     "doc_summary": "Q2 FY22 letter: net loss $439.4M, guidance cut from $5.4B to $3.7-3.8B, Foley announces his own CEO transition, restructuring detailed"},
    {"id": "peloton_2022-02-08_restructuring-pr", "file": "peloton_2022-02-08_restructuring-pr.md", "doc_type": "press_release", "narrative_role": "reversal_content", "filing_date": "2022-02-08",
     "doc_summary": "$800M annual cost savings, ~2,800 job cuts, winding down in-house manufacturing (POP), $150M capex cut"},
    {"id": "peloton_2022-06-06_8k", "file": "peloton_2022-06-06_8k.md", "doc_type": "8-K", "narrative_role": "reversal_marker", "filing_date": "2022-06-06",
     "doc_summary": "8-K detailing CFO transition, Woodworth to Coddington"},
    {"id": "peloton_2022-06-06_pr", "file": "peloton_2022-06-06_pr.md", "doc_type": "press_release", "narrative_role": "reversal_marker", "filing_date": "2022-06-06",
     "doc_summary": "Press release announcing Liz Coddington as CFO, succeeding Jill Woodworth"},
    {"id": "peloton_2024-05-20_8k", "file": "peloton_2024-05-20_8k.md", "doc_type": "8-K", "narrative_role": "resolution", "filing_date": "2024-05-20",
     "doc_summary": "8-K announcing global refinancing: $275M convertible notes, $1.0B term loan, $100M revolver, repurchasing ~$800M existing notes"},
    {"id": "peloton_2024-05-20_pr", "file": "peloton_2024-05-20_pr.md", "doc_type": "press_release", "narrative_role": "resolution", "filing_date": "2024-05-20",
     "doc_summary": "Press release detailing the refinancing terms"},
]

TENANT_METADATA_SCHEMA = [
    {"name": "doc_type", "data_type": "VARCHAR", "max_length": 128, "enable_match": True},
    {"name": "narrative_role", "data_type": "VARCHAR", "max_length": 128, "enable_match": True},
    {"name": "filing_date", "data_type": "VARCHAR", "max_length": 32, "enable_match": True},
    {"name": "doc_summary", "data_type": "VARCHAR", "max_length": 1024,
     "enable_dense_embedding": True, "enable_sparse_embedding": True},
]


def log(msg):
    print(f"[setup_and_ingest_sdk] {msg}", flush=True)


def load_results():
    if RESULTS_PATH.exists():
        with open(RESULTS_PATH) as f:
            return json.load(f)
    return {}


def save_results(partial):
    RESULTS_PATH.parent.mkdir(exist_ok=True)
    results = load_results()
    results.update(partial)
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2, default=str)
    log(f"Saved to {RESULTS_PATH} (key(s): {list(partial.keys())})")


def step_create():
    log(f"client.databases.create(database={TENANT_ID!r}, tenant_metadata_schema=...)")
    resp = client.databases.create(database=TENANT_ID, tenant_metadata_schema=TENANT_METADATA_SCHEMA)
    log(f"  -> {resp}")
    save_results({"create_response_sdk": resp.model_dump() if hasattr(resp, "model_dump") else str(resp)})


def step_poll(timeout_s=300, interval_s=5):
    start = time.time()
    while time.time() - start < timeout_s:
        status = client.databases.status(database=TENANT_ID)
        vs = status.data.infra.vectorstore_status
        log(f"infra={status.data.infra}")
        # Only requiring knowledge readiness, same reasoning as the REST script —
        # we never touch Memory in this project.
        if status.data.infra.graph_status and vs.knowledge:
            log("Knowledge ready (graph_status + vectorstore_status.knowledge).")
            save_results({"poll_response_sdk": status.data.model_dump()})
            return
        time.sleep(interval_s)
    log("WARNING: timed out waiting for ready signal; proceeding anyway.")


def step_ingest(doc_id=None):
    """One client.context.ingest() call per document — SDK doesn't support the
    REST endpoint's multi-file batch upload in a single call.

    If doc_id is given, only that one document (matched against DOCUMENTS[i]['id'])
    is (re-)ingested — e.g. to retry a single document stuck on Vectorisation
    without re-running all 13. Ids are deterministic per filename/tenant/
    sub-tenant, so `upsert: true` dedupes correctly without an explicit id
    param. Still recommended to remove the stuck document in the dashboard
    first anyway, to force a genuinely fresh processing attempt."""
    docs_to_ingest = DOCUMENTS if doc_id is None else [d for d in DOCUMENTS if d["id"] == doc_id]
    if doc_id is not None and not docs_to_ingest:
        log(f"No document with id={doc_id!r} found in DOCUMENTS.")
        return
    results = load_results().get("ingest_responses_sdk", []) if doc_id is not None else []
    for doc in docs_to_ingest:
        path = DATA_DIR / doc["file"]
        # Must be a JSON array even for one document — server expects
        # file_metadata as []json.RawMessage (findings log #13). Each entry
        # needs an "id" plus the actual fields nested under "metadata" (per
        # api-reference/v2/endpoint/ingest-context.md) — a flat object with
        # no "id"/"metadata" wrapper silently attaches nothing.
        metadata_json = json.dumps([{
            "id": doc["id"],
            "metadata": {
                "doc_type": doc["doc_type"],
                "narrative_role": doc["narrative_role"],
                "filing_date": doc["filing_date"],
                "doc_summary": doc["doc_summary"],
            },
        }])
        with open(path, "rb") as f:
            log(f"client.context.ingest(tenant_id={TENANT_ID!r}, documents={doc['file']!r}, ...)")
            resp = client.context.ingest(
                tenant_id=TENANT_ID,
                sub_tenant_id=SUB_TENANT_ID,
                type="knowledge",
                upsert="true",
                documents=(doc["file"], f, "text/markdown"),
                document_metadata=metadata_json,
            )
        log(f"  -> {resp}")
        results.append({"doc_id": doc["id"], "response": resp.model_dump() if hasattr(resp, "model_dump") else str(resp)})
    save_results({"ingest_responses_sdk": results})
    log(f"Ingested {len(results)} documents via SDK, one call each.")


def step_status():
    """Uses the server-generated ids returned by step_ingest (saved in
    ingest_responses_sdk), NOT our own DOCUMENTS[i]['id'] values —
    client.context.ingest has no id/file_id param, so HydraDB assigns its own
    id per document."""
    results_so_far = load_results()
    ingest_responses = results_so_far.get("ingest_responses_sdk")
    if not ingest_responses:
        log("No ingest_responses_sdk found — run --step ingest first.")
        return
    ids = []
    id_to_doc = {}
    for item in ingest_responses:
        real_id = item["response"]["data"]["results"][0]["id"]
        ids.append(real_id)
        id_to_doc[real_id] = item["doc_id"]
    remaining = set(ids)
    results = {}
    start = time.time()
    timeout_s = 1200
    while remaining and time.time() - start < timeout_s:
        status = client.context.status(tenant_id=TENANT_ID, sub_tenant_id=SUB_TENANT_ID, ids=list(remaining))
        for s in status.data.statuses:
            # SDK response field is `.id`, not REST's `.file_id`.
            if s.indexing_status in ("completed", "success", "errored"):
                doc_label = id_to_doc.get(s.id, s.id)
                results[doc_label] = s.model_dump() if hasattr(s, "model_dump") else str(s)
                remaining.discard(s.id)
        log(f"Still waiting on: {[id_to_doc.get(i, i) for i in remaining]}" if remaining else "All resolved.")
        if remaining:
            time.sleep(10)
    for fid in remaining:
        results[id_to_doc.get(fid, fid)] = {"indexing_status": "timeout"}
    save_results({"status_results_sdk": results})
    n_completed = sum(1 for v in results.values() if isinstance(v, dict) and v.get("indexing_status") in ("completed", "success"))
    log(f"{n_completed}/{len(ids)} documents completed indexing.")


DEFAULT_RECALL_QUERY = (
    "How did Peloton's leadership changes in 2022 relate to its financial guidance "
    "cuts and restructuring around the same time?"
)


def step_recall(query=None, mode="thinking"):
    """mode="thinking" is required for a populated synthesis_context.
    sub_tenant_id must be passed explicitly — omitting it returns empty
    results even for fully-indexed documents (findings log #14/#18)."""
    result = client.query(
        tenant_id=TENANT_ID,
        sub_tenant_id=SUB_TENANT_ID,
        query=query or DEFAULT_RECALL_QUERY,
        mode=mode,
        graph_context=True,
        max_results=10,
    )
    log(f"chunks: {len(result.data.chunks or [])}, "
        f"graph_paths: {len(result.data.graph_context.query_paths or [])}")
    log(f"synthesis_context: {result.data.graph_context.synthesis_context}")
    save_results({"recall_response_sdk": result.data.model_dump() if hasattr(result.data, "model_dump") else str(result.data)})


def step_all():
    """create -> poll -> ingest -> status. Run --step recall manually afterward
    to confirm indexing status "completed" actually translates into usable
    chunks/synthesis."""
    step_create()
    step_poll()
    step_ingest()
    step_status()


STEPS = {
    "create": step_create,
    "poll": step_poll,
    "ingest": step_ingest,
    "status": step_status,
    "recall": step_recall,
    "all": step_all,
}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", choices=STEPS.keys(), default="all")
    parser.add_argument("--query", default=None)
    parser.add_argument("--mode", choices=["fast", "thinking", "auto"], default="thinking")
    parser.add_argument(
        "--doc-id", default=None,
        help="Only used with --step ingest. Re-ingest just this one document (match "
             "against the 'id' field in DOCUMENTS, e.g. "
             "peloton_2021-08-26_shareholder-letter) instead of all 13. Ids are "
             "deterministic, so re-ingesting the same filename safely updates the "
             "existing record.",
    )
    args = parser.parse_args()
    log(f"Target tenant: {TENANT_ID} | step: {args.step}")
    if args.step == "recall":
        step_recall(args.query, mode=args.mode)
    elif args.step == "ingest":
        step_ingest(doc_id=args.doc_id)
    else:
        STEPS[args.step]()


if __name__ == "__main__":
    main()
