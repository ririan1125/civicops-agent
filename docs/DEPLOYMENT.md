# Deployment

Project: CivicOps Agent

## Live Services

- Frontend: https://ririan1125.github.io/civicops-agent/
- Backend API: https://civicops-agent-api-ririan1125.onrender.com
- Backend docs: https://civicops-agent-api-ririan1125.onrender.com/docs
- Repository: https://github.com/ririan1125/civicops-agent

## Backend

The backend is deployed on Render from `render.yaml`.

Render service:

```text
civicops-agent-api-ririan1125
```

Render database:

```text
civicops-agent-db
```

Runtime:

- Docker
- FastAPI
- PostgreSQL
- pgvector initialized through `POST /rag/vector-store/init`

Important environment variables:

```text
DATABASE_URL=<from Render database>
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=<Render secret, sync disabled>
EMBEDDING_PROVIDER=bge
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_API_KEY=<Render secret, sync disabled when used>
RAG_INCLUDE_REMOTE_SOURCES=true
RAG_MAX_311_ARTICLES=120
INGESTION_SYNC_LIMIT=5000
INGESTION_SYNC_LOOKBACK_DAYS=7
```

Secrets are configured in Render only and must not be committed to GitHub.

## Frontend

The frontend is deployed through GitHub Pages.

Build output:

```text
frontend/dist
```

The live frontend uses:

```text
VITE_API_BASE_URL=https://civicops-agent-api-ririan1125.onrender.com
```

## Data Refresh

SQL data is refreshed by:

```text
POST /ingestion/sync-latest
```

RAG documents are refreshed by:

```text
POST /rag/reindex/jobs
GET /rag/reindex/jobs/{job_id}
POST /rag/vector-store/init
```

For full BGE corpus refreshes on small Render instances, prefer local or CI precomputation:

```powershell
.\backend\.venv\Scripts\python backend\scripts\build_and_upload_rag_index.py `
  --api-base https://civicops-agent-api-ririan1125.onrender.com `
  --max-311-articles 120
```

That script uses the same open-source BGE model locally, uploads documents, chunks, and vectors through `POST /rag/reindex/precomputed`, and lets the deployed API backfill pgvector.

Automation:

```text
.github/workflows/daily-data-sync.yml
```

- Daily: sync latest NYC 311 records.
- Weekly on Monday UTC: start a background RAG refresh, poll the job until success, and rebuild/check the pgvector mirror.

## Manual Verification

Health:

```powershell
curl.exe https://civicops-agent-api-ririan1125.onrender.com/health
```

RAG retrieval eval:

```powershell
curl.exe -X POST https://civicops-agent-api-ririan1125.onrender.com/evals/rag-retrieval
```

Vector store schema:

```powershell
curl.exe https://civicops-agent-api-ririan1125.onrender.com/rag/vector-store/schema
```

Frontend:

```text
https://ririan1125.github.io/civicops-agent/
```

## Production Boundaries

- Render free tier can sleep and has resource limits.
- Public admin-like endpoints should be protected before real production use.
- Reindexing supports a background job endpoint and a precomputed-index import path. Full-corpus BGE indexing is safer from a local machine or CI runner than from a small free web instance.
- Live embedding defaults to the open-source `BAAI/bge-small-en-v1.5` model through FastEmbed/ONNX, with the model cache preloaded into the Docker image.
