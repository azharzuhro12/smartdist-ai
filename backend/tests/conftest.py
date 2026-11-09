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
from backend.app.models.user import User, UserRole
from backend.app.api.deps import get_current_user, get_current_active_user

mock_admin_user = User(
    id=999,
    username="testadmin",
    email="testadmin@smartdist.ai",
    hashed_password="mock_hashed_password",
    role=UserRole.ADMIN,
    is_active=True,
    full_name="Test Admin",
)


@pytest.fixture(scope="session", autouse=True)
def setup_default_test_auth():
    """
    Autouse session fixture providing an authenticated administrator session by default.
    Ensures all baseline Phase 1-4 tests and any TestClient(app) instances continue
    to pass seamlessly without modification.
    """
    app.dependency_overrides[get_current_user] = lambda: mock_admin_user
    app.dependency_overrides[get_current_active_user] = lambda: mock_admin_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_active_user, None)


@pytest.fixture(scope="session")
def client() -> TestClient:
    """
    TestClient fixture for FastAPI application tests.
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def unauthenticated_client() -> TestClient:
    """
    TestClient with auth overrides removed to test authentic authentication,
    rate limiting, and 401/403 security enforcement.
    """
    old_overrides = dict(app.dependency_overrides)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_active_user, None)
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.update(old_overrides)




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
