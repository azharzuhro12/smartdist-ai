"""
PostgreSQL least-privilege tests.
Verifies that SQL Assistant executor operates within read-only boundaries,
cannot execute DDL/DML, and cannot query authentication/user tables.
"""

import pytest
from ai_assistant.sql_agent.sql_validator import SQLValidator, SQLValidationError
from ai_assistant.sql_agent.sql_executor import SafeSQLExecutor, SQLExecutionError


@pytest.fixture
def validator():
    return SQLValidator()


@pytest.fixture
def executor():
    return SafeSQLExecutor()


def test_sql_validator_blocks_users_table(validator):
    """Validator must strictly reject queries targeting the users table."""
    with pytest.raises(SQLValidationError) as exc:
        validator.validate_and_sanitize("SELECT * FROM users")
    assert "users" in str(exc.value).lower() or "not allowed" in str(exc.value).lower()


def test_sql_validator_blocks_credentials_query(validator):
    """Validator must reject queries targeting password hashes or audit tables."""
    with pytest.raises(SQLValidationError):
        validator.validate_and_sanitize("SELECT username, hashed_password FROM users")

    with pytest.raises(SQLValidationError):
        validator.validate_and_sanitize("SELECT * FROM alembic_version")


def test_executor_blocks_mutation(executor):
    """Executor must reject mutation commands (INSERT, UPDATE, DELETE)."""
    with pytest.raises(SQLValidationError):
        executor.execute_query("DELETE FROM daily_sales WHERE id = 1")

    with pytest.raises(SQLValidationError):
        executor.execute_query("INSERT INTO products (product_code, product_name) VALUES ('P1', 'Test')")

    with pytest.raises(SQLValidationError):
        executor.execute_query("UPDATE branches SET is_active = false WHERE id = 1")


def test_executor_blocks_ddl(executor):
    """Executor must reject schema modification commands (DROP, ALTER, CREATE)."""
    with pytest.raises(SQLValidationError):
        executor.execute_query("DROP TABLE products")

    with pytest.raises(SQLValidationError):
        executor.execute_query("ALTER TABLE users ADD COLUMN hacked text")


def test_executor_permits_safe_business_queries(executor, db_session):
    """Executor allows safe SELECT queries on authorized business tables."""
    res = executor.execute_query("SELECT id, product_code, product_name FROM products LIMIT 5", db=db_session)
    assert res["success"] is True
    assert "columns" in res
    assert "rows" in res
    assert res["provenance"] is not None

