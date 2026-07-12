"""
FastAPI backend for the Stock Story Explainer (Peloton edition).

Four real endpoints, matching the "timeline + chat + evidence panel" shape
from 03_project_stock_explainer.md:
  - GET  /api/timeline  — reads the precomputed cache (data/timeline_cache.json),
    built by `python timeline.py` from live HydraDB queries + price_data.py
  - GET  /api/documents/{filename} — serves one source document's full clean
    text from data/ for the evidence panel, so it can show the real document
    a chunk came from instead of just the retrieved fragment
  - GET  /api/knowledge-graph — live, on-demand version of the same merged
    graph that's precomputed into every /api/timeline event's
    "knowledge_graph" field (via timeline.py) — dev/fallback tool, not the
    frontend's primary path. See backend/knowledge_graph.py and finding #24
    in hydradb_findings_log.md for why the merge step exists
  - POST /api/chat      — live HydraDB retrieval + synthesis.py answer generation
Plus /api/health for a quick "is HydraDB reachable" check during dev.

Run locally (not in a sandboxed environment without network access to
api.hydradb.com — see CONTEXT_UPDATES.md's "Operating constraint" section):
    cd backend
    pip install -r requirements.txt
    python timeline.py          # builds/refreshes the timeline cache
    uvicorn main:app --reload --port 8000
"""
import re
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import hydradb_client
import knowledge_graph
import synthesis
import timeline

app = FastAPI(title="Stock Story Explainer API")

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
# source_titles coming back from HydraDB are always this dataset's own
# filenames (e.g. peloton_2020-12-21_8k.md) — reject anything else so this
# endpoint can't be used to read arbitrary files off disk.
SAFE_FILENAME_RE = re.compile(r"^[\w.-]+\.md$")

# Dev-friendly CORS: allow local frontend dev servers (Vite default 5173, CRA
# default 3000). Tighten this before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str
    mode: Optional[str] = "thinking"  # multi-query expansion + reranking + graph relations
    max_results: Optional[int] = 10


class ChatResponse(BaseModel):
    question: str
    mode: str
    answer: Optional[str]
    answer_source: Literal["llm_synthesis", "none"]
    chunks: list
    graph_paths: list
    chunk_relations: list
    warning: Optional[str] = None


def _dump(obj):
    return obj.model_dump() if hasattr(obj, "model_dump") else obj


@app.get("/api/health")
def health():
    try:
        status = hydradb_client.infra_status()
        return {"ok": True, "infra": status.infra.model_dump() if hasattr(status.infra, "model_dump") else str(status.infra)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"HydraDB unreachable: {e}")


@app.get("/api/timeline")
def get_timeline():
    try:
        return {"months": timeline.load_cache()}
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Timeline cache not built yet — run `python timeline.py`.")


@app.get("/api/documents/{filename}")
def get_document(filename: str):
    if not SAFE_FILENAME_RE.match(filename):
        raise HTTPException(status_code=400, detail="Invalid document filename.")
    path = DATA_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Document not found: {filename}")
    return {"filename": filename, "content": path.read_text()}


@app.get("/api/knowledge-graph")
def get_knowledge_graph(documents: str):
    """Live/on-demand only — the frontend's normal path reads
    event.knowledge_graph straight out of /api/timeline (precomputed by
    timeline.py). This exists for testing document sets ad hoc, or as a
    fallback if the cache hasn't been rebuilt since new documents were
    added. documents: comma-separated filenames."""
    filenames = [f.strip() for f in documents.split(",") if f.strip()]
    if not filenames:
        raise HTTPException(status_code=400, detail="documents must include at least one filename.")
    try:
        return knowledge_graph.build_graph(filenames)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"HydraDB knowledge-graph lookup failed: {e}")


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question must not be empty")

    try:
        data = hydradb_client.query(req.question, mode=req.mode, max_results=req.max_results)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"HydraDB query failed: {e}")

    graph_context = data.graph_context
    query_paths = graph_context.query_paths if graph_context and graph_context.query_paths else []
    chunk_relations = graph_context.chunk_relations if graph_context and graph_context.chunk_relations else []
    chunks = data.chunks or []

    answer = synthesis.synthesize_answer(
        req.question, chunks=chunks, chunk_relations=chunk_relations, query_paths=query_paths
    )

    if answer:
        answer_source = "llm_synthesis"
        warning = None
    else:
        answer_source = "none"
        if not (chunks or chunk_relations or query_paths):
            warning = "No chunks or graph relationships were found for this question."
        else:
            warning = "Evidence was retrieved but synthesis failed — check OPENAI_API_KEY is set."

    return ChatResponse(
        question=req.question,
        mode=req.mode,
        answer=answer,
        answer_source=answer_source,
        chunks=[_dump(c) for c in chunks],
        graph_paths=[_dump(p) for p in query_paths],
        chunk_relations=[_dump(p) for p in chunk_relations],
        warning=warning,
    )
