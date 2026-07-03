from app.services.agent.router import route_question
from app.services.agent import planner


def test_agent_routes_metric_questions_to_sql_tool() -> None:
    decision = route_question("What are the top complaint types?")
    assert decision.route == "sql"
    assert decision.selected_tool == "safe_sql_analysis"
    assert decision.steps
    assert decision.planner_provider == "heuristic"


def test_agent_routes_policy_questions_to_rag_tool() -> None:
    decision = route_question("What policy explains allowed SQL statements?")
    assert decision.route == "rag"
    assert decision.selected_tool == "rag_policy_assistant"


def test_agent_routes_311_faq_questions_to_rag_tool() -> None:
    decision = route_question("How do I check a NYC311 service request status?")
    assert decision.route == "rag"
    assert decision.selected_tool == "rag_policy_assistant"


def test_agent_planner_falls_back_when_llm_call_fails(monkeypatch) -> None:
    monkeypatch.setattr(planner, "llm_planning_enabled", lambda: True)

    def fail_completion(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(planner, "optional_deepseek_completion", fail_completion)

    decision = planner.plan_agent("How do I check a NYC311 service request status?")

    assert decision.route == "rag"
    assert decision.planner_provider == "heuristic"


def test_rag_intent_bypasses_llm_planner(monkeypatch) -> None:
    monkeypatch.setattr(planner, "llm_planning_enabled", lambda: True)

    def wrong_completion(*args, **kwargs):
        return '{"selected_tool":"safe_sql_analysis","reason":"wrong","steps":[],"confidence":0.9}'

    monkeypatch.setattr(planner, "optional_deepseek_completion", wrong_completion)

    decision = planner.plan_agent("How do I check a NYC311 service request status?")

    assert decision.route == "rag"
    assert decision.selected_tool == "rag_policy_assistant"
    assert decision.planner_provider == "heuristic"
