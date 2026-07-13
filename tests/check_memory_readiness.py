"""
Quick check: does the stock-market-decoder tenant's Memory infrastructure
actually come back ready, without needing to recreate the database?

Per the SDK's TenantsVectorstoreStatusV2 type, a tenant's vectorstore_status
carries two independent readiness flags — `knowledge` and `memories` — both
provisioned together when the tenant was created via client.databases.create().
Our original setup script (setup_and_ingest_sdk.py) only ever polled
`vectorstore_status.knowledge`, since Memory was never used. This just reads
the same status endpoint and prints the flag we never checked.

Run: python tests/check_memory_readiness.py
"""
import os

from dotenv import load_dotenv
from hydra_db import HydraDB

load_dotenv()

API_KEY = os.environ.get("HYDRA_DB_API_KEY")
TENANT_ID = os.environ.get("HYDRA_DB_TENANT_ID", "stock-market-decoder")

if not API_KEY:
    raise SystemExit("HYDRA_DB_API_KEY not set in .env")

client = HydraDB(token=API_KEY)


def log(msg):
    print(f"[check_memory_readiness] {msg}", flush=True)


def check_memory_readiness():
    status = client.databases.status(database=TENANT_ID)
    infra = status.data.infra
    vs = infra.vectorstore_status if infra else None

    log(f"tenant: {TENANT_ID!r}")
    log(f"graph_status: {infra.graph_status if infra else None}")
    log(f"scheduler_status: {infra.scheduler_status if infra else None}")
    log(f"vectorstore_status.knowledge: {vs.knowledge if vs else None}")
    log(f"vectorstore_status.memories: {vs.memories if vs else None}")

    if vs and vs.memories:
        log("✓ Memory infra is ready — no database recreation needed. "
            "Safe to call context.ingest(type='memory', ...) directly.")
    elif vs is not None:
        log("✗ Memory infra not ready yet. Options: wait and re-run this "
            "check, or attempt one context.ingest(type='memory', ...) call "
            "anyway — some tenants provision memory infra lazily on first "
            "write rather than up front.")
    else:
        log("vectorstore_status came back empty/null — inspect the raw "
            "`status` object below to see what the API actually returned.")
        log(f"raw status.data: {status.data}")


if __name__ == "__main__":
    check_memory_readiness()
