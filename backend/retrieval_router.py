"""
Stage 1 (redesigned) — routes a question to timeline events using REAL
retrieved evidence, not a bare headline. Supersedes orchestrator.classify()
— see docs/workflow_overview.md for how this fits into the pipeline, and
tests/test_retrieval_based_routing.py / tests/test_retrieval_llm_hybrid.py
for the experiment history behind this decision.

Two-step pipeline, both grounded in the real HydraDB corpus, not a summary:
  1. One unscoped HydraDB query() across the whole tenant (no
     metadata_filters, no event pre-selection) — real excerpts, not headlines.
  2. A lightweight LLM step (prompts/retrieval_router.yaml) reads those real
     excerpts, grouped by which event they came from, and confirms
     event_ids + query_type.

orchestrator.classify() (headline-only, never touches HydraDB) is kept in
the codebase as the prior approach / fallback reference — chat.py no longer
calls it, but it still has its own test coverage (tests/test_orchestrator.py,
tests/test_prompt_grounding.py) in case this redesign needs to be reverted.

Known, accepted gap (not fixed — see docs/limitations_and_future_considerations.md): range/before-after
questions can under-include the correct boundary window, since this router
has no explicit date-arithmetic rule the way classify()'s BOUNDARY RULE did
(tests/test_retrieval_llm_hybrid.py's one failing case). Over-inclusion
elsewhere is absorbed by chat_answer.yaml's synthesis-stage grounding rule,
so it isn't treated as a blocking issue.

Cost/latency tradeoff, stated plainly: this adds one extra unscoped
HydraDB query() call per chat turn (for routing) on top of stage 2's
existing scoped retrieval (for synthesis evidence) — two HydraDB calls per
turn instead of one. Accepted as the cost of grounding the routing decision
in real content instead of a one-line headline.
"""
import json
import os
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv
from openai import OpenAI

import hydradb_client
import orchestrator  # reused for load_event_catalog() + VALID_QUERY_TYPES

load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
MODEL = "gpt-4o-mini"

_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_ROUTER_PROMPT = yaml.safe_load((PROMPTS_DIR / "retrieval_router.yaml").read_text())["route_from_evidence"]

MAX_RESULTS = 20  # matches retrieval.py's established max_results fix (finding #12)
SNIPPETS_PER_EVENT = 2  # top excerpts per candidate event shown to the LLM confirmation step


def _filename_to_event_id(catalog: list) -> dict:
    """filename -> event_id, via HydraDB's own live filing_date metadata
    mapped through the catalog's dates-per-event. Live lookup (not a static
    manifest), matching this project's established pattern — see
    hydradb_client.list_filing_dates()'s docstring for the same reasoning."""
    date_to_event_id = {date: e["event_id"] for e in catalog for date in e["dates"]}
    filename_to_date = hydradb_client.filename_to_filing_date()
    return {
        filename: date_to_event_id[date]
        for filename, date in filename_to_date.items()
        if date in date_to_event_id
    }


def _retrieve_real_evidence(question: str, filename_to_event_id: dict) -> dict:
    """One unscoped query across the whole tenant. Returns
    {event_id: [(text, score), ...]}, each list sorted by score descending
    and capped at SNIPPETS_PER_EVENT."""
    data = hydradb_client.query(question, mode="thinking", max_results=MAX_RESULTS, graph_context=False)
    grouped: dict = {}
    for c in (data.chunks or []):
        event_id = filename_to_event_id.get(c.source_title)
        if not event_id or not c.chunk_content:
            continue
        grouped.setdefault(event_id, []).append((c.chunk_content.strip(), c.relevancy_score or 0))

    for event_id in grouped:
        grouped[event_id].sort(key=lambda x: x[1], reverse=True)
        grouped[event_id] = grouped[event_id][:SNIPPETS_PER_EVENT]
    return grouped


def _build_evidence_block(grouped: dict) -> str:
    if not grouped:
        return "(no evidence retrieved for this question)"
    lines = []
    for event_id in sorted(grouped, key=lambda e: grouped[e][0][1], reverse=True):
        best_score = grouped[event_id][0][1]
        lines.append(f"[{event_id}] (best score: {best_score:.3f})")
        for text, score in grouped[event_id]:
            snippet = text[:280] + ("..." if len(text) > 280 else "")
            lines.append(f'  - "{snippet}"')
    return "\n".join(lines)


def route_via_retrieval(question: str, catalog: Optional[list] = None) -> Optional[dict]:
    """Stage 1 (adopted). Returns {query_type, event_ids, reasoning} — same
    shape orchestrator.classify() returned, so chat.py's downstream code
    (price_stats, retrieval, synthesis) is unchanged. Returns None on the
    same "can't proceed" conditions classify() used (no key, empty question,
    empty catalog), so chat.py's existing warning-fallback path keeps
    working unmodified."""
    if not question or not question.strip() or _client is None:
        return None

    catalog = catalog if catalog is not None else orchestrator.load_event_catalog()
    if not catalog:
        return None

    filename_map = _filename_to_event_id(catalog)
    grouped = _retrieve_real_evidence(question, filename_map)
    evidence_block = _build_evidence_block(grouped)

    prompt = _ROUTER_PROMPT.format(question=question.strip(), evidence_block=evidence_block)
    response = _client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={"type": "json_object"},
    )

    try:
        raw = json.loads(response.choices[0].message.content)
    except (json.JSONDecodeError, TypeError, AttributeError):
        return None

    query_type = raw.get("query_type")
    if query_type not in orchestrator.VALID_QUERY_TYPES:
        query_type = "single"  # safest fallback shape, same as classify()

    valid_ids = {e["event_id"] for e in catalog}
    event_ids = [eid for eid in (raw.get("event_ids") or []) if eid in valid_ids]

    return {
        "query_type": query_type,
        "event_ids": event_ids,
        "reasoning": raw.get("reasoning") or "",
    }
