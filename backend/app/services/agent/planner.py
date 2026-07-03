import json
from dataclasses import dataclass

from app.services.agent.tools import get_tool, tool_manifest
from app.services.llm.providers import llm_planning_enabled, optional_deepseek_completion


@dataclass(frozen=True)
class AgentPlan:
    route: str
    selected_tool: str
    reason: str
    steps: list[str]
    confidence: float
    planner_provider: str


SQL_KEYWORDS = [
    "count",
    "total",
    "top",
    "trend",
    "borough",
    "agency",
    "open",
    "closed",
    "workload",
    "多少",
    "最多",
    "排名",
    "趋势",
    "区域",
    "部门",
]

RAG_KEYWORDS = [
    "policy",
    "procedure",
    "process",
    "should",
    "citation",
    "document",
    "allowed",
    "rule",
    "政策",
    "流程",
    "规定",
    "依据",
    "引用",
    "允许",
]


def _heuristic_plan(question: str) -> AgentPlan:
    q = question.lower()
    if any(keyword in q for keyword in SQL_KEYWORDS):
        return AgentPlan(
            route="sql",
            selected_tool="safe_sql_analysis",
            reason="The question asks for structured metrics or database aggregation.",
            steps=[
                "Identify the question as a structured-data analytics request.",
                "Use the safe SQL tool with the service_requests schema.",
                "Validate that generated SQL is read-only before execution.",
            ],
            confidence=0.78,
            planner_provider="heuristic",
        )
    if any(keyword in q for keyword in RAG_KEYWORDS):
        return AgentPlan(
            route="rag",
            selected_tool="rag_policy_assistant",
            reason="The question asks for policy/process knowledge that needs document evidence.",
            steps=[
                "Identify the question as a document-grounded policy/process request.",
                "Retrieve relevant policy chunks with hybrid search.",
                "Generate a grounded answer with citations or refuse weak evidence.",
            ],
            confidence=0.76,
            planner_provider="heuristic",
        )
    return AgentPlan(
        route="clarify",
        selected_tool="clarification",
        reason="The question is ambiguous; the system should ask which knowledge source to use.",
        steps=["Ask whether the user needs database metrics or policy document evidence."],
        confidence=0.45,
        planner_provider="heuristic",
    )


def _coerce_llm_plan(raw: str) -> AgentPlan | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    selected_tool = str(payload.get("selected_tool", "clarification"))
    tool = get_tool(selected_tool)
    steps = payload.get("steps", [])
    if not isinstance(steps, list):
        steps = []
    confidence = payload.get("confidence", 0.6)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.6
    return AgentPlan(
        route=tool.route,
        selected_tool=tool.name,
        reason=str(payload.get("reason") or tool.description),
        steps=[str(step) for step in steps][:6],
        confidence=max(0.0, min(1.0, confidence)),
        planner_provider="deepseek",
    )


def plan_agent(question: str) -> AgentPlan:
    if not llm_planning_enabled():
        return _heuristic_plan(question)

    raw = optional_deepseek_completion(
        system_prompt=(
            "You are an agent planner for CivicOps Agent. Choose exactly one tool. "
            "Return only valid JSON with keys: selected_tool, reason, steps, confidence."
        ),
        user_prompt=json.dumps(
            {
                "question": question,
                "tools": tool_manifest(),
                "selection_rules": [
                    "Use safe_sql_analysis for counts, rankings, trends, workload, status, and database metrics.",
                    "Use rag_policy_assistant for policy, process, rule, governance, citation, or document-evidence questions.",
                    "Use clarification when the source or intent is ambiguous.",
                ],
            },
            ensure_ascii=False,
        ),
    )
    if raw:
        planned = _coerce_llm_plan(raw)
        if planned:
            return planned
    return _heuristic_plan(question)
