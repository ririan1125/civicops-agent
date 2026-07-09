from datetime import datetime

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.db.models import RagIndexJob
from app.db.session import SessionLocal
from app.services.rag.embeddings import embedding_runtime_label
from app.services.rag.indexer import index_policy_documents


def _serialize_job(job: RagIndexJob) -> dict:
    return {
        "id": job.id,
        "status": job.status,
        "include_remote": job.include_remote,
        "max_311_articles": job.max_311_articles,
        "documents_indexed": job.documents_indexed,
        "chunks_indexed": job.chunks_indexed,
        "local_sources_indexed": job.local_sources_indexed,
        "remote_sources_indexed": job.remote_sources_indexed,
        "embedding_provider": job.embedding_provider,
        "embedding_model": job.embedding_model,
        "warnings": job.warnings or [],
        "error_message": job.error_message,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "updated_at": job.updated_at,
    }


def create_reindex_job(
    db: Session,
    *,
    include_remote: bool,
    max_311_articles: int | None,
) -> dict:
    provider, model = embedding_runtime_label()
    job = RagIndexJob(
        status="queued",
        include_remote=include_remote,
        max_311_articles=max_311_articles,
        embedding_provider=provider,
        embedding_model=model,
        warnings=[],
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return _serialize_job(job)


def get_reindex_job(db: Session, job_id: int) -> dict | None:
    job = db.get(RagIndexJob, job_id)
    return _serialize_job(job) if job else None


def get_latest_reindex_job(db: Session) -> dict | None:
    job = db.query(RagIndexJob).order_by(desc(RagIndexJob.created_at), desc(RagIndexJob.id)).first()
    return _serialize_job(job) if job else None


def _mark_job(
    db: Session,
    job: RagIndexJob,
    *,
    status: str,
    now: datetime,
    error_message: str | None = None,
) -> None:
    job.status = status
    job.updated_at = now
    if status == "running":
        job.started_at = now
    if status in {"success", "failed"}:
        job.finished_at = now
    if error_message:
        job.error_message = error_message[:4000]
    db.add(job)
    db.commit()
    db.refresh(job)


def run_reindex_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = db.get(RagIndexJob, job_id)
        if job is None:
            return
        _mark_job(db, job, status="running", now=utc_now())
        result = index_policy_documents(
            db,
            include_remote=job.include_remote,
            max_311_articles=job.max_311_articles,
        )
        provider, model = embedding_runtime_label()
        job.documents_indexed = result.documents_indexed
        job.chunks_indexed = result.chunks_indexed
        job.local_sources_indexed = result.local_sources_indexed
        job.remote_sources_indexed = result.remote_sources_indexed
        job.embedding_provider = provider
        job.embedding_model = model
        job.warnings = result.warnings or []
        _mark_job(db, job, status="success", now=utc_now())
    except Exception as exc:
        db.rollback()
        failed_job = db.get(RagIndexJob, job_id)
        if failed_job is not None:
            _mark_job(db, failed_job, status="failed", now=utc_now(), error_message=str(exc))
    finally:
        db.close()
