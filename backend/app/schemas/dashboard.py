from pydantic import BaseModel


class MetricCard(BaseModel):
    label: str
    value: int | float | str
    helper: str | None = None


class BreakdownItem(BaseModel):
    label: str
    value: int | float


class DashboardSummary(BaseModel):
    total_requests: int
    open_requests: int
    closed_requests: int
    average_resolution_hours: float | None
    top_complaints: list[BreakdownItem]
    borough_distribution: list[BreakdownItem]
    agency_workload: list[BreakdownItem]
    daily_trend: list[BreakdownItem]
