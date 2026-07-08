import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.schemas.evals import EvalMetric, EvalRunResponse, RAGRetrievalCaseResult, RAGRetrievalEvalResponse
from app.services.rag.answerer import answer_rag_question
from app.services.rag.embeddings import embedding_runtime_label
from app.services.rag.retriever import retrieve_chunks
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


def _matches_expected(text: str, expected_values: list[str]) -> bool:
    normalized = text.lower()
    return any(expected.lower() in normalized for expected in expected_values)


def run_rag_retrieval_eval(db: Session) -> RAGRetrievalEvalResponse:
    cases = _load_json(evals_dir() / "rag_retrieval_cases.json")
    case_results: list[RAGRetrievalCaseResult] = []
    hit_at_1 = 0
    hit_at_3 = 0
    hit_at_5 = 0
    reciprocal_rank_sum = 0.0

    for case in cases:
        expected = [str(value) for value in case.get("expected", [])]
        retrieved = retrieve_chunks(db, case["question"], top_k=5, candidate_pool=80)
        labels = [
            f"{item.chunk.document.title} | {item.chunk.heading or ''} | {item.chunk.document.source_path or ''}"
            for item in retrieved
        ]
        hit_rank: int | None = None
        for index, label in enumerate(labels, start=1):
            if _matches_expected(label, expected):
                hit_rank = index
                break
        reciprocal_rank = round(1 / hit_rank, 4) if hit_rank else 0.0
        reciprocal_rank_sum += reciprocal_rank
        if hit_rank is not None and hit_rank <= 1:
            hit_at_1 += 1
        if hit_rank is not None and hit_rank <= 3:
            hit_at_3 += 1
        if hit_rank is not None and hit_rank <= 5:
            hit_at_5 += 1
        case_results.append(
            RAGRetrievalCaseResult(
                name=case["name"],
                question=case["question"],
                expected=expected,
                retrieved=labels,
                hit_rank=hit_rank,
                reciprocal_rank=reciprocal_rank,
                top_score=retrieved[0].score if retrieved else None,
            )
        )

    total = len(cases)
    metrics = [
        EvalMetric(name="rag_recall_at_1", passed=hit_at_1, total=total, score=round(hit_at_1 / total, 3) if total else 0.0),
        EvalMetric(name="rag_recall_at_3", passed=hit_at_3, total=total, score=round(hit_at_3 / total, 3) if total else 0.0),
        EvalMetric(name="rag_recall_at_5", passed=hit_at_5, total=total, score=round(hit_at_5 / total, 3) if total else 0.0),
        EvalMetric(name="rag_mrr", passed=round(reciprocal_rank_sum, 3), total=total, score=round(reciprocal_rank_sum / total, 3) if total else 0.0),
    ]
    provider, model = embedding_runtime_label()
    return RAGRetrievalEvalResponse(metrics=metrics, cases=case_results, embedding_provider=provider, embedding_model=model)
