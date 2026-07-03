from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import PolicyChunk, PolicyDocument
from app.services.rag.chunker import chunk_markdown


def sample_policy_dir() -> Path:
    return Path(__file__).resolve().parents[4] / "sample_data" / "policies"


def clear_policy_index(db: Session) -> None:
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
        for index, chunk in enumerate(chunks):
            db.add(
                PolicyChunk(
                    document_id=document.id,
                    chunk_index=index,
                    heading=chunk.heading,
                    content=chunk.content,
                    token_count=chunk.token_count,
                )
            )
            chunks_indexed += 1
        documents_indexed += 1
    db.commit()
    return documents_indexed, chunks_indexed
