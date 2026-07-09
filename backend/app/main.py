from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_agent import router as agent_router
from app.api.routes_dashboard import router as dashboard_router
from app.api.routes_evals import router as evals_router
from app.api.routes_health import router as health_router
from app.api.routes_ingestion import router as ingestion_router
from app.api.routes_rag import router as rag_router
from app.api.routes_traces import router as traces_router
from app.core.config import get_settings
from app.db.schema_compat import ensure_rag_v2_columns
from app.db.session import init_db
from app.db.session import SessionLocal


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        ensure_rag_v2_columns(db)
    finally:
        db.close()
    yield


settings = get_settings()

app = FastAPI(
    title="CivicOps Agent API",
    version=settings.app_version,
    description="Urban service request analytics, safe SQL agent, RAG assistant, and execution tracing.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(ingestion_router)
app.include_router(dashboard_router)
app.include_router(agent_router)
app.include_router(rag_router)
app.include_router(traces_router)
app.include_router(evals_router)


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    return {
        "service": "civicops-api",
        "message": "Open /docs for the API reference.",
        "version": settings.app_version,
    }
