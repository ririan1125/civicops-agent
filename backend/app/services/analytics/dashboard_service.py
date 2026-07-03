from datetime import datetime

from sqlalchemy import case, desc, func
from sqlalchemy.orm import Session

from app.db.models import ServiceRequest
from app.schemas.dashboard import BreakdownItem, DashboardSummary


def _count(db: Session) -> int:
    return int(db.query(func.count(ServiceRequest.id)).scalar() or 0)


def _status_count(db: Session, status: str) -> int:
    return int(db.query(func.count(ServiceRequest.id)).filter(func.lower(ServiceRequest.status) == status.lower()).scalar() or 0)


def _breakdown(db: Session, column, limit: int = 8) -> list[BreakdownItem]:
    rows = (
        db.query(column.label("label"), func.count(ServiceRequest.id).label("value"))
        .filter(column.is_not(None))
        .group_by(column)
        .order_by(desc("value"))
        .limit(limit)
        .all()
    )
    return [BreakdownItem(label=str(label), value=int(value)) for label, value in rows]


def _daily_trend(db: Session, limit: int = 14) -> list[BreakdownItem]:
    rows = (
        db.query(func.date(ServiceRequest.created_date).label("day"), func.count(ServiceRequest.id).label("value"))
        .filter(ServiceRequest.created_date.is_not(None))
        .group_by(func.date(ServiceRequest.created_date))
        .order_by(desc("day"))
        .limit(limit)
        .all()
    )
    items = [BreakdownItem(label=str(day), value=int(value)) for day, value in rows]
    return list(reversed(items))


def _average_resolution_hours(db: Session) -> float | None:
    rows: list[tuple[datetime | None, datetime | None]] = (
        db.query(ServiceRequest.created_date, ServiceRequest.closed_date)
        .filter(ServiceRequest.created_date.is_not(None), ServiceRequest.closed_date.is_not(None))
        .limit(5000)
        .all()
    )
    durations = [
        (closed - created).total_seconds() / 3600
        for created, closed in rows
        if created and closed and closed >= created
    ]
    if not durations:
        return None
    return round(sum(durations) / len(durations), 2)


def get_dashboard_summary(db: Session) -> DashboardSummary:
    total = _count(db)
    closed = _status_count(db, "closed")
    open_count = total - closed
    if total == 0:
        open_count = 0

    return DashboardSummary(
        total_requests=total,
        open_requests=open_count,
        closed_requests=closed,
        average_resolution_hours=_average_resolution_hours(db),
        top_complaints=_breakdown(db, ServiceRequest.complaint_type),
        borough_distribution=_breakdown(db, ServiceRequest.borough),
        agency_workload=_breakdown(db, ServiceRequest.agency),
        daily_trend=_daily_trend(db),
    )
