import re

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import PolicyChunk
from app.schemas.rag import Citation, RAGAskResponse
from app.services.llm.providers import complete_chat
from app.services.rag.indexer import index_policy_documents
from app.services.rag.retriever import RetrievedChunk, retrieve_chunks


JSON_RETRIEVAL_METHOD = "hybrid_bm25_json_vector_graph_mmr"
PGVECTOR_RETRIEVAL_METHOD = "hybrid_bm25_pgvector_graph_mmr"


def _snippet(text: str, max_chars: int = 260) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3] + "..."


def _citation(item: RetrievedChunk) -> Citation:
    document = item.chunk.document
    source_url = document.source_path if document.source_path and document.source_path.startswith("http") else None
    metadata = item.chunk.chunk_metadata or {}
    return Citation(
        document_title=document.title,
        chunk_id=item.chunk.id,
        heading=item.chunk.heading,
        source_url=source_url,
        snippet=_snippet(item.chunk.content),
        score=item.score,
        lexical_score=item.lexical_score,
        vector_score=item.vector_score,
        vector_backend=item.vector_backend,
        graph_entities=item.graph_entities or [],
        matched_terms=item.matched_terms,
        reranker_score=item.reranker_score,
        sparse_score=item.sparse_score,
        source_partition=metadata.get("logical_partition"),
    )


def _compose_answer(question: str, retrieved: list[RetrievedChunk]) -> tuple[str, str]:
    evidence_blocks = []
    for item in retrieved:
        evidence_blocks.append(
            f"[chunk_id={item.chunk.id} title={item.chunk.document.title} heading={item.chunk.heading or 'Untitled'} "
            f"score={item.score}]\n{_snippet(item.chunk.content, 700)}"
        )
    completion = complete_chat(
        system_prompt=(
            "You are a civic operations assistant. Answer only from the provided evidence. "
            "If evidence is insufficient, say you cannot answer confidently from the indexed documents. "
            "Keep the answer concise and mention the supporting chunk ids or source titles when useful."
        ),
        user_prompt=f"Question: {question}\n\nEvidence:\n\n" + "\n\n".join(evidence_blocks),
    )
    return completion.content, completion.provider


def _asks_for_private_contact(question: str) -> bool:
    normalized = question.lower()
    contact_terms = [
        "phone",
        "email",
        "address",
        "contact",
        "telephone",
        "\u624b\u673a",
        "\u7535\u8bdd",
        "\u90ae\u7bb1",
        "\u5730\u5740",
        "\u8054\u7cfb\u65b9\u5f0f",
    ]
    private_terms = ["private", "personal", "home", "\u79c1\u4eba", "\u4e2a\u4eba", "\u5bb6\u5ead"]
    return any(term in normalized for term in contact_terms) and any(term in normalized for term in private_terms)


def _has_sufficient_evidence(retrieved: list[RetrievedChunk]) -> bool:
    if not retrieved:
        return False
    top = retrieved[0]
    if len(top.matched_terms) < 1 and top.lexical_score <= 0:
        return False
    if top.lexical_score >= 0.3 and top.score >= 0.18:
        return True
    if top.vector_score >= 0.32 and top.score >= 0.16:
        return True
    return top.score >= 0.2 and top.lexical_score >= 0.08


def _retrieval_method(retrieved: list[RetrievedChunk]) -> str:
    if any(item.vector_backend == "pgvector" for item in retrieved):
        return PGVECTOR_RETRIEVAL_METHOD
    return JSON_RETRIEVAL_METHOD


def answer_rag_question(db: Session, question: str, top_k: int = 4) -> RAGAskResponse:
    if db.query(PolicyChunk).count() == 0:
        index_policy_documents(db, include_remote=get_settings().rag_include_remote_sources)

    retrieved = retrieve_chunks(db, question, top_k=top_k)
    retrieval_method = _retrieval_method(retrieved)
    if _asks_for_private_contact(question) or not _has_sufficient_evidence(retrieved):
        return RAGAskResponse(
            question=question,
            answer="I cannot answer confidently from the indexed policy documents.",
            citations=[],
            confidence=0.0,
            refused=True,
            retrieval_method=retrieval_method,
            generation_provider="none",
            query_plan=retrieved[0].query_plan if retrieved else None,
        )

    answer, provider = _compose_answer(question, retrieved)
    confidence = min(0.95, round(sum(item.score for item in retrieved[:3]) / max(1, min(3, len(retrieved))) * 2, 2))
    return RAGAskResponse(
        question=question,
        answer=answer,
        citations=[_citation(item) for item in retrieved],
        confidence=confidence,
        refused=False,
        retrieval_method=retrieval_method,
        generation_provider=provider,
        query_plan=retrieved[0].query_plan if retrieved else None,
    )
