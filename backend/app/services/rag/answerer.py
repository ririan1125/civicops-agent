import re

from sqlalchemy.orm import Session

from app.db.models import PolicyChunk
from app.schemas.rag import Citation, RAGAskResponse
from app.services.llm.providers import optional_deepseek_completion
from app.services.rag.indexer import index_policy_documents
from app.services.rag.retriever import RetrievedChunk, retrieve_chunks


def _snippet(text: str, max_chars: int = 260) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3] + "..."


def _citation(item: RetrievedChunk) -> Citation:
    document = item.chunk.document
    return Citation(
        document_title=document.title,
        chunk_id=item.chunk.id,
        heading=item.chunk.heading,
        snippet=_snippet(item.chunk.content),
        score=item.score,
    )


def _compose_answer(question: str, retrieved: list[RetrievedChunk]) -> str:
    evidence = " ".join(_snippet(item.chunk.content, 220) for item in retrieved[:2])
    llm_answer = optional_deepseek_completion(
        system_prompt=(
            "You are a civic operations assistant. Answer only from the provided evidence. "
            "If evidence is insufficient, say you cannot answer confidently from the indexed documents."
        ),
        user_prompt=f"Question: {question}\n\nEvidence:\n{evidence}",
    )
    if llm_answer:
        return llm_answer
    return (
        "Based on the indexed policy/process documents, the relevant guidance is: "
        f"{evidence} "
        "Use the citations below to inspect the exact supporting chunks."
    )


def answer_rag_question(db: Session, question: str, top_k: int = 4) -> RAGAskResponse:
    if db.query(PolicyChunk).count() == 0:
        index_policy_documents(db)

    retrieved = retrieve_chunks(db, question, top_k=top_k)
    if not retrieved or retrieved[0].score < 0.04:
        return RAGAskResponse(
            question=question,
            answer="I cannot answer confidently from the indexed policy documents.",
            citations=[],
            confidence=0.0,
            refused=True,
        )

    confidence = min(0.95, round(sum(item.score for item in retrieved[:3]) / max(1, min(3, len(retrieved))) * 3, 2))
    return RAGAskResponse(
        question=question,
        answer=_compose_answer(question, retrieved),
        citations=[_citation(item) for item in retrieved],
        confidence=confidence,
        refused=False,
    )
