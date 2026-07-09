from sqlalchemy import text
from sqlalchemy.orm import Session


def ensure_rag_v2_columns(db: Session) -> None:
    if db.bind is None:
        return
    dialect = db.bind.dialect.name
    if dialect == "postgresql":
        db.execute(text("ALTER TABLE policy_chunks ADD COLUMN IF NOT EXISTS parent_heading VARCHAR(255)"))
        db.execute(text("ALTER TABLE policy_chunks ADD COLUMN IF NOT EXISTS metadata JSON"))
        db.execute(text("ALTER TABLE policy_chunks ADD COLUMN IF NOT EXISTS sparse_terms JSON"))
        db.commit()
    elif dialect == "sqlite":
        existing = {row[1] for row in db.execute(text("PRAGMA table_info(policy_chunks)")).all()}
        for name, column_type in {
            "parent_heading": "VARCHAR(255)",
            "metadata": "JSON",
            "sparse_terms": "JSON",
        }.items():
            if name not in existing:
                db.execute(text(f"ALTER TABLE policy_chunks ADD COLUMN {name} {column_type}"))
        db.commit()
