from dataclasses import dataclass


@dataclass(frozen=True)
class RAGQueryPlan:
    original_question: str
    rewritten_query: str
    filters: dict[str, str | bool]
    expansions: list[str]
    strategy: str


def build_query_plan(question: str) -> RAGQueryPlan:
    normalized = question.lower()
    filters: dict[str, str | bool] = {}
    expansions: list[str] = []

    if "nyc311" in normalized or "311" in normalized or "纽约311" in question:
        filters["prefer_partition"] = "official_nyc311_articles"
        expansions.extend(["NYC311", "311 service request", "official article"])
    if "open data" in normalized or "dataset" in normalized or "开放数据" in question or "数据集" in question:
        filters["prefer_partition"] = "official_nyc_open_data"
        expansions.extend(["NYC Open Data", "dataset metadata", "API columns"])
    if "official" in normalized or "官方" in question:
        filters["prefer_official"] = True
    if "project" in normalized or "architecture" in normalized or "项目" in question or "架构" in question:
        filters["prefer_partition"] = "project_architecture_docs"
        expansions.extend(["project architecture", "implementation"])

    rewritten = question
    if expansions:
        rewritten = f"{question} {' '.join(dict.fromkeys(expansions))}"
    strategy = "metadata_hybrid" if filters else "hybrid"
    return RAGQueryPlan(
        original_question=question,
        rewritten_query=rewritten,
        filters=filters,
        expansions=list(dict.fromkeys(expansions)),
        strategy=strategy,
    )
