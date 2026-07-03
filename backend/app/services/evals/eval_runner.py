import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.schemas.evals import EvalMetric, EvalRunResponse
from app.services.rag.answerer import answer_rag_question
from app.services.sql_agent.safety import SQLSafetyError, assert_safe_select


def evals_dir() -> Path:
    return Path(__file__).resolve().parents[4] / "evals"


def _load_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def run_sql_safety_eval() -> tuple[EvalMetric, list[dict]]:
    cases = _load_json(evals_dir() / "sql_safety_cases.json")
    failures: list[dict] = []
    passed = 0
    for case in cases:
        should_allow = bool(case["should_allow"])
        try:
            assert_safe_select(case["sql"])
            allowed = True
        except SQLSafetyError:
            allowed = False
        ok = allowed == should_allow
        passed += int(ok)
        if not ok:
            failures.append({"suite": "sql_safety", "case": case, "observed_allowed": allowed})
    total = len(cases)
    score = round(passed / total, 3) if total else 0.0
    return EvalMetric(name="sql_safety_pass_rate", passed=passed, total=total, score=score), failures


def run_rag_eval(db: Session) -> tuple[EvalMetric, list[dict]]:
    cases = _load_json(evals_dir() / "rag_cases.json")
    failures: list[dict] = []
    passed = 0
    for case in cases:
        response = answer_rag_question(db, case["question"], top_k=4)
        expected_refusal = bool(case.get("should_refuse", False))
        has_citation = len(response.citations) > 0
        expected_terms = [str(term).lower() for term in case.get("expected_terms", [])]
        retrieved_text = " ".join(citation.snippet.lower() for citation in response.citations)
        terms_hit = all(term in retrieved_text for term in expected_terms)
        ok = response.refused == expected_refusal and (expected_refusal or (has_citation and terms_hit))
        passed += int(ok)
        if not ok:
            failures.append(
                {
                    "suite": "rag",
                    "case": case,
                    "observed_refused": response.refused,
                    "citation_count": len(response.citations),
                    "terms_hit": terms_hit,
                }
            )
    total = len(cases)
    score = round(passed / total, 3) if total else 0.0
    return EvalMetric(name="rag_citation_and_refusal_rate", passed=passed, total=total, score=score), failures


def run_all_evals(db: Session) -> EvalRunResponse:
    sql_metric, sql_failures = run_sql_safety_eval()
    rag_metric, rag_failures = run_rag_eval(db)
    return EvalRunResponse(metrics=[sql_metric, rag_metric], failures=sql_failures + rag_failures)
