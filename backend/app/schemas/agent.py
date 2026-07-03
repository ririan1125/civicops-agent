from pydantic import BaseModel, Field


class SQLQuestionRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)


class SQLResult(BaseModel):
    columns: list[str]
    rows: list[dict]
    row_count: int


class SQLQuestionResponse(BaseModel):
    question: str
    generated_sql: str
    confidence: float
    assumptions: list[str]
    result: SQLResult
    answer: str
    trace_id: int | None = None


class AgentRouteRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)


class AgentRouteResponse(BaseModel):
    route: str
    reason: str
    response: dict
    selected_tool: str | None = None
    planner_provider: str = "heuristic"
    plan_steps: list[str] = []
    confidence: float | None = None
    trace_id: int | None = None
