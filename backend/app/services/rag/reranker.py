from app.services.rag.query_planner import RAGQueryPlan


def heuristic_rerank_score(
    *,
    question: str,
    heading: str | None,
    content: str,
    document_title: str,
    metadata: dict | None,
    matched_terms: list[str],
    plan: RAGQueryPlan,
) -> float:
    normalized_question = question.lower()
    text = f"{document_title} {heading or ''} {content[:1200]}".lower()
    score = 0.0
    for term in matched_terms:
        if term.lower() in text:
            score += 0.035
    if heading and heading.lower() in normalized_question:
        score += 0.08
    for expansion in plan.expansions:
        if expansion.lower() in text:
            score += 0.025
    metadata = metadata or {}
    prefer_partition = plan.filters.get("prefer_partition")
    if prefer_partition and metadata.get("logical_partition") == prefer_partition:
        score += 0.08
    if plan.filters.get("prefer_official") and metadata.get("is_remote"):
        score += 0.04
    return round(min(0.2, score), 4)
