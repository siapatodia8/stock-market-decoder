# Documentation Accuracy Findings

Places where HydraDB's documentation and its actual, confirmed behavior diverge - all verified hands-on, not from doc-reading alone.

---

| Finding | Docs Say | Reality | Severity |
|---|---|---|---|
| `synthesis_context`'s gating condition isn't stated where a developer would read it | The field appears in the response schema alongside `chunk_relations`/`query_paths`, described as available structured output | It's only populated when `mode="thinking"` - `fast` and `auto` return `None` even with `graph_context=True`. The one sentence that explains this (populated only for `requires_synthesis=True`, multi-step queries) exists in exactly one place: a raw OpenAPI schema block at the bottom of one reference page, not in either narrative page that discusses the field. | Moderate |
| Chunk metadata field is named differently in the docs' own example vs. the SDK object | The docs' own JSON schema example for a chunk names this field `additional_metadata` | The installed SDK's Python chunk object exposes the identical field as `.metadata`, not `.additional_metadata` - confirmed working correctly in production, but diverging from the docs' own schema example for that same field. | Minor |
| Undocumented `_retrieval_source` field appears inside `additional_metadata` | `additional_metadata` is documented as the bucket for caller-supplied custom fields only, with no mention of reserved or internal keys | An unfiltered query returned chunks carrying `additional_metadata: {"_retrieval_source": "graph"}` - a key never supplied by our own ingestion code and undocumented anywhere, appearing even with `graph_context=False` set on the call. | Minor |

---
