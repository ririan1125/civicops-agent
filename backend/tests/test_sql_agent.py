from app.db.models import ServiceRequest
from app.services.sql_agent.sql_tool import run_safe_select
from app.services.sql_agent.text_to_sql import plan_sql


def test_planner_generates_safe_count_query(db_session) -> None:
    db_session.add(ServiceRequest(unique_key="1", complaint_type="Noise", borough="BROOKLYN", status="Open"))
    db_session.commit()
    planned = plan_sql("How many requests are there?")
    result = run_safe_select(db_session, planned.sql)
    assert result.rows[0]["total_requests"] == 1
