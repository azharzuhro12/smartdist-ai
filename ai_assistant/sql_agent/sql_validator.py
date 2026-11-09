"""
Hardened regular-expression and keyword security gateway for Safe Text-to-SQL execution in SmartDist AI.
Guarantees SELECT-only queries, table allowlisting, injection prevention, row limits, and blocks access
to PostgreSQL system functions, set-returning functions, metadata catalogs, recursive CTEs, and implicit comma joins.

Note on Architecture, Scope & Known Limitations:
This validator utilizes strict regular-expression, keyword boundary, and structural token parsing rather than
a full dialect-specific Abstract Syntax Tree (AST) compiler (such as sqlglot or pglast). It is specifically
designed to enforce safety in the SmartDist AI analytical environment on internal ALLOWED_TABLES.
Known limitations of regex/token-based validation:
1. It does not build a full semantic parse tree of arbitrary nested SQL expressions or complex window frames.
2. It conservatively blocks entire categories of keywords (e.g. RECURSIVE, SHOW, SET) and any `pg_*()` function call.
3. Defense-in-depth is therefore enforced at the database execution boundary via PostgreSQL `SET LOCAL transaction_read_only = on`
   and `SET LOCAL statement_timeout = '5000ms'`.
"""

import re
from typing import Set, Tuple, Optional
from ai_assistant.sql_agent.schema_context import ALLOWED_TABLES, ALLOWED_COLUMNS


class SQLValidationError(Exception):
    """Raised when an SQL query fails safety validation."""
    pass


# Forbidden SQL commands, mutation keywords, and recursive CTE modifiers
DISALLOWED_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "REPLACE", "GRANT", "REVOKE", "EXEC", "EXECUTE",
    "CALL", "COPY", "VACUUM", "REINDEX", "EXPLAIN", "PREPARE",
    "DEALLOCATE", "DECLARE", "LOCK", "SET", "RESET", "SHOW",
    "INTO", "OUTFILE", "DUMPFILE", "PG_SLEEP", "DBLINK",
    "RECURSIVE",
}

# Forbidden system catalog and schema identifiers
DISALLOWED_SCHEMAS = {
    "information_schema", "pg_catalog", "pg_temp", "pg_toast",
    "sqlite_master", "mysql", "performance_schema", "sys",
}

# Forbidden PostgreSQL system metadata, privilege inspection, and set-returning functions
DISALLOWED_FUNCTIONS = {
    "VERSION",
    "CURRENT_USER",
    "SESSION_USER",
    "SYSTEM_USER",
    "USER",
    "CURRENT_ROLE",
    "CURRENT_DATABASE",
    "CURRENT_CATALOG",
    "CURRENT_SCHEMA",
    "CURRENT_SCHEMAS",
    "CURRENT_SETTING",
    "CURRENT_QUERY",
    "INET_SERVER_ADDR",
    "INET_SERVER_PORT",
    "INET_CLIENT_ADDR",
    "INET_CLIENT_PORT",
    "PG_BACKEND_PID",
    "PG_STAT_FILE",
    "PG_READ_FILE",
    "PG_READ_BINARY_FILE",
    "PG_LS_DIR",
    "PG_SLEEP",
    "PG_TERMINATE_BACKEND",
    "PG_CANCEL_BACKEND",
    "PG_MY_TEMP_SCHEMA",
    "PG_CONF_LOAD_TIME",
    "PG_POSTMASTER_START_TIME",
    "PG_IS_IN_RECOVERY",
    "HAS_TABLE_PRIVILEGE",
    "HAS_SCHEMA_PRIVILEGE",
    "HAS_DATABASE_PRIVILEGE",
    "HAS_COLUMN_PRIVILEGE",
    "DBLINK",
    "DBLINK_EXEC",
    "TXID_CURRENT",
    "GENERATE_SERIES",
    "UNNEST",
    "JSON_EACH",
    "JSONB_EACH",
    "JSON_TO_RECORDSET",
    "JSONB_TO_RECORDSET",
    "REGEXP_SPLIT_TO_TABLE",
    "XPATH",
}

MAX_ALLOWED_LIMIT = 100
DEFAULT_LIMIT = 50

# SQL clause boundary pattern denoting the end of a FROM clause
END_OF_FROM_PATTERN = (
    r"(?:\bWHERE\b|\bGROUP\s+BY\b|\bHAVING\b|\bORDER\s+BY\b|"
    r"\bLIMIT\b|\bOFFSET\b|\bWINDOW\b|\bUNION\b|\bINTERSECT\b|\bEXCEPT\b|;|\Z)"
)


class SQLValidator:
    """Validates and sanitizes SQL queries before execution using hardened pattern checks."""

    def __init__(self, allowed_tables: Optional[Set[str]] = None, max_limit: int = MAX_ALLOWED_LIMIT):
        self.allowed_tables = allowed_tables or ALLOWED_TABLES
        self.max_limit = max_limit

    def validate_and_sanitize(self, sql: str) -> str:
        """
        Validates an SQL query against strict security rules and returns the sanitized,
        limit-enforced SQL query.
        
        Raises SQLValidationError if query violates safety constraints.
        """
        if not sql or not isinstance(sql, str):
            raise SQLValidationError("SQL query must be a non-empty string.")

        clean_sql = sql.strip()

        # 1. Strip trailing semicolons; reject internal semicolons (prevent multi-statement execution)
        if clean_sql.endswith(";"):
            clean_sql = clean_sql[:-1].strip()

        if ";" in clean_sql:
            raise SQLValidationError("Multi-statement execution (semicolon chaining) is strictly prohibited.")

        # 2. Reject comment-based SQL injection patterns (-- or /* */)
        if "--" in clean_sql or "/*" in clean_sql or "*/" in clean_sql:
            raise SQLValidationError("SQL comments (-- or /* */) are not permitted.")

        # 3. Check for disallowed keywords using word boundary regex
        for keyword in DISALLOWED_KEYWORDS:
            pattern = rf"\b{keyword}\b"
            if re.search(pattern, clean_sql, re.IGNORECASE):
                # Exception: INTO is only disallowed when modifying (SELECT ... INTO or INSERT INTO)
                if keyword == "INTO" and not re.search(r"\bSELECT\b.*\bINTO\b", clean_sql, re.IGNORECASE):
                    continue
                raise SQLValidationError(f"Forbidden SQL keyword detected: '{keyword}'. Only non-recursive SELECT queries are permitted.")

        # 4. Check for disallowed system functions, set-returning functions, and any pg_*() function
        for func in DISALLOWED_FUNCTIONS:
            pattern = rf"\b{func}\b"
            if re.search(pattern, clean_sql, re.IGNORECASE):
                raise SQLValidationError(
                    f"Forbidden system function or metadata access detected: '{func}'. "
                    "Access to database environment, set-returning generators, and system metadata is strictly prohibited."
                )

        pg_func_match = re.search(r"\b(pg_[a-z0-9_]+)\s*\(", clean_sql, re.IGNORECASE)
        if pg_func_match:
            raise SQLValidationError(
                f"Forbidden PostgreSQL internal function detected: '{pg_func_match.group(1)}'. "
                "Access to pg_* system functions is strictly prohibited."
            )

        # 5. Must start with SELECT or WITH (for CTE queries)
        first_token_match = re.match(r"^\s*([a-zA-Z]+)", clean_sql)
        if not first_token_match:
            raise SQLValidationError("Could not parse leading SQL token.")
        first_token = first_token_match.group(1).upper()
        if first_token not in {"SELECT", "WITH"}:
            raise SQLValidationError(f"Query must begin with SELECT or WITH, got '{first_token}'.")

        # 6. Check for disallowed system schemas
        for sys_schema in DISALLOWED_SCHEMAS:
            if re.search(rf"\b{sys_schema}\b", clean_sql, re.IGNORECASE):
                raise SQLValidationError(f"Access to system schema or table '{sys_schema}' is strictly prohibited.")

        # 7. Disallow implicit comma joins (FROM a, b) to prevent bypasses and enforce explicit ANSI JOINs
        self._check_for_comma_joins(clean_sql)

        # 8. Extract CTE aliases defined in query (e.g. WITH my_cte AS (...))
        cte_aliases = self._extract_cte_aliases(clean_sql)

        # 9. Extract tables referenced in FROM and JOIN clauses and verify allowlist & schema qualifiers
        referenced_tables = self._extract_tables(clean_sql)
        if not referenced_tables:
            raise SQLValidationError("No valid source table identified in query.")

        effective_allowed = self.allowed_tables | cte_aliases
        physical_tables_referenced = set()

        for tbl in referenced_tables:
            parts = [p.strip('"').strip("'").lower() for p in tbl.split(".") if p.strip()]
            if len(parts) > 2:
                raise SQLValidationError(f"Invalid table identifier format: '{tbl}'.")
            if len(parts) == 2 and parts[0] != "public":
                raise SQLValidationError(
                    f"Unauthorized schema qualifier '{parts[0]}'. Only the 'public' schema is permitted."
                )
            bare_tbl = parts[-1]
            if bare_tbl not in effective_allowed:
                raise SQLValidationError(
                    f"Table '{bare_tbl}' is not in the allowed tables list: {sorted(list(self.allowed_tables))}"
                )
            if bare_tbl in self.allowed_tables:
                physical_tables_referenced.add(bare_tbl)

        if not physical_tables_referenced:
            raise SQLValidationError("Query must reference at least one allowed physical table.")

        # 10. Check and enforce LIMIT
        sanitized_sql = self._enforce_limit(clean_sql)

        return sanitized_sql

    def _check_for_comma_joins(self, sql: str) -> None:
        """Detect and block comma-separated tables in FROM clauses while allowing multi-CTE definitions."""
        from_matches = re.finditer(rf"\bFROM\s+(.+?){END_OF_FROM_PATTERN}", sql, re.IGNORECASE | re.DOTALL)
        for m in from_matches:
            clause = m.group(1).strip()
            paren_depth = 0
            for ch in clause:
                if ch == "(":
                    paren_depth += 1
                elif ch == ")":
                    if paren_depth == 0:
                        # The enclosing subquery or CTE containing this FROM clause has closed
                        break
                    paren_depth -= 1
                elif ch == "," and paren_depth == 0:
                    raise SQLValidationError(
                        "Implicit comma joins ('FROM a, b') are strictly prohibited. "
                        "Use explicit ANSI JOIN syntax (e.g. INNER JOIN, LEFT JOIN)."
                    )

    def _extract_cte_aliases(self, sql: str) -> Set[str]:
        """Extract CTE alias names defined in WITH cte_name [(cols)] AS (...) blocks."""
        cte_aliases = set()
        matches = re.finditer(
            r"(?:WITH|,)\s*([a-zA-Z0-9_]+)(?:\s*\([^)]*\))?\s+AS\s*\(",
            sql,
            re.IGNORECASE,
        )
        for m in matches:
            cte_aliases.add(m.group(1).lower())
        return cte_aliases

    def _extract_tables(self, sql: str) -> Set[str]:
        """Extract table names from FROM and JOIN clauses."""
        tables = set()

        # Match table after FROM
        from_matches = re.finditer(
            r"\bFROM\s+([a-zA-Z0-9_\.\"]+)", sql, re.IGNORECASE
        )
        for m in from_matches:
            tbl = m.group(1).strip()
            # If it's a subquery starting with '(', ignore the '('
            if not tbl.startswith("("):
                tables.add(tbl.lower())

        # Match table after JOIN (INNER, LEFT, RIGHT, FULL, CROSS JOIN)
        join_matches = re.finditer(
            r"\bJOIN\s+([a-zA-Z0-9_\.\"]+)", sql, re.IGNORECASE
        )
        for m in join_matches:
            tbl = m.group(1).strip()
            if not tbl.startswith("("):
                tables.add(tbl.lower())

        return tables

    def _enforce_limit(self, sql: str) -> str:
        """Enforces a maximum LIMIT <= 100, or appends LIMIT 50 if missing."""
        limit_match = re.search(r"\bLIMIT\s+(\d+)", sql, re.IGNORECASE)

        if limit_match:
            current_limit = int(limit_match.group(1))
            if current_limit > self.max_limit:
                # Replace with max_limit
                sql = re.sub(
                    r"\bLIMIT\s+\d+",
                    f"LIMIT {self.max_limit}",
                    sql,
                    flags=re.IGNORECASE,
                )
            return sql
        else:
            # Append DEFAULT_LIMIT
            return f"{sql} LIMIT {DEFAULT_LIMIT}"
