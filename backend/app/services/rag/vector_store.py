import json
import re

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload

from app.db.models import PolicyChunkEmbedding
from app.services.rag.embeddings import embedding_runtime_label


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(str(float(value)) for value in vector) + "]"


def _is_postgresql(db: Session) -> bool:
    return bool(db.bind is not None and db.bind.dialect.name == "postgresql")


def _pgvector_table_exists(db: Session) -> bool:
    if not _is_postgresql(db):
        return False
    result = db.execute(text("SELECT to_regclass('public.rag_vector_embeddings')")).scalar()
    return result is not None


def _existing_pgvector_dimensions(db: Session) -> int | None:
    if not _pgvector_table_exists(db):
        return None
    typmod = db.execute(
        text(
            """
            SELECT format_type(attribute.atttypid, attribute.atttypmod)
            FROM pg_attribute attribute
            WHERE attribute.attrelid = 'public.rag_vector_embeddings'::regclass
              AND attribute.attname = 'embedding'
              AND NOT attribute.attisdropped
            """
        )
    ).scalar()
    if not typmod:
        return None
    match = re.search(r"vector\((\d+)\)", str(typmod))
    return int(match.group(1)) if match else None


def _source_partition(source_path: str | None, title: str | None = None) -> str:
    source = (source_path or "").lower()
    title_text = (title or "").lower()
    if "portal.311.nyc.gov" in source:
        return "official_nyc311_articles"
    if "data.cityofnewyork.us" in source or "opendata" in source or "cityofnewyork.github.io" in source:
        return "official_nyc_open_data"
    if "sample_data" in source and "rag_assets" in source:
        return "local_multimodal_assets"
    if "sample_data" in source and "policies" in source:
        return "local_policy_docs"
    if "readme" in title_text or "architecture" in title_text or "overview" in title_text:
        return "project_architecture_docs"
    return "other"


def _embedding_metadata(embedding: PolicyChunkEmbedding) -> str:
    chunk = embedding.chunk
    document = chunk.document if chunk is not None else None
    source_path = document.source_path if document is not None else None
    title = document.title if document is not None else None
    return json.dumps(
        {
            "document_title": title,
            "source_path": source_path,
            "heading": chunk.heading if chunk is not None else None,
            "chunk_index": chunk.chunk_index if chunk is not None else None,
            "logical_partition": _source_partition(source_path, title),
        },
        ensure_ascii=False,
    )


def initialize_pgvector_store(db: Session) -> dict:
    dialect = db.bind.dialect.name if db.bind is not None else "unknown"
    if dialect != "postgresql":
        return {
            "status": "unsupported",
            "backend": dialect,
            "pgvector_enabled": False,
            "dimensions": None,
            "index_type": None,
            "rows_backfilled": 0,
            "message": "pgvector initialization is only available on PostgreSQL.",
        }

    first_embedding = db.query(PolicyChunkEmbedding).first()
    if not first_embedding:
        return {
            "status": "empty",
            "backend": dialect,
            "pgvector_enabled": False,
            "dimensions": None,
            "index_type": None,
            "rows_backfilled": 0,
            "message": "No chunk embeddings exist yet. Run /rag/reindex first.",
        }

    dimensions = int(first_embedding.dimensions)
    provider, model = embedding_runtime_label()
    db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    existing_dimensions = _existing_pgvector_dimensions(db)
    if existing_dimensions is not None and existing_dimensions != dimensions:
        db.execute(text("DROP TABLE IF EXISTS rag_vector_embeddings"))
    db.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS rag_vector_embeddings (
                id BIGSERIAL PRIMARY KEY,
                chunk_id INTEGER UNIQUE NOT NULL REFERENCES policy_chunks(id) ON DELETE CASCADE,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                dimensions INTEGER NOT NULL,
                embedding vector({dimensions}) NOT NULL,
                metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )
    db.execute(text("CREATE INDEX IF NOT EXISTS idx_rag_vector_embeddings_chunk_id ON rag_vector_embeddings (chunk_id)"))
    db.execute(text("DELETE FROM rag_vector_embeddings WHERE chunk_id NOT IN (SELECT id FROM policy_chunks)"))

    embeddings = (
        db.query(PolicyChunkEmbedding)
        .options(joinedload(PolicyChunkEmbedding.chunk).joinedload(PolicyChunk.document))
        .all()
    )
    rows_backfilled = 0
    for embedding in embeddings:
        if embedding.dimensions != dimensions:
            continue
        db.execute(
            text(
                """
                INSERT INTO rag_vector_embeddings (chunk_id, provider, model, dimensions, embedding, metadata)
                VALUES (:chunk_id, :provider, :model, :dimensions, CAST(:embedding AS vector), CAST(:metadata AS jsonb))
                ON CONFLICT (chunk_id) DO UPDATE SET
                    provider = EXCLUDED.provider,
                    model = EXCLUDED.model,
                    dimensions = EXCLUDED.dimensions,
                    embedding = EXCLUDED.embedding,
                    metadata = EXCLUDED.metadata
                """
            ),
            {
                "chunk_id": embedding.chunk_id,
                "provider": embedding.provider,
                "model": embedding.model,
                "dimensions": embedding.dimensions,
                "embedding": _vector_literal(embedding.vector),
                "metadata": _embedding_metadata(embedding),
            },
        )
        rows_backfilled += 1

    db.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_rag_vector_embeddings_hnsw_cosine
            ON rag_vector_embeddings
            USING hnsw (embedding vector_cosine_ops)
            """
        )
    )
    db.commit()
    return {
        "status": "ready",
        "backend": dialect,
        "pgvector_enabled": True,
        "dimensions": dimensions,
        "index_type": "hnsw_vector_cosine_ops",
        "rows_backfilled": rows_backfilled,
        "message": f"pgvector store initialized for {provider}/{model}.",
    }


def sync_pgvector_store_if_available(db: Session) -> dict | None:
    if not _is_postgresql(db):
        return None
    try:
        if not _pgvector_table_exists(db):
            return None
        return initialize_pgvector_store(db)
    except SQLAlchemyError:
        db.rollback()
        return None


def search_pgvector(db: Session, query_embedding: list[float], limit: int = 80) -> dict[int, float]:
    if not query_embedding or not _is_postgresql(db):
        return {}
    provider, model = embedding_runtime_label()
    try:
        if not _pgvector_table_exists(db):
            return {}
        rows = db.execute(
            text(
                """
                SELECT chunk_id, 1 - (embedding <=> CAST(:query_embedding AS vector)) AS cosine_score
                FROM rag_vector_embeddings
                WHERE dimensions = :dimensions
                  AND provider = :provider
                  AND model = :model
                ORDER BY embedding <=> CAST(:query_embedding AS vector)
                LIMIT :limit
                """
            ),
            {
                "query_embedding": _vector_literal(query_embedding),
                "dimensions": len(query_embedding),
                "provider": provider,
                "model": model,
                "limit": max(1, limit),
            },
        ).mappings()
        scores: dict[int, float] = {}
        for row in rows:
            raw_score = float(row["cosine_score"])
            scores[int(row["chunk_id"])] = round(max(0.0, min(1.0, raw_score)), 4)
        return scores
    except SQLAlchemyError:
        db.rollback()
        return {}


def describe_vector_store(db: Session) -> dict:
    dialect = db.bind.dialect.name if db.bind is not None else "unknown"
    provider, model = embedding_runtime_label()
    if dialect != "postgresql":
        return {
            "status": "unsupported",
            "backend": dialect,
            "pgvector_enabled": False,
            "collection_name": "policy_documents",
            "physical_table": "policy_chunk_embeddings",
            "embedding_provider": provider,
            "embedding_model": model,
            "dimensions": None,
            "index_type": "application_side_cosine",
            "total_vectors": db.query(PolicyChunkEmbedding).count(),
            "logical_partitions": [],
        }

    try:
        if not _pgvector_table_exists(db):
            return {
                "status": "not_initialized",
                "backend": dialect,
                "pgvector_enabled": False,
                "collection_name": "policy_documents",
                "physical_table": "rag_vector_embeddings",
                "embedding_provider": provider,
                "embedding_model": model,
                "dimensions": None,
                "index_type": None,
                "total_vectors": 0,
                "logical_partitions": [],
            }

        total_vectors = int(db.execute(text("SELECT COUNT(*) FROM rag_vector_embeddings")).scalar() or 0)
        dimensions = db.execute(text("SELECT MAX(dimensions) FROM rag_vector_embeddings")).scalar()
        indexed_runtime = db.execute(
            text(
                """
                SELECT provider, model, COUNT(*) AS row_count
                FROM rag_vector_embeddings
                GROUP BY provider, model
                ORDER BY row_count DESC
                LIMIT 1
                """
            )
        ).mappings().first()
        indexed_provider = str(indexed_runtime["provider"]) if indexed_runtime else provider
        indexed_model = str(indexed_runtime["model"]) if indexed_runtime else model
        partition_rows = db.execute(
            text(
                """
                SELECT
                    CASE
                        WHEN d.source_path ILIKE 'https://portal.311.nyc.gov/%' THEN 'official_nyc311_articles'
                        WHEN d.source_path ILIKE '%data.cityofnewyork.us%' THEN 'official_nyc_open_data'
                        WHEN d.source_path ILIKE '%opendata%' THEN 'official_nyc_open_data'
                        WHEN d.source_path ILIKE '%cityofnewyork.github.io%' THEN 'official_nyc_open_data'
                        WHEN d.source_path ILIKE '%sample_data%rag_assets%' THEN 'local_multimodal_assets'
                        WHEN d.source_path ILIKE '%sample_data%policies%' THEN 'local_policy_docs'
                        WHEN d.title ILIKE '%readme%' THEN 'project_architecture_docs'
                        WHEN d.title ILIKE '%architecture%' THEN 'project_architecture_docs'
                        ELSE 'other'
                    END AS partition_name,
                    COUNT(*) AS chunk_count
                FROM rag_vector_embeddings v
                JOIN policy_chunks c ON c.id = v.chunk_id
                JOIN policy_documents d ON d.id = c.document_id
                GROUP BY partition_name
                ORDER BY chunk_count DESC
                """
            )
        ).mappings()
        partitions = [
            {"name": str(row["partition_name"]), "chunk_count": int(row["chunk_count"])}
            for row in partition_rows
        ]
        return {
            "status": "ready",
            "backend": dialect,
            "pgvector_enabled": True,
            "collection_name": "policy_documents",
            "physical_table": "rag_vector_embeddings",
            "embedding_provider": indexed_provider,
            "embedding_model": indexed_model,
            "dimensions": int(dimensions) if dimensions is not None else None,
            "index_type": "hnsw_vector_cosine_ops",
            "total_vectors": total_vectors,
            "logical_partitions": partitions,
            "message": (
                "Indexed embeddings do not match the current runtime model. Run /rag/reindex and /rag/vector-store/init."
                if (indexed_provider, indexed_model) != (provider, model)
                else None
            ),
        }
    except SQLAlchemyError as exc:
        db.rollback()
        return {
            "status": "error",
            "backend": dialect,
            "pgvector_enabled": False,
            "collection_name": "policy_documents",
            "physical_table": "rag_vector_embeddings",
            "embedding_provider": provider,
            "embedding_model": model,
            "dimensions": None,
            "index_type": None,
            "total_vectors": 0,
            "logical_partitions": [],
            "message": str(exc),
        }
