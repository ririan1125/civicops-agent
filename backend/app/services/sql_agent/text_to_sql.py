from dataclasses import dataclass


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


def plan_sql(question: str) -> PlannedSQL:
    q = question.lower()
    assumptions = ["Using table service_requests.", "Only read-only SELECT SQL is generated."]

    if any(token in q for token in ["top complaint", "most common", "最多", "高频", "投诉类型排名"]):
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

    if any(token in q for token in ["borough", "区域", "行政区", "区分布"]):
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

    if any(token in q for token in ["agency", "部门", "机构", "workload"]):
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

    if any(token in q for token in ["open", "未关闭", "未完成", "open cases"]):
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

    if any(token in q for token in ["resolution", "解决时间", "处理时间", "average time", "avg time"]):
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

    if any(token in q for token in ["trend", "趋势", "daily", "每天", "recent"]):
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

    if any(token in q for token in ["count", "total", "how many", "number of", "多少", "总数"]):
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
