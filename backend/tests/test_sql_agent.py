from app.db.models import ServiceRequest
from app.services.sql_agent.sql_tool import run_safe_select
from app.services.sql_agent import text_to_sql
from app.services.sql_agent.text_to_sql import plan_sql


def test_planner_generates_safe_count_query(db_session) -> None:
    db_session.add(ServiceRequest(unique_key="1", complaint_type="Noise", borough="BROOKLYN", status="Open"))
    db_session.commit()
    planned = plan_sql("How many requests are there?")
    result = run_safe_select(db_session, planned.sql)
    assert result.rows[0]["total_requests"] == 1


def test_planner_handles_chinese_top_complaint_question() -> None:
    planned = plan_sql("投诉最多的类型是什么？")
    assert "complaint_type" in planned.sql
    assert "GROUP BY complaint_type" in planned.sql


def test_sql_planner_falls_back_when_llm_call_fails(monkeypatch) -> None:
    monkeypatch.setattr(text_to_sql, "llm_planning_enabled", lambda: True)

    def fail_completion(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(text_to_sql, "optional_deepseek_completion", fail_completion)

    planned = plan_sql("What are the top complaint types?")

    assert "GROUP BY complaint_type" in planned.sql
    assert planned.assumptions[2] == "Planner provider: deterministic template fallback."
