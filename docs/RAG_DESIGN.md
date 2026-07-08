# RAG Design

Project: CivicOps Agent

## Scope

RAG is for policy, process, FAQ, metadata, source, governance, and project architecture questions. SQL is for structured NYC 311 metrics and row-level data analysis.

## Indexed Sources

- Local operating policy docs in `sample_data/policies/`.
- Project docs such as `README.md`, `docs/ARCHITECTURE.md`, and `docs/PROJECT_OVERVIEW_CN.md`.
- Local PDF/image assets under `sample_data/rag_assets/`.
- Official NYC311 service request pages.
- Official NYC311 article pages discovered from `https://portal.311.nyc.gov/report-problems/`.
- Official NYC 311 Socrata metadata from `https://data.cityofnewyork.us/api/views/erm2-nwe9`.
- Official NYC Open Data technical standards pages and optional PDFs.

## Pipeline

```text
source loading
  -> markdown-like normalization
  -> heading-aware chunking
  -> embedding
  -> policy_documents / policy_chunks / policy_chunk_embeddings
  -> optional pgvector mirror table
  -> hybrid retrieval
  -> evidence gate
  -> grounded answer with citations
```

## Chunking

Current implementation: `backend/app/services/rag/chunker.py`.

- Preserves Markdown headings as chunk metadata.
- Uses a default `900` character max chunk size.
- Uses `120` character overlap after splitting.
- Stores estimated token count for each chunk.

## Retrieval

Current retrieval method:

```text
query expansion
  -> query embedding
  -> pgvector vector recall if initialized
  -> JSON cosine fallback if pgvector is unavailable
  -> BM25 lexical scoring
  -> heading and phrase bonuses
  -> source-aware bonus
  -> lightweight knowledge-graph entity bonus
  -> MMR diversity selection
```

The retriever returns citations with hybrid score, vector score, vector backend, lexical score, matched terms, and graph entities.

## Vector Store

Portable fallback:

- `policy_chunk_embeddings.vector` JSON column
- application-side cosine scoring

PostgreSQL deployment:

- `rag_vector_embeddings.embedding vector(384)`
- HNSW index with `vector_cosine_ops`
- metadata JSONB with document title, source path, heading, chunk index, and logical partition

Inspect the live schema through:

```text
GET /rag/vector-store/schema
```

## Knowledge Graph

The current graph is a lightweight entity co-occurrence graph, not a separate graph database. It extracts:

- NYC311 article ids such as `KA-01066`;
- boroughs;
- common agencies such as NYPD, DSNY, DOT, HPD, DOB, DEP, DOHMH;
- service topics such as illegal parking, blocked driveway, noise, apartment maintenance, open data, safe SQL, and human approval.

Inspect it through:

```text
GET /rag/knowledge-graph
```

## Answer Rules

- Cite source chunks.
- Do not answer from general model knowledge when the question asks about indexed policy/process knowledge.
- Refuse when retrieved evidence is weak.
- Refuse private contact requests.
- Keep answers concise and grounded in retrieved evidence.

## Evaluation

Endpoints:

- `POST /evals/run`
- `POST /evals/rag-retrieval`
- `POST /evals/embedding-benchmark`

Metrics:

- SQL safety pass rate
- RAG citation and refusal rate
- Recall@1
- Recall@3
- Recall@5
- MRR

Additional dimensions to add later:

- citation precision
- faithfulness
- answer correctness
- latency
- cost
- prompt-injection resistance
- document freshness

## Boundaries

- Live deployment defaults to `local_hash` embedding unless an external embedding API is configured.
- Current multimodal support indexes PDF text and image OCR/caption text; true image embeddings require a multimodal embedding provider.
- Reindexing is synchronous and should become a background job for larger crawls.
- Admin-like endpoints need authentication before production use.
