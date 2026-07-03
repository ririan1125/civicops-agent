from datetime import datetime

from pydantic import BaseModel


class TraceRecord(BaseModel):
    id: int
    user_query: str
    route: str
    selected_tool: str
    tool_input: dict | None
    tool_output: dict | None
    status: str
    latency_ms: int
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
