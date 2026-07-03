from datetime import datetime

from app.db.models import ServiceRequest
from app.services.analytics.dashboard_service import get_dashboard_summary


def test_dashboard_summary_counts_records(db_session) -> None:
    db_session.add_all(
        [
            ServiceRequest(
                unique_key="1",
                created_date=datetime(2026, 7, 1),
                closed_date=datetime(2026, 7, 2),
                agency="DEP",
                complaint_type="Noise",
                borough="BROOKLYN",
                status="Closed",
            ),
            ServiceRequest(
                unique_key="2",
                created_date=datetime(2026, 7, 1),
                agency="DOT",
                complaint_type="Street Condition",
                borough="QUEENS",
                status="Open",
            ),
        ]
    )
    db_session.commit()

    summary = get_dashboard_summary(db_session)
    assert summary.total_requests == 2
    assert summary.closed_requests == 1
    assert summary.open_requests == 1
    assert summary.top_complaints[0].value == 1
