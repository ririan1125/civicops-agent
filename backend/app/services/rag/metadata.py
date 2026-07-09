from app.services.rag.vector_store import source_partition


def source_metadata(title: str, source_path: str | None, source_type: str | None = None) -> dict:
    partition = source_partition(source_path, title)
    path = source_path or ""
    return {
        "source_type": source_type or "unknown",
        "logical_partition": partition,
        "is_remote": path.startswith("http"),
        "is_official_nyc311": "portal.311.nyc.gov" in path.lower(),
        "is_open_data": partition == "official_nyc_open_data",
    }
