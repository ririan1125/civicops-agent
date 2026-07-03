import hashlib
import math
import re
from dataclasses import dataclass

import httpx

from app.core.config import get_settings


TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]")


class EmbeddingProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class EmbeddingBatch:
    provider: str
    model: str
    dimensions: int
    vectors: list[list[float]]


def _tokens_and_ngrams(text: str) -> list[str]:
    tokens = TOKEN_PATTERN.findall(text.lower())
    features = list(tokens)
    for left, right in zip(tokens, tokens[1:]):
        features.append(f"{left}_{right}")
    compact = re.sub(r"\s+", "", text.lower())
    for index in range(max(0, len(compact) - 2)):
        features.append(compact[index : index + 3])
    return features


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [round(value / norm, 6) for value in vector]


def _local_hash_embedding(text: str, dimensions: int) -> list[float]:
    vector = [0.0] * dimensions
    for feature in _tokens_and_ngrams(text):
        digest = hashlib.sha256(feature.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[bucket] += sign
    return _normalize(vector)


def _api_embeddings(texts: list[str]) -> EmbeddingBatch:
    settings = get_settings()
    if not settings.embedding_base_url or not settings.embedding_api_key:
        raise EmbeddingProviderError("Embedding API requires EMBEDDING_BASE_URL and EMBEDDING_API_KEY.")

    payload = {"model": settings.embedding_model, "input": texts}
    headers = {"Authorization": f"Bearer {settings.embedding_api_key}"}
    with httpx.Client(timeout=60) as client:
        response = client.post(
            f"{settings.embedding_base_url.rstrip('/')}/v1/embeddings",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()

    data = response.json()
    vectors = [item["embedding"] for item in sorted(data["data"], key=lambda item: item["index"])]
    dimensions = len(vectors[0]) if vectors else 0
    return EmbeddingBatch(
        provider="api",
        model=settings.embedding_model,
        dimensions=dimensions,
        vectors=[_normalize([float(value) for value in vector]) for vector in vectors],
    )


def embed_texts(texts: list[str]) -> EmbeddingBatch:
    settings = get_settings()
    provider = settings.embedding_provider.lower()
    if provider == "api":
        return _api_embeddings(texts)

    dimensions = max(64, settings.embedding_dimensions)
    return EmbeddingBatch(
        provider="local_hash",
        model=f"local-hash-{dimensions}",
        dimensions=dimensions,
        vectors=[_local_hash_embedding(text, dimensions) for text in texts],
    )


def embed_query(text: str) -> EmbeddingBatch:
    return embed_texts([text])


def cosine_similarity(left: list[float] | None, right: list[float] | None) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    if size == 0:
        return 0.0
    return round(sum(left[index] * right[index] for index in range(size)), 4)
