import os
from pathlib import Path
import pytest
from unittest.mock import patch
from sqlalchemy import create_engine

# Configure isolated test database BEFORE app imports or models load
TEST_DB_PATH = Path(__file__).resolve().parent.parent / "test_incidentpilot.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.config import settings
settings.database_url = TEST_DATABASE_URL

from app.db import database as app_db
from app.db.database import SessionLocal, init_db, Base
from app.db.seed import seed_database
from app.main import app
from fastapi.testclient import TestClient

# Create isolated test engine and rebind application engine and SessionLocal
test_connect_args = {"check_same_thread": False} if TEST_DATABASE_URL.startswith("sqlite") else {}
test_engine = create_engine(TEST_DATABASE_URL, connect_args=test_connect_args)
app_db.engine = test_engine
app_db.SessionLocal.configure(bind=test_engine)
engine = test_engine


def _override_get_db():
    db = app_db.SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[app_db.get_db] = _override_get_db


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Initializes and seeds isolated test database once for test session with fresh schema."""
    live_db_name = "incidentpilot.db"
    test_db_name = "test_incidentpilot.db"
    engine_url_str = str(engine.url)

    assert test_db_name in engine_url_str, (
        f"CRITICAL SAFETY VIOLATION: Test database engine must point to {test_db_name}, got {engine_url_str}"
    )
    db_file_name = Path(engine.url.database).name if engine.url.database else ""
    assert db_file_name == test_db_name, (
        f"CRITICAL SAFETY VIOLATION: Expected database file {test_db_name}, got {db_file_name}!"
    )
    assert db_file_name != live_db_name, (
        f"CRITICAL SAFETY VIOLATION: Test engine must NOT point to live {live_db_name}!"
    )

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
