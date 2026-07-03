from dataclasses import dataclass


@dataclass(frozen=True)
class AgentTool:
    name: str
    route: str
    description: str
    input_contract: str


TOOLS: dict[str, AgentTool] = {
    "safe_sql_analysis": AgentTool(
        name="safe_sql_analysis",
        route="sql",
        description="Answer metrics, counts, rankings, trends, workload, and status questions from service_requests.",
        input_contract="Natural-language analytics question. The tool generates and executes read-only SELECT SQL.",
    ),
    "rag_policy_assistant": AgentTool(
        name="rag_policy_assistant",
        route="rag",
        description="Answer policy, process, governance, and operating-rule questions from indexed documents with citations.",
        input_contract="Natural-language policy/process question. The tool retrieves evidence chunks before generating an answer.",
    ),
    "clarification": AgentTool(
        name="clarification",
        route="clarify",
        description="Ask the user to clarify whether the question needs database metrics or document evidence.",
        input_contract="Ambiguous user question.",
    ),
}


def tool_manifest() -> list[dict[str, str]]:
    return [
        {
            "name": tool.name,
            "route": tool.route,
            "description": tool.description,
            "input_contract": tool.input_contract,
        }
        for tool in TOOLS.values()
    ]


def get_tool(name: str) -> AgentTool:
    return TOOLS.get(name, TOOLS["clarification"])
