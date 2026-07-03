from datetime import date, datetime

from pydantic import BaseModel, Field


class IngestionRequest(BaseModel):
    limit: int = Field(default=1000, ge=1, le=10000)
    offset: int = Field(default=0, ge=0)
    start_date: date | None = None
    end_date: date | None = None
    borough: str | None = None


class IngestionResponse(BaseModel):
    run_id: int | None = None
    source: str = "nyc_311"
    requested_limit: int
    fetched_count: int
    inserted_count: int
    updated_count: int
    status: str
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class IngestionSyncRequest(BaseModel):
    limit: int = Field(default=5000, ge=1, le=10000)
    lookback_days: int = Field(default=7, ge=0, le=90)
    borough: str | None = None


class IngestionSyncResponse(IngestionResponse):
    sync_mode: str = "latest_with_lookback"
    previous_latest_created_date: datetime | None = None
    sync_start_date: date | None = None
