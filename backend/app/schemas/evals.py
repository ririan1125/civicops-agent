from pydantic import BaseModel


class EvalMetric(BaseModel):
    name: str
    passed: int | float
    total: int
    score: float


class EvalRunResponse(BaseModel):
    metrics: list[EvalMetric]
    failures: list[dict]


class RAGRetrievalCaseResult(BaseModel):
    name: str
    question: str
    expected: list[str]
    retrieved: list[str]
    hit_rank: int | None
    reciprocal_rank: float
    top_score: float | None = None


class RAGRetrievalEvalResponse(BaseModel):
    metrics: list[EvalMetric]
    cases: list[RAGRetrievalCaseResult]
    embedding_provider: str
    embedding_model: str


class EmbeddingBenchmarkVariant(BaseModel):
    provider: str
    model: str
    dimensions: int
    metrics: list[EvalMetric]
    cases: list[RAGRetrievalCaseResult]


class EmbeddingBenchmarkResponse(BaseModel):
    corpus_chunks: int
    cases_count: int
    best_variant: str | None = None
    variants: list[EmbeddingBenchmarkVariant]
    notes: list[str] = []
