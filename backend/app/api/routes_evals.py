from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.schemas.evals import EvalRunResponse
from app.services.evals.eval_runner import run_all_evals

router = APIRouter(prefix="/evals", tags=["evals"])


@router.post("/run", response_model=EvalRunResponse)
def run_evals(db: Session = Depends(get_session)) -> EvalRunResponse:
    return run_all_evals(db)
