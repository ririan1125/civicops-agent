from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.schemas.rag import RAGAskRequest, RAGAskResponse, ReindexResponse
from app.services.rag.answerer import answer_rag_question
from app.services.rag.indexer import index_policy_documents
from app.services.tracing.trace_service import record_trace, timed_call

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/reindex", response_model=ReindexResponse)
def reindex_policy_docs(db: Session = Depends(get_session)) -> ReindexResponse:
    documents, chunks = index_policy_documents(db)
    return ReindexResponse(documents_indexed=documents, chunks_indexed=chunks)


@router.post("/ask", response_model=RAGAskResponse)
def ask_rag(request: RAGAskRequest, db: Session = Depends(get_session)) -> RAGAskResponse:
    response, latency_ms = timed_call(lambda: answer_rag_question(db, request.question, top_k=request.top_k))
    trace = record_trace(
        db,
        user_query=request.question,
        route="rag",
        selected_tool="rag_policy_assistant",
        tool_input=request.model_dump(),
        tool_output=response.model_dump(),
        status="refused" if response.refused else "success",
        latency_ms=latency_ms,
    )
    response.trace_id = trace.id
    return response
