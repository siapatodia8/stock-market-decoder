"""
Stage 3: turns HydraDB's retrieved evidence (chunks, graph relationships)
into an actual answer via GPT-4o-mini. HydraDB only returns evidence, not an
answer (see CONTEXT_UPDATES.md's pipeline structure section) — this is the
app-layer synthesis step that fills that gap. Prompts live in prompts/*.yaml,
not inline, so wording changes don't require touching this file.
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

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_CHAT_PROMPT = yaml.safe_load((PROMPTS_DIR / "chat_answer.yaml").read_text())["answer"]
_TIMELINE_PROMPT = yaml.safe_load((PROMPTS_DIR / "timeline_event.yaml").read_text())["event"]


def get_context_snippets(chunks=None, chunk_relations=None, query_paths=None, limit=8) -> list:
    """Combines chunk_relations/query_paths combined_context strings (proven
    reliable — finding #19) with raw chunk text, ranked together by
    relevancy_score. Previously only used raw chunk text as a last resort
    when relations were completely empty — meaning a single thin/off-target
    relation result could silently block a stronger fact sitting in a raw
    chunk from ever being seen (e.g. the 2022-02-05 CEO-transition date:
    one weak relation snippet about a comp package was enough to hide the
    actual transition sentence, which likely was sitting in the raw chunk).

    Raw chunk text field is chunk_content — confirmed against the response
    schema in docs.hydradb.com/essentials/v2/api-results.md."""
    candidates = []
    for p in (chunk_relations or []) + (query_paths or []):
        text = getattr(p, "combined_context", None)
        score = getattr(p, "relevancy_score", 0) or 0
        if text:
            candidates.append((score, text.strip()))

    for c in (chunks or []):
        text = getattr(c, "chunk_content", None)
        score = getattr(c, "relevancy_score", 0) or 0
        if text:
            candidates.append((score, text.strip()))

    candidates.sort(key=lambda x: x[0], reverse=True)
    seen = set()
    snippets = []
    for _, text in candidates:
        if text in seen:
            continue
        seen.add(text)
        snippets.append(text)
        if len(snippets) >= limit:
            break
    return snippets


def synthesize_answer(question: str, chunks=None, chunk_relations=None, query_paths=None) -> Optional[str]:
    """Chat endpoint synthesis. Returns a grounded answer string, or None if
    there's no evidence to ground on or no OpenAI key configured."""
    snippets = get_context_snippets(chunks, chunk_relations, query_paths)
    if not snippets or _client is None:
        return None

    context_block = "\n\n".join(f"- {s}" for s in snippets)
    prompt = _CHAT_PROMPT.format(context_block=context_block, question=question)
    response = _client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return response.choices[0].message.content.strip()


def synthesize_timeline_event(question: str, date_groups: list) -> Optional[dict]:
    """Timeline event synthesis. date_groups is a list of
    {"date": "YYYY-MM-DD", "narrative_role": str|None, "snippets": [str]},
    one entry per filing_date-scoped query (kept separate per date so the
    prompt can anchor the headline on the reversal_marker fact and order
    detail chronologically). Returns {"headline": str, "detail": str}, or
    None if there's no evidence or no OpenAI key configured."""
    non_empty = [g for g in date_groups if g.get("snippets")]
    if not non_empty or _client is None:
        return None

    context_block = "\n\n".join(
        f"[{g['narrative_role'] or 'unknown'}, {g['date']}]\n"
        + "\n".join(f"- {s}" for s in g["snippets"])
        for g in non_empty
    )
    prompt = _TIMELINE_PROMPT.format(question=question, context_block=context_block)

    response = _client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=220,
        response_format={"type": "json_object"},
    )
    try:
        return json.loads(response.choices[0].message.content)
    except (json.JSONDecodeError, TypeError, AttributeError):
        return None
