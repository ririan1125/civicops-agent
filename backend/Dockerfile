FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

ENV EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
ENV EMBEDDING_CACHE_DIR=/app/.cache/fastembed
RUN python -c "from fastembed import TextEmbedding; model = TextEmbedding(model_name='BAAI/bge-small-en-v1.5', cache_dir='/app/.cache/fastembed', threads=1); list(model.embed(['civicops bge warmup'], batch_size=1))"

COPY backend/app /app/backend/app
COPY sample_data /app/sample_data
COPY evals /app/evals
COPY README.md /app/README.md
COPY docs /app/docs

WORKDIR /app/backend

EXPOSE 8000
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
