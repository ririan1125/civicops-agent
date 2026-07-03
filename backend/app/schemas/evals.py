from pydantic import BaseModel


class EvalMetric(BaseModel):
    name: str
    passed: int
    total: int
    score: float


class EvalRunResponse(BaseModel):
    metrics: list[EvalMetric]
    failures: list[dict]
