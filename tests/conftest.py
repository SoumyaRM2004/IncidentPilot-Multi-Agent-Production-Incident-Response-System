import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.db.database import SessionLocal, init_db, Base, engine
from app.db.seed import seed_database
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Initializes and seeds database once for test session with fresh schema."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_database()


@pytest.fixture(autouse=True)
def reset_rate_limit_between_tests():
    """Ensure rate-limit state from real LLM calls does not leak across tests."""
    from app.agents.llm import reset_rate_limit_state
    reset_rate_limit_state()
    yield
    reset_rate_limit_state()


@pytest.fixture
def db_session():
    """Yields a database session for test verification."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def api_client():
    """Yields a FastAPI test client."""
    with TestClient(app) as client:
        yield client


def _mock_root_cause_llm_response(system_prompt, user_prompt, schema_model=None):
    import re
    # Extract evidence IDs and metadata from user_prompt
    ids = re.findall(r'"id":\s*"([^"]+)"', user_prompt)
    service_match = re.search(r'Service:\s*([^\n]+)', user_prompt)
    service = service_match.group(1).strip() if service_match else "target-service"
    title_match = re.search(r'Title:\s*([^\n]+)', user_prompt)
    title = title_match.group(1).strip() if title_match else "Incident"

    # Select empirical evidence IDs ensuring multi-domain diversity (e.g. log + metric/deployment)
    log_ids = [i for i in ids if i.startswith("LOG") or i.startswith("FREQ")]
    metric_ids = [i for i in ids if i.startswith("METRIC")]
    dep_ids = [i for i in ids if i.startswith("DEP")]
    runbook_ids = [i for i in ids if i.startswith("RUNBOOK")]

    supporting = []
    if log_ids:
        supporting.append(log_ids[0])
    if metric_ids:
        supporting.append(metric_ids[0])
    if dep_ids:
        supporting.append(dep_ids[0])
    if runbook_ids and len(supporting) < 3:
        supporting.append(runbook_ids[0])

    if len(supporting) < 2:
        supporting = ids[:3]

    return {
        "selected_root_cause": f"Diagnosed service anomaly on {service} related to {title}",
        "confidence": 0.85,
        "supporting_evidence_ids": supporting,
        "contradictory_evidence_ids": [],
        "reasoning_summary": f"Observed empirical telemetry on {service} corroborates degradation matching {title}.",
        "hypotheses": [
            {
                "id": "HYP-1",
                "title": f"Diagnosed service anomaly on {service} related to {title}",
                "confidence": 0.85,
                "supporting_evidence_ids": supporting,
                "contradictory_evidence_ids": [],
                "rationale": "Direct empirical corroboration across telemetry sources."
            }
        ],
        "recommended_action": {
            "action": f"Apply operational runbook remediation on {service}",
            "target_service": service,
            "human_approval_required": True,
            "approval_status": "PENDING_APPROVAL",
            "estimated_risk": "LOW",
            "rationale": "Remediates verified root cause."
        }
    }


@pytest.fixture
def mock_layer2_verified():
    """Provides a simulated LLM environment for Root Cause and Layer 2 semantic verification."""
    with patch("app.agents.verification.get_groq_client", return_value=True), \
         patch("app.agents.verification.call_groq_json", return_value={
             "verified": True,
             "confidence_acceptable": True,
             "evidence_sufficient": True,
             "contradictions_found": False,
             "explanation": "Empirically verified across collected evidence."
         }), \
         patch("app.agents.root_cause.get_groq_client", return_value=True), \
         patch("app.agents.root_cause.call_groq_json", side_effect=_mock_root_cause_llm_response):
        yield
