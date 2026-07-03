from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.agent import SQLResult
from app.services.sql_agent.safety import assert_safe_select, enforce_limit


def run_safe_select(db: Session, sql: str) -> SQLResult:
    assert_safe_select(sql)
    safe_sql = enforce_limit(sql)
    result = db.execute(text(safe_sql))
    rows = result.mappings().all()
    serialized = [dict(row) for row in rows]
    columns = list(result.keys())
    return SQLResult(columns=columns, rows=serialized, row_count=len(serialized))


def summarize_sql_result(question: str, sql: str, result: SQLResult) -> str:
    if result.row_count == 0:
        return "No matching rows were found for this question."
    if result.row_count == 1 and len(result.rows[0]) == 1:
        key, value = next(iter(result.rows[0].items()))
        return f"The answer to '{question}' is {value} based on `{key}`."

    first = result.rows[0]
    preview = ", ".join(f"{key}={value}" for key, value in list(first.items())[:3])
    return f"Returned {result.row_count} rows. The top row is: {preview}."
