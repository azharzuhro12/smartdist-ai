from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from backend.app.core.config import settings
from backend.app.core.logging import logger

engine = create_engine(
    settings.sync_database_uri,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dedicated engine for SQL Assistant under least-privilege readonly role
readonly_engine = engine
ReadOnlySessionLocal: sessionmaker[Session] = SessionLocal

try:
    readonly_engine = create_engine(
        settings.readonly_database_uri,
        pool_size=5,
        max_overflow=10,
        pool_timeout=settings.DATABASE_POOL_TIMEOUT,
        pool_pre_ping=True,
    )
    ReadOnlySessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=readonly_engine)
except Exception as exc:
    logger.warning(f"Could not initialize dedicated readonly_engine: {exc}. Falling back to default engine.")


def get_readonly_db() -> Generator[Session, None, None]:
    """
    Yields a SQLAlchemy session bound to the least-privilege read-only engine.
    """
    db = ReadOnlySessionLocal()
    try:
        yield db
    finally:
        db.close()



def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a SQLAlchemy database session and ensures
    clean teardown upon request completion.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    """
    Execute a lightweight connectivity ping (SELECT 1) against the database.
    Returns True if healthy, False otherwise.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning(f"Database health check failed: {exc}")
        return False
