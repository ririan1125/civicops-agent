from app.services.agent.router import route_question


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
