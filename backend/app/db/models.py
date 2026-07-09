from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.core.time import utc_now


class ServiceRequest(Base):
    __tablename__ = "service_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    unique_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), index=True)
    closed_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    agency: Mapped[str | None] = mapped_column(String(64), index=True)
    agency_name: Mapped[str | None] = mapped_column(String(255))
    complaint_type: Mapped[str | None] = mapped_column(String(255), index=True)
    descriptor: Mapped[str | None] = mapped_column(String(255))
    location_type: Mapped[str | None] = mapped_column(String(255))
    incident_zip: Mapped[str | None] = mapped_column(String(32), index=True)
    borough: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[str | None] = mapped_column(String(64), index=True)
    resolution_description: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    raw_payload: Mapped[dict | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())


Index("ix_service_requests_borough_complaint", ServiceRequest.borough, ServiceRequest.complaint_type)
Index("ix_service_requests_created_status", ServiceRequest.created_date, ServiceRequest.status)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source: Mapped[str] = mapped_column(String(128), default="nyc_311")
    requested_limit: Mapped[int] = mapped_column(Integer)
    fetched_count: Mapped[int] = mapped_column(Integer, default=0)
    inserted_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(64), default="success")
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))


class PolicyDocument(Base):
    __tablename__ = "policy_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), unique=True)
    source_path: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now)

    chunks: Mapped[list["PolicyChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class PolicyChunk(Base):
    __tablename__ = "policy_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("policy_documents.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    heading: Mapped[str | None] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    parent_heading: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chunk_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    sparse_terms: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    document: Mapped[PolicyDocument] = relationship(back_populates="chunks")
    embedding: Mapped["PolicyChunkEmbedding"] = relationship(
        back_populates="chunk",
        cascade="all, delete-orphan",
        uselist=False,
    )


class PolicyChunkEmbedding(Base):
    __tablename__ = "policy_chunk_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chunk_id: Mapped[int] = mapped_column(ForeignKey("policy_chunks.id", ondelete="CASCADE"), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    dimensions: Mapped[int] = mapped_column(Integer)
    vector: Mapped[list[float]] = mapped_column(JSON)

    chunk: Mapped[PolicyChunk] = relationship(back_populates="embedding")


class RagIndexJob(Base):
    __tablename__ = "rag_index_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    status: Mapped[str] = mapped_column(String(64), default="queued", index=True)
    include_remote: Mapped[bool] = mapped_column(Boolean, default=True)
    max_311_articles: Mapped[int | None] = mapped_column(Integer, nullable=True)
    documents_indexed: Mapped[int] = mapped_column(Integer, default=0)
    chunks_indexed: Mapped[int] = mapped_column(Integer, default=0)
    local_sources_indexed: Mapped[int] = mapped_column(Integer, default=0)
    remote_sources_indexed: Mapped[int] = mapped_column(Integer, default=0)
    embedding_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    warnings: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, onupdate=utc_now)


class AgentTrace(Base):
    __tablename__ = "agent_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_query: Mapped[str] = mapped_column(Text)
    route: Mapped[str] = mapped_column(String(64), index=True)
    selected_tool: Mapped[str] = mapped_column(String(128))
    tool_input: Mapped[dict | None] = mapped_column(JSON)
    tool_output: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(64), index=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=utc_now, index=True)
