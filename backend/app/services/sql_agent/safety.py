import re

try:
    import sqlglot
    from sqlglot import exp
except Exception:  # pragma: no cover - fallback used only if optional parser is unavailable
    sqlglot = None
    exp = None


FORBIDDEN_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REPLACE|MERGE|CALL|EXEC|GRANT|REVOKE|VACUUM|PRAGMA)\b",
    re.IGNORECASE,
)


class SQLSafetyError(ValueError):
    pass


def strip_sql_comments(sql: str) -> str:
    without_block_comments = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    without_line_comments = re.sub(r"--[^\n\r]*", " ", without_block_comments)
    return without_line_comments


def _has_multiple_statements(sql: str) -> bool:
    stripped = sql.strip()
    if ";" not in stripped:
        return False
    return stripped.rstrip().rstrip(";").find(";") != -1


def assert_safe_select(sql: str) -> None:
    stripped = strip_sql_comments(sql).strip()
    if not stripped:
        raise SQLSafetyError("SQL is empty.")
    if _has_multiple_statements(stripped):
        raise SQLSafetyError("Multiple SQL statements are not allowed.")
    if FORBIDDEN_PATTERN.search(stripped):
        raise SQLSafetyError("Only read-only SELECT queries are allowed.")
    if not stripped.lower().startswith("select"):
        raise SQLSafetyError("Query must start with SELECT.")

    if sqlglot and exp:
        parsed = sqlglot.parse_one(stripped.rstrip(";"), read="sqlite")
        if not isinstance(parsed, exp.Select):
            raise SQLSafetyError("Only SELECT statements are allowed.")


def enforce_limit(sql: str, limit: int = 100) -> str:
    stripped = strip_sql_comments(sql).strip().rstrip(";")
    if re.search(r"\blimit\s+\d+\b", stripped, re.IGNORECASE):
        return stripped
    return f"{stripped} LIMIT {limit}"
