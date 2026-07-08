from app.services.evals.eval_runner import run_rag_retrieval_eval
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
