from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.db.models import IngestionRun, ServiceRequest
from app.schemas.ingestion import IngestionRequest, IngestionResponse
from app.services.data_ingestion.cleaner import clean_311_record
from app.services.data_ingestion.nyc_311_client import fetch_311_requests


def _upsert_service_request(db: Session, cleaned: dict) -> str:
    existing = db.query(ServiceRequest).filter(ServiceRequest.unique_key == cleaned["unique_key"]).one_or_none()
    if existing:
        for key, value in cleaned.items():
            setattr(existing, key, value)
        return "updated"
    db.add(ServiceRequest(**cleaned))
    return "inserted"


def run_ingestion(db: Session, request: IngestionRequest) -> IngestionResponse:
    started_at = utc_now()
    run = IngestionRun(
        requested_limit=request.limit,
        fetched_count=0,
        inserted_count=0,
        updated_count=0,
        status="running",
        started_at=started_at,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    inserted_count = 0
    updated_count = 0
    try:
        raw_records = fetch_311_requests(
            limit=request.limit,
            offset=request.offset,
            start_date=request.start_date,
            end_date=request.end_date,
            borough=request.borough,
        )
        for raw in raw_records:
            cleaned = clean_311_record(raw)
            action = _upsert_service_request(db, cleaned)
            if action == "inserted":
                inserted_count += 1
            else:
                updated_count += 1

        run.fetched_count = len(raw_records)
        run.inserted_count = inserted_count
        run.updated_count = updated_count
        run.status = "success"
        run.finished_at = utc_now()
        db.commit()
    except Exception as exc:
        db.rollback()
        run.status = "failed"
        run.error_message = str(exc)
        run.finished_at = utc_now()
        db.add(run)
        db.commit()

    db.refresh(run)
    return IngestionResponse(
        run_id=run.id,
        requested_limit=run.requested_limit,
        fetched_count=run.fetched_count,
        inserted_count=run.inserted_count,
        updated_count=run.updated_count,
        status=run.status,
        error_message=run.error_message,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )
