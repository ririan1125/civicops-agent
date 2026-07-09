import argparse
import json
import os
import sys
from pathlib import Path

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.rag.chunker import chunk_markdown
from app.services.rag.embeddings import embed_texts
from app.services.rag.source_loader import load_document_sources


DEFAULT_API_BASE = "https://civicops-agent-api-ririan1125.onrender.com"


def build_payload(include_remote: bool, max_311_articles: int | None) -> dict:
    loaded = load_document_sources(include_remote=include_remote, max_311_articles=max_311_articles)
    documents: list[dict] = []
    embedding_provider = ""
    embedding_model = ""
    dimensions = 0

    for source_index, source in enumerate(loaded.sources, start=1):
        chunks = chunk_markdown(source.content)
        if not chunks:
            continue
        embedding_inputs = [f"{chunk.heading or ''}\n{chunk.content}" for chunk in chunks]
        embeddings = embed_texts(embedding_inputs)
        embedding_provider = embeddings.provider
        embedding_model = embeddings.model
        dimensions = embeddings.dimensions
        documents.append(
            {
                "title": source.title,
                "source_path": source.source_path,
                "source_type": source.source_type,
                "chunks": [
                    {
                        "heading": chunk.heading,
                        "content": chunk.content,
                        "token_count": chunk.token_count,
                        "embedding": embeddings.vectors[index],
                    }
                    for index, chunk in enumerate(chunks)
                ],
            }
        )
        print(
            f"[{source_index}/{len(loaded.sources)}] {source.title}: "
            f"{len(chunks)} chunks embedded with {embeddings.provider}/{embeddings.model}",
            flush=True,
        )

    return {
        "embedding_provider": embedding_provider,
        "embedding_model": embedding_model,
        "dimensions": dimensions,
        "documents": documents,
        "warnings": loaded.warnings,
    }


def upload_payload(api_base: str, payload: dict, timeout_seconds: int) -> dict:
    url = f"{api_base.rstrip('/')}/rag/reindex/precomputed"
    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a BGE RAG index locally and upload it to CivicOps API.")
    parser.add_argument("--api-base", default=os.getenv("API_BASE_URL", DEFAULT_API_BASE))
    parser.add_argument("--max-311-articles", type=int, default=120)
    parser.add_argument("--skip-remote", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--write-payload", type=Path)
    parser.add_argument("--no-upload", action="store_true")
    args = parser.parse_args()

    payload = build_payload(include_remote=not args.skip_remote, max_311_articles=args.max_311_articles)
    print(
        "Built payload:",
        json.dumps(
            {
                "documents": len(payload["documents"]),
                "chunks": sum(len(document["chunks"]) for document in payload["documents"]),
                "embedding_provider": payload["embedding_provider"],
                "embedding_model": payload["embedding_model"],
                "dimensions": payload["dimensions"],
                "warnings": len(payload["warnings"]),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    if args.write_payload:
        args.write_payload.parent.mkdir(parents=True, exist_ok=True)
        args.write_payload.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote payload to {args.write_payload}", flush=True)

    if args.no_upload:
        return

    result = upload_payload(args.api_base, payload, args.timeout_seconds)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
