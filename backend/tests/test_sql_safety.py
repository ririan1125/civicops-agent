import pytest

from app.services.sql_agent.safety import SQLSafetyError, assert_safe_select, enforce_limit


def test_allows_single_select() -> None:
    assert_safe_select("SELECT COUNT(*) FROM service_requests")


def test_blocks_destructive_sql() -> None:
    with pytest.raises(SQLSafetyError):
        assert_safe_select("DELETE FROM service_requests")


def test_blocks_multiple_statements() -> None:
    with pytest.raises(SQLSafetyError):
        assert_safe_select("SELECT * FROM service_requests; DROP TABLE service_requests;")


def test_enforce_limit_adds_default_limit() -> None:
    assert enforce_limit("SELECT * FROM service_requests").endswith("LIMIT 100")
