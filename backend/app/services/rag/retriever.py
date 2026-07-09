import math
import re
from collections import Counter
from dataclasses import asdict
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload

from app.core.config import get_settings
from app.db.models import PolicyChunk
from app.services.rag.embeddings import EmbeddingProviderError, cosine_similarity, embed_query, embedding_runtime_label
from app.services.rag.knowledge_graph import extract_text_entities
from app.services.rag.query_planner import RAGQueryPlan, build_query_plan
from app.services.rag.reranker import heuristic_rerank_score
from app.services.rag.text_processing import tokenize
from app.services.rag.vector_store import search_pgvector


@dataclass
class RetrievedChunk:
    chunk: PolicyChunk
    score: float
    lexical_score: float
    vector_score: float
    matched_terms: list[str]
    vector_backend: str = "json"
    graph_entities: list[str] | None = None
    reranker_score: float = 0.0
    sparse_score: float = 0.0
    query_plan: dict | None = None


QUERY_EXPANSIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("\u670d\u52a1\u8bf7\u6c42", ("service", "request", "service request", "311")),
    ("\u67e5\u8be2\u72b6\u6001", ("check", "status", "service request status")),
    ("\u72b6\u6001", ("status", "service request status")),
    ("\u6295\u8bc9", ("complaint", "report", "problem")),
    ("\u566a\u97f3", ("noise", "neighbor", "residential")),
    ("\u505c\u8f66", ("parking", "illegal parking", "blocked driveway")),
    ("\u5783\u573e", ("garbage", "sanitation", "trash")),
    ("\u7ef4\u4fee", ("maintenance", "repair")),
    ("\u516c\u5bd3", ("apartment", "housing")),
    ("\u4f9b\u6696", ("heat", "hot water")),
    ("\u70ed\u6c34", ("hot water", "heat")),
    ("\u5f00\u653e\u6570\u636e", ("open data", "dataset", "metadata")),
    ("\u6570\u636e\u96c6", ("dataset", "metadata", "columns")),
    ("\u5b57\u6bb5", ("field", "column", "metadata")),
    ("\u653f\u7b56", ("policy", "governance", "standard")),
    ("\u6d41\u7a0b", ("process", "procedure", "request")),
    ("\u5f15\u7528", ("citation", "source", "evidence")),
    ("\u8bc1\u636e", ("evidence", "source", "citation")),
    ("sql", ("sql", "select", "query")),
    ("\u5b89\u5168", ("safety", "safe", "guardrail")),
)


def expand_query(question: str) -> str:
    normalized = question.lower()
    additions: list[str] = []
    for phrase, terms in QUERY_EXPANSIONS:
        if phrase.lower() in normalized:
            additions.extend(terms)
    if additions:
        return f"{question} {' '.join(additions)}"
    return question


def _chunk_tokens(chunk: PolicyChunk) -> list[str]:
    heading_tokens = tokenize(chunk.heading or "")
    content_tokens = tokenize(chunk.content)
    return heading_tokens * 3 + content_tokens


def _chunk_sparse_terms(chunk: PolicyChunk) -> dict[str, int]:
    sparse_terms = chunk.sparse_terms or {}
    if isinstance(sparse_terms, dict) and sparse_terms:
        return {str(term): int(count) for term, count in sparse_terms.items()}
    return Counter(_chunk_tokens(chunk))


def _bm25_score(
    query_terms: list[str],
    document_terms: list[str],
    document_frequency: Counter[str],
    doc_count: int,
    avg_doc_len: float,
) -> float:
    if not query_terms or not document_terms:
        return 0.0
    term_frequency = Counter(document_terms)
    doc_len = len(document_terms)
    k1 = 1.4
    b = 0.75
    score = 0.0
    for term in set(query_terms):
        frequency = term_frequency.get(term, 0)
        if frequency == 0:
            continue
        df = max(1, document_frequency.get(term, 0))
        idf = math.log(1 + (doc_count - df + 0.5) / (df + 0.5))
        denominator = frequency + k1 * (1 - b + b * doc_len / max(avg_doc_len, 1))
        score += idf * ((frequency * (k1 + 1)) / denominator)
    return round(score, 4)


def _heading_bonus(query_terms: set[str], heading: str | None) -> float:
    if not heading:
        return 0.0
    heading_terms = set(tokenize(heading))
    if not heading_terms:
        return 0.0
    overlap = query_terms & heading_terms
    return min(0.12, 0.04 * len(overlap))


def _phrase_bonus(question: str, content: str) -> float:
    normalized_question = " ".join(tokenize(question))
    normalized_content = " ".join(tokenize(content))
    if len(normalized_question) >= 8 and normalized_question in normalized_content:
        return 0.08
    bonus = 0.0
    for phrase, terms in QUERY_EXPANSIONS:
        if phrase in question and any(term in normalized_content for term in terms):
            bonus += 0.02
    return min(0.08, bonus)


def _graph_bonus(query_entities: set[str], chunk: PolicyChunk) -> tuple[float, list[str]]:
    if not query_entities:
        return 0.0, []
    document = chunk.document
    text = " ".join(
        [
            document.title if document else "",
            document.source_path if document and document.source_path else "",
            chunk.heading or "",
            chunk.content[:2000],
        ]
    )
    overlap = sorted(query_entities & extract_text_entities(text))
    return min(0.08, 0.03 * len(overlap)), overlap


def _source_bonus(question: str, chunk: PolicyChunk) -> float:
    document = chunk.document
    source_path = (document.source_path if document else "") or ""
    normalized_question = question.lower()
    if "311" in normalized_question and "portal.311.nyc.gov" in source_path:
        return 0.03
    if ("open data" in normalized_question or "dataset" in normalized_question) and (
        "data.cityofnewyork.us" in source_path or "opendata" in source_path or "cityofnewyork.github.io" in source_path
    ):
        return 0.03
    return 0.0


def _metadata_bonus(plan: RAGQueryPlan, chunk: PolicyChunk) -> float:
    metadata = chunk.chunk_metadata or {}
    bonus = 0.0
    prefer_partition = plan.filters.get("prefer_partition")
    if prefer_partition and metadata.get("logical_partition") == prefer_partition:
        bonus += 0.05
    if plan.filters.get("prefer_official") and metadata.get("is_remote"):
        bonus += 0.03
    return min(0.08, bonus)


def _matched_terms(query_terms: list[str], document_terms: list[str]) -> list[str]:
    return sorted(set(query_terms) & set(document_terms))


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _select_diverse(candidates: list[RetrievedChunk], tokenized_by_chunk_id: dict[int, set[str]], top_k: int) -> list[RetrievedChunk]:
    if top_k <= 0:
        return []
    selected: list[RetrievedChunk] = []
    remaining = list(candidates)
    per_document: Counter[int] = Counter()
    max_per_document = max(1, min(2, top_k))

    while remaining and len(selected) < top_k:
        allowed = [
            item
            for item in remaining
            if per_document[item.chunk.document_id] < max_per_document
        ] or remaining

        def mmr_score(item: RetrievedChunk) -> float:
            item_tokens = tokenized_by_chunk_id.get(item.chunk.id, set())
            redundancy = max(
                (_jaccard(item_tokens, tokenized_by_chunk_id.get(chosen.chunk.id, set())) for chosen in selected),
                default=0.0,
            )
            same_document_penalty = 0.04 * per_document[item.chunk.document_id]
            return round((0.78 * item.score) - (0.18 * redundancy) - same_document_penalty, 6)

        chosen = max(allowed, key=mmr_score)
        selected.append(chosen)
        per_document[chosen.chunk.document_id] += 1
        remaining.remove(chosen)

    return selected


def retrieve_chunks(db: Session, question: str, top_k: int = 4, candidate_pool: int = 60) -> list[RetrievedChunk]:
    settings = get_settings()
    plan = build_query_plan(question)
    expanded_question = expand_query(plan.rewritten_query)
    query_terms = tokenize(expanded_question)
    if not query_terms:
        return []

    try:
        query_batch = embed_query(expanded_question)
        query_embedding = query_batch.vectors[0]
        runtime_provider, runtime_model = query_batch.provider, query_batch.model
    except EmbeddingProviderError:
        query_embedding = []
        runtime_provider, runtime_model = embedding_runtime_label()

    pgvector_scores = search_pgvector(db, query_embedding, limit=max(candidate_pool * 4, top_k * 10)) if query_embedding else {}
    vector_backend = "pgvector" if pgvector_scores else "json"
    chunks = db.query(PolicyChunk).options(joinedload(PolicyChunk.embedding), joinedload(PolicyChunk.document)).all()
    if not chunks:
        return []

    tokenized_chunks = [_chunk_tokens(chunk) for chunk in chunks]
    tokenized_by_chunk_id = {
        chunk.id: set(tokens)
        for chunk, tokens in zip(chunks, tokenized_chunks)
    }
    doc_count = len(tokenized_chunks)
    avg_doc_len = sum(len(tokens) for tokens in tokenized_chunks) / max(doc_count, 1)
    document_frequency: Counter[str] = Counter()
    for tokens in tokenized_chunks:
        document_frequency.update(set(tokens))

    raw_items: list[tuple[PolicyChunk, float, float, list[str], float, float, float, list[str], float, float, float]] = []
    max_bm25 = 0.0
    query_term_set = set(query_terms)
    query_entities = extract_text_entities(expanded_question)
    for chunk, chunk_terms in zip(chunks, tokenized_chunks):
        bm25 = _bm25_score(query_terms, chunk_terms, document_frequency, doc_count, avg_doc_len)
        max_bm25 = max(max_bm25, bm25)
        if pgvector_scores:
            vector = pgvector_scores.get(chunk.id, 0.0)
        else:
            stored_vector = None
            if (
                query_embedding
                and chunk.embedding
                and chunk.embedding.provider == runtime_provider
                and chunk.embedding.model == runtime_model
            ):
                stored_vector = chunk.embedding.vector
            vector = cosine_similarity(query_embedding, stored_vector)
        matched = _matched_terms(query_terms, chunk_terms)
        heading_bonus = _heading_bonus(query_term_set, chunk.heading)
        phrase_bonus = _phrase_bonus(question, chunk.content)
        graph_bonus, graph_entities = _graph_bonus(query_entities, chunk)
        source_bonus = _source_bonus(expanded_question, chunk)
        metadata_bonus = _metadata_bonus(plan, chunk)
        sparse_terms = _chunk_sparse_terms(chunk)
        sparse_overlap = sum(sparse_terms.get(term, 0) for term in set(query_terms))
        sparse_score = min(1.0, sparse_overlap / max(1, len(set(query_terms)) * 2))
        raw_items.append(
            (
                chunk,
                bm25,
                vector,
                matched,
                heading_bonus,
                phrase_bonus,
                graph_bonus,
                graph_entities,
                source_bonus,
                metadata_bonus,
                sparse_score,
            )
        )

    scored: list[RetrievedChunk] = []
    for (
        chunk,
        bm25,
        vector,
        matched,
        heading_bonus,
        phrase_bonus,
        graph_bonus,
        graph_entities,
        source_bonus,
        metadata_bonus,
        sparse_score,
    ) in raw_items:
        lexical = round(bm25 / max_bm25, 4) if max_bm25 > 0 else 0.0
        match_density = len(matched) / max(1, len(set(query_terms)))
        reranker_score = (
            heuristic_rerank_score(
                question=question,
                heading=chunk.heading,
                content=chunk.content,
                document_title=chunk.document.title if chunk.document else "",
                metadata=chunk.chunk_metadata,
                matched_terms=matched,
                plan=plan,
            )
            if settings.rag_reranker_enabled
            else 0.0
        )
        score = round(
            (settings.rag_vector_weight * vector)
            + (settings.rag_lexical_weight * lexical)
            + (settings.rag_sparse_weight * max(match_density, sparse_score))
            + (settings.rag_reranker_weight * reranker_score)
            + heading_bonus
            + phrase_bonus
            + graph_bonus
            + metadata_bonus
            + source_bonus,
            4,
        )
        if score <= 0:
            continue
        scored.append(
            RetrievedChunk(
                chunk=chunk,
                score=score,
                lexical_score=lexical,
                vector_score=vector,
                matched_terms=matched[:12],
                vector_backend=vector_backend,
                graph_entities=graph_entities,
                reranker_score=reranker_score,
                sparse_score=round(sparse_score, 4),
                query_plan=asdict(plan),
            )
        )

    candidates = sorted(scored, key=lambda item: item.score, reverse=True)[:candidate_pool]
    return _select_diverse(candidates, tokenized_by_chunk_id, top_k)
