from dataclasses import dataclass


@dataclass
class RouteDecision:
    route: str
    reason: str


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
    q = question.lower()
    if any(keyword in q for keyword in SQL_KEYWORDS):
        return RouteDecision(route="sql", reason="Question asks for structured metrics or database aggregation.")
    if any(keyword in q for keyword in RAG_KEYWORDS):
        return RouteDecision(route="rag", reason="Question asks for policy/process knowledge that needs document evidence.")
    return RouteDecision(route="clarify", reason="Question is ambiguous; ask the user whether they need metrics or policy evidence.")
