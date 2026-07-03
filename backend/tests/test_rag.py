from app.services.rag.answerer import answer_rag_question
from app.services.rag.indexer import index_policy_documents
from app.services.rag.retriever import expand_query, retrieve_chunks


def test_rag_indexes_sample_documents_and_returns_citation(db_session) -> None:
    docs, chunks = index_policy_documents(db_session)
    assert docs >= 1
    assert chunks >= 1

    response = answer_rag_question(db_session, "What SQL statements is the agent allowed to execute?")
    assert response.refused is False
    assert response.citations
    assert response.retrieval_method == "hybrid_bm25_vector_rerank"
    assert response.generation_provider == "mock"
    assert response.citations[0].vector_score is not None


def test_rag_refuses_when_evidence_is_weak(db_session) -> None:
    index_policy_documents(db_session)
    response = answer_rag_question(db_session, "What is the private phone number?")
    assert response.refused is True


def test_hybrid_retriever_returns_scored_chunks(db_session) -> None:
    index_policy_documents(db_session)
    retrieved = retrieve_chunks(db_session, "safe SQL allowed statements", top_k=3)
    assert retrieved
    assert retrieved[0].score > 0
    assert retrieved[0].vector_score is not None
    assert retrieved[0].lexical_score is not None


def test_query_expansion_supports_chinese_service_request_status() -> None:
    expanded = expand_query("怎么查询服务请求状态")
    assert "service request" in expanded
    assert "status" in expanded
