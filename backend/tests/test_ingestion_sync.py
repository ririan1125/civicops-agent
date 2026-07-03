from datetime import datetime

from app.db.models import ServiceRequest
from app.schemas.ingestion import IngestionSyncRequest
from app.services.data_ingestion import ingestion_service
from app.services.data_ingestion.ingestion_service import run_latest_sync


def test_latest_sync_uses_recent_lookback_and_upserts(db_session, monkeypatch) -> None:
    db_session.add(
        ServiceRequest(
            unique_key="existing",
            created_date=datetime(2026, 7, 3, 12, 0, 0),
            complaint_type="Noise",
            borough="BROOKLYN",
            status="Open",
        )
    )
    db_session.commit()

    calls = {}

    def fake_fetch_311_requests(**kwargs):
        calls.update(kwargs)
        return [
            {
                "unique_key": "existing",
                "created_date": "2026-07-03T12:00:00.000",
                "complaint_type": "Noise",
                "borough": "BROOKLYN",
                "status": "Closed",
            },
            {
                "unique_key": "new",
                "created_date": "2026-07-04T08:00:00.000",
                "complaint_type": "Street Condition",
                "borough": "QUEENS",
                "status": "Open",
            },
        ]

    monkeypatch.setattr(ingestion_service, "fetch_311_requests", fake_fetch_311_requests)

    response = run_latest_sync(db_session, IngestionSyncRequest(limit=100, lookback_days=2))

    assert response.status == "success"
    assert response.inserted_count == 1
    assert response.updated_count == 1
    assert calls["start_date"].isoformat() == "2026-07-01"
    assert calls["limit"] == 100
    assert db_session.query(ServiceRequest).filter(ServiceRequest.unique_key == "new").count() == 1
    assert db_session.query(ServiceRequest).filter(ServiceRequest.unique_key == "existing").one().status == "Closed"
