# 📈 Stock Market Decoder

An AI-powered dashboard that documents a stock's price history alongside the key market events behind it - built as a learning platform to help people understand how stocks and markets move together, and how major events drive stock movements.

Built and rerun end-to-end specifically as a hands-on evaluation of HydraDB itself, with every SDK behavior, documentation gap, and retrieval quirk found along the way logged as a finding.

Built with **HydraDB** (knowledge graph + retrieval), **OpenAI** (reasoning), **FastAPI** (backend), and **React** (frontend).

---

## Overview

Most financial tools are built for professionals, focused on forecasting future prices rather than explaining past ones. Financial literacy apps, meanwhile, teach concepts in isolation, disconnected from real market history. As a result, people learning to trade and invest rarely have the resources to understand how stocks and markets actually move together - despite historical analysis being one of the clearest ways to build that intuition. This system helps by:

- **Event Timeline** - Charts a company's monthly price movements against the key events behind them, pairing what happened with how the price responded
- **Source Documents** - Every event links back to the original SEC filings, shareholder letters, and press releases it's drawn from, viewable in full alongside the chart
- **Decoder Chat** - Ask about any event and get a grounded explanation of what it was and how the price moved around it, framed as correlation, not a proven cause
- **Knowledge Graph** - Maps the entities, roles, and relationships behind each event into a browsable graph, making dense, multi-part disclosures easier to interpret at a glance

The system uses HydraDB's knowledge graph and retrieval over 13 real SEC filings - 8-Ks, press releases, and shareholder letters spanning five key Peloton events from 2020 to 2024 - paired with real daily price history, with every question scoped to the right event before it's answered.

**Note:** this is a prototype, built and tested on a single company within a 3-day build window - the dashboard covers Peloton only. That scope was intentional: alongside the app itself, the primary goal of this build was a hands-on evaluation of HydraDB itself - its strengths, errors, and limitations - documented in full below.

For detailed documentation, see below:

| Document | Description |
|---|---|
| [Workflow Overview](docs/workflow_overview.md) | Step-by-step breakdown of both workflows - ingesting and indexing the data, and answering a live question |
| [Why HydraDB](docs/why_hydradb.md) | What HydraDB delivered for this build, and where it earned its place in the stack |
| [Limitations & Future Considerations](docs/limitations_and_future_considerations.md) | Our own data scope and system design choices, and where this could grow next |
| [Testing & Findings](docs/testing_and_findings.md) | How this project tested and evaluated HydraDB, and an index of every findings doc below |
| ↳ [SDK & Ingestion Findings](docs/findings/sdk_and_ingestion.md) | SDK behavior quirks and ingestion pipeline gotchas |
| ↳ [Documentation Accuracy Findings](docs/findings/documentation_accuracy.md) | Where HydraDB's docs and actual behavior diverge |
| ↳ [Query & Retrieval Quality Findings](docs/findings/query_and_retrieval_quality.md) | Retrieval reliability, reranking stability, and grounding quality |
| ↳ [Knowledge Graph Findings](docs/findings/knowledge_graph.md) | What entity resolution and relationship extraction got right and wrong |

---

## Prerequisites

| Dependency | Version | Purpose |
|---|---|---|
| **Python** | 3.10+ (tested on 3.13) | Backend runtime |
| **Node.js** | 18+ | React frontend |
| **HydraDB API Key** | - | Knowledge graph + retrieval |
| **HydraDB Tenant ID** | - | Target database for this build |
| **OpenAI API Key** | - | Routing confirmation + answer synthesis |

### Get a HydraDB API Key
1. Go to [dashboard.hydradb.com](https://dashboard.hydradb.com)
2. Sign up or log in
3. Create an API key from the dashboard

### Get an OpenAI API Key
1. Go to [platform.openai.com](https://platform.openai.com)
2. Sign up or log in
3. Navigate to **API Keys** and create a new key (starts with `sk-...`)

---

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/siapatodia8/stock-market-decoder.git
cd stock-market-decoder
```

### 2. Install Backend Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### 3. Configure Environment Variables

Copy the template and fill in real values:

```bash
cp .env.example .env
```

```bash
# .env

# Required - HydraDB (knowledge graph + retrieval)
HYDRA_DB_API_KEY=hdb_xxxxxxxxxxxxxxxxxxxxx
HYDRA_DB_TENANT_ID=stock-decoder

# Required - OpenAI (routing confirmation + answer synthesis)
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxx
```

`HYDRA_DB_TENANT_ID` isn't a shared or existing database - it's just the name step 4 below will use to create a brand-new database in *your own* HydraDB account. Pick anything (`stock-decoder` is just what this build used).

> ⚠️ **Never commit `.env` to version control.** An `.env.example` template is included in the repo for reference.

### 4. Create the Database and Ingest the Data

The 13 SEC filings and the price history CSV are already committed under `data/` - no need to re-fetch anything. This step creates the HydraDB database (under the tenant name you chose above) and ingests those 13 documents as Knowledge:

```bash
python3 scripts/setup_and_ingest_sdk.py --step all
```

This runs create → poll (wait for the database to be ready) → ingest (all 13 documents) → status (confirm every document finished indexing). Each sub-step can also be run individually via `--step create|poll|ingest|status`, useful if a step needs to be retried.

### 5. Build the Event Timeline

Once ingestion is confirmed complete, run this to build the event timeline the app reads from. It makes live HydraDB calls against the documents you just ingested and writes the result to `outputs/timeline_cache.json` - generated output specific to your own tenant, so it isn't committed to the repo and every clone needs to build its own:

```bash
cd backend
python3 timeline.py
```

### 6. Install Frontend Dependencies

```bash
cd frontend
npm install
```

---

## Running the Application

The app runs as two processes: a **FastAPI backend** and a **React frontend**. You'll need two terminal windows.

**Terminal 1 - Start the API server** (from the project root):
```bash
cd backend
uvicorn main:app --reload --port 8000
```

**Terminal 2 - Start the React frontend**:
```bash
cd frontend
npm run dev
```

Once both are running, open [http://localhost:5173](http://localhost:5173) in your browser.

### Verify It's Working

```bash
curl http://localhost:8000/api/health
```
Should return `{"ok": true, ...}`. A `502` here means HydraDB is unreachable - check your `.env`.

```bash
curl http://localhost:8000/api/timeline
```
Should return the 5 built events. A `503` here means step 5 (build the event timeline) wasn't run yet.

If both return real data, the dashboard should load with the price chart, timeline events, and Decoder Chat all working.

---

## Project Structure

```
stock-market-decoder/
├── .env.example                     # Template for .env setup
├── README.md
├── backend/
│   ├── requirements.txt             # Python dependencies
│   ├── main.py                      # FastAPI server - all /api/* endpoints
│   ├── chat.py                      # 3-stage chat pipeline: route → retrieve → synthesize
│   ├── retrieval_router.py          # Stage 1 - HydraDB retrieval + LLM confirmation (routing)
│   ├── orchestrator.py              # Superseded stage 1 (headline-only classify) - kept as fallback reference
│   ├── retrieval.py                 # Stage 2 - scoped HydraDB retrieval for a given event
│   ├── synthesis.py                 # Stage 3 - grounded answer generation over HydraDB evidence
│   ├── timeline.py                  # Builds the event timeline cache (outputs/timeline_cache.json)
│   ├── knowledge_graph.py           # Per-event knowledge graph builder (entity-resolution workaround included)
│   ├── highlight.py                 # Locates a retrieved chunk's exact span within its source document
│   ├── price_stats.py               # Volatility/return/drawdown over a date window - computed from the price CSV, never HydraDB
│   ├── price_data.py                # Price CSV loading + monthly aggregation for the chart
│   ├── hydradb_client.py            # Thin HydraDB SDK wrapper (auth, tenant scoping, shared helpers)
│   └── prompts/                     # YAML prompt files, one per LLM call
│       ├── retrieval_router.yaml    # Stage 1 routing-confirmation prompt
│       ├── chat_answer.yaml         # Stage 3 synthesis prompt (grounding rules)
│       ├── orchestrator.yaml        # Superseded stage 1 classify prompt
│       └── timeline_event.yaml      # Event headline/summary generation prompt
├── frontend/                        # React/Vite single-page app
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx                  # Layout, panel state, resizable columns
│       ├── api.js                   # Fetch wrappers for the backend API
│       ├── documentLabels.js        # Filename → display label formatting
│       ├── graphColors.js           # Knowledge graph node color scheme
│       ├── utils.js                 # Date/percent formatting helpers
│       ├── index.css                # All styling
│       └── components/
│           ├── PriceChart.jsx       # Log-scale price chart, hover tooltip, event markers
│           ├── ChatPanel.jsx        # Decoder Chat - question input, answer, source chips
│           ├── DocumentViewer.jsx   # Source document viewer with passage highlighting
│           ├── KnowledgeGraph.jsx   # Force-directed graph canvas (d3)
│           ├── SelectedNodePanel.jsx # Entity detail panel for a clicked graph node
│           └── Resizer.jsx          # Draggable panel divider, shared by every resizable panel
├── data/                            # 13 real SEC filings (8-Ks, press releases, shareholder letters) + price history CSV
├── scripts/
│   ├── setup_and_ingest_sdk.py      # create → poll → ingest → status pipeline
│   ├── fetch_price_history.py       # Regenerates the price CSV via yfinance (optional - CSV is already committed)
│   └── cleanup_duplicate_ingest.py  # One-off cleanup for a duplicate-on-ingest bug hit during the original build
├── docs/                            # Findings, architecture notes, and dataset reference (see below)
├── tests/                           # App-layer test scripts (chat pipeline, retrieval, prompts) - run manually, findings summarized in docs/
└── sdk_tests/                       # HydraDB SDK rerun log - source material the findings docs are drawn from
```

---