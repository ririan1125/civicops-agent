from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.schemas.agent import AgentRouteRequest, AgentRouteResponse, SQLQuestionRequest, SQLQuestionResponse
from app.services.agent.router import route_question
from app.services.rag.answerer import answer_rag_question
from app.services.sql_agent.safety import SQLSafetyError
from app.services.sql_agent.sql_tool import run_safe_select, summarize_sql_result
from app.services.sql_agent.text_to_sql import plan_sql
from app.services.tracing.trace_service import record_trace, timed_call

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/sql", response_model=SQLQuestionResponse)
def ask_sql_agent(request: SQLQuestionRequest, db: Session = Depends(get_session)) -> SQLQuestionResponse:
    planned = plan_sql(request.question)

    try:
        result, latency_ms = timed_call(lambda: run_safe_select(db, planned.sql))
        answer = summarize_sql_result(request.question, planned.sql, result)
        response = SQLQuestionResponse(
            question=request.question,
            generated_sql=planned.sql,
            confidence=planned.confidence,
            assumptions=planned.assumptions,
            result=result,
            answer=answer,
        )
        trace = record_trace(
            db,
            user_query=request.question,
            route="sql",
            selected_tool="safe_sql_analysis",
            tool_input={"sql": planned.sql, "assumptions": planned.assumptions},
            tool_output=response.model_dump(),
            status="success",
            latency_ms=latency_ms,
        )
        response.trace_id = trace.id
        return response
    except SQLSafetyError as exc:
        trace = record_trace(
            db,
            user_query=request.question,
            route="sql",
            selected_tool="safe_sql_analysis",
            tool_input={"sql": planned.sql},
            tool_output=None,
            status="blocked",
            latency_ms=0,
            error_message=str(exc),
        )
        raise HTTPException(status_code=400, detail={"message": str(exc), "trace_id": trace.id}) from exc


@router.post("/route", response_model=AgentRouteResponse)
def route_and_answer(request: AgentRouteRequest, db: Session = Depends(get_session)) -> AgentRouteResponse:
    decision = route_question(request.question)
    if decision.route == "sql":
        sql_response = ask_sql_agent(SQLQuestionRequest(question=request.question), db)
        return AgentRouteResponse(
            route="sql",
            reason=decision.reason,
            response=sql_response.model_dump(),
            selected_tool=decision.selected_tool,
            planner_provider=decision.planner_provider,
            plan_steps=decision.steps,
            confidence=decision.confidence,
            trace_id=sql_response.trace_id,
        )
    if decision.route == "rag":
        rag_response = answer_rag_question(db, request.question)
        trace = record_trace(
            db,
            user_query=request.question,
            route="rag",
            selected_tool=decision.selected_tool,
            tool_input={
                "question": request.question,
                "planner_provider": decision.planner_provider,
                "plan_steps": decision.steps,
            },
            tool_output=rag_response.model_dump(),
            status="refused" if rag_response.refused else "success",
            latency_ms=0,
        )
        rag_response.trace_id = trace.id
        return AgentRouteResponse(
            route="rag",
            reason=decision.reason,
            response=rag_response.model_dump(),
            selected_tool=decision.selected_tool,
            planner_provider=decision.planner_provider,
            plan_steps=decision.steps,
            confidence=decision.confidence,
            trace_id=trace.id,
        )

    trace = record_trace(
        db,
        user_query=request.question,
        route="clarify",
        selected_tool=decision.selected_tool,
        tool_input={
            "question": request.question,
            "planner_provider": decision.planner_provider,
            "plan_steps": decision.steps,
        },
        tool_output={"message": "Please clarify whether you need a metric from the database or an answer from policy documents."},
        status="needs_clarification",
        latency_ms=0,
    )
    return AgentRouteResponse(
        route="clarify",
        reason=decision.reason,
        response={"message": "Please clarify whether you need SQL metrics or RAG policy evidence."},
        selected_tool=decision.selected_tool,
        planner_provider=decision.planner_provider,
        plan_steps=decision.steps,
        confidence=decision.confidence,
        trace_id=trace.id,
    )
