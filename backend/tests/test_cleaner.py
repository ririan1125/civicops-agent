from app.services.data_ingestion.cleaner import clean_311_record


def test_clean_311_record_parses_core_fields() -> None:
    cleaned = clean_311_record(
        {
            "unique_key": "123",
            "created_date": "2026-07-01T12:00:00.000",
            "closed_date": "",
            "agency": "DEP",
            "complaint_type": "Noise",
            "borough": "BROOKLYN",
            "status": "Open",
            "latitude": "40.7",
            "longitude": "-73.9",
        }
    )
    assert cleaned["unique_key"] == "123"
    assert cleaned["closed_date"] is None
    assert cleaned["latitude"] == 40.7
    assert cleaned["raw_payload"]["agency"] == "DEP"
