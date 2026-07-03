import time
from collections.abc import Callable
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.db.models import AgentTrace


def record_trace(
    db: Session,
    *,
    user_query: str,
    route: str,
    selected_tool: str,
    tool_input: dict | None,
    tool_output: dict | None,
    status: str,
    latency_ms: int,
    error_message: str | None = None,
) -> AgentTrace:
    trace = AgentTrace(
        user_query=user_query,
        route=route,
        selected_tool=selected_tool,
        tool_input=jsonable_encoder(tool_input),
        tool_output=jsonable_encoder(tool_output),
        status=status,
        latency_ms=latency_ms,
        error_message=error_message,
    )
    db.add(trace)
    db.commit()
    db.refresh(trace)
    return trace


def timed_call(fn: Callable[[], Any]) -> tuple[Any, int]:
    start = time.perf_counter()
    result = fn()
    latency_ms = int((time.perf_counter() - start) * 1000)
    return result, latency_ms
