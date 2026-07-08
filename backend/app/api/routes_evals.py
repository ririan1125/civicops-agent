from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.schemas.evals import EvalRunResponse, RAGRetrievalEvalResponse
from app.services.evals.eval_runner import run_all_evals, run_rag_retrieval_eval

router = APIRouter(prefix="/evals", tags=["evals"])


@router.post("/run", response_model=EvalRunResponse)
def run_evals(db: Session = Depends(get_session)) -> EvalRunResponse:
    return run_all_evals(db)


@router.post("/rag-retrieval", response_model=RAGRetrievalEvalResponse)
def run_rag_retrieval_evals(db: Session = Depends(get_session)) -> RAGRetrievalEvalResponse:
    return run_rag_retrieval_eval(db)


@router.post("/embedding-benchmark", response_model=RAGRetrievalEvalResponse)
def run_embedding_benchmark(db: Session = Depends(get_session)) -> RAGRetrievalEvalResponse:
    return run_rag_retrieval_eval(db)
