# Stock Market Decoder - Why HydraDB

This project is a small, single-company build, but HydraDB's core value proposition shows up clearly even at this scale - and would only matter more at production size.

---

## What HydraDB Replaced

Building this app's retrieval layer from scratch would have meant standing up several separate pieces of infrastructure. HydraDB collapsed all of it into one API:

- **Chunking and embedding** - Every filing gets split and embedded (dense + sparse) automatically on ingestion. No separate chunking strategy or embedding pipeline to design and maintain.
- **Entity and relationship extraction** - Every document is parsed into a knowledge graph (people, roles, organizations, deals) at ingestion time, with no separate NER/extraction step of our own.
- **Hybrid retrieval and reranking** - `query()` handles semantic search, filtering, and reranking behind one call, instead of us wiring together a vector store, a filter layer, and a reranker separately.

## Where It Showed Up in Practice

- **Retrieval found things headline-matching couldn't.** A question describing Precor by what it actually does ("a commercial fitness equipment company serving gyms and hotels") matched the right event through semantic similarity alone, with zero lexical overlap against that event's own headline text - something a simpler keyword or headline-only routing approach would have missed outright.
- **The knowledge graph gave us a real feature for free.** The per-event graph view (people, roles, relationships behind each event) is built entirely from `context.relations()` on data already ingested for retrieval - no separate graph-building effort of our own.
- **Structured retrieval output made grounding easier to enforce.** `chunks`, `chunk_relations`, and `query_paths` gave synthesis real, attributable evidence to cite, which is what makes the "answer only from what's provided" grounding rule enforceable in practice, not just a prompt instruction hoping the model complies.

## At This Project's Scale

13 documents and one company is a small test bed - not enough for HydraDB's retrieval ranking to do much real filtering work (every question's candidate set was effectively all 5 events regardless of retrieval, per `docs/workflow_overview.md`'s routing step). The value case here comes from what ingestion and the graph delivered automatically, not from retrieval discriminating at scale. A larger, multi-company corpus is where that second half of the value proposition - retrieval actually narrowing a large candidate set - would get tested for real.

---
