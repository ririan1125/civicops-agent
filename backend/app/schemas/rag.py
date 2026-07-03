from pydantic import BaseModel, Field


class ReindexResponse(BaseModel):
    documents_indexed: int
    chunks_indexed: int
    local_sources_indexed: int = 0
    remote_sources_indexed: int = 0
    embedding_provider: str | None = None
    embedding_model: str | None = None
    warnings: list[str] = []


class ReindexRequest(BaseModel):
    include_remote: bool = True
    max_311_articles: int | None = Field(default=None, ge=0, le=300)


class RAGSourceInfo(BaseModel):
    title: str
    url: str
    source_type: str
    required: bool
    notes: str | None = None


class RAGAskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    top_k: int = Field(default=4, ge=1, le=10)


class Citation(BaseModel):
    document_title: str
    chunk_id: int
    heading: str | None = None
    source_url: str | None = None
    snippet: str
    score: float
    lexical_score: float | None = None
    vector_score: float | None = None
    matched_terms: list[str] = []


class RAGAskResponse(BaseModel):
    question: str
    answer: str
    citations: list[Citation]
    confidence: float
    refused: bool
    retrieval_method: str = "hybrid_bm25_vector_rerank"
    generation_provider: str = "mock"
    trace_id: int | None = None
