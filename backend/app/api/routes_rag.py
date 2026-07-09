from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.schemas.rag import (
    KnowledgeGraphResponse,
    PrecomputedReindexRequest,
    RAGAskRequest,
    RAGAskResponse,
    RAGSourceInfo,
    ReindexJobResponse,
    ReindexRequest,
    ReindexResponse,
    VectorStoreInitResponse,
    VectorStoreSchemaResponse,
)
from app.services.rag.answerer import answer_rag_question
from app.services.rag.embeddings import embedding_runtime_label
from app.services.rag.indexer import import_precomputed_policy_documents, index_policy_documents
from app.services.rag.knowledge_graph import build_knowledge_graph
from app.services.rag.reindex_jobs import create_reindex_job, get_latest_reindex_job, get_reindex_job, run_reindex_job
from app.services.rag.source_loader import available_remote_sources
from app.services.rag.vector_store import describe_vector_store, initialize_pgvector_store
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


@router.post("/reindex/jobs", response_model=ReindexJobResponse)
def start_reindex_job(
    background_tasks: BackgroundTasks,
    request: ReindexRequest | None = None,
    db: Session = Depends(get_session),
) -> ReindexJobResponse:
    include_remote = True if request is None else request.include_remote
    max_311_articles = None if request is None else request.max_311_articles
    job = create_reindex_job(db, include_remote=include_remote, max_311_articles=max_311_articles)
    background_tasks.add_task(run_reindex_job, job["id"])
    return ReindexJobResponse(**job)


@router.get("/reindex/jobs/latest", response_model=ReindexJobResponse)
def latest_reindex_job(db: Session = Depends(get_session)) -> ReindexJobResponse:
    job = get_latest_reindex_job(db)
    if job is None:
        raise HTTPException(status_code=404, detail="No RAG reindex job has been created.")
    return ReindexJobResponse(**job)


@router.get("/reindex/jobs/{job_id}", response_model=ReindexJobResponse)
def reindex_job_status(job_id: int, db: Session = Depends(get_session)) -> ReindexJobResponse:
    job = get_reindex_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="RAG reindex job not found.")
    return ReindexJobResponse(**job)


@router.post("/reindex/precomputed", response_model=ReindexResponse)
def import_precomputed_reindex(
    request: PrecomputedReindexRequest,
    db: Session = Depends(get_session),
) -> ReindexResponse:
    try:
        result = import_precomputed_policy_documents(
            db,
            documents=[document.model_dump() for document in request.documents],
            embedding_provider=request.embedding_provider,
            embedding_model=request.embedding_model,
            dimensions=request.dimensions,
            warnings=request.warnings,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Precomputed RAG import failed.") from exc
    return ReindexResponse(
        documents_indexed=result.documents_indexed,
        chunks_indexed=result.chunks_indexed,
        local_sources_indexed=result.local_sources_indexed,
        remote_sources_indexed=result.remote_sources_indexed,
        embedding_provider=request.embedding_provider,
        embedding_model=request.embedding_model,
        warnings=result.warnings or [],
    )


@router.post("/ask", response_model=RAGAskResponse)
def ask_rag(request: RAGAskRequest, db: Session = Depends(get_session)) -> RAGAskResponse:
    try:
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
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="RAG ask failed.") from exc


@router.post("/vector-store/init", response_model=VectorStoreInitResponse)
def init_vector_store(db: Session = Depends(get_session)) -> VectorStoreInitResponse:
    return VectorStoreInitResponse(**initialize_pgvector_store(db))


@router.get("/vector-store/schema", response_model=VectorStoreSchemaResponse)
def vector_store_schema(db: Session = Depends(get_session)) -> VectorStoreSchemaResponse:
    return VectorStoreSchemaResponse(**describe_vector_store(db))


@router.get("/knowledge-graph", response_model=KnowledgeGraphResponse)
def rag_knowledge_graph(db: Session = Depends(get_session)) -> KnowledgeGraphResponse:
    return KnowledgeGraphResponse(**build_knowledge_graph(db))
