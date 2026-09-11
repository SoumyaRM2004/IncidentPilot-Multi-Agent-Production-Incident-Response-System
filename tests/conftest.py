import pytest
from fastapi.testclient import TestClient
from app.db.database import SessionLocal, init_db
from app.db.seed import seed_database
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Initializes and seeds database once for test session."""
    init_db()
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
