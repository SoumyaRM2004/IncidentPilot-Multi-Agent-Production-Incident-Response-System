# IncidentPilot: Autonomous Production Incident Response Agent (V1)

IncidentPilot is a multi-agent AI system designed to investigate simulated production incidents. Built using Python 3.11, LangGraph, Groq, Qdrant, SQLAlchemy/PostgreSQL, FastAPI, and Streamlit, IncidentPilot coordinates specialized agents to analyze logs, telemetry metrics, deployment history, and operational runbooks to formulate, challenge, and verify evidence-backed root cause diagnoses.

> **Note**: This is a V1 demonstration system built for interview explainability and portfolio demonstration, showcasing deterministic tool usage, LangGraph state management, evidence-backed verification loops, and human-in-the-loop guardrails.

---

## Table of Contents
1. [Problem](#1-problem)
2. [Why the Problem Matters](#2-why-the-problem-matters)
3. [Solution](#3-solution)
4. [Architecture](#4-architecture)
5. [Agent Responsibilities](#5-agent-responsibilities)
6. [LangGraph Workflow](#6-langgraph-workflow)
7. [Tool Architecture](#7-tool-architecture)
8. [RAG Architecture](#8-rag-architecture)
9. [Database Design](#9-database-design)
10. [API Specification](#10-api-specification)
11. [Evaluation Methodology](#11-evaluation-methodology)
12. [Results from Actual Tests](#12-results-from-actual-tests)
13. [Failure Handling](#13-failure-handling)
14. [Human-in-the-Loop Design](#14-human-in-the-loop-design)
15. [Setup Instructions](#15-setup-instructions)
16. [Docker Instructions](#16-docker-instructions)
17. [Example Investigation Walkthrough](#17-example-investigation-walkthrough)
18. [Limitations](#18-limitations)
19. [Future Improvements](#19-future-improvements)

---

## 1. Problem
During production outages, on-call Site Reliability Engineers (SREs) face fragmented telemetry across isolated observability silos: log aggregators, deployment release consoles, time-series metric databases, and internal operational wikis. Triaging an outage manually requires high cognitive load under severe time pressure: identifying timestamps, correlating release rollouts with metric anomalies, filtering out noise in stack traces, and searching for matching incident runbooks.

## 2. Why the Problem Matters
- **Mean Time to Resolution (MTTR)**: High MTTR directly translates to revenue loss, SLA violations, and customer churn.
- **Operator Fatigue & Alert Burnout**: Repetitive diagnostic steps during high-severity outages lead to human error and misdiagnoses.
- **LLM Hallucination Risks**: Generic LLM chatbots cannot be trusted in production environments because they hallucinate ungrounded explanations, lack deterministic audit trails, and cannot verify whether a hypothesis is mathematically backed by telemetry.

## 3. Solution
IncidentPilot replaces ad-hoc chatbot queries with a deterministic, multi-agent investigation pipeline orchestrated via LangGraph. Specialized agents perform structured inspections using database queries and semantic runbook retrieval. A dedicated Root Cause Analyst formulates candidate hypotheses supported strictly by verified evidence IDs, while a mandatory Verification Agent audits the evidence catalog, challenges ungrounded assertions, and triggers a re-investigation loop when evidence is insufficient or contradictory.

---

## 4. Architecture

```
                               +-----------------------------+
                               |     Production Incident     |
                               +-----------------------------+
                                              |
                                              v
                               +-----------------------------+
                               |      Supervisor Agent       |
                               +-----------------------------+
                                              |
                                     Investigation Plan
                                              |
                   +--------------------------+--------------------------+
                   |                          |                          |
                   v                          v                          v
       +-----------------------+  +-----------------------+  +-----------------------+
       | Log Investigation     |  | Deployment Agent      |  | Metrics Agent         |
       +-----------------------+  +-----------------------+  +-----------------------+
                   |                          |                          |
           search_logs()              get_deployments()          get_service_metrics()
           error_frequency()          deployment_details()       metric_window()
                   |                          |                          |
                   +--------------------------+--------------------------+
                                              |
                                              v
                               +-----------------------------+
                               |     Runbook / RAG Agent     |
                               +-----------------------------+
                                              |
                                     Qdrant Vector DB
                                  (Cosine / BAAI bge-small)
                                              |
                                              v
                               +-----------------------------+
                               |  Root Cause Analyst Agent   |
                               +-----------------------------+
                                              |
                                     Ranked Hypotheses
                                              |
                                              v
                               +-----------------------------+
                               |     Verification Agent      |
                               +-----------------------------+
                                        /           \
                                  [PASS]             [FAIL]
                                    |                   |
                                    |                   v
                                    |         Iteration < Max (2)?
                                    |          /                 \
                                    |       [YES]               [NO]
                                    |         |                   |
                                    |   Re-investigate            v
                                    |   (Loop to Sup.)   INSUFFICIENT_EVIDENCE
                                    v
                       +-----------------------------+
                       |    Recommended Action       |
                       +-----------------------------+
                                    |
                                    v
                       +-----------------------------+
                       |   HUMAN APPROVAL REQUIRED   |
                       |    (Simulated Gating)       |
                       +-----------------------------+
                                    |
                                    v
                       +-----------------------------+
                       |     Final Incident Report   |
                       +-----------------------------+
```

---

## 5. Agent Responsibilities

| Agent | Module | Primary Responsibilities | Tools / Data Sources |
|---|---|---|---|
| **Supervisor Agent** | `app/agents/supervisor.py` | Interprets incident symptoms, formulates multi-step investigation plans, delegates tasks, and re-plans upon verification challenge. | Shared state, Groq LLM |
| **Log Investigation Agent** | `app/agents/logs.py` | Discovers error clusters, stack traces, and frequency anomalies within the incident window. | `search_logs`, `get_error_frequency`, `get_service_logs` |
| **Deployment Agent** | `app/agents/deployments.py` | Inspects recent releases, changesets, and versions to establish temporal correlation. | `get_recent_deployments`, `get_deployment_details` |
| **Metrics Agent** | `app/agents/metrics.py` | Evaluates telemetry (CPU, memory, pool saturation, latency, packet loss). | `get_service_metrics`, `get_metric_window` |
| **Runbook / RAG Agent** | `app/agents/runbook.py` | Performs dense semantic vector search over operational runbooks in Qdrant. | Qdrant Vector Client, FastEmbed |
| **Root Cause Analyst** | `app/agents/root_cause.py` | Consumes collected evidence, ranks candidate hypotheses, assigns confidence, and cites evidence IDs. | Groq LLM / grounded reasoning |
| **Verification Agent** | `app/agents/verification.py` | Audits hypothesis against evidence catalog, detects hallucinated IDs, flags contradictions, and routes workflow. | Deterministic evidence auditor, Groq LLM |

---

## 6. LangGraph Workflow
IncidentPilot's execution state is formalized in `InvestigationState` (`app/graph/state.py`):
```python
class InvestigationState(TypedDict):
    incident: Dict[str, Any]
    investigation_plan: Dict[str, Any]
    current_agent: str
    collected_evidence: List[Dict[str, Any]]
    hypotheses: List[Dict[str, Any]]
    selected_hypothesis: Optional[Dict[str, Any]]
    verification_result: Optional[Dict[str, Any]]
    confidence: float
    recommended_action: Optional[Dict[str, Any]]
    investigation_status: str  # SUCCESS | INSUFFICIENT_EVIDENCE | INVESTIGATION_FAILED
    agent_history: List[Dict[str, Any]]
    iteration_count: int
    max_iterations: int
    error_message: Optional[str]
```
The graph routes deterministically from `supervisor` through specialized collector agents into the `root_cause` analyst and `verification` agent. The verification conditional edge routes execution:
- **Verified**: Proceeds to `END`, outputting the report and human approval requirement.
- **Failed & Iterations < Max (2)**: Routes back to `supervisor` with the verification challenge explanation to gather broader evidence.
- **Failed & Iterations >= Max (2)**: Halts execution with `INSUFFICIENT_EVIDENCE` rather than fabricating a diagnosis.

---

## 7. Tool Architecture
All tools operate on actual database rows and return structured records containing immutable evidence IDs:
- **Log Tools** (`app/tools/logs.py`):
  - `search_logs(service, query, level, limit)`: Returns rows with IDs matching `LOG-xxx`.
  - `get_error_frequency(service, minutes)`: Returns aggregated counts under ID `FREQ-xxx`.
  - `get_service_logs(service, limit)`: Returns recent chronological logs.
- **Deployment Tools** (`app/tools/deployments.py`):
  - `get_recent_deployments(service, limit)`: Returns release records with IDs matching `DEP-xxx`.
  - `get_deployment_details(deployment_id)`: Returns full deployment metadata.
- **Metrics Tools** (`app/tools/metrics.py`):
  - `get_service_metrics(service, metric_name)`: Returns telemetry points with IDs matching `METRIC-xxx`.
  - `get_metric_window(service, metric_name, minutes)`: Returns time-series telemetry arrays.

---

## 8. RAG Architecture
- **Vector Database**: Qdrant running in-memory/embedded (`:memory:` or local directory) for local development and tests, or as a standalone container (`http://qdrant:6333`) in Docker Compose.
- **Embedding Model**: FastEmbed using `BAAI/bge-small-en-v1.5` (384 dimensions), running locally via ONNX Runtime without external API key requirements.
- **Chunking Strategy**: Section-aware markdown chunker (`app/rag/runbooks.py`) that indexes document titles, section headers (e.g. Symptoms, Root Cause, Remediation), and assigns persistent chunk identifiers (`RUNBOOK-01`, `RUNBOOK-02`, etc.) with similarity scoring.

---

## 9. Database Design
PostgreSQL schema implemented via SQLAlchemy (`app/db/models.py`), with automated fallback to SQLite for local development:
- **`incidents`**: `id`, `title`, `description`, `service`, `severity`, `created_at`, `status`.
- **`deployments`**: `id`, `service`, `version`, `deployed_at`, `environment`.
- **`logs`**: `id`, `timestamp`, `service`, `level`, `message`, `trace_id`.
- **`metrics`**: `id`, `timestamp`, `service`, `metric_name`, `value`.
- **`investigations`**: `id`, `incident_id`, `started_at`, `completed_at`, `status`, `final_confidence`, `report`.

---

## 10. API Specification
FastAPI REST API (`app/api/routes.py`):
- `GET /health`: Health check and system timestamp.
- `POST /incidents`: Create a new incident (`title`, `description`, `service`, `severity`).
- `GET /incidents`: List all production incidents.
- `GET /incidents/{incident_id}`: Retrieve incident metadata.
- `POST /incidents/{incident_id}/investigate`: Trigger the LangGraph multi-agent investigation.
- `GET /investigations/{investigation_id}`: Retrieve completed investigation report, evidence catalog, verification status, and recommended action.

---

## 11. Evaluation Methodology
The evaluation suite (`evaluation/run_eval.py`) validates the pipeline against a benchmark dataset of 5 known ground-truth incidents (`evaluation/incidents.json`):
1. **Root Cause Accuracy**: Measures whether the agent's selected root cause correctly matches the ground truth.
2. **Evidence Support Rate**: Verifies that 100% of cited supporting evidence IDs actually exist in the collected evidence catalog (0% hallucinated IDs).
3. **Verification Accuracy**: Measures whether the verification agent correctly accepts valid diagnoses and challenges ungrounded assertions.

---

## 12. Results from Actual Tests
Evaluation executed on Python 3.11 with all 5 production scenarios:
```
============================================================
IncidentPilot V1 Autonomous Incident Response Evaluation
============================================================
[INC-001] payment-service        | RC: PASS | Evidence: 5/5 | Verif: PASS | Conf: 92%
[INC-002] order-service          | RC: PASS | Evidence: 5/5 | Verif: PASS | Conf: 95%
[INC-003] auth-service           | RC: PASS | Evidence: 5/5 | Verif: PASS | Conf: 91%
[INC-004] notification-service   | RC: PASS | Evidence: 5/5 | Verif: PASS | Conf: 89%
[INC-005] user-service           | RC: PASS | Evidence: 5/5 | Verif: PASS | Conf: 88%
------------------------------------------------------------
1. Root Cause Accuracy:    100.0% (5/5)
2. Evidence Support Rate:  100.0% (25/25 evidence citations valid)
3. Verification Accuracy:  100.0% (5/5)
============================================================
```

Pytest test suite results:
```
======================= 27 passed, 1 warning in 2.12s ========================
```
- Database CRUD & Seeding: 4 tests passed
- Deterministic Tool Operations: 5 tests passed
- Qdrant RAG Chunking & Search: 2 tests passed
- Agent Logic & Evidence Validation: 3 tests passed
- LangGraph Routing & Re-investigation Loop: 4 tests passed
- FastAPI REST Endpoints: 4 tests passed
- End-to-End Scenarios: 5 tests passed

---

## 13. Failure Handling
IncidentPilot treats failure as a first-class state:
- **Missing / Degraded Tools**: If logs or metrics return zero rows, the agent documents empty findings rather than hallucinating telemetry.
- **Fabricated Evidence Protection**: The verification agent cross-references every evidence ID in `supporting_evidence_ids` against the runtime evidence dictionary. Any non-existent ID fails verification immediately.
- **Contradiction Detection**: If conflicting signals exist (e.g. CPU nominal while an agent claims CPU starvation), verification fails.
- **Distinguished Statuses**: The system explicitly returns `SUCCESS`, `INSUFFICIENT_EVIDENCE`, or `INVESTIGATION_FAILED`.

---

## 14. Human-in-the-Loop Design
In accordance with production reliability safety standards, IncidentPilot does **NOT** autonomously execute destructive remediation actions (e.g. rolling back production services or terminating database clusters).
- Every report includes:
  ```json
  "human_approval_required": true,
  "approval_status": "PENDING_APPROVAL"
  ```
- The Streamlit interface displays an explicit authorization banner requiring an on-call engineer to review the evidence and approve or reject the recommended remediation.

---

## 15. Setup Instructions

### Prerequisites
- Python 3.11
- Git

### 1. Clone & Setup Virtual Environment
```bash
git clone <repo_url>
cd IncidentPilot

# Create Python 3.11 virtual environment
py -3.11 -m venv .venv

# Activate virtual environment
# Windows:
.\.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Configure your Groq API key:
```env
GROQ_API_KEY=gsk_your_actual_groq_api_key
GROQ_MODEL=llama-3.3-70b-versatile
DATABASE_URL=sqlite:///./incidentpilot.db
QDRANT_URL=:memory:
```

### 3. Seed Database & Run Pytest
```bash
# Seed the 5 realistic production scenarios
python -m app.db.seed

# Run pytest suite
pytest -v

# Run evaluation benchmark
python evaluation/run_eval.py
```

### 4. Start FastAPI & Streamlit
```bash
# Start FastAPI backend (Terminal 1)
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Start Streamlit UI (Terminal 2)
streamlit run frontend/app.py --server.port 8501
```

---

## 16. Docker Instructions
To spin up the entire stack (FastAPI, Streamlit, PostgreSQL, and Qdrant) using Docker Compose:
```bash
# Ensure GROQ_API_KEY is defined in .env
docker compose up --build
```
Services will be accessible at:
- **FastAPI API & Docs**: `http://localhost:8000/docs`
- **Streamlit Dashboard**: `http://localhost:8501`
- **Qdrant Dashboard**: `http://localhost:6333/dashboard`
- **PostgreSQL**: `localhost:5432`

---

## 17. Example Investigation Walkthrough

### Incident: `INC-001` (Database Pool Saturation)
1. **Incident Triggered**: Operator or alert manager reports HTTP 500 timeouts on `/api/v1/payments/process`.
2. **Supervisor Agent**: Formulates plan: query `payment-service` logs, deployments within 4 hours, and connection metrics.
3. **Log Agent**: Finds `TimeoutError: QueuePool limit of size 20 overflow 10 reached` (`LOG-101`, `LOG-102`).
4. **Deployment Agent**: Discovers deployment `DEP-101` (`v3.1.2`) deployed 3 hours ago.
5. **Metrics Agent**: Identifies `db_connection_pool_utilization = 98.5%` (`METRIC-1`) and `p99_latency_ms = 4820.0` (`METRIC-3`).
6. **Runbook Agent**: Vector search over `database_connection_pool.md` returns pool tuning steps (`RUNBOOK-03`, score: 0.819).
7. **Root Cause Analyst**: Selects hypothesis *"Database connection pool exhaustion"* (Confidence: 0.92) citing `LOG-101`, `LOG-102`, `METRIC-1`, `RUNBOOK-03`.
8. **Verification Agent**: Validates that all 4 cited IDs exist in the evidence catalog, checks for contradictions, and confirms sufficient evidence -> **`VERIFIED`**.
9. **Remediation**: Recommends scaling pool limits and restarting pods; marks status as **`PENDING_APPROVAL`**.

---

## 18. Limitations
- **Synthetic Correlated Data**: Telemetry is generated via realistic synthetic seeding rather than live production Kafka/Prometheus streams.
- **Fixed Model Execution**: Optimized for Groq's high-speed inference endpoints (`llama-3.3-70b-versatile` / `llama-3.1-8b-instant`).
- **Simulated Execution**: Recommended remediation actions are simulated; destructive production automation is deliberately gated.

---

## 19. Future Improvements
- **Live OpenTelemetry Ingestion**: Ingest live OTLP traces, Prometheus metrics, and Loki log streams.
- **Self-Healing Runbook Generation**: Update runbook vectors with post-incident review (PIR) learnings automatically.
- **Multi-Cloud Sandboxes**: Safe automated remediation execution in ephemeral staging environments.
