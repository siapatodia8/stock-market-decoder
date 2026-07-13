"""
Creates the HydraDB tenant (`stock-market-decoder`) with our metadata schema,
waits for it to be ready, then ingests the 13 Peloton documents as Knowledge via
the raw REST API. Also includes standalone diagnostic steps (recall, boolean
search, memory test, sub-tenant test) for probing specific API behavior.

Reads HYDRA_DB_API_KEY / HYDRA_DB_TENANT_ID from .env.
"""
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("HYDRA_DB_API_KEY")
TENANT_ID = os.environ.get("HYDRA_DB_TENANT_ID", "stock-market-decoder")
SUB_TENANT_ID = "default"
BASE_URL = "https://api.hydradb.com"

if not API_KEY:
    sys.exit("HYDRA_DB_API_KEY not set in .env")

JSON_HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}
AUTH_ONLY_HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
}  # used for multipart calls — let `requests` set its own Content-Type w/ boundary

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
RESULTS_PATH = REPO_ROOT / "outputs" / "_ingestion_results.json"

# Per-document metadata, from PELOTON_DATASET.md
DOCUMENTS = [
    {"id": "peloton_2020-12-21_8k", "file": "peloton_2020-12-21_8k.md", "doc_type": "8-K", "narrative_role": "claim", "filing_date": "2020-12-21",
     "doc_summary": "Peloton announces agreement to acquire Precor for $420M to establish U.S. manufacturing capacity"},
    {"id": "peloton_2020-12-21_pr", "file": "peloton_2020-12-21_pr.md", "doc_type": "press_release", "narrative_role": "claim", "filing_date": "2020-12-21",
     "doc_summary": "Press release detailing the Precor acquisition — U.S. manufacturing, R&D, and commercial-market expansion plans"},
    {"id": "peloton_2021-08-26_8k", "file": "peloton_2021-08-26_8k.md", "doc_type": "8-K", "narrative_role": "claim", "filing_date": "2021-08-26",
     "doc_summary": "8-K cover filing referencing FY2021 Q4 results and attached shareholder letter"},
    {"id": "peloton_2021-08-26_shareholder-letter", "file": "peloton_2021-08-26_shareholder-letter.md", "doc_type": "shareholder_letter", "narrative_role": "claim", "filing_date": "2021-08-26",
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

# tenant_metadata_schema is a LIST of field definitions (per CustomPropertyDefinition
# in the real OpenAPI spec), not a dict. `name` is the field name; `data_type` uses
# the MilvusDataType enum (VARCHAR for all our text fields).
TENANT_METADATA_SCHEMA = [
    {"name": "doc_type", "data_type": "VARCHAR", "max_length": 128, "enable_match": True},
    {"name": "narrative_role", "data_type": "VARCHAR", "max_length": 128, "enable_match": True},
    {"name": "filing_date", "data_type": "VARCHAR", "max_length": 32, "enable_match": True},
    {"name": "doc_summary", "data_type": "VARCHAR", "max_length": 1024,
     "enable_dense_embedding": True, "enable_sparse_embedding": True},
]


def log(msg):
    print(f"[setup_and_ingest] {msg}", flush=True)


def create_database():
    """POST /tenants/create. A 409 means the tenant already exists, treated as
    success."""
    url = f"{BASE_URL}/tenants/create"
    payload = {
        "tenant_id": TENANT_ID,
        "is_embeddings_tenant": True,
        "tenant_metadata_schema": TENANT_METADATA_SCHEMA,
    }
    log(f"POST {url}\n  payload={json.dumps(payload, indent=2)}")
    resp = requests.post(url, headers=JSON_HEADERS, json=payload, timeout=30)
    log(f"  -> status={resp.status_code} body={resp.text[:2000]}")
    if resp.status_code == 409:
        log("  tenant already exists, continuing")
        return {"already_exists": True}
    resp.raise_for_status()
    return resp.json()


def poll_database_ready(timeout_s=300, interval_s=5):
    """GET /tenants/infra/status. Ready = scheduler_status + graph_status + at
    least one vectorstore_status entry true (array is [0]=Knowledge,
    [1]=Memories — see findings log #2). Only requires ANY entry true, not both:
    this project never calls /memories/add_memory, so Memory's flag may never
    turn true, and Knowledge's flag alone has been observed staying false for
    20+ minutes even when ingestion is proceeding normally. Later `status`/
    `recall` steps are the real source of truth on whether data is usable."""
    url = f"{BASE_URL}/tenants/infra/status"
    params = {"tenant_id": TENANT_ID}
    start = time.time()
    while time.time() - start < timeout_s:
        resp = requests.get(url, headers=JSON_HEADERS, params=params, timeout=30)
        log(f"GET {url}?tenant_id={TENANT_ID} -> status={resp.status_code} body={resp.text[:1500]}")
        if resp.status_code == 200:
            body = resp.json()
            infra = body.get("infra", {})
            vs = infra.get("vectorstore_status", [])
            ready = (
                infra.get("scheduler_status") is True
                and infra.get("graph_status") is True
                and len(vs) == 2
                and any(vs)
            )
            if ready:
                log("Tenant infra reports ready (scheduler + graph + at least one vectorstore — "
                    "not requiring both, since we never use Memory; see docstring).")
                return body
        time.sleep(interval_s)
    log("WARNING: timed out waiting for ready signal; proceeding anyway.")
    return {}


def ingest_documents():
    """POST /ingestion/upload_knowledge, multipart. `files` holds the binary
    documents; `file_metadata` is a JSON-string array, one object per file, in the
    same order, each with file_id/metadata/additional_metadata."""
    url = f"{BASE_URL}/ingestion/upload_knowledge"
    files = []
    file_metadata = []
    opened = []
    try:
        for doc in DOCUMENTS:
            path = DATA_DIR / doc["file"]
            f = open(path, "rb")
            opened.append(f)
            files.append(("files", (doc["file"], f, "text/markdown")))
            file_metadata.append({
                "file_id": doc["id"],
                "metadata": {
                    "doc_type": doc["doc_type"],
                    "narrative_role": doc["narrative_role"],
                    "filing_date": doc["filing_date"],
                    "doc_summary": doc["doc_summary"],
                },
            })

        data = {
            "tenant_id": TENANT_ID,
            "sub_tenant_id": SUB_TENANT_ID,
            "upsert": "true",
            "file_metadata": json.dumps(file_metadata),
        }
        log(f"POST {url} (multipart) with {len(DOCUMENTS)} documents")
        resp = requests.post(url, headers=AUTH_ONLY_HEADERS, data=data, files=files, timeout=120)
        log(f"  -> status={resp.status_code} body={resp.text[:3000]}")
        resp.raise_for_status()
        return resp.json()
    finally:
        for f in opened:
            f.close()


TEST_SUBTENANT_ID = "diagnostic_subtenant_test"
TEST_SUBTENANT_FILE_ID = "subtenant_test_precor_doc"


def ingest_test_doc_custom_subtenant():
    """POST /ingestion/upload_knowledge — same tenant (stock-market-decoder), but a
    custom-named sub_tenant_id instead of 'default'. Uploads one already-ingested-
    under-default file (peloton_2020-12-21_pr.md, contains 'Precor' verbatim) under
    a NEW file_id so it's a distinct source, purely to test whether sub_tenant
    naming ('default' vs. a custom name) affects whether chunks become searchable."""
    url = f"{BASE_URL}/ingestion/upload_knowledge"
    path = DATA_DIR / "peloton_2020-12-21_pr.md"
    with open(path, "rb") as f:
        files = [("files", (path.name, f, "text/markdown"))]
        file_metadata = [{
            "file_id": TEST_SUBTENANT_FILE_ID,
            "metadata": {
                "doc_type": "press_release",
                "narrative_role": "claim",
                "filing_date": "2020-12-21",
                "doc_summary": "Diagnostic re-upload of the Precor acquisition press release, under a custom sub_tenant_id instead of default.",
            },
        }]
        data = {
            "tenant_id": TENANT_ID,
            "sub_tenant_id": TEST_SUBTENANT_ID,
            "upsert": "true",
            "file_metadata": json.dumps(file_metadata),
        }
        log(f"POST {url} (multipart) — custom sub_tenant_id='{TEST_SUBTENANT_ID}'")
        resp = requests.post(url, headers=AUTH_ONLY_HEADERS, data=data, files=files, timeout=120)
        log(f"  -> status={resp.status_code} body={resp.text[:3000]}")
        resp.raise_for_status()
        return resp.json()


def test_boolean_recall_custom_subtenant(query="Precor", operator="or", max_results=10):
    """Same as test_boolean_recall, but scoped to TEST_SUBTENANT_ID instead of
    'default' — the direct comparison point for the sub-tenant-naming theory."""
    url = f"{BASE_URL}/recall/boolean_recall"
    payload = {
        "tenant_id": TENANT_ID,
        "sub_tenant_id": TEST_SUBTENANT_ID,
        "query": query,
        "operator": operator,
        "max_results": max_results,
        "search_mode": "sources",
    }
    log(f"POST {url}\n  payload={json.dumps(payload, indent=2)}")
    resp = requests.post(url, headers=JSON_HEADERS, json=payload, timeout=60)
    log(f"  -> status={resp.status_code} body={resp.text[:5000]}")
    resp.raise_for_status()
    return resp.json()


def step_subtenant_test():
    """Full comparison: ingest one test doc under a custom sub_tenant_id, poll its
    processing status, then boolean_recall for 'Precor' scoped to that sub-tenant.
    We already know boolean_recall for 'Precor' under sub_tenant_id='default'
    returns 0 chunks (see hydradb_findings_log.md) — this isolates whether 'default'
    specifically is the problem, or whether it's tenant-wide regardless of
    sub-tenant naming."""
    ingest_resp = ingest_test_doc_custom_subtenant()
    log("=== Polling verify_processing for the custom-sub_tenant test doc ===")
    status = poll_ingestion_status([TEST_SUBTENANT_FILE_ID], timeout_s=300, interval_s=10)
    log("=== boolean_recall('Precor') scoped to the custom sub_tenant ===")
    recall_resp = test_boolean_recall_custom_subtenant("Precor")
    n_chunks = len(recall_resp.get("chunks", []))
    log(f"Custom sub_tenant boolean_recall returned {n_chunks} chunk(s) "
        f"(compare to 0 chunks under sub_tenant_id='default' for the same term).")
    save_results({
        "subtenant_test": {
            "ingest_response": ingest_resp,
            "processing_status": status,
            "boolean_recall_response": recall_resp,
        }
    })


def test_recall(query, mode="thinking", graph_context=True, max_results=10):
    """POST /recall/full_recall — the actual search/synthesis endpoint. Used here
    specifically to test finding #3 in hydradb_findings_log.md: does recall work
    correctly even though verify_processing never reported 'completed'? A query
    that specifically requires connecting facts ACROSS documents (not just
    matching one) is the real test of graph_context, not just basic search."""
    url = f"{BASE_URL}/recall/full_recall"
    payload = {
        "tenant_id": TENANT_ID,
        "sub_tenant_id": SUB_TENANT_ID,
        "query": query,
        "max_results": max_results,
        "mode": mode,
        "graph_context": graph_context,
    }
    log(f"POST {url}\n  payload={json.dumps(payload, indent=2)}")
    resp = requests.post(url, headers=JSON_HEADERS, json=payload, timeout=60)
    log(f"  -> status={resp.status_code} body={resp.text[:5000]}")
    resp.raise_for_status()
    return resp.json()


def test_boolean_recall(query, operator="or", max_results=10):
    """POST /recall/boolean_recall — pure BM25 exact-term search, NO embeddings
    involved at all. Used to isolate why full_recall returns empty chunks/sources:
    if this finds real matches, the problem is specific to embedding/hybrid search
    (full_recall's vector path). If this ALSO returns nothing, chunk indexing
    itself likely hasn't happened yet — separate from graph extraction, which we
    already confirmed works via the dashboard and graph_context results."""
    url = f"{BASE_URL}/recall/boolean_recall"
    payload = {
        "tenant_id": TENANT_ID,
        "sub_tenant_id": SUB_TENANT_ID,
        "query": query,
        "operator": operator,
        "max_results": max_results,
        "search_mode": "sources",
    }
    log(f"POST {url}\n  payload={json.dumps(payload, indent=2)}")
    resp = requests.post(url, headers=JSON_HEADERS, json=payload, timeout=60)
    log(f"  -> status={resp.status_code} body={resp.text[:5000]}")
    resp.raise_for_status()
    return resp.json()


TEST_MEMORY_ID = "_diagnostic_test_memory_do_not_use_as_real_data"


def add_test_memory():
    """POST /memories/add_memory — ONE throwaway diagnostic item, clearly separate
    from real project data. Purpose: empirically determine, via cause-and-effect
    rather than trusting any doc, whether using Memory measurably changes anything
    (vectorstore_status index, /tenants/monitor's memory_collection stats, and
    whether recall_preferences can find it) — independent confirmation of which
    store is which, and a speed contrast against our stuck Knowledge documents."""
    url = f"{BASE_URL}/memories/add_memory"
    payload = {
        "tenant_id": TENANT_ID,
        "sub_tenant_id": SUB_TENANT_ID,
        "memories": [
            {
                "text": "Diagnostic test memory: the user's favorite test color is purple.",
                "infer": False,
                "source_id": TEST_MEMORY_ID,
            }
        ],
    }
    log(f"POST {url}\n  payload={json.dumps(payload, indent=2)}")
    resp = requests.post(url, headers=JSON_HEADERS, json=payload, timeout=30)
    log(f"  -> status={resp.status_code} body={resp.text[:2000]}")
    if resp.status_code >= 400:
        # Don't crash the whole diagnostic — a failure here (e.g. Memory's
        # collection not being provisioned) is itself the finding we're after.
        return {"error": True, "status_code": resp.status_code, "body": resp.json() if resp.text else None}
    return resp.json()


def test_recall_preferences(query, mode="fast"):
    """POST /recall/recall_preferences — same shape as full_recall but targets the
    Memory collection specifically. Used to confirm whether our test memory item is
    actually searchable, as a speed/functionality contrast to Knowledge."""
    url = f"{BASE_URL}/recall/recall_preferences"
    payload = {
        "tenant_id": TENANT_ID,
        "sub_tenant_id": SUB_TENANT_ID,
        "query": query,
        "max_results": 5,
        "mode": mode,
    }
    log(f"POST {url}\n  payload={json.dumps(payload, indent=2)}")
    resp = requests.post(url, headers=JSON_HEADERS, json=payload, timeout=60)
    log(f"  -> status={resp.status_code} body={resp.text[:3000]}")
    resp.raise_for_status()
    return resp.json()


def step_memory_test():
    """Full diagnostic: snapshot infra/monitor before, add one test memory, poll its
    processing status, snapshot infra/monitor after, then try recall_preferences.
    Prints a clear before/after comparison so the effect of adding Memory content is
    directly observable, rather than inferred from documentation."""
    log("=== BEFORE: infra/status + monitor ===")
    before_infra = requests.get(f"{BASE_URL}/tenants/infra/status", headers=JSON_HEADERS,
                                 params={"tenant_id": TENANT_ID}, timeout=30).json()
    before_monitor = monitor_tenant()
    log(f"BEFORE infra.vectorstore_status = {before_infra.get('infra', {}).get('vectorstore_status')}")
    log(f"BEFORE monitor = {json.dumps(before_monitor, indent=2)}")

    add_resp = add_test_memory()

    mem_status = {}
    recall_resp = None
    if add_resp.get("error"):
        log(f"add_memory FAILED (status={add_resp['status_code']}) — this is itself a "
            f"finding, not a script bug. Skipping processing-status poll and "
            f"recall_preferences test since there's nothing to look for.")
    else:
        log("=== Polling verify_processing for the test memory (docs claim seconds) ===")
        mem_status = poll_ingestion_status([TEST_MEMORY_ID], timeout_s=120, interval_s=5)
        log("=== Trying recall_preferences for the test memory ===")
        recall_resp = test_recall_preferences("What is the user's favorite test color?")

    log("=== AFTER: infra/status + monitor ===")
    after_infra = requests.get(f"{BASE_URL}/tenants/infra/status", headers=JSON_HEADERS,
                                params={"tenant_id": TENANT_ID}, timeout=30).json()
    after_monitor = monitor_tenant()
    log(f"AFTER infra.vectorstore_status = {after_infra.get('infra', {}).get('vectorstore_status')}")
    log(f"AFTER monitor = {json.dumps(after_monitor, indent=2)}")

    save_results({
        "memory_test": {
            "before_infra": before_infra,
            "before_monitor": before_monitor,
            "add_memory_response": add_resp,
            "memory_processing_status": mem_status,
            "after_infra": after_infra,
            "after_monitor": after_monitor,
            "recall_preferences_response": recall_resp,
        }
    })
    log("Saved full before/after comparison under 'memory_test' key.")


def extract_source_ids(ingest_resp):
    """IDs come back as results[].source_id in the upload response."""
    if not isinstance(ingest_resp, dict):
        return []
    return [r["source_id"] for r in ingest_resp.get("results", []) if r.get("source_id")]


def poll_ingestion_status(source_ids, timeout_s=1200, interval_s=10):
    """POST /ingestion/verify_processing — despite being a POST, all inputs are
    query params (file_ids repeated, tenant_id, sub_tenant_id), no JSON body.
    Terminal states: 'completed' (or legacy alias 'success') and 'errored'."""
    url = f"{BASE_URL}/ingestion/verify_processing"
    remaining = set(source_ids)
    results = {}
    start = time.time()
    while remaining and time.time() - start < timeout_s:
        params = {
            "file_ids": list(remaining),
            "tenant_id": TENANT_ID,
            "sub_tenant_id": SUB_TENANT_ID,
        }
        resp = requests.post(url, headers=JSON_HEADERS, params=params, timeout=30)
        log(f"POST {url} file_ids={list(remaining)} -> status={resp.status_code} body={resp.text[:2000]}")
        if resp.status_code == 200:
            body = resp.json()
            for s in body.get("statuses", []):
                fid = s.get("file_id")
                status = s.get("indexing_status")
                if status in ("completed", "success", "errored"):
                    results[fid] = s
                    remaining.discard(fid)
        if remaining:
            time.sleep(interval_s)
    for fid in remaining:
        results[fid] = {"indexing_status": "timeout"}
    return results


def monitor_tenant():
    """GET /tenants/monitor — real collection stats (row_count, dimensions), useful
    as a second opinion when /tenants/infra/status's vectorstore_status flag looks
    stuck. Knowledge's collection field is `knowledge_collection` (not
    `normal_collection`, despite the docs' example response — findings log #7)."""
    url = f"{BASE_URL}/tenants/monitor"
    resp = requests.get(url, headers=JSON_HEADERS, params={"tenant_id": TENANT_ID}, timeout=30)
    log(f"GET {url}?tenant_id={TENANT_ID} -> status={resp.status_code} body={resp.text[:2000]}")
    resp.raise_for_status()
    return resp.json()


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
    result = create_database()
    save_results({"create_response": result})


def step_poll():
    result = poll_database_ready()
    save_results({"poll_response": result})


def step_monitor():
    result = monitor_tenant()
    save_results({"monitor_response": result})


def step_ingest():
    result = ingest_documents()
    save_results({"ingest_response": result})
    ids = extract_source_ids(result)
    if ids:
        log(f"Found source_id(s) to track: {ids}")
    else:
        log("No source_id(s) found in response shape — check the raw body above.")


def step_status():
    results = load_results()
    ingest_resp = results.get("ingest_response")
    ids = extract_source_ids(ingest_resp) if ingest_resp else []
    if not ids:
        log("No source_ids saved from a previous 'ingest' step — run --step ingest first.")
        return
    status_results = poll_ingestion_status(ids)
    save_results({"status_results": status_results})


# Deliberately requires connecting facts ACROSS documents (the CEO change is in one
# filing, the guidance cut / restructuring is in another) — a plain keyword match on
# a single chunk wouldn't answer this well; a working graph should.
DEFAULT_RECALL_QUERY = (
    "How did Peloton's leadership changes in 2022 relate to its financial guidance "
    "cuts and restructuring around the same time?"
)


def step_recall(query=None, mode="thinking", graph_context=True):
    result = test_recall(query or DEFAULT_RECALL_QUERY, mode=mode, graph_context=graph_context)
    save_results({"recall_response": result})
    n_chunks = len(result.get("chunks", []))
    n_paths = len(result.get("graph_context", {}).get("query_paths", []))
    log(f"Recall returned {n_chunks} chunk(s) and {n_paths} graph query_path(s).")


def step_boolean(query=None, operator="or"):
    result = test_boolean_recall(query or "Precor", operator=operator)
    save_results({"boolean_recall_response": result})
    n_chunks = len(result.get("chunks", []))
    log(f"Boolean recall returned {n_chunks} chunk(s).")


def step_all():
    step_create()
    step_poll()
    step_ingest()
    step_status()


STEPS = {
    "create": step_create,   # just create the tenant + schema
    "poll": step_poll,       # just poll /tenants/infra/status until ready (or timeout)
    "monitor": step_monitor, # just check /tenants/monitor (real collection stats — second opinion on readiness)
    "ingest": step_ingest,   # just upload the 13 documents
    "status": step_status,   # just poll verify_processing, using ids saved by the last 'ingest' run
    "recall": step_recall,   # just run a full_recall query to test search/synthesis directly
    "boolean": step_boolean, # plain BM25 text search, no embeddings — isolates vector vs. chunk-indexing issues
    "memtest": step_memory_test,  # add one throwaway memory item, compare infra/monitor before+after, confirm via recall_preferences
    "subtenant": step_subtenant_test,  # test whether sub_tenant_id='default' specifically is the problem
    "all": step_all,         # run the full sequence
}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--step", choices=STEPS.keys(), default="all",
        help="Run just one step (create/poll/ingest/status/recall) instead of the full "
             "sequence. Each step reads/writes outputs/_ingestion_results.json so you can "
             "run them separately, one at a time, and still have 'status' pick up ids "
             "from a previous 'ingest' run.",
    )
    parser.add_argument(
        "--query", default=None,
        help="Only used with --step recall. Overrides the default cross-document test query.",
    )
    parser.add_argument(
        "--mode", choices=["fast", "thinking"], default="thinking",
        help="Only used with --step recall.",
    )
    parser.add_argument(
        "--no-graph-context", action="store_true",
        help="Only used with --step recall. Disable graph_context to test plain retrieval only.",
    )
    parser.add_argument(
        "--operator", choices=["or", "and", "phrase"], default="or",
        help="Only used with --step boolean.",
    )
    args = parser.parse_args()
    log(f"Target tenant: {TENANT_ID} | step: {args.step}")
    if args.step == "recall":
        step_recall(args.query, mode=args.mode, graph_context=not args.no_graph_context)
    elif args.step == "boolean":
        step_boolean(args.query, operator=args.operator)
    else:
        STEPS[args.step]()


if __name__ == "__main__":
    main()
