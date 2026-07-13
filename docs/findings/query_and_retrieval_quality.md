# Query & Retrieval Quality Findings

How reliably HydraDB's retrieval and query behavior held up under repeated, hands-on testing - the most consequential findings from this project.

---

## Reranking Instability Near `max_results` Boundaries

The headline finding of this project. Under `mode="thinking"` at low `max_results` values, a correct, relevant chunk can silently vanish from the results of an identical, repeated call - a directly reproduced non-determinism in the final result set.

Running the same scoped query 8 times in a row at `max_results=10` returned the correct source document in only 2 of 8 runs, with its relevancy score swinging wildly between hits (0.044 to 0.881 - not close values). Raising only `max_results` to 20, with nothing else changed, fixed it 8 of 8 times, with scores stabilizing into a tight band. Switching to `mode="fast"` at the original `max_results=10` was also stable 8 of 8 times, with the identical score every single run. This project didn't inspect HydraDB's internals directly, so the exact mechanism isn't confirmed - but the fast/thinking comparison is a well-supported basis for the working theory that `mode="thinking"`'s additional reranking step is what introduces the instability, while the underlying retrieval/embedding step behind it stayed deterministic in every test we ran.

This isn't theoretical: it caused two consecutive automated builds of this app's event timeline to mislabel a real disclosure's date, because the correct source document dropped out of the result set and only a differently-dated document survived.

This app mitigates it by using `max_results=20` everywhere. To measure how well that mitigation holds, we ran 25 questions (5 questions x 5 runs each) through the real production pipeline at this setting - 25 of 25 came back correct, with zero instability observed. That result doesn't mean the underlying issue is gone: this is a small, 13-document dataset, and a live question in the actual UI failed once under this same mitigation before that test, then answered correctly on an identical retry with no code change - a real, if lower-probability, repro of the same instability even at the "safe" setting. Whether a larger, more document-heavy corpus would surface this more often wasn't tested - that's an open question, not a finding, flagged in Limitations & Future Considerations.

**Severity: Significant.**

---

## Other Query & Retrieval Findings

| Finding | Expected | Found | Severity |
|---|---|---|---|
| `metadata_filters` has no OR/IN semantics across multiple values | A list of values (e.g. two dates) matches any of them, the way a single value matches one | A single value, or a single value wrapped in a list, works exactly as documented. A list of two or more *different* real values returns zero chunks, even though each value individually returns real results on its own. Exact single-value match only - retrieving multiple dates requires one filtered call per date, merged in code. | Moderate |
| `synthesis_context` rarely produces usable content, even in `mode="thinking"` | It's a byproduct field, not a Q&A answer - HydraDB's own cookbooks always generate the actual answer via the caller's own LLM call over `chunks`/`graph_context`. When populated (multi-step queries only), it should still contain a coherent synthesized summary of the retrieved context | Across 6 live query attempts (3 different phrasings), it never once produced a usable summary - 4 of 6 returned a stub restating the query instead of synthesizing anything, 2 of 6 returned `None`. This happened even with strong retrieval underneath it (11-18 chunks/graph paths) and even though `chunk_relations`/`query_paths` held correct, well-grounded content the whole time. Not a broken promise, since nothing here was ever meant to be a final answer - but a real reliability gap in the one thing this field is for. | Moderate |

---

## Untested Surface

`query_by` (`hybrid`/`text`), `alpha` (semantic/BM25 blend weight), and `operator` (`or`/`and`/`phrase`) were never explicitly set anywhere in this project - every query ran on whatever HydraDB defaults to when they're omitted. This isn't a finding, it's a coverage gap - see Limitations & Future Considerations.

---
