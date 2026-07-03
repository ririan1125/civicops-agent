import json
from dataclasses import dataclass

from app.services.llm.providers import llm_planning_enabled, optional_deepseek_completion
from app.services.sql_agent.safety import SQLSafetyError, assert_safe_select


@dataclass
class PlannedSQL:
    sql: str
    confidence: float
    assumptions: list[str]


def service_requests_schema_context() -> str:
    return (
        "service_requests(unique_key, created_date, closed_date, agency, agency_name, "
        "complaint_type, descriptor, location_type, incident_zip, borough, status, "
        "resolution_description, latitude, longitude)"
    )


def _contains_any(question: str, tokens: list[str]) -> bool:
    return any(token in question for token in tokens)


def _template_plan(question: str) -> PlannedSQL:
    q = question.lower()
    assumptions = [
        "Using table service_requests.",
        "Only read-only SELECT SQL is generated.",
        "Planner provider: deterministic template fallback.",
    ]

    if _contains_any(q, ["top complaint", "most common", "complaint type", "最多", "高频", "投诉类型", "投诉排名"]):
        return PlannedSQL(
            sql=(
                "SELECT complaint_type, COUNT(*) AS request_count "
                "FROM service_requests "
                "WHERE complaint_type IS NOT NULL "
                "GROUP BY complaint_type "
                "ORDER BY request_count DESC "
                "LIMIT 10"
            ),
            confidence=0.93,
            assumptions=assumptions + ["Ranking complaint_type by count."],
        )

    if _contains_any(q, ["borough", "行政区", "区域", "区分布", "哪个区"]):
        return PlannedSQL(
            sql=(
                "SELECT borough, COUNT(*) AS request_count "
                "FROM service_requests "
                "WHERE borough IS NOT NULL "
                "GROUP BY borough "
                "ORDER BY request_count DESC"
            ),
            confidence=0.91,
            assumptions=assumptions + ["Grouping by borough."],
        )

    if _contains_any(q, ["agency", "workload", "部门", "机构", "处理机构", "工作量"]):
        return PlannedSQL(
            sql=(
                "SELECT agency, COUNT(*) AS request_count "
                "FROM service_requests "
                "WHERE agency IS NOT NULL "
                "GROUP BY agency "
                "ORDER BY request_count DESC "
                "LIMIT 10"
            ),
            confidence=0.9,
            assumptions=assumptions + ["Using agency as workload owner."],
        )

    if _contains_any(q, ["open", "closed", "status", "未关闭", "未完成", "已关闭", "状态"]):
        return PlannedSQL(
            sql=(
                "SELECT status, COUNT(*) AS request_count "
                "FROM service_requests "
                "GROUP BY status "
                "ORDER BY request_count DESC"
            ),
            confidence=0.86,
            assumptions=assumptions + ["Status is used to estimate open versus closed work."],
        )

    if _contains_any(q, ["resolution", "average time", "avg time", "解决时间", "处理时间", "平均耗时"]):
        return PlannedSQL(
            sql=(
                "SELECT complaint_type, COUNT(*) AS closed_count "
                "FROM service_requests "
                "WHERE closed_date IS NOT NULL AND complaint_type IS NOT NULL "
                "GROUP BY complaint_type "
                "ORDER BY closed_count DESC "
                "LIMIT 10"
            ),
            confidence=0.72,
            assumptions=assumptions
            + ["SQLite/PostgreSQL timestamp arithmetic differs, so API computes average resolution separately."],
        )

    if _contains_any(q, ["trend", "daily", "recent", "趋势", "每天", "最近"]):
        return PlannedSQL(
            sql=(
                "SELECT DATE(created_date) AS request_day, COUNT(*) AS request_count "
                "FROM service_requests "
                "WHERE created_date IS NOT NULL "
                "GROUP BY DATE(created_date) "
                "ORDER BY request_day DESC "
                "LIMIT 14"
            ),
            confidence=0.88,
            assumptions=assumptions + ["Daily trend uses created_date."],
        )

    if _contains_any(q, ["count", "total", "how many", "number of", "多少", "总数", "数量"]):
        return PlannedSQL(
            sql="SELECT COUNT(*) AS total_requests FROM service_requests",
            confidence=0.88,
            assumptions=assumptions + ["Counting all ingested rows."],
        )

    return PlannedSQL(
        sql=(
            "SELECT unique_key, created_date, borough, complaint_type, status "
            "FROM service_requests "
            "ORDER BY created_date DESC "
            "LIMIT 20"
        ),
        confidence=0.55,
        assumptions=assumptions + ["Question is broad; returning recent service requests as a safe fallback."],
    )


def _coerce_llm_sql(raw: str) -> PlannedSQL | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    sql = str(payload.get("sql") or "").strip()
    if not sql:
        return None
    try:
        assert_safe_select(sql)
    except SQLSafetyError:
        return None
    assumptions = payload.get("assumptions", [])
    if not isinstance(assumptions, list):
        assumptions = []
    try:
        confidence = float(payload.get("confidence", 0.68))
    except (TypeError, ValueError):
        confidence = 0.68
    return PlannedSQL(
        sql=sql,
        confidence=max(0.0, min(0.95, confidence)),
        assumptions=["Planner provider: deepseek schema-aware SQL planner."] + [str(item) for item in assumptions[:6]],
    )


def plan_sql(question: str) -> PlannedSQL:
    if llm_planning_enabled():
        try:
            raw = optional_deepseek_completion(
                system_prompt=(
                    "You are a SQL planner. Generate exactly one safe read-only SELECT query. "
                    "Use only the provided schema. Return only valid JSON with keys sql, confidence, assumptions. "
                    "Do not use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, PRAGMA, multiple statements, or comments."
                ),
                user_prompt=json.dumps(
                    {
                        "question": question,
                        "schema": service_requests_schema_context(),
                        "rules": [
                            "Use only table service_requests.",
                            "Prefer aggregate SQL for counts, rankings, distributions, trends, and workload.",
                            "Always include LIMIT for row-level listing queries.",
                        ],
                    },
                    ensure_ascii=False,
                ),
            )
            if raw:
                planned = _coerce_llm_sql(raw)
                if planned:
                    return planned
        except Exception:
            return _template_plan(question)
    return _template_plan(question)
