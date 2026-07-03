from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.schemas.rag import RAGAskRequest, RAGAskResponse, RAGSourceInfo, ReindexRequest, ReindexResponse
from app.services.rag.answerer import answer_rag_question
from app.services.rag.embeddings import embedding_runtime_label
from app.services.rag.indexer import index_policy_documents
from app.services.rag.source_loader import available_remote_sources
from app.services.tracing.trace_service import record_trace, timed_call

router = APIRouter(prefix="/rag", tags=["rag"])


@router.get("/sources", response_model=list[RAGSourceInfo])
def rag_sources() -> list[RAGSourceInfo]:
    return [RAGSourceInfo(**source) for source in available_remote_sources()]


@router.post("/reindex", response_model=ReindexResponse)
def reindex_policy_docs(
    request: ReindexRequest | None = None,
    db: Session = Depends(get_session),
) -> ReindexResponse:
    include_remote = True if request is None else request.include_remote
    max_311_articles = None if request is None else request.max_311_articles
    result = index_policy_documents(db, include_remote=include_remote, max_311_articles=max_311_articles)
    embedding_provider, embedding_model = embedding_runtime_label()
    return ReindexResponse(
        documents_indexed=result.documents_indexed,
        chunks_indexed=result.chunks_indexed,
        local_sources_indexed=result.local_sources_indexed,
        remote_sources_indexed=result.remote_sources_indexed,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
        warnings=result.warnings or [],
    )


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
