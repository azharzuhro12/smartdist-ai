from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.app.db.session import SessionLocal, check_db_connection, get_db


def test_db_session_lifecycle():
    """Verify get_db generator yields a valid session and closes cleanly."""
    gen = get_db()
    session = next(gen)
    assert session is not None
    assert isinstance(session, Session)
    # Complete generator
    try:
        next(gen)
    except StopIteration:
        pass


def test_db_live_connectivity():
    """
    Test live database connectivity.
    Executes SELECT 1 to verify PostgreSQL connection and SQL query execution.
    """
    is_connected = check_db_connection()
    if not is_connected:
        import pytest
        pytest.fail(
            "PostgreSQL database is currently unreachable. Ensure the database container is running and healthy."
        )

    with SessionLocal() as session:
        result = session.execute(text("SELECT 1 AS alive")).scalar()
        assert result == 1
