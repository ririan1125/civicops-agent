from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.schemas.ingestion import IngestionRequest, IngestionResponse, IngestionSyncRequest, IngestionSyncResponse
from app.services.data_ingestion.ingestion_service import run_ingestion, run_latest_sync

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post("/run", response_model=IngestionResponse)
def trigger_ingestion(request: IngestionRequest, db: Session = Depends(get_session)) -> IngestionResponse:
    return run_ingestion(db, request)


@router.post("/sync-latest", response_model=IngestionSyncResponse)
def sync_latest(
    request: IngestionSyncRequest | None = None,
    db: Session = Depends(get_session),
) -> IngestionSyncResponse:
    return run_latest_sync(db, request)
