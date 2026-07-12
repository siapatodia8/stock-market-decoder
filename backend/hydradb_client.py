"""
Thin wrapper around the HydraDB Python SDK's query and infra-status calls for
this project's backend.
"""
import os

from dotenv import load_dotenv
from hydra_db import HydraDB

load_dotenv()

API_KEY = os.environ.get("HYDRA_DB_API_KEY")
TENANT_ID = os.environ.get("HYDRA_DB_TENANT_ID", "stock-market-decoder")
SUB_TENANT_ID = "default"

if not API_KEY:
    raise RuntimeError("HYDRA_DB_API_KEY not set in .env")

_client = HydraDB(token=API_KEY)


def query(question: str, mode: str = "thinking", max_results: int = 10,
          graph_context: bool = True, metadata_filters: dict = None):
    """Runs a HydraDB query and returns the raw SDK response object.
    metadata_filters is a flat top-level dict, e.g. {"filing_date": "2020-12-21"}
    — matches one exact value only, no multi-value "any of" support."""
    result = _client.query(
        tenant_id=TENANT_ID,
        sub_tenant_id=SUB_TENANT_ID,  # required explicitly — omitting it returns empty results
        query=question,
        mode=mode,  # "thinking" required for graph_context.synthesis_context to ever populate
        graph_context=graph_context,
        max_results=max_results,
        metadata_filters=metadata_filters,
    )
    return result.data


def infra_status():
    """Tenant infra readiness check — used by /api/health."""
    status = _client.databases.status(database=TENANT_ID)
    return status.data


def list_filing_dates() -> dict:
    """Returns {"YYYY-MM": {"YYYY-MM-DD": narrative_role, ...}} built from the
    filing_date + narrative_role metadata on every live document in the
    tenant. Live lookup, not a static manifest, so it always matches what's
    actually ingested."""
    result = _client.context.list(
        tenant_id=TENANT_ID,
        sub_tenant_id=SUB_TENANT_ID,
        type="knowledge",
    )
    month_to_dates: dict = {}
    for doc in result.data.sources:
        metadata = doc.get("metadata") or {}
        filing_date = metadata.get("filing_date")
        if not filing_date:
            continue
        month_to_dates.setdefault(filing_date[:7], {})[filing_date] = metadata.get("narrative_role")
    return month_to_dates
