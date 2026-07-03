from app.services.rag.answerer import answer_rag_question
from app.services.rag.indexer import index_policy_documents


def test_rag_indexes_sample_documents_and_returns_citation(db_session) -> None:
    docs, chunks = index_policy_documents(db_session)
    assert docs >= 1
    assert chunks >= 1

    response = answer_rag_question(db_session, "What SQL statements is the agent allowed to execute?")
    assert response.refused is False
    assert response.citations


def test_rag_refuses_when_evidence_is_weak(db_session) -> None:
    index_policy_documents(db_session)
    response = answer_rag_question(db_session, "What is the private phone number?")
    assert response.refused is True
