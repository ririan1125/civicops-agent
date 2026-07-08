from app.services.evals.eval_runner import run_embedding_benchmark, run_rag_retrieval_eval
from app.services.rag.indexer import index_policy_documents


def test_rag_retrieval_eval_returns_rank_metrics(db_session) -> None:
    index_policy_documents(db_session)
    response = run_rag_retrieval_eval(db_session)
    metric_names = {metric.name for metric in response.metrics}
    assert "rag_recall_at_1" in metric_names
    assert "rag_recall_at_3" in metric_names
    assert "rag_recall_at_5" in metric_names
    assert "rag_mrr" in metric_names
    assert response.embedding_provider
    assert response.embedding_model


def test_embedding_benchmark_compares_local_hash_dimensions(db_session) -> None:
    index_policy_documents(db_session)
    response = run_embedding_benchmark(db_session)
    assert response.corpus_chunks > 0
    assert response.cases_count > 0
    assert len(response.variants) == 3
    assert response.best_variant
