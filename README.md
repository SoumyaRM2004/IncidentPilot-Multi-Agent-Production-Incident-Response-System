# IncidentPilot: Autonomous Production Incident Response System

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110.0-009688.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.0.30-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector%20DB-red.svg)](https://qdrant.tech/)
[![Tests](https://img.shields.io/badge/Tests-30%20passed-brightgreen.svg)](tests/)

IncidentPilot is an autonomous multi-agent incident response system designed to investigate production outages. Built with **Python 3.11, LangGraph, Groq LLM, Qdrant, SQLAlchemy, FastAPI, and Streamlit**, IncidentPilot coordinates specialized investigation agents across logs, metrics, deployment changes, and operational runbooks to formulate, challenge, and verify evidence-backed root cause diagnoses.

Every diagnostic assertion is backed by strict evidence provenance: hypotheses cite verified telemetry IDs, a deterministic **Two-Layer Verification Agent** audits evidence to eliminate hallucinations, and destructive actions are protected by persistent human-in-the-loop operator approval.

---

## Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Why Multi-Agent SRE Systems Matter](#2-why-multi-agent-sre-systems-matter)
3. [Core Architecture & Data Flow](#3-core-architecture--data-flow)
4. [Multi-Agent Design & Responsibilities](#4-multi-agent-design--responsibilities)
5. [Unified Evidence Model & Provenance](#5-unified-evidence-model--provenance)
6. [Two-Layer Verification Architecture](#6-two-layer-verification-architecture)
7. [LangGraph State Machine & Re-investigation Loop](#7-langgraph-state-machine--re-investigation-loop)
8. [Deterministic Tool Architecture](#8-deterministic-tool-architecture)
9. [Dense Runbook Retrieval (RAG)](#9-dense-runbook-retrieval-rag)
10. [Database Schema & Persistent Gating](#10-database-schema--persistent-gating)
11. [REST API Specification](#11-rest-api-specification)
12. [Evaluation Benchmark & Empirical Results](#12-evaluation-benchmark--empirical-results)
13. [Failure Modes & Graceful Degradation](#13-failure-modes--graceful-degradation)
14. [Strict Architecture Boundaries (Frontend vs Backend)](#14-strict-architecture-boundaries-frontend-vs-backend)
15. [Setup & Quickstart Guide](#15-setup--quickstart-guide)
16. [Docker Deployment](#16-docker-deployment)
17. [Interview Defense & Architectural Tradeoffs](#17-interview-defense--architectural-tradeoffs)

---

## 1. Executive Summary

During production outages, Site Reliability Engineers (SREs) face fragmented telemetry across isolated observability silos: log aggregators, deployment release consoles, time-series metric databases, and internal operational runbooks. Triaging an outage manually under severe time pressure incurs high cognitive load, increasing Mean Time to Resolution (MTTR).

Generic LLM chatbots fail in production SRE workflows because:
- **Hallucinated Diagnostics**: Chatbots generate plausible-sounding root causes unsupported by actual logs or metrics.
- **Lack of Evidence Provenance**: Generic models cannot cite deterministic record identifiers for mathematical verification.
- **Absence of Self-Correction**: When given incomplete or noisy telemetry, chatbots commit to ungrounded guesses rather than triggering targeted re-investigation.

IncidentPilot solves this by replacing ad-hoc prompt chains with a **deterministic, evidence-grounded multi-agent graph**:
- Telemetry tools yield structured `EvidenceItem` records with immutable, traceable IDs.
- Root cause analysis synthesizes hypotheses strictly from empirical findings.
- A **Two-Layer Verification Agent** enforces deterministic validation (Layer 1) before allowing semantic LLM review (Layer 2).
- Destructive remediations are gated behind persistent operator approval (`PENDING_APPROVAL` $\rightarrow$ `APPROVED` / `REJECTED`).

---

## 2. Why Multi-Agent SRE Systems Matter

| Traditional Chatbot Approach | IncidentPilot Multi-Agent Architecture |
|---|---|
| Dumps raw logs and telemetry into a massive prompt context window | Specialized domain agents query filtered time windows deterministically |
| Hallucinates imaginary log lines and phantom configuration flags | Every cited fact is bound to an immutable `evidence_id` in the database |
| Single-pass generation with zero validation or cross-checking | Two-layer verification audits citations and challenges flawed hypotheses |
| Guesswork when evidence is missing or inconclusive | Explicitly terminates with `INSUFFICIENT_EVIDENCE` and low calibrated confidence |
| Autonomous hallucinations executing unvetted terminal commands | Persistent operator approval gating required for all remediation actions |

---

## 3. Core Architecture & Data Flow

```
                                +-----------------------------+
                                |     Production Incident     |
                                +-----------------------------+
                                               |
                                               v
                                +-----------------------------+
                                |      Supervisor Agent       |
                                |  (Plan / Allowlist Filter)  |
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
                                   (Cosine / bge-small)
                                               |
                                               v
                                +-----------------------------+
                                |  Root Cause Analyst Agent   |
                                | (Evidence-Driven Synthesis) |
                                +-----------------------------+
                                               |
                                      Ranked Hypotheses
                                               |
                                               v
                                +-----------------------------+
                                |     Verification Agent      |
                                |  [Layer 1: Deterministic]   |
                                |  [Layer 2: Semantic LLM]    |
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
                                     |   (Challenge Feedback) INSUFFICIENT_EVIDENCE
                                     v
                        +-----------------------------+
                        |    Recommended Action       |
                        +-----------------------------+
                                     |
                                     v
                        +-----------------------------+
                        |   HUMAN OPERATOR APPROVAL   |
                        |   (POST /approve or /reject)|
                        +-----------------------------+
                                     |
                                     v
                        +-----------------------------+
                        |     Final Incident Report   |
                        +-----------------------------+
```

---

## 4. Multi-Agent Design & Responsibilities

1. **Supervisor Agent** (`app/agents/supervisor.py`):
   - Formulates a targeted investigation plan based on incident symptoms and affected services.
   - Enforces an agent allowlist (`ALLOWED_AGENTS = {"logs", "deployments", "metrics", "runbook"}`) to prevent arbitrary execution.
   - Consumes verification challenge feedback during re-investigation loops to adapt query parameters and broaden collection scope.

2. **Log Investigation Agent** (`app/agents/logs.py`):
   - Executes deterministic SQL-backed queries against service logs within the incident time window.
   - Computes error frequency velocity and extracts error clusters and stack traces.

3. **Deployment Agent** (`app/agents/deployments.py`):
   - Inspects recent releases, versions, commit SHAs, and deployment timestamps to identify temporal correlations.

4. **Metrics Agent** (`app/agents/metrics.py`):
   - Queries telemetry for system saturation: CPU utilization, memory thresholds, DB pool saturation, network packet loss, and latency percentiles.

5. **Runbook / RAG Agent** (`app/agents/runbook.py`):
   - Performs dense vector semantic retrieval against operational SRE runbooks in Qdrant.
   - Matches operational failure modes to institutional remediation procedures with similarity scoring.

6. **Root Cause Analyst Agent** (`app/agents/root_cause.py`):
   - Synthesizes findings strictly from the collected evidence catalog.
   - Formulates ranked hypotheses, explains causal chains, calculates calibrated confidence scores, and cites supporting `evidence_id`s.

7. **Verification Agent** (`app/agents/verification.py`):
   - Audits hypotheses against collected evidence.
   - Layer 1 runs deterministic checks for hallucinated IDs, evidence sufficiency, multi-source corroboration, and metric contradictions.
   - Layer 2 executes semantic verification via Groq LLM.

---

## 5. Unified Evidence Model & Provenance

To guarantee zero hallucinated citations, every agent emits evidence complying with the Pydantic `EvidenceItem` schema (`app/graph/state.py`):

```python
class EvidenceItem(BaseModel):
    evidence_id: str             # e.g., "LOG-101", "METRIC-2", "DEP-101", "RUNBOOK-03"
    evidence_type: str           # "application_logs" | "service_metrics" | "deployment_records" | "operational_runbook"
    source_agent: str            # "logs" | "deployments" | "metrics" | "runbook"
    timestamp: str               # ISO 8601 UTC timestamp
    service: str                 # Microservice identifier
    summary: str                 # Concise factual observation
    details: Dict[str, Any]      # Tool raw payload (metrics, log message, version)
    confidence_score: float      # Signal quality score (0.0 to 1.0)
```

By enforcing this structure across all data collectors, the Root Cause Analyst cannot introduce phantom observations, and the Verification Agent can audit every cited ID against the collected catalog via set-intersection operations.

---

## 6. Two-Layer Verification Architecture

The Verification Agent is designed with an authoritative deterministic layer that LLM generation cannot override:

```
[Candidate Hypothesis + Supporting Evidence IDs]
                     |
                     v
   +------------------------------------+
   | LAYER 1: Deterministic Validation  |
   | - Hallucinated ID Check            |
   | - Minimum Evidence Threshold (>= 2)|
   | - Multi-Source Corroboration Check |
   | - Telemetry Contradiction Check    |
   | - Uncalibrated Confidence Penalty  |
   +------------------------------------+
              /              \
           [PASS]           [FAIL]
             |                 \
             v                  \
   +--------------------+        \
   | LAYER 2: Semantic  |         \
   | Verification (LLM) |          \
   +--------------------+           \
             |                       \
          Outcome                     Outcome: Deterministic Rejection
    (Verified / Rejected)             (LLM CANNOT OVERRIDE)
```

### Layer 1 Checks:
1. **Hallucination Detection**: Ensures `supporting_evidence_ids` $\subseteq$ `{collected_evidence.evidence_id}`. Any phantom ID triggers immediate rejection.
2. **Sufficiency Check**: Rejects hypotheses supported by fewer than 2 distinct evidence items.
3. **Multi-Source Corroboration**: Flags single-source claims (e.g. only logs without metrics or deployment records).
4. **Contradiction Detection**: Cross-checks claims against quantitative metrics (e.g. rejects "CPU starvation" if metric data shows CPU utilization $< 70\%$).
5. **Confidence Calibration**: Caps confidence to $\le 0.50$ when evidence is minimal or inconclusive, preventing unjustified high-confidence claims.

---

## 7. LangGraph State Machine & Re-investigation Loop

The orchestration state is defined in `InvestigationState` (`app/graph/state.py`):

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

### Dynamic Routing Logic:
- `route_after_verification(state)`:
  - If `verification_result.verified == True` $\rightarrow$ proceed to `END` with status `SUCCESS`.
  - If `verification_result.verified == False` and `iteration_count < max_iterations (2)`:
    - Increment `iteration_count`.
    - Route back to `supervisor` with `verification_result.challenge_explanation` to formulate an expanded re-investigation plan.
  - If `iteration_count >= max_iterations (2)`:
    - Mark status as `INSUFFICIENT_EVIDENCE`.
    - Terminate safely rather than forcing an ungrounded guess.

---

## 8. Deterministic Tool Architecture

Tools execute parameter-filtered queries directly against database rows and return structured dictionaries satisfying both the strict `EvidenceItem` schema and top-level fields:

- **Log Tools** (`app/tools/logs.py`):
  - `search_logs(service, query, level, limit)`: Returns matching logs with IDs (`LOG-xxx`).
  - `get_error_frequency(service, minutes)`: Returns time-windowed error frequency and velocity metrics (`FREQ-xxx`).
  - `get_service_logs(service, limit)`: Returns chronological logs within the incident window.
- **Deployment Tools** (`app/tools/deployments.py`):
  - `get_recent_deployments(service, limit)`: Returns releases with version tags and commit hashes (`DEP-xxx`).
  - `get_deployment_details(deployment_id)`: Fetches configuration changes and environment variables.
- **Metrics Tools** (`app/tools/metrics.py`):
  - `get_service_metrics(service, metric_name)`: Returns specific time-series points (`METRIC-xxx`).
  - `get_metric_window(service, metric_name, minutes)`: Returns aggregated metric windows (mean, max, anomaly detection).

---

## 9. Dense Runbook Retrieval (RAG)

- **Vector Database**: Qdrant (`:memory:` embedded mode for tests and local development; Docker container for production).
- **Embedding Model**: FastEmbed running `BAAI/bge-small-en-v1.5` (384 dimensions) locally via ONNX Runtime (zero external embedding API costs or latency).
- **Section-Aware Chunking**: Markdown runbooks in `data/runbooks/` are split into semantic units indexed by document title, failure category, and remediation procedures (`RUNBOOK-01`, `RUNBOOK-02`, etc.) with similarity scoring.

---

## 10. Database Schema & Persistent Gating

PostgreSQL schema implemented via SQLAlchemy (`app/db/models.py`), with SQLite automated fallback for local testing:

```
+--------------------------------------------------------------------------------+
|                                 DATABASE SCHEMA                                |
+--------------------+---------------------+--------------------+----------------+
|    incidents       |     deployments     |       logs         |    metrics     |
+--------------------+---------------------+--------------------+----------------+
| id (PK)            | id (PK)             | id (PK)            | id (PK)        |
| title              | service             | timestamp (UTC)    | timestamp (UTC)|
| description        | version             | service            | service        |
| service            | deployed_at (UTC)   | level              | metric_name    |
| severity           | environment         | message            | value          |
| created_at (UTC)   | commit_hash         | trace_id           |                |
| status             |                     |                    |                |
+--------------------+---------------------+--------------------+----------------+
                                           |
                                           v
                     +-------------------------------------------+
                     |              investigations               |
                     +-------------------------------------------+
                     | id (PK)                                   |
                     | incident_id (FK -> incidents.id)          |
                     | started_at (UTC)                          |
                     | completed_at (UTC)                        |
                     | status (SUCCESS | INSUFFICIENT_EVIDENCE)  |
                     | final_confidence                          |
                     | report (JSON)                             |
                     | approval_status (PENDING|APPROVED|REJECTED|
                     | approved_at (UTC)                         |
                     | operator_decision                         |
                     | operator_notes                            |
                     +-------------------------------------------+
```

### Persistent Approval Gating:
All remediation recommendations require explicit operator sign-off. When an investigation completes:
1. `investigations.approval_status` is initialized to `PENDING_APPROVAL`.
2. The operator reviews the evidence and issues a decision via the API or UI.
3. The decision, UTC timestamp, and operator audit notes are persistently written to the database.

---

## 11. REST API Specification

FastAPI application exposes clean endpoints with request/response Pydantic models (`app/api/routes.py`):

| Method | Path | Description | Key Request / Response Fields |
|---|---|---|---|
| `GET` | `/health` | System health check | `status`, `timestamp`, `version` |
| `POST` | `/incidents` | Create a new incident | Body: `title`, `service`, `description`, `severity` |
| `GET` | `/incidents` | List all incidents | Returns array of `IncidentResponse` |
| `GET` | `/incidents/{id}` | Retrieve incident details | Returns `IncidentResponse` |
| `POST` | `/incidents/{id}/investigate` | Trigger LangGraph multi-agent investigation | Initiates workflow, returns `InvestigationResponse` |
| `GET` | `/investigations/{id}` | Retrieve investigation results | Returns status, evidence catalog, hypothesis, and approval status |
| `POST` | `/investigations/{id}/approve` | Persistently approve remediation action | Body: `decision="APPROVED"`, `operator_notes`. Returns updated status |
| `POST` | `/investigations/{id}/reject` | Persistently reject remediation action | Body: `decision="REJECTED"`, `operator_notes`. Returns updated status |

---

## 12. Evaluation Benchmark & Empirical Results

The system is evaluated against an expanded benchmark dataset of **9 production incidents** across 4 categories (`evaluation/incidents.json`):
1. **Standard Scenarios (5 incidents)**: Ground-truth production failures (DB pool saturation, bad deployment, OOM leak, third-party SMS 504, network degradation).
2. **Paraphrased Scenarios (2 incidents)**: Completely reworded symptoms to demonstrate zero dependency on keyword matching.
3. **Noisy Telemetry (1 incident)**: Intermittent warnings and background noise to verify robust signal extraction.
4. **Insufficient Telemetry (1 incident)**: Missing metrics and logs to verify safe termination without hallucination.

### Empirical Evaluation Output:
```
================================================================================
IncidentPilot Multi-Agent Production Incident Response Evaluation
================================================================================
ID        | Category       | Service            | RC   | Evidence | Verif | Iters | Conf 
--------------------------------------------------------------------------------
INC-001   | standard       | payment-service    | PASS | 3/3      | PASS  | 0     | 85%  
INC-002   | standard       | order-service      | PASS | 4/4      | PASS  | 0     | 88%  
INC-003   | standard       | auth-service       | PASS | 3/3      | PASS  | 0     | 85%  
INC-004   | standard       | notification-service | PASS | 3/3      | PASS  | 0     | 85%  
INC-005   | standard       | user-service       | PASS | 3/3      | PASS  | 0     | 88%  
INC-006   | paraphrased    | payment-service    | PASS | 3/3      | PASS  | 0     | 85%  
INC-007   | paraphrased    | order-service      | PASS | 4/4      | PASS  | 0     | 88%  
INC-008   | noisy          | auth-service       | PASS | 3/3      | PASS  | 0     | 85%  
INC-009   | insufficient_telemetry | analytics-service  | PASS | 0/0      | PASS  | 2     | 20%  
================================================================================
KEY METRICS:
1. Root Cause Accuracy:         100.0% (9/9)
2. Evidence Grounding Rate:       100.0% (26/26 citations grounded in telemetry)
3. Hallucination Rate:           0.0% (0/26 fabricated citation IDs)
4. Verification Accuracy:        100.0% (9/9 correctly judged)
5. Verification Rejection Rate:  11.1% (1/9 flagged or rejected)
6. Avg Iterations to Converge:   0.22
================================================================================
ALL EVALUATION BENCHMARKS PASSED SUCCESSFULLY.
```

### Pytest Verification Suite:
```
============================== 30 passed in 2.18s ==============================
- Agent Planning & Evidence Collection: 6 tests passed
- Deterministic Tool Execution: 5 tests passed
- Two-Layer Verification Guardrails: 4 tests passed
- Database Models & UTC Timestamps: 4 tests passed
- LangGraph Routing & Re-investigation: 3 tests passed
- Qdrant Vector Retrieval: 2 tests passed
- Paraphrased & Empty Telemetry Scenarios: 2 tests passed
- API Investigation & Approval Lifecycle: 4 tests passed
```

---

## 13. Failure Modes & Graceful Degradation

IncidentPilot treats failure as an expected first-class state:
- **Zero Hallucination Guarantee**: If an agent references an evidence ID not present in the run's collected evidence catalog, Layer 1 verification fails immediately.
- **Empty Telemetry Handling**: If a service has no logs, metrics, or deployments, confidence is capped at $\le 20\%$ with empty supporting IDs, correctly concluding with `INSUFFICIENT_EVIDENCE`.
- **Bounded Re-investigation**: The feedback loop is strictly bounded by `max_iterations = 2`, preventing infinite token loops or runaway execution.
- **Contradiction Rejection**: If telemetry directly contradicts a hypothesis (e.g., claiming CPU exhaustion when metrics show nominal CPU), Layer 1 rejects the diagnosis with challenge notes.

---

## 14. Strict Architecture Boundaries (Frontend vs Backend)

The frontend (`frontend/app.py`) is designed as a **strictly decoupled HTTP consumer**:
- **Zero Direct Database Access**: Never imports `SessionLocal`, SQLAlchemy models, or direct database connections.
- **Zero Direct Workflow Execution**: Never imports LangGraph graphs or agent nodes directly.
- **API Boundary Enforcement**: All incident listings, trigger investigations, and operator approval actions execute via standard REST calls (`requests.get`, `requests.post`) against FastAPI (`http://localhost:8000`).
- **Resilient Degraded Mode**: If the FastAPI backend is down, the UI renders an actionable connection alert rather than crashing with unhandled exceptions.

---

## 15. Setup & Quickstart Guide

### Prerequisites
- Python 3.11
- Git

### 1. Clone & Set Up Environment
```bash
git clone https://github.com/SoumyaRM2004/IncidentPilot-Multi-Agent-Production-Incident-Response-System.git
cd IncidentPilot-Multi-Agent-Production-Incident-Response-System

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.\.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Configure your `.env` file:
```env
GROQ_API_KEY=gsk_your_actual_groq_api_key
GROQ_MODEL=llama-3.3-70b-versatile
DATABASE_URL=sqlite:///./incidentpilot.db
QDRANT_URL=:memory:
```

### 3. Run Tests and Evaluation
```bash
# Seed the database with telemetry scenarios
python -m app.db.seed

# Run the full 30-test suite
pytest -v

# Run the 9-incident benchmark evaluation
python evaluation/run_eval.py
```

### 4. Run Services
```bash
# Terminal 1: Launch FastAPI Backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Launch Streamlit Dashboard
streamlit run frontend/app.py --server.port 8501
```

Access the application:
- **FastAPI OpenAPI Swagger Docs**: `http://localhost:8000/docs`
- **Streamlit Interactive UI**: `http://localhost:8501`

---

## 16. Docker Deployment

To launch the full production-style containerized stack (FastAPI backend, Streamlit frontend, Qdrant vector database, and PostgreSQL):

```bash
# Ensure GROQ_API_KEY is configured in .env
docker compose up --build
```

Services will be accessible at:
- **FastAPI API**: `http://localhost:8000/docs`
- **Streamlit Console**: `http://localhost:8501`
- **Qdrant Dashboard**: `http://localhost:6333/dashboard`
- **PostgreSQL**: `localhost:5432`

---

## 17. Interview Defense & Architectural Tradeoffs

### 1. Why LangGraph instead of a simple ReAct loop or Autogen?
> **Answer**: Production incident response requires predictable state progression, strict audit trails, and deterministic branch routing. LangGraph gives us an explicit state machine where execution between the Supervisor, specialized agents, Root Cause Analyst, and Verification Agent is strictly governed. ReAct loops often suffer from tool call thrashing and runaway token consumption during high-stress incident triage.

### 2. Why Two-Layer Verification instead of asking the LLM "is this correct"?
> **Answer**: LLMs suffer from confirmation bias and self-evaluation hallucinations. If an LLM fabricates an evidence ID during hypothesis synthesis, asking the same LLM or another prompt if the evidence is sound will often result in a rubber-stamped verification. Layer 1 verification runs deterministic Python code that performs set-intersection checks against database IDs and verifies metric thresholds. The LLM is never allowed to override a Layer 1 failure.

### 3. How do you prevent hallucinated remediation execution?
> **Answer**: Destructive actions are never executed autonomously. The system outputs recommendations marked `human_approval_required: true` and sets `approval_status: PENDING_APPROVAL`. Only when an authorized on-call engineer submits an explicit approval via `POST /investigations/{id}/approve` is the action logged as authorized, maintaining compliance with SRE safety standards.

### 4. Why local FastEmbed ONNX instead of OpenAI / Cohere embeddings?
> **Answer**: During an incident response scenario, dependencies on external third-party embedding APIs introduce additional points of failure and network latency. FastEmbed executes the `BAAI/bge-small-en-v1.5` model locally via ONNX Runtime inside the service process, ensuring zero external API latency, zero per-token cost, and zero external dependency failure.

---

## License
MIT License. Built for production reliability engineering research and portfolio demonstration.
