from app.services.rag.answerer import answer_rag_question
from app.services.rag.indexer import import_precomputed_policy_documents, index_policy_documents
from app.services.rag.knowledge_graph import build_knowledge_graph
from app.services.rag.retriever import expand_query, retrieve_chunks
from app.services.rag.vector_store import describe_vector_store, initialize_pgvector_store


def test_rag_indexes_sample_documents_and_returns_citation(db_session) -> None:
    docs, chunks = index_policy_documents(db_session)
    assert docs >= 1
    assert chunks >= 1

    response = answer_rag_question(db_session, "What SQL statements is the agent allowed to execute?")
    assert response.refused is False
    assert response.citations
    assert response.retrieval_method == "hybrid_bm25_json_vector_graph_mmr"
    assert response.generation_provider == "mock"
    assert response.citations[0].vector_score is not None
    assert response.citations[0].vector_backend == "json"


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
    expanded = expand_query("\u600e\u4e48\u67e5\u8be2\u670d\u52a1\u8bf7\u6c42\u72b6\u6001")
    assert "service request" in expanded
    assert "status" in expanded


def test_pgvector_init_reports_unsupported_on_sqlite(db_session) -> None:
    result = initialize_pgvector_store(db_session)
    assert result["status"] == "unsupported"
    assert result["pgvector_enabled"] is False


def test_vector_store_schema_reports_json_fallback_on_sqlite(db_session) -> None:
    index_policy_documents(db_session)
    result = describe_vector_store(db_session)
    assert result["status"] == "unsupported"
    assert result["physical_table"] == "policy_chunk_embeddings"
    assert result["total_vectors"] > 0


def test_precomputed_rag_import_writes_embeddings(db_session) -> None:
    result = import_precomputed_policy_documents(
        db_session,
        documents=[
            {
                "title": "Precomputed Policy",
                "source_path": "memory://policy",
                "source_type": "local_markdown",
                "chunks": [
                    {
                        "heading": "Safe SQL",
                        "content": "Only SELECT statements are allowed.",
                        "token_count": 5,
                        "embedding": [1.0, 0.0, 0.0],
                    }
                ],
            }
        ],
        embedding_provider="bge",
        embedding_model="BAAI/bge-small-en-v1.5",
        dimensions=3,
    )
    assert result.documents_indexed == 1
    assert result.chunks_indexed == 1
    schema = describe_vector_store(db_session)
    assert schema["total_vectors"] == 1


def test_knowledge_graph_builds_nodes_from_index(db_session) -> None:
    index_policy_documents(db_session)
    result = build_knowledge_graph(db_session)
    assert result["chunks_scanned"] > 0
    assert result["nodes"]
