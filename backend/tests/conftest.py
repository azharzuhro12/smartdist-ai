import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.db.session import SessionLocal


@pytest.fixture(scope="session")
def client() -> TestClient:
    """
    TestClient fixture for FastAPI application tests.
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    """
    Yields a SQLAlchemy session for test execution and ensures proper closure.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
