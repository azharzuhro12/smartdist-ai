import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError, InternalError
from backend.app.core.config import settings


@pytest.fixture(scope="module")
def postgres_live_connection():
    """Connect using postgresql connection settings."""
    engine = create_engine(settings.sync_database_uri)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        pytest.skip("Live PostgreSQL database is not reachable.")


def test_smartdist_owner_role_attributes(postgres_live_connection):
    """smartdist_owner must not be superuser, createdb, createrole, or replication."""
    engine = create_engine(settings.sync_database_uri)
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication "
                "FROM pg_roles WHERE rolname = 'smartdist_owner'"
            )
        ).fetchone()

        if result:
            assert result[0] is False, "smartdist_owner must not be superuser"
            assert result[1] is False, "smartdist_owner must not have createdb"
            assert result[2] is False, "smartdist_owner must not have createrole"
            assert result[3] is False, "smartdist_owner must not have replication"


def test_smartdist_readonly_privileges(postgres_live_connection):
    """smartdist_readonly can query products, but cannot query users or execute DML/DDL."""
    ro_uri = settings.readonly_database_uri
    engine = create_engine(ro_uri)

    with engine.connect() as conn:
        # Can read public business entities
        res = conn.execute(text("SELECT count(*) FROM products")).scalar()
        assert res >= 0

        # CANNOT read users / credential table
        with pytest.raises(ProgrammingError) as exc_info:
            conn.execute(text("SELECT count(*) FROM users"))
        assert "permission denied" in str(exc_info.value).lower()

    # CANNOT execute INSERT
    with engine.connect() as conn:
        with pytest.raises((ProgrammingError, InternalError)) as exc_info:
            conn.execute(
                text(
                    "INSERT INTO products (product_code, product_name, category_id, source_family, unit_of_measure, is_active, data_origin, created_at, updated_at) "
                    "VALUES ('TEST_RO', 'TEST_RO', 1, 'TEST', 'UNIT', true, 'TEST', now(), now())"
                )
            )
        assert "read-only" in str(exc_info.value).lower() or "permission denied" in str(exc_info.value).lower()


def test_smartdist_app_cannot_ddl(postgres_live_connection):
    """smartdist_app runtime role cannot create or drop tables in the public schema."""
    app_uri = (
        f"postgresql+psycopg2://smartdist_app:smartdist_app_secure_pass@"
        f"{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )
    engine = create_engine(app_uri)
    with engine.connect() as conn:
        with pytest.raises(ProgrammingError) as exc_info:
            conn.execute(text("CREATE TABLE test_unauthorized_tbl (id serial primary key)"))
        assert "permission denied" in str(exc_info.value).lower()
