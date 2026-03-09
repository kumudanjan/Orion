# 🔍 Log Intelligence Assistant
### PROJECT 4 — Genpact Generative AI Capstone

> A GenAI-powered log intelligence system that ingests logs, detects anomalies, and performs plain-language root-cause analysis using a ReAct agent loop.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit UI                              │
│  Log Ingestion │ Anomaly Detection │ RCA Agent │ RAG │ Obs  │
└─────────────┬───────────────────────────────────────────────┘
              │
     ┌────────▼──────────┐
     │  Ingestion Pipeline│  Parse → PII Mask → Chunk → Embed
     └────────┬──────────┘
              │
     ┌────────▼──────────┐      ┌──────────────────┐
     │   Vector Store     │◄────►│  Azure AI Search  │
     │   (ChromaDB)       │      │  (cloud option)   │
     └────────┬──────────┘      └──────────────────┘
              │
     ┌────────▼──────────────────────────────────┐
     │              Core Agents                   │
     │  ┌─────────────────┐  ┌─────────────────┐ │
     │  │ Anomaly Detector│  │    RCA Agent    │ │
     │  │ (stat + LLM)    │  │  (ReAct loop)  │ │
     │  └─────────────────┘  └─────────────────┘ │
     │  ┌─────────────────┐  ┌─────────────────┐ │
     │  │   RAG Engine    │  │  Observability  │ │
     │  │ (logs + SOPs)   │  │   (metrics)     │ │
     │  └─────────────────┘  └─────────────────┘ │
     └────────┬──────────────────────────────────┘
              │
     ┌────────▼──────────┐
     │   Azure OpenAI    │  GPT-4o via Azure or OpenAI
     │   (LLM Backend)   │
     └───────────────────┘
```

---

## Quick Start

### 1. Clone and install

```bash
git clone <repo>
cd project4
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add your AZURE_OPENAI_KEY or OPENAI_API_KEY
```

### 3. Run the app

```bash
# ✅ Always run from inside the project4 folder using run_app.py
cd project4
streamlit run run_app.py
```

> ⚠️ Do NOT run `streamlit run app/main.py` directly — use `run_app.py` from the project root.

### 4. Run tests

```bash
pytest tests/ -v
```

---

## Project Structure

```
project4/
├── app/
│   ├── main.py                  # Streamlit entry point
│   ├── config.py                # Central configuration
│   ├── ingestion/
│   │   ├── parser.py            # Log parsing pipeline (JSON, text, Apache, syslog)
│   │   └── vector_store.py      # ChromaDB / Azure AI Search abstraction
│   ├── anomaly/
│   │   └── detector.py          # Statistical + LLM anomaly detection
│   ├── rca/
│   │   └── agent.py             # ReAct RCA agent with tool use
│   ├── rag/
│   │   └── engine.py            # RAG pipeline over logs + SOPs
│   ├── llm/
│   │   └── client.py            # Azure OpenAI / OpenAI client
│   ├── guardrails/
│   │   └── pii_masker.py        # PII scrubbing, credential detection, hallucination check
│   ├── observability/
│   │   └── metrics.py           # KPI tracking, App Insights integration
│   ├── ui/
│   │   ├── sidebar.py
│   │   ├── log_upload.py
│   │   ├── anomaly_view.py
│   │   ├── rca_view.py
│   │   ├── rag_view.py
│   │   └── observability.py
│   └── data/
│       └── sample_logs.py       # Demo log data
├── tests/
│   └── test_core.py             # Unit tests
├── requirements.txt
├── .env.example
└── README.md
```

---

## Core Features

| Feature | Implementation |
|---|---|
| Log ingestion + parsing | `app/ingestion/parser.py` — JSON, text, Apache, syslog, OTEL |
| Vector index | `app/ingestion/vector_store.py` — ChromaDB (local) / Azure AI Search |
| Anomaly detection | `app/anomaly/detector.py` — Z-score + LLM pattern matching |
| RCA Agent | `app/rca/agent.py` — ReAct loop with 4 tools |
| RAG over logs + SOPs | `app/rag/engine.py` — retrieve + generate + validate |
| Deployment-ready | Azure App Service / Container Apps via env vars |
| Observability | `app/observability/metrics.py` — KPI tracking + App Insights |
| RAI Guardrails | `app/guardrails/pii_masker.py` — PII, credentials, hallucination check |

---

## RCA Agent Tools

The agent has 4 tools available in its ReAct reasoning loop:

1. **`search_logs(query)`** — semantic vector search over ingested logs
2. **`get_error_context(line_no)`** — fetch surrounding lines for any log line
3. **`lookup_sop(topic)`** — retrieve SOPs / runbooks from knowledge base
4. **`count_errors(level)`** — count entries by severity level

---

## RAI Guardrails

- **PII masking**: passwords, API keys, JWTs, emails, AWS keys scrubbed at ingestion
- **Credential detection**: applied before storing in vector DB or sending to LLM
- **Hallucination scoring**: measures answer grounding against retrieved context
- **LLM output validation**: blocks responses that accidentally contain sensitive data

---

## Observability KPIs

| KPI | Metric Name |
|---|---|
| Ingestion latency | `log_ingestion_latency_ms` |
| Anomaly detection latency | `anomaly_detection_latency_ms` |
| RCA agent latency | `rca_agent_latency_ms` |
| RAG query latency | `rag_query_latency_ms` |
| Hallucination / grounding score | `rag_hallucination_score` |
| Anomalies detected | `anomalies_detected` |
| Chunks indexed | `chunks_indexed` |

---

## Deployment

### Azure App Service

```bash
az webapp create --name log-intelligence --runtime PYTHON:3.11
az webapp config appsettings set --name log-intelligence \
  --settings AZURE_OPENAI_KEY=<key> AZURE_OPENAI_ENDPOINT=<endpoint>
az webapp up
```

### Docker / Container Apps

```bash
docker build -t log-intelligence .
docker run -p 8501:8501 --env-file .env log-intelligence
```
