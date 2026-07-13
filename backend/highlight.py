"""
Locates a HydraDB-retrieved chunk's text within its full source document, so
the frontend can highlight the exact passage an answer drew from — not just
name the source document (finding #16: chunk objects carry no offset/position
field, so this has to be solved app-side with the raw texts we already hold,
not via any HydraDB call).

Three progressively looser strategies, in order:
  1. Exact substring match — chunk_content is often verbatim in the source.
  2. Whitespace-tolerant match — same content, but markdown line-wrapping or
     chunking-time whitespace changes mean an exact substring search misses
     it. Builds a regex that requires the same non-whitespace text but lets
     any whitespace run match any other whitespace run, so this only relaxes
     formatting, never the actual words.
  3. Fuzzy fallback — difflib's longest contiguous matching block, for
     content that's been reformatted or lightly altered beyond whitespace.
     Only returned above min_fuzzy_score, so a poor match surfaces as no
     highlight rather than a misleading one.
"""
import difflib
import re
from typing import Optional


def _normalize_for_regex(text: str) -> str:
    """Splits text into whitespace/non-whitespace runs, escapes each
    non-whitespace run literally, and lets whitespace runs match any
    whitespace (\\s+) — so formatting differences don't block a match, but
    the actual required content is unchanged."""
    parts = re.split(r"(\s+)", text)
    pattern_parts = []
    for part in parts:
        if not part:
            continue
        pattern_parts.append(r"\s+" if part.isspace() else re.escape(part))
    return "".join(pattern_parts)


def find_chunk_span(document_text: str, chunk_text: str, min_fuzzy_score: float = 0.6) -> Optional[dict]:
    """Returns {start, end, matched_text, score, method} for chunk_text's
    location within document_text, or None if nothing clears the fuzzy
    threshold. method is one of "exact" / "whitespace_tolerant" / "fuzzy"."""
    chunk_text = (chunk_text or "").strip()
    if not chunk_text or not document_text:
        return None

    idx = document_text.find(chunk_text)
    if idx != -1:
        return {
            "start": idx,
            "end": idx + len(chunk_text),
            "matched_text": document_text[idx:idx + len(chunk_text)],
            "score": 1.0,
            "method": "exact",
        }

    pattern = _normalize_for_regex(chunk_text)
    try:
        m = re.search(pattern, document_text)
    except re.error:
        m = None
    if m:
        return {
            "start": m.start(),
            "end": m.end(),
            "matched_text": document_text[m.start():m.end()],
            "score": 1.0,
            "method": "whitespace_tolerant",
        }

    matcher = difflib.SequenceMatcher(None, document_text, chunk_text, autojunk=False)
    block = matcher.find_longest_match(0, len(document_text), 0, len(chunk_text))
    if block.size == 0:
        return None
    score = block.size / max(len(chunk_text), 1)
    if score < min_fuzzy_score:
        return None
    return {
        "start": block.a,
        "end": block.a + block.size,
        "matched_text": document_text[block.a:block.a + block.size],
        "score": round(score, 3),
        "method": "fuzzy",
    }
