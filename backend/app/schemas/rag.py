from pydantic import BaseModel, Field


class ReindexResponse(BaseModel):
    documents_indexed: int
    chunks_indexed: int


class RAGAskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    top_k: int = Field(default=4, ge=1, le=10)


class Citation(BaseModel):
    document_title: str
    chunk_id: int
    heading: str | None = None
    snippet: str
    score: float


class RAGAskResponse(BaseModel):
    question: str
    answer: str
    citations: list[Citation]
    confidence: float
    refused: bool
    trace_id: int | None = None
