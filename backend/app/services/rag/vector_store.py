from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import PolicyChunkEmbedding
from app.services.rag.embeddings import embedding_runtime_label


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(str(float(value)) for value in vector) + "]"


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

    embeddings = db.query(PolicyChunkEmbedding).all()
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
                "metadata": "{}",
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
