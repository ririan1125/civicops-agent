# CivicOps Agent Architecture

Source type: project architecture documentation.

## Product Scope

CivicOps Agent is an urban operations copilot for NYC 311 service request analysis. It combines structured operational data in SQL with document-grounded RAG so analysts can ask both metric questions and policy/process questions from one interface.

## Main Runtime Flow

1. The React frontend sends a question to the FastAPI backend.
2. The agent planner classifies the question as SQL analysis, RAG document QA, or clarification.
3. SQL questions use the service request database and a read-only SQL safety guard.
4. RAG questions retrieve indexed documentation chunks and generate an evidence-grounded answer.
5. Every tool run is recorded in the trace table for inspection and debugging.

## SQL Data Pipeline

The SQL pipeline handles structured NYC 311 service request records.

1. The backend calls the official NYC Open Data API endpoint for 311 service requests.
2. Raw JSON records are cleaned into stable columns such as `unique_key`, `created_date`, `closed_date`, `agency`, `complaint_type`, `borough`, `status`, `resolution_description`, `latitude`, and `longitude`.
3. Records are upserted into the `service_requests` table by `unique_key`.
4. Dashboard and SQL-agent endpoints query this table for counts, rankings, distributions, status breakdowns, and trends.
5. The backend validates generated SQL before execution. It allows a single read-only `SELECT`, blocks destructive keywords, blocks multiple statements, and enforces limits on row listings.

## RAG Document Pipeline

The RAG pipeline handles unstructured and semi-structured documentation.

1. Local project documents, local policy markdown files, official NYC311 pages, official NYC Open Data pages, Socrata dataset metadata, and optional official PDFs are loaded as document sources.
   The NYC311 loader also discovers official `article/?kanumber=KA-xxxxx` links from the NYC311 report-problems directory and indexes a bounded set of article pages.
2. Each source is converted to markdown-like text with a source title and source URL or local path.
3. The text is chunked by markdown headings and maximum character length.
4. Each chunk is embedded and written to `policy_chunks` and `policy_chunk_embeddings`.
5. A user question is embedded and compared with chunk embeddings.
6. Retrieval combines BM25 lexical scoring, vector similarity, query expansion, heading matches, and exact phrase signals.
7. If evidence is weak, the system refuses instead of guessing.
8. If evidence is strong, the backend sends the question and retrieved evidence to the configured chat provider and returns citations.

The current live refresh limit is controlled by `RAG_MAX_311_ARTICLES` and defaults to 120 official NYC311 article pages. The crawler uses bounded concurrency so a refresh can index a meaningful corpus without overwhelming the official source or the hosted backend.

## Routing Boundary

SQL is for questions about rows, counts, dates, boroughs, agencies, complaint types, statuses, and workload metrics.

RAG is for questions about system rules, safe SQL policy, tool execution rules, human approval, traceability, NYC311 service request process, dataset metadata, and open data governance guidance.

If a question mixes both, the planner chooses the most direct tool first. A production expansion could add a multi-step route that runs SQL first and then uses RAG to explain the result.

## Update Strategy

NYC 311 records change over time. The system supports manual imports and incremental sync. Incremental sync looks back over recent records and upserts them by `unique_key`, which captures new requests and status changes for recently created requests.

Official documentation can also change. The RAG reindex endpoint can refresh remote official sources and rebuild the chunk index. A scheduled workflow can call the data sync endpoint daily and the RAG reindex endpoint periodically.

## Current Production Tradeoffs

The public demo defaults to local deterministic embeddings and mock grounded generation when no external keys are configured. This keeps the public system reproducible without committing secrets. When API keys are configured, the same pipeline can use an external chat model and an OpenAI-compatible embedding service.

The current vector store uses JSON vectors and application-side cosine scoring. This is simple and portable for the demo. A larger production corpus should use pgvector or another vector database, background jobs, source freshness metadata, and authenticated admin endpoints.

Detailed Chinese implementation notes: [docs/ADVANCED_RAG_IMPLEMENTATION_CN.md](ADVANCED_RAG_IMPLEMENTATION_CN.md).
