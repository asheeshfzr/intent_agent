---

# ⚡ Intent-Routed Agentic AI System

### *Next-Gen LangGraph + LLM Orchestration Framework for Autonomous Multi-Tool Reasoning*

> “Not just an agent — a thinking system that understands, plans, reasons, and adapts.”

---

## 🧠 Overview

This project is a **next-generation Agentic AI system** built with **LangGraph**, **LangChain**, and **Local LLMs**, designed to showcase how an **autonomous reasoning agent** can understand human intent, dynamically route tasks, invoke multiple specialized tools, and iteratively improve its reasoning through feedback loops.

It demonstrates the fusion of **Generative AI (LLMs)** and **Agentic AI frameworks** to create a system that can:

* Interpret a **natural language query**
* Choose the optimal **workflow and tools** via **LangGraph orchestration**
* Perform **multi-hop reasoning and inference**
* Adapt and re-route via **feedback and confidence-based recovery**
* Return **traceable, explainable outputs**

This is not just a POC — it’s a **foundational blueprint** for building **autonomous AI agents** capable of **tool orchestration**, **self-healing reasoning**, and **contextual decision-making**.

---

## 🧩 Core Features

### 🧭 **LangGraph-Powered Orchestration**

The system leverages **LangGraph**, the latest evolution in LLM orchestration frameworks, to model workflows as **directed stateful graphs** — giving fine-grained control over reasoning steps, node transitions, and failure recovery.

Each user query triggers a **dynamic agent graph**, composed of reasoning nodes:

```
understand → route → fetch → infer → finalize
```

These nodes can re-activate or redirect themselves based on intermediate results — introducing **true agentic adaptability**.

---

### 🧠 **LLM-Driven Intent Router**

The **router** (using prompt from `router_v1.txt`) classifies the query into:

* `metrics_lookup`
* `knowledge_lookup`
* `calc_compare`
* `unknown`

It provides structured JSON with `intent`, `confidence`, and `entities` extracted (e.g., service name, duration window, etc.), enabling deterministic downstream planning.

---

### 🧰 **Multi-Tool Reasoning Framework**

Integrated via **LangChain + LangGraph hybrid nodes**, the agent dynamically selects tools to fulfill the task:

| Tool                      | Description                                                            | Technology                               |
| ------------------------- | ---------------------------------------------------------------------- | ---------------------------------------- |
| **Metrics Tool**          | Queries a REST/HTTP mock metrics API for service latency, errors, etc. | `httpx`, FastAPI                         |
| **Vector Knowledge Tool** | Performs vector-based doc search via **Qdrant** or TF-IDF fallback     | `qdrant-client`, `sentence-transformers` |
| **Utility SQL Tool**      | Runs analytical operations or comparison queries locally               | SQLite, LangChain Tool Interface         |

Each tool can be **composed** or **sequenced** by the LangGraph workflow for multi-step reasoning (e.g., comparison or aggregation tasks).

---

### 🔁 **Inference + Feedback Loops**

After execution, the system performs reasoning and validation:

* **Inference Engine:** Evaluates results (e.g., latency thresholds or reliability checks)
* **Feedback Loop:** Detects low-confidence responses, missing data, or ambiguous outputs
  → triggers alternative tool paths or clarification requests.

This introduces **self-healing reasoning**, a core property of advanced Agentic AI systems.

---

### 🧮 **Local LLM Runtime**

* Uses **Llama.cpp (GGUF)** models for local inference (`llm_local.py`)
* Optimized for **fast, offline reasoning**
* Controlled generation (low temperature, short context)
* Seamlessly switches between **LangChain** and **LangGraph** execution modes depending on environment configuration

This design ensures privacy, cost efficiency, and consistent deterministic reasoning.

---

### 📊 **Traceable AI Decisions**

Every node, reasoning step, and tool invocation is logged via `trace.py` and accessible via:

* `GET /trace` → detailed provenance graph
* `POST /clear_trace` → reset trace memory

The API also returns **compact inlined traces** for transparency and explainability.

---

## ⚙️ Architecture Diagram

```
                    ┌────────────────────────────┐
                    │       User Query           │
                    └────────────┬───────────────┘
                                 │
                    ┌────────────▼───────────────┐
                    │  LLM Intent Router         │
                    │ (router_v1.txt prompt)     │
                    └────────────┬───────────────┘
                                 │
                    ┌────────────▼───────────────┐
                    │  LangGraph Orchestrator    │
                    │  (stateful agent graph)    │
                    └────────────┬───────────────┘
                                 │
         ┌───────────────────────┼────────────────────────┐
         │                       │                        │
┌────────▼────────┐     ┌────────▼────────┐      ┌────────▼────────┐
│ Metrics Tool    │     │ Vector Search   │      │ Utility SQL     │
│ (REST API)      │     │ (Qdrant / TF-IDF)│     │ (Local calc)   │
└────────┬────────┘     └────────┬────────┘      └────────┬────────┘
         │                       │                        │
         └──────────────┬────────┴──────────────┬──────────┘
                        ▼                       ▼
                 ┌────────────────────────────────────┐
                 │ Inference + Feedback Loop          │
                 │ (confidence checks, rerouting)     │
                 └────────────────────────────────────┘
                                │
                                ▼
                 ┌────────────────────────────────────┐
                 │ Final Answer + Execution Trace      │
                 └────────────────────────────────────┘
```

---

## 🧪 Example Queries

**1️⃣ Metrics Lookup**

```bash
curl -s -X POST "http://localhost:8000/query" \
-H "Content-Type: application/json" \
-d '{"query":"what is the p95 latency for service payments in last 5m?"}'
```

Response:

```json
{"answer":"payments p95=250ms > 200ms threshold","trace":["intent_router","metrics_fetch","inference"]}
```

**2️⃣ Knowledge Search**

```bash
curl -s -X POST "http://localhost:8000/query" \
-d '{"query":"how to configure SAML for internal dashboard?"}'
```

Response:

```json
{"answer":"Found doc: saml_setup.md - SAML configuration guide snippet...","trace":["intent_router","vector_search"]}
```

**3️⃣ Comparative Reasoning**

```bash
curl -s -X POST "http://localhost:8000/query" \
-d '{"query":"compare p95 latency between payments and orders"}'
```

Response:

```json
{"answer":"Payments=250ms, Orders=180ms, diff=70ms","trace":["intent_router","fetch_metrics","aggregate"]}
```

---

## 🧰 Tech Stack

| Layer                    | Technology                   | Purpose                         |
| ------------------------ | ---------------------------- | ------------------------------- |
| **Core Framework**       | Python 3.10+, FastAPI        | API & orchestration layer       |
| **LLM Runtime**          | llama-cpp-python             | Local inference engine          |
| **Agentic Graph Engine** | LangGraph 0.2.16             | Stateful agent orchestration    |
| **Reasoning Framework**  | LangChain                    | Tool abstractions + ReAct agent |
| **Vector Search**        | Qdrant / TF-IDF              | Knowledge retrieval             |
| **Data Models**          | Pydantic v2                  | Typed settings/configuration    |
| **Mock Services**        | FastAPI (docs & metrics)     | Simulation of external APIs     |
| **Observability**        | Trace logs + JSON provenance | Explainable agent behavior      |

---

## 🧠 Why This Matters

This project captures the **emergent capabilities of Agentic AI** — moving from prompt-based LLMs to **goal-driven, tool-using, and self-correcting autonomous systems**.

By combining:

* **LLMs for reasoning**
* **LangGraph for planning**
* **LangChain for tool execution**
* **Qdrant for semantic memory**

…it builds the foundation of a **self-directed AI reasoning system** that can orchestrate data, tools, and logic — just like a human operator.

---

## ⚡ Getting Started

### 1. Setup environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

Edit `.env` and set:

```
GGML_MODEL_PATH=/path/to/llama-2-7b-chat.Q4_0.gguf
USE_QDRANT=true
USE_LANGCHAIN=true
```

### 3. Run locally

```bash
./start_local.sh
```

This script auto-starts:

* Metrics mock (port 9000)
* Docs mock (port 9010)
* Agent API (port 8000)

### 4. Optional: Run via Docker Compose

```bash
docker-compose up --build
```

---

## 📚 API Endpoints

| Endpoint       | Method | Description                    |
| -------------- | ------ | ------------------------------ |
| `/query`       | POST   | Execute an agentic query       |
| `/trace`       | GET    | Retrieve full provenance graph |
| `/clear_trace` | POST   | Reset stored traces            |

---

## 🧩 Future Enhancements

* 🔮 Memory-augmented reasoning with persistent LangGraph states
* 🕵️ Context-aware RAG pipelines
* 🧠 Agent collaboration graphs (multi-agent orchestration)
* ⚙️ Advanced confidence-based recovery & self-critique reasoning

---

## 🏁 Summary

This project bridges **Generative AI** and **Agentic Intelligence**, turning LLMs from “responders” into **autonomous reasoning entities** capable of understanding goals, decomposing tasks, and acting with purpose.

It embodies the evolution from **prompt-based AI → tool-using AI → goal-oriented autonomous AI**.

---
