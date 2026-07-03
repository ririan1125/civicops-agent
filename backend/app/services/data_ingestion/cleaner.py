from datetime import datetime


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed.replace(tzinfo=None)


def parse_float(value: str | float | int | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def clean_311_record(record: dict) -> dict:
    unique_key = normalize_text(record.get("unique_key"))
    if not unique_key:
        raise ValueError("NYC 311 record is missing unique_key")

    return {
        "unique_key": unique_key,
        "created_date": parse_datetime(record.get("created_date")),
        "closed_date": parse_datetime(record.get("closed_date")),
        "agency": normalize_text(record.get("agency")),
        "agency_name": normalize_text(record.get("agency_name")),
        "complaint_type": normalize_text(record.get("complaint_type")),
        "descriptor": normalize_text(record.get("descriptor")),
        "location_type": normalize_text(record.get("location_type")),
        "incident_zip": normalize_text(record.get("incident_zip")),
        "borough": normalize_text(record.get("borough")),
        "status": normalize_text(record.get("status")),
        "resolution_description": normalize_text(record.get("resolution_description")),
        "latitude": parse_float(record.get("latitude")),
        "longitude": parse_float(record.get("longitude")),
        "raw_payload": record,
    }
