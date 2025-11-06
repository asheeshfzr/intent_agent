# Intent Agent POC

This POC implements an intent-routed agent that takes a natural-language query, chooses the right tools, executes a small workflow, applies a simple inference + feedback loop, and returns a final answer with a short trace.

## Architecture

- **Router**: `app/router.py` → `classify_and_extract()` uses a compact few-shot prompt to classify into `metrics_lookup | knowledge_lookup | calc_compare`, and extracts entities (e.g., `service`, `window`).
- **Orchestrator**: `app/orchestrator_adapter.py` → `execute_workflow()` wires the router to a LangChain ReAct agent (or deterministic fallbacks) and records provenance via `record_prov()` in `app/trace.py`.
- **Agent + Tools**: `app/langchain_integration.py` defines `LocalLangChain` (wrapping the local LLM) and three tools:
  - `metrics_tool` (HTTP/REST via httpx → mock metrics server)
  - `vector_tool` (Qdrant+embeddings if available, else TF‑IDF over `seed_data/docs/`)
  - `util_sql` (SQLite SELECT/sample calc)
- **Local LLM**: `app/llm_local.py` loads a local llama-cpp model; routing prompt runs with `n_ctx=2048` and tight generation. For agent steps, generation is limited (`max_tokens=128`).
- **Provenance**: `app/trace.py` stores nodes for `/trace` API and is also summarized inline in `/query` as a compact 2–3 step trace.

## Inference + Feedback loop

- **Metrics inference**: check `p95` against `DEFAULT_P95_THRESHOLD_MS` to produce `> 200ms` or `OK` style conclusion.
- **Feedback**: if confidence is low or data is missing, fallback to alternate tools or request user clarification. Agent stalls are recovered via guided tool calls per intent.

## How to run

1) Create and populate `.env` (or use provided defaults). Make sure `GGML_MODEL_PATH` points to your local gguf file.
2) Install deps in a virtualenv:
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```
3) Start services:
```bash
./start_local.sh
```
This script frees ports 8000/9000/9010, prefers `.venv/bin/uvicorn`, starts the metrics/docs mocks, and runs the API on `:8000`.

Optional: Run Qdrant (for vector search) and seed data:
```bash
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant
# ensure USE_QDRANT=true in .env, then add docs to a collection named agent_docs
```

## Example queries

- Metrics
```bash
curl -sS -X POST "http://localhost:8000/query" -H "Content-Type: application/json" \
  -d '{"query":"what is the p95 latency for service payments in last 5m?","user_id":"alice"}'
```
Response (example):
```json
{"answer":"payments p95=250ms > 200ms","status":"done","trace":[ {"node_id":"intent"}, {"node_id":"langchain_agent"} ]}
```

- Knowledge
```bash
curl -sS -X POST "http://localhost:8000/query" -H "Content-Type: application/json" \
  -d '{"query":"how to configure SAML for internal dashboard?","user_id":"alice"}'
```
Response (example):
```json
{"answer":"Found doc: saml_setup.md - snippet: SAML configuration guide...","status":"done","trace":[{"node_id":"intent"},{"node_id":"langchain_agent"}]}
```

- Calc/Compare (multi-tool aggregation demo)
```bash
curl -sS -X POST "http://localhost:8000/query" -H "Content-Type: application/json" \
  -d '{"query":"compare p95 of payments and orders for last 15m","user_id":"alice"}'
```
Response (example):
```json
{"answer":"Payments p95=250ms, Orders p95=180ms, diff=70ms, (live: payments 250ms, orders 180ms)",
 "status":"done","trace":[{"node_id":"langchain_agent"},{"node_id":"fetch_metrics"},{"node_id":"fetch_metrics"}]}
```

## API

- `POST /query` → `{answer, status, trace}`  (trace is a compact summary; full details via `/trace`)
- `GET /trace` → full provenance nodes
- `POST /clear_trace` → clears recorded provenance

## Notes

- The agent uses a ReAct-style prompt with explicit tool input formats to reduce parsing issues; if the agent stalls, the orchestrator performs a guided single-step tool call and still records a successful `langchain_agent` node.
- TF‑IDF fallback is used when Qdrant/embeddings are not available.
*** End Patch
