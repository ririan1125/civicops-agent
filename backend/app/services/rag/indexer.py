from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import PolicyChunk, PolicyChunkEmbedding, PolicyDocument
from app.services.rag.chunker import chunk_markdown
from app.services.rag.embeddings import embed_texts
from app.services.rag.source_loader import DocumentSource, load_document_sources, sample_policy_dir


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
    if title not in used_titles:
        used_titles.add(title)
        return title
    suffix = 2
    while f"{title} ({suffix})" in used_titles:
        suffix += 1
    unique = f"{title} ({suffix})"
    used_titles.add(unique)
    return unique


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
) -> IndexResult:
    if directory is not None:
        sources = _sources_from_directory(directory)
        warnings: list[str] = []
    else:
        loaded = load_document_sources(include_remote=include_remote)
        sources = loaded.sources
        warnings = loaded.warnings

    if not sources:
        return IndexResult(documents_indexed=0, chunks_indexed=0, warnings=warnings)

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
                heading=chunk.heading,
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
    return IndexResult(
        documents_indexed=documents_indexed,
        chunks_indexed=chunks_indexed,
        local_sources_indexed=local_sources_indexed,
        remote_sources_indexed=remote_sources_indexed,
        warnings=warnings,
    )
