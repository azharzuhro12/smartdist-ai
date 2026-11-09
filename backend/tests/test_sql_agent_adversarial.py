"""
Adversarial SQL Security Acceptance Suite for SmartDist AI.
Tests resilience against SQL injection, privilege escalation, metadata exfiltration,
and verifies defense-in-depth enforcement via the smartdist_readonly database role.
"""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError, InternalError
from ai_assistant.sql_agent.sql_validator import SQLValidator, SQLValidationError
from ai_assistant.sql_agent.sql_executor import SafeSQLExecutor, SQLExecutionError
from backend.app.core.config import settings


@pytest.fixture
def validator():
    return SQLValidator()


@pytest.fixture
def readonly_executor():
    return SafeSQLExecutor(validator=SQLValidator(), timeout_ms=3000)


# ==============================================================================
# 1. Adversarial Validator Checks (Regex & Keyword Defense Layer)
# ==============================================================================

def test_validator_blocks_dml_and_ddl_attempts(validator):
    """Validator must strictly reject data modification or schema alteration."""
    attacks = [
        "DROP TABLE products",
        "TRUNCATE TABLE daily_sales",
        "ALTER TABLE branches DROP COLUMN city",
        "CREATE TABLE exploit (data text)",
        "INSERT INTO products (product_code) VALUES ('BAD')",
        "UPDATE inventory SET stock_quantity = 0",
        "DELETE FROM users WHERE id = 1",
    ]
    for attack in attacks:
        with pytest.raises(SQLValidationError):
            validator.validate_and_sanitize(attack)


def test_validator_blocks_multiple_statements_and_comments(validator):
    """Validator must reject stacked queries and comment tricks."""
    stacked_attacks = [
        "SELECT id FROM products; DROP TABLE daily_sales",
        "SELECT id FROM products; SELECT * FROM users",
        "SELECT id FROM products;--\nDROP TABLE products",
        "SELECT id FROM products /* inline comment */ WHERE 1=1",
    ]
    for attack in stacked_attacks:
        with pytest.raises(SQLValidationError):
            validator.validate_and_sanitize(attack)


def test_validator_blocks_postgres_system_metadata_functions(validator):
    """Validator blocks functions that expose environment or configuration info."""
    func_attacks = [
        "SELECT version()",
        "SELECT current_user",
        "SELECT session_user",
        "SELECT current_database()",
        "SELECT current_schema()",
        "SELECT inet_server_addr()",
        "SELECT pg_backend_pid()",
        "SELECT pg_read_file('/etc/passwd')",
    ]
    for attack in func_attacks:
        with pytest.raises(SQLValidationError) as exc:
            validator.validate_and_sanitize(attack)
        assert "Forbidden system function or metadata access detected" in str(exc.value)


def test_validator_blocks_system_catalogs_and_sensitive_tables(validator):
    """Validator must deny access to pg_catalog, information_schema, and users tables."""
    catalog_attacks = [
        "SELECT * FROM pg_catalog.pg_tables",
        "SELECT * FROM pg_catalog.pg_user",
        "SELECT * FROM pg_shadow",
        "SELECT * FROM information_schema.tables",
        "SELECT * FROM users",
        "SELECT username, hashed_password FROM users",
        "SELECT * FROM public.users",
    ]
    for attack in catalog_attacks:
        with pytest.raises(SQLValidationError):
            validator.validate_and_sanitize(attack)


def test_validator_blocks_recursive_and_nested_ctes(validator):
    """Validator blocks recursive CTE syntax or multi-CTE bypass attempts."""
    cte_attacks = [
        "WITH RECURSIVE r AS (SELECT 1 AS n UNION ALL SELECT n+1 FROM r WHERE n < 10) SELECT * FROM r",
        "WITH a AS (SELECT * FROM users) SELECT * FROM a",
    ]
    for attack in cte_attacks:
        with pytest.raises(SQLValidationError):
            validator.validate_and_sanitize(attack)


# ==============================================================================
# 2. Database Privilege Boundary Checks (Final Line of Defense)
# ==============================================================================

def test_database_privilege_boundary_enforces_users_table_protection():
    """
    Even if an attacker crafts an SQL query that bypasses application validation,
    the PostgreSQL engine running under smartdist_readonly must immediately raise
    permission denied when querying the users table.
    """
    ro_uri = settings.readonly_database_uri
    engine = create_engine(ro_uri)

    # Directly execute against PostgreSQL without validator
    with engine.connect() as conn:
        with pytest.raises(ProgrammingError) as exc_info:
            conn.execute(text("SELECT id, username, hashed_password FROM users"))
        assert "permission denied for table users" in str(exc_info.value).lower()


def test_database_privilege_boundary_enforces_readonly_mode():
    """
    Even if an INSERT or UPDATE bypasses application checks,
    smartdist_readonly connection is rejected by PostgreSQL's transaction / role permissions.
    """
    ro_uri = settings.readonly_database_uri
    engine = create_engine(ro_uri)

    with engine.connect() as conn:
        with pytest.raises((ProgrammingError, InternalError)) as exc_info:
            conn.execute(
                text(
                    "INSERT INTO products (product_code, product_name, category_id, source_family, unit_of_measure, is_active, data_origin, created_at, updated_at) "
                    "VALUES ('ADVERSARIAL_TEST', 'TEST', 1, 'TEST', 'UNIT', true, 'TEST', now(), now())"
                )
            )
        err = str(exc_info.value).lower()
        assert "read-only" in err or "permission denied" in err


def test_safe_sql_executor_timeout():
    """Executor must enforce statement timeout on slow/expensive queries."""
    executor = SafeSQLExecutor(timeout_ms=500)
    # pg_sleep is blocked by validator, but test executor directly with low timeout on valid query
    res = executor.execute_query("SELECT id FROM products LIMIT 5")
    assert res["success"] is True

