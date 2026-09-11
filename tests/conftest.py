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


@pytest.fixture
def mock_layer2_verified():
    """Provides a semantic Layer 2 verifier that confirms causal verification."""
    with patch("app.agents.verification.get_groq_client", return_value=True):
        with patch("app.agents.verification.call_groq_json", return_value={
            "verified": True,
            "confidence_acceptable": True,
            "evidence_sufficient": True,
            "contradictions_found": False,
            "explanation": "Empirically verified across collected evidence."
        }):
            yield
