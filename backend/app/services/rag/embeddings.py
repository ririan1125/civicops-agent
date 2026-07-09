import hashlib
import math
import re
from dataclasses import dataclass
from functools import lru_cache

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


def embed_texts_local_hash(texts: list[str], dimensions: int) -> EmbeddingBatch:
    dimensions = max(64, dimensions)
    return EmbeddingBatch(
        provider="local_hash",
        model=f"local-hash-{dimensions}",
        dimensions=dimensions,
        vectors=[_local_hash_embedding(text, dimensions) for text in texts],
    )


def _api_embeddings(texts: list[str]) -> EmbeddingBatch:
    settings = get_settings()
    if not settings.embedding_base_url or not settings.embedding_api_key:
        raise EmbeddingProviderError("Embedding API requires EMBEDDING_BASE_URL and EMBEDDING_API_KEY.")

    headers = {"Authorization": f"Bearer {settings.embedding_api_key}"}
    batch_size = max(1, min(settings.embedding_batch_size, 256))
    vectors: list[list[float]] = []
    with httpx.Client(timeout=60) as client:
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            payload = {"model": settings.embedding_model, "input": batch}
            response = client.post(
                f"{settings.embedding_base_url.rstrip('/')}/v1/embeddings",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            vectors.extend(item["embedding"] for item in sorted(data["data"], key=lambda item: item["index"]))

    dimensions = len(vectors[0]) if vectors else 0
    return EmbeddingBatch(
        provider="api",
        model=settings.embedding_model,
        dimensions=dimensions,
        vectors=[_normalize([float(value) for value in vector]) for vector in vectors],
    )


@lru_cache(maxsize=4)
def _fastembed_model(model_name: str, cache_dir: str | None):
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise EmbeddingProviderError("BGE embeddings require the fastembed package.") from exc

    settings = get_settings()
    kwargs = {"model_name": model_name, "threads": max(1, settings.embedding_threads)}
    if cache_dir:
        kwargs["cache_dir"] = cache_dir
    try:
        return TextEmbedding(**kwargs)
    except TypeError:
        kwargs.pop("cache_dir", None)
        return TextEmbedding(**kwargs)


def _as_float_list(vector) -> list[float]:
    if hasattr(vector, "tolist"):
        vector = vector.tolist()
    return [float(value) for value in vector]


def _prepare_bge_text(text: str, *, is_query: bool) -> str:
    settings = get_settings()
    instruction = settings.embedding_query_instruction
    if is_query and instruction.strip() and not text.startswith(instruction):
        separator = "" if instruction[-1].isspace() else " "
        return f"{instruction}{separator}{text}"
    return text


def _bge_embeddings(texts: list[str], *, is_query: bool = False) -> EmbeddingBatch:
    settings = get_settings()
    model_name = settings.embedding_model or "BAAI/bge-small-en-v1.5"
    model = _fastembed_model(model_name, settings.embedding_cache_dir)
    batch_size = max(1, min(settings.embedding_batch_size, 128))
    prepared_texts = [_prepare_bge_text(text, is_query=is_query) for text in texts]
    vectors = [_normalize(_as_float_list(vector)) for vector in model.embed(prepared_texts, batch_size=batch_size)]
    dimensions = len(vectors[0]) if vectors else 0
    return EmbeddingBatch(provider="bge", model=model_name, dimensions=dimensions, vectors=vectors)


def embed_texts(texts: list[str]) -> EmbeddingBatch:
    settings = get_settings()
    provider = settings.embedding_provider.lower()
    if provider in {"api", "openai_compatible"}:
        return _api_embeddings(texts)
    if provider in {"bge", "fastembed"}:
        return _bge_embeddings(texts, is_query=False)

    return embed_texts_local_hash(texts, settings.embedding_dimensions)


def embed_query(text: str) -> EmbeddingBatch:
    settings = get_settings()
    provider = settings.embedding_provider.lower()
    if provider in {"api", "openai_compatible"}:
        return _api_embeddings([text])
    if provider in {"bge", "fastembed"}:
        return _bge_embeddings([text], is_query=True)
    return embed_texts_local_hash([text], settings.embedding_dimensions)


def embedding_runtime_label() -> tuple[str, str]:
    settings = get_settings()
    provider = settings.embedding_provider.lower()
    if provider in {"api", "openai_compatible"}:
        return provider, settings.embedding_model
    if provider in {"bge", "fastembed"}:
        return "bge", settings.embedding_model
    dimensions = max(64, settings.embedding_dimensions)
    return "local_hash", f"local-hash-{dimensions}"


def cosine_similarity(left: list[float] | None, right: list[float] | None) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    if size == 0:
        return 0.0
    return round(sum(left[index] * right[index] for index in range(size)), 4)
