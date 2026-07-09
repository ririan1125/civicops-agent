from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import PolicyChunk, PolicyChunkEmbedding, PolicyDocument
from app.services.rag.chunker import chunk_markdown
from app.services.rag.embeddings import embed_texts
from app.services.rag.source_loader import DocumentSource, load_document_sources, sample_policy_dir
from app.services.rag.vector_store import clear_pgvector_store_if_available, sync_pgvector_store_if_available


@dataclass
class IndexResult:
    documents_indexed: int
    chunks_indexed: int
    local_sources_indexed: int = 0
    remote_sources_indexed: int = 0
    warnings: list[str] | None = None

    def __iter__(self):
        yield self.documents_indexed
        yield self.chunks_indexed


def clear_policy_index(db: Session) -> None:
    db.query(PolicyChunkEmbedding).delete()
    db.query(PolicyChunk).delete()
    db.query(PolicyDocument).delete()
    db.commit()


def _unique_title(title: str, used_titles: set[str]) -> str:
    title = title[:240]
    if title not in used_titles:
        used_titles.add(title)
        return title
    suffix = 2
    while f"{title} ({suffix})" in used_titles:
        suffix += 1
    unique = f"{title} ({suffix})"
    used_titles.add(unique)
    return unique


def _truncate(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    return value[:max_length]


def _sources_from_directory(directory: Path) -> list[DocumentSource]:
    if not directory.exists():
        return []
    return [
        DocumentSource(
            title=path.stem.replace("_", " ").title(),
            source_path=str(path),
            content=path.read_text(encoding="utf-8"),
            source_type="local_markdown",
        )
        for path in sorted(directory.glob("*.md"))
    ]


def index_policy_documents(
    db: Session,
    directory: Path | None = None,
    *,
    include_remote: bool = False,
    max_311_articles: int | None = None,
) -> IndexResult:
    if directory is not None:
        sources = _sources_from_directory(directory)
        warnings: list[str] = []
    else:
        loaded = load_document_sources(include_remote=include_remote, max_311_articles=max_311_articles)
        sources = loaded.sources
        warnings = loaded.warnings

    if not sources:
        return IndexResult(documents_indexed=0, chunks_indexed=0, warnings=warnings)

    clear_pgvector_store_if_available(db)
    clear_policy_index(db)
    documents_indexed = 0
    chunks_indexed = 0
    local_sources_indexed = 0
    remote_sources_indexed = 0
    used_titles: set[str] = set()
    for source in sources:
        document = PolicyDocument(title=_unique_title(source.title, used_titles), source_path=source.source_path)
        db.add(document)
        db.flush()
        chunks = chunk_markdown(source.content)
        embedding_inputs = [f"{chunk.heading or ''}\n{chunk.content}" for chunk in chunks]
        embeddings = embed_texts(embedding_inputs) if embedding_inputs else None
        for index, chunk in enumerate(chunks):
            policy_chunk = PolicyChunk(
                document_id=document.id,
                chunk_index=index,
                heading=_truncate(chunk.heading, 255),
                content=chunk.content,
                token_count=chunk.token_count,
            )
            db.add(policy_chunk)
            db.flush()
            if embeddings:
                db.add(
                    PolicyChunkEmbedding(
                        chunk_id=policy_chunk.id,
                        provider=embeddings.provider,
                        model=embeddings.model,
                        dimensions=embeddings.dimensions,
                        vector=embeddings.vectors[index],
                    )
                )
            chunks_indexed += 1
        documents_indexed += 1
        if source.source_type.startswith("remote_"):
            remote_sources_indexed += 1
        else:
            local_sources_indexed += 1
        db.commit()
    sync_pgvector_store_if_available(db)
    return IndexResult(
        documents_indexed=documents_indexed,
        chunks_indexed=chunks_indexed,
        local_sources_indexed=local_sources_indexed,
        remote_sources_indexed=remote_sources_indexed,
        warnings=warnings,
    )


def import_precomputed_policy_documents(
    db: Session,
    *,
    documents: list[dict],
    embedding_provider: str,
    embedding_model: str,
    dimensions: int,
    warnings: list[str] | None = None,
) -> IndexResult:
    if dimensions <= 0:
        raise ValueError("Embedding dimensions must be positive.")

    clear_pgvector_store_if_available(db)
    clear_policy_index(db)
    documents_indexed = 0
    chunks_indexed = 0
    local_sources_indexed = 0
    remote_sources_indexed = 0
    used_titles: set[str] = set()

    for source in documents:
        chunks = source.get("chunks") or []
        if not chunks:
            continue
        document = PolicyDocument(
            title=_unique_title(str(source.get("title") or "Untitled Document"), used_titles),
            source_path=source.get("source_path"),
        )
        db.add(document)
        db.flush()
        for index, chunk in enumerate(chunks):
            vector = [float(value) for value in chunk.get("embedding") or []]
            if len(vector) != dimensions:
                raise ValueError(
                    f"Embedding dimension mismatch for {document.title} chunk {index}: "
                    f"expected {dimensions}, received {len(vector)}."
                )
            policy_chunk = PolicyChunk(
                document_id=document.id,
                chunk_index=index,
                heading=_truncate(chunk.get("heading"), 255),
                content=str(chunk.get("content") or ""),
                token_count=int(chunk.get("token_count") or 0),
            )
            db.add(policy_chunk)
            db.flush()
            db.add(
                PolicyChunkEmbedding(
                    chunk_id=policy_chunk.id,
                    provider=embedding_provider,
                    model=embedding_model,
                    dimensions=dimensions,
                    vector=vector,
                )
            )
            chunks_indexed += 1
        documents_indexed += 1
        source_type = str(source.get("source_type") or "")
        source_path = str(source.get("source_path") or "")
        if source_type.startswith("remote_") or source_path.startswith("http"):
            remote_sources_indexed += 1
        else:
            local_sources_indexed += 1
        db.commit()

    sync_pgvector_store_if_available(db)
    return IndexResult(
        documents_indexed=documents_indexed,
        chunks_indexed=chunks_indexed,
        local_sources_indexed=local_sources_indexed,
        remote_sources_indexed=remote_sources_indexed,
        warnings=warnings or [],
    )
