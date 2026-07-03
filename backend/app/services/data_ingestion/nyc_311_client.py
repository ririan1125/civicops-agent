from datetime import date

import httpx

from app.core.config import get_settings


def build_where_clause(start_date: date | None, end_date: date | None, borough: str | None) -> str | None:
    parts: list[str] = []
    if start_date:
        parts.append(f"created_date >= '{start_date.isoformat()}T00:00:00'")
    if end_date:
        parts.append(f"created_date < '{end_date.isoformat()}T00:00:00'")
    if borough:
        parts.append(f"upper(borough) = '{borough.upper()}'")
    return " AND ".join(parts) if parts else None


def fetch_311_requests(
    *,
    limit: int = 1000,
    offset: int = 0,
    start_date: date | None = None,
    end_date: date | None = None,
    borough: str | None = None,
) -> list[dict]:
    settings = get_settings()
    params: dict[str, str | int] = {
        "$limit": min(limit, 10000),
        "$offset": offset,
        "$order": "created_date DESC",
    }
    where = build_where_clause(start_date, end_date, borough)
    if where:
        params["$where"] = where

    with httpx.Client(timeout=40) as client:
        response = client.get(settings.nyc_311_endpoint, params=params)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("NYC 311 API returned a non-list payload")
        return payload
