from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import PolicyChunk, PolicyChunkEmbedding, PolicyDocument
from app.services.rag.chunker import chunk_markdown
from app.services.rag.embeddings import embed_texts


def sample_policy_dir() -> Path:
    return Path(__file__).resolve().parents[4] / "sample_data" / "policies"


def clear_policy_index(db: Session) -> None:
    db.query(PolicyChunkEmbedding).delete()
    db.query(PolicyChunk).delete()
    db.query(PolicyDocument).delete()
    db.commit()


def index_policy_documents(db: Session, directory: Path | None = None) -> tuple[int, int]:
    directory = directory or sample_policy_dir()
    if not directory.exists():
        return 0, 0

    clear_policy_index(db)
    documents_indexed = 0
    chunks_indexed = 0
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        document = PolicyDocument(title=path.stem.replace("_", " ").title(), source_path=str(path))
        db.add(document)
        db.flush()
        chunks = chunk_markdown(text)
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
    db.commit()
    return documents_indexed, chunks_indexed
