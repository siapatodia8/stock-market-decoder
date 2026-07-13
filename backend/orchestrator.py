"""
Chat stage 1, ORIGINAL approach — the headline-only events orchestrator.

SUPERSEDED — see docs/workflow_overview.md for the current pipeline.
chat.py no longer calls classify() here, it calls
retrieval_router.route_via_retrieval() instead. This module is kept for
reference and as a fallback path (its own test coverage,
tests/test_orchestrator.py + tests/test_prompt_grounding.py, still passes and
still runs standalone) in case the redesign needs to be reverted. Everything
below describes how THIS approach worked, not what chat.py currently does.

Given a free-text user question, decide WHICH timeline events it concerns and
WHAT SHAPE the question has (single / multi / comparative / range), BEFORE any
HydraDB retrieval runs.

This was deliberately our own app-layer code, not a HydraDB call, for two
reasons:
  1. "event" is a grouping we defined ourselves (one event per filing month in
     the timeline cache). HydraDB only knows individual documents and their
     metadata — it has no notion of "the CFO transition event".
  2. Deciding scope with an unscoped whole-tenant query() is exactly the
     instability documented as finding #12. Classifying over ~5 known event
     summaries instead is a far easier and more reliable problem, and it never
     touches HydraDB.
Reason 2 is exactly what the redesign revisited: real retrieved evidence
turned out to matter enough (see the redesign write-up) that the tradeoff
was worth taking back on.

The output ({query_type, event_ids}) feeds two downstream consumers:
  - HydraDB retrieval, scoped to the chosen events' filing_dates.
  - the price-stat computation, over the chosen events' date range.

HydraDB is a retrieval / knowledge layer — it never generates the answer. The
answer is synthesized later by synthesis.py over what HydraDB retrieves. This
module only picks the scope.
"""
import json
import os
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
MODEL = "gpt-4o-mini"

_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = REPO_ROOT / "outputs" / "timeline_cache.json"

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_CLASSIFY_PROMPT = yaml.safe_load((PROMPTS_DIR / "orchestrator.yaml").read_text())["classify"]

VALID_QUERY_TYPES = {"single", "multi", "comparative", "range"}


def load_event_catalog(cache_path: Optional[Path] = None) -> list:
    """Reads the timeline cache and returns the compact catalog the classifier
    reasons over: one entry per month that actually has an event.

    Returns a list of {"event_id": "YYYY-MM", "dates": [str], "headline": str},
    in chronological order. Deterministic — no LLM, no network. event_id is the
    month string, which is the cache's natural per-event key."""
    path = cache_path or CACHE_PATH
    months = json.loads(Path(path).read_text())

    catalog = []
    for month in months:
        event = month.get("event")
        if not event:
            continue
        catalog.append({
            "event_id": month["month"],
            "dates": event.get("filing_dates") or [],
            "headline": event.get("headline") or "",
        })
    catalog.sort(key=lambda e: e["event_id"])
    return catalog


def format_catalog(catalog: list) -> str:
    """Renders the catalog into the numbered block the prompt embeds. Kept
    separate from prompt-building so it can be inspected/tested on its own."""
    lines = []
    for e in catalog:
        dates = ", ".join(e["dates"]) if e["dates"] else "no date"
        lines.append(f'- id="{e["event_id"]}" ({dates}): {e["headline"]}')
    return "\n".join(lines)


def build_classification_prompt(question: str, catalog: list) -> str:
    """Deterministic — builds the exact prompt string sent to the model.
    Testable without any network access."""
    return _CLASSIFY_PROMPT.format(
        catalog_block=format_catalog(catalog),
        question=question.strip(),
    )


def _valid_event_ids(catalog: list) -> set:
    return {e["event_id"] for e in catalog}


def classify(question: str, catalog: Optional[list] = None) -> Optional[dict]:
    """Classifies a free-text question into {query_type, event_ids, reasoning}.

    Needs OpenAI (like synthesis.py) — returns None if no key is configured or
    the question is empty. event_ids are validated against the catalog, so the
    model can never invent an id that doesn't exist. Downstream code should
    treat a None return as "couldn't scope — fall back to asking the user to
    rephrase or to a safe default", not as an error."""
    if not question or not question.strip() or _client is None:
        return None

    catalog = catalog if catalog is not None else load_event_catalog()
    if not catalog:
        return None

    prompt = build_classification_prompt(question, catalog)
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
    if query_type not in VALID_QUERY_TYPES:
        query_type = "single"  # safest fallback shape

    valid_ids = _valid_event_ids(catalog)
    event_ids = [eid for eid in (raw.get("event_ids") or []) if eid in valid_ids]

    return {
        "query_type": query_type,
        "event_ids": event_ids,
        "reasoning": raw.get("reasoning") or "",
    }


if __name__ == "__main__":
    # Quick manual check of the deterministic pieces (no network needed).
    cat = load_event_catalog()
    print(f"Loaded {len(cat)} events:\n")
    print(format_catalog(cat))
