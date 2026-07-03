from dataclasses import dataclass

from app.services.agent.planner import plan_agent


@dataclass
class RouteDecision:
    route: str
    reason: str
    selected_tool: str
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
    "政策",
    "流程",
    "规定",
    "依据",
    "引用",
]


def route_question(question: str) -> RouteDecision:
    plan = plan_agent(question)
    return RouteDecision(
        route=plan.route,
        reason=plan.reason,
        selected_tool=plan.selected_tool,
        steps=plan.steps,
        confidence=plan.confidence,
        planner_provider=plan.planner_provider,
    )
