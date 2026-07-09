from datetime import datetime

from pydantic import BaseModel, Field


class ReindexResponse(BaseModel):
    documents_indexed: int
    chunks_indexed: int
    local_sources_indexed: int = 0
    remote_sources_indexed: int = 0
    embedding_provider: str | None = None
    embedding_model: str | None = None
    warnings: list[str] = []


class VectorStoreInitResponse(BaseModel):
    status: str
    backend: str
    pgvector_enabled: bool
    dimensions: int | None = None
    index_type: str | None = None
    rows_backfilled: int = 0
    message: str


class VectorPartitionStats(BaseModel):
    name: str
    chunk_count: int


class VectorStoreSchemaResponse(BaseModel):
    status: str
    backend: str
    pgvector_enabled: bool
    collection_name: str
    physical_table: str
    embedding_provider: str
    embedding_model: str
    dimensions: int | None = None
    index_type: str | None = None
    total_vectors: int
    logical_partitions: list[VectorPartitionStats] = []
    message: str | None = None


class ReindexRequest(BaseModel):
    include_remote: bool = True
    max_311_articles: int | None = Field(default=None, ge=0, le=300)


class ReindexJobResponse(BaseModel):
    id: int
    status: str
    include_remote: bool
    max_311_articles: int | None = None
    documents_indexed: int = 0
    chunks_indexed: int = 0
    local_sources_indexed: int = 0
    remote_sources_indexed: int = 0
    embedding_provider: str | None = None
    embedding_model: str | None = None
    warnings: list[str] = Field(default_factory=list)
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    updated_at: datetime


class PrecomputedChunk(BaseModel):
    heading: str | None = None
    parent_heading: str | None = None
    section_path: list[str] = Field(default_factory=list)
    content: str = Field(min_length=1)
    token_count: int = Field(default=0, ge=0)
    sparse_terms: dict[str, int] = Field(default_factory=dict)
    embedding: list[float]


class PrecomputedDocument(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    source_path: str | None = None
    source_type: str = "unknown"
    chunks: list[PrecomputedChunk]


class PrecomputedReindexRequest(BaseModel):
    embedding_provider: str = Field(min_length=1, max_length=64)
    embedding_model: str = Field(min_length=1, max_length=128)
    dimensions: int = Field(gt=0, le=4096)
    documents: list[PrecomputedDocument]
    warnings: list[str] = Field(default_factory=list)


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
    vector_backend: str | None = None
    graph_entities: list[str] = []
    matched_terms: list[str] = []
    reranker_score: float | None = None
    sparse_score: float | None = None
    source_partition: str | None = None


class RAGAskResponse(BaseModel):
    question: str
    answer: str
    citations: list[Citation]
    confidence: float
    refused: bool
    retrieval_method: str = "hybrid_bm25_json_vector_graph_mmr"
    generation_provider: str = "mock"
    trace_id: int | None = None
    query_plan: dict | None = None


class KnowledgeGraphNode(BaseModel):
    id: str
    label: str
    type: str
    mentions: int
    example_documents: list[str] = []


class KnowledgeGraphEdge(BaseModel):
    source: str
    target: str
    weight: int


class KnowledgeGraphResponse(BaseModel):
    nodes: list[KnowledgeGraphNode]
    edges: list[KnowledgeGraphEdge]
    chunks_scanned: int
