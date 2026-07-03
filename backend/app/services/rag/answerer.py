import re

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import PolicyChunk
from app.schemas.rag import Citation, RAGAskResponse
from app.services.llm.providers import complete_chat
from app.services.rag.indexer import index_policy_documents
from app.services.rag.retriever import RetrievedChunk, retrieve_chunks


RETRIEVAL_METHOD = "hybrid_bm25_vector_rerank"


def _snippet(text: str, max_chars: int = 260) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3] + "..."


def _citation(item: RetrievedChunk) -> Citation:
    document = item.chunk.document
    source_url = document.source_path if document.source_path and document.source_path.startswith("http") else None
    return Citation(
        document_title=document.title,
        chunk_id=item.chunk.id,
        heading=item.chunk.heading,
        source_url=source_url,
        snippet=_snippet(item.chunk.content),
        score=item.score,
        lexical_score=item.lexical_score,
        vector_score=item.vector_score,
        matched_terms=item.matched_terms,
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
    contact_terms = ["phone", "email", "address", "contact", "telephone", "手机", "电话", "邮箱", "地址", "联系方式"]
    private_terms = ["private", "personal", "home", "私人", "个人", "家庭"]
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


def answer_rag_question(db: Session, question: str, top_k: int = 4) -> RAGAskResponse:
    if db.query(PolicyChunk).count() == 0:
        index_policy_documents(db, include_remote=get_settings().rag_include_remote_sources)

    retrieved = retrieve_chunks(db, question, top_k=top_k)
    if _asks_for_private_contact(question) or not _has_sufficient_evidence(retrieved):
        return RAGAskResponse(
            question=question,
            answer="I cannot answer confidently from the indexed policy documents.",
            citations=[],
            confidence=0.0,
            refused=True,
            retrieval_method=RETRIEVAL_METHOD,
            generation_provider="none",
        )

    answer, provider = _compose_answer(question, retrieved)
    confidence = min(0.95, round(sum(item.score for item in retrieved[:3]) / max(1, min(3, len(retrieved))) * 2, 2))
    return RAGAskResponse(
        question=question,
        answer=answer,
        citations=[_citation(item) for item in retrieved],
        confidence=confidence,
        refused=False,
        retrieval_method=RETRIEVAL_METHOD,
        generation_provider=provider,
    )
