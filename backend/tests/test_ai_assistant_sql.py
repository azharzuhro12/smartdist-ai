"""
Tests for Safe Text-to-SQL Engine and SQL Security Validator.
"""

import pytest
from ai_assistant.sql_agent.sql_validator import SQLValidator, SQLValidationError
from ai_assistant.sql_agent.sql_executor import SafeSQLExecutor, SQLExecutionError
from ai_assistant.sql_agent.nl_to_sql import NLToSQLAgent
from backend.app.db.session import SessionLocal


def test_sql_validator_allows_valid_select():
    val = SQLValidator()
    q = "SELECT id, product_name FROM products WHERE is_active = true"
    sanitized = val.validate_and_sanitize(q)
    assert sanitized.startswith("SELECT id, product_name FROM products")
    assert "LIMIT 50" in sanitized


def test_sql_validator_enforces_max_limit():
    val = SQLValidator()
    q = "SELECT id, product_name FROM products LIMIT 500"
    sanitized = val.validate_and_sanitize(q)
    assert "LIMIT 100" in sanitized
    assert "500" not in sanitized


def test_sql_validator_blocks_dml_and_ddl():
    val = SQLValidator()
    attacks = [
        "DROP TABLE daily_sales",
        "DELETE FROM daily_sales WHERE id = 1",
        "INSERT INTO products (product_name) VALUES ('Hacked')",
        "UPDATE inventory SET stock_quantity = 0",
        "ALTER TABLE branches ADD COLUMN secret text",
        "TRUNCATE TABLE suppliers",
        "CREATE TABLE backdoor (id int)",
    ]
    for attack in attacks:
        with pytest.raises(SQLValidationError):
            val.validate_and_sanitize(attack)


def test_sql_validator_blocks_multi_statements():
    val = SQLValidator()
    q = "SELECT * FROM products; DROP TABLE daily_sales"
    with pytest.raises(SQLValidationError) as exc:
        val.validate_and_sanitize(q)
    assert "Multi-statement" in str(exc.value)


def test_sql_validator_blocks_comments():
    val = SQLValidator()
    with pytest.raises(SQLValidationError):
        val.validate_and_sanitize("SELECT * FROM products -- malicious bypass")
    with pytest.raises(SQLValidationError):
        val.validate_and_sanitize("SELECT * FROM products /* block comment */")


def test_sql_validator_blocks_system_schemas():
    val = SQLValidator()
    with pytest.raises(SQLValidationError):
        val.validate_and_sanitize("SELECT * FROM pg_catalog.pg_tables")
    with pytest.raises(SQLValidationError):
        val.validate_and_sanitize("SELECT * FROM information_schema.tables")


def test_sql_validator_blocks_unauthorized_tables():
    val = SQLValidator()
    with pytest.raises(SQLValidationError):
        val.validate_and_sanitize("SELECT * FROM users_passwords")


def test_safe_sql_executor_runs_and_returns_provenance():
    executor = SafeSQLExecutor()
    res = executor.execute_query("SELECT id, product_name FROM products LIMIT 3")
    assert res["success"] is True
    assert res["row_count"] <= 3
    assert len(res["rows"]) <= 3
    assert "provenance" in res
    assert res["execution_time_ms"] >= 0


def test_nl_to_sql_top_selling_products():
    agent = NLToSQLAgent()
    res = agent.query("What are the top 3 selling products by volume?")
    assert res["success"] is True
    assert res["row_count"] == 3
    assert res["provenance"].startswith("KAGGLE_PUBLIC")
    assert "total_quantity_sold" in res["columns"]


def test_nl_to_sql_branch_sales():
    agent = NLToSQLAgent()
    res = agent.query("Show sales by branch")
    assert res["success"] is True
    assert res["row_count"] > 0
    assert "branch_name" in res["columns"]


def test_sql_validator_blocks_system_functions():
    val = SQLValidator()
    system_func_attacks = [
        "SELECT version() FROM products",
        "SELECT current_user FROM products",
        "SELECT session_user FROM products",
        "SELECT current_database() FROM products",
        "SELECT current_schema() FROM products",
        "SELECT inet_server_addr() FROM products",
        "SELECT pg_backend_pid() FROM products",
        "SELECT pg_read_file('/etc/passwd') FROM products",
    ]
    for attack in system_func_attacks:
        with pytest.raises(SQLValidationError) as exc:
            val.validate_and_sanitize(attack)
        assert "Forbidden system function or metadata access detected" in str(exc.value)


def test_sql_validator_blocks_comma_joins():
    val = SQLValidator()
    comma_join_queries = [
        "SELECT * FROM daily_sales, branches WHERE daily_sales.branch_id = branches.id",
        "SELECT * FROM daily_sales, secret_passwords",
        "SELECT * FROM (SELECT * FROM daily_sales), products",
    ]
    for q in comma_join_queries:
        with pytest.raises(SQLValidationError) as exc:
            val.validate_and_sanitize(q)
        assert "Implicit comma joins" in str(exc.value)


def test_sql_validator_supports_and_scopes_ctes():
    val = SQLValidator()
    # Valid CTE accessing allowed table
    valid_cte = (
        "WITH branch_totals AS ("
        "  SELECT branch_id, SUM(quantity_sold) AS total_qty "
        "  FROM daily_sales "
        "  GROUP BY branch_id"
        ") "
        "SELECT * FROM branch_totals"
    )
    sanitized = val.validate_and_sanitize(valid_cte)
    assert "WITH branch_totals AS" in sanitized
    assert "LIMIT 50" in sanitized

    # CTE accessing unauthorized table must fail
    invalid_cte = (
        "WITH secret_data AS ("
        "  SELECT * FROM secret_passwords"
        ") "
        "SELECT * FROM secret_data"
    )
    with pytest.raises(SQLValidationError) as exc:
        val.validate_and_sanitize(invalid_cte)
    assert "Table 'secret_passwords' is not in the allowed tables list" in str(exc.value)


def test_sql_validator_multiple_and_recursive_ctes():
    val = SQLValidator()
    # Multiple valid CTEs joined via explicit ANSI JOIN
    multi_cte = (
        "WITH c1 AS (SELECT id, branch_id FROM daily_sales), "
        "c2 AS (SELECT id, branch_name FROM branches) "
        "SELECT c1.id, c2.branch_name FROM c1 JOIN c2 ON c1.branch_id = c2.id"
    )
    sanitized = val.validate_and_sanitize(multi_cte)
    assert "LIMIT 50" in sanitized

    # Multiple CTEs where second CTE queries an unauthorized table must fail
    multi_cte_bad = (
        "WITH c1 AS (SELECT id FROM daily_sales), "
        "c2 AS (SELECT id FROM secret_users) "
        "SELECT * FROM c1 JOIN c2 ON c1.id = c2.id"
    )
    with pytest.raises(SQLValidationError):
        val.validate_and_sanitize(multi_cte_bad)

    # Recursive CTE must be blocked to prevent infinite loop DoS
    recursive_cte = (
        "WITH RECURSIVE r AS ("
        "  SELECT id FROM products WHERE id = 1 "
        "  UNION ALL "
        "  SELECT p.id FROM products p JOIN r ON p.id = r.id + 1"
        ") SELECT * FROM r"
    )
    with pytest.raises(SQLValidationError) as exc:
        val.validate_and_sanitize(recursive_cte)
    assert "RECURSIVE" in str(exc.value)


def test_sql_validator_blocks_set_returning_and_pg_internal_functions():
    val = SQLValidator()
    attacks = [
        "SELECT generate_series(1, 100000) FROM products",
        "SELECT * FROM generate_series(1, 100)",
        "SELECT unnest(ARRAY[1,2,3]) FROM products",
        "SELECT * FROM json_each('{\"a\":1}')",
        "SELECT has_table_privilege('products', 'SELECT') FROM products",
        "SELECT pg_my_temp_schema() FROM products",
        "SELECT pg_conf_load_time() FROM products",
    ]
    for attack in attacks:
        with pytest.raises(SQLValidationError):
            val.validate_and_sanitize(attack)


def test_sql_validator_schema_qualified_and_union_subqueries():
    val = SQLValidator()
    # Allowed public schema and quoted identifier
    assert "LIMIT 50" in val.validate_and_sanitize("SELECT id FROM public.products")
    assert "LIMIT 50" in val.validate_and_sanitize('SELECT id FROM "products"')

    # Disallowed custom schema qualifier
    with pytest.raises(SQLValidationError) as exc:
        val.validate_and_sanitize("SELECT id FROM internal_schema.products")
    assert "Unauthorized schema qualifier" in str(exc.value)

    # Disallowed UNION and subquery table access
    with pytest.raises(SQLValidationError):
        val.validate_and_sanitize("SELECT id FROM products UNION SELECT id FROM secret_users")
    with pytest.raises(SQLValidationError):
        val.validate_and_sanitize("SELECT * FROM (SELECT * FROM secret_users) sub")
    with pytest.raises(SQLValidationError):
        val.validate_and_sanitize('SELECT * FROM "pg_catalog"."pg_tables"')


def test_safe_sql_executor_select_with_rows_live():
    executor = SafeSQLExecutor()
    res = executor.execute_query("SELECT id, product_name FROM products LIMIT 5")
    assert res["success"] is True
    assert res["columns"] == ["id", "product_name"]
    assert res["row_count"] > 0
    assert len(res["rows"]) == res["row_count"]
    for row in res["rows"]:
        assert "id" in row
        assert "product_name" in row


def test_safe_sql_executor_select_empty_result():
    executor = SafeSQLExecutor()
    res = executor.execute_query("SELECT id, product_name FROM products WHERE id = -999999")
    assert res["success"] is True
    assert res["columns"] == ["id", "product_name"]
    assert res["row_count"] == 0
    assert res["rows"] == []


def test_safe_sql_executor_resource_closed_handled_cleanly():
    """Statements without rows (raising ResourceClosedError) should produce empty columns/rows without failure."""
    from unittest.mock import MagicMock
    from sqlalchemy.exc import ResourceClosedError

    mock_db = MagicMock()
    mock_result = MagicMock()
    mock_result.keys.side_effect = ResourceClosedError("Result does not return rows.")
    mock_result.fetchall.side_effect = ResourceClosedError("Result does not return rows.")
    mock_db.execute.return_value = mock_result

    executor = SafeSQLExecutor()
    res = executor.execute_query("SELECT id FROM products", db=mock_db)
    assert res["success"] is True
    assert res["columns"] == []
    assert res["rows"] == []
    assert res["row_count"] == 0


def test_safe_sql_executor_database_error_propagates():
    """Operational/database errors must raise SQLExecutionError and not be swallowed."""
    from unittest.mock import MagicMock
    from sqlalchemy.exc import OperationalError

    mock_db = MagicMock()
    mock_db.execute.side_effect = OperationalError("connection lost", {}, Exception("DB down"))

    executor = SafeSQLExecutor()
    with pytest.raises(SQLExecutionError) as exc_info:
        executor.execute_query("SELECT id FROM products", db=mock_db)
    assert "Database execution failed" in str(exc_info.value)


def test_safe_sql_executor_mutations_blocked_before_db():
    """Mutations must be blocked at validation layer before any DB call."""
    executor = SafeSQLExecutor()
    for mutation in [
        "INSERT INTO products (product_name) VALUES ('x')",
        "UPDATE products SET is_active = false",
        "DELETE FROM products WHERE id = 1",
        "DROP TABLE products",
    ]:
        with pytest.raises(SQLValidationError):
            executor.execute_query(mutation)




