from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import AgentTrace
from app.db.session import get_session
from app.schemas.traces import TraceRecord

router = APIRouter(prefix="/traces", tags=["traces"])


@router.get("", response_model=list[TraceRecord])
def list_traces(limit: int = 50, db: Session = Depends(get_session)) -> list[AgentTrace]:
    return db.query(AgentTrace).order_by(AgentTrace.created_at.desc()).limit(min(limit, 200)).all()


@router.get("/{trace_id}", response_model=TraceRecord)
def get_trace(trace_id: int, db: Session = Depends(get_session)) -> AgentTrace:
    trace = db.get(AgentTrace, trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace
