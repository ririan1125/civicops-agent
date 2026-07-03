import math
import re
from collections import Counter
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import PolicyChunk
from app.services.rag.embeddings import EmbeddingProviderError, cosine_similarity, embed_query


@dataclass
class RetrievedChunk:
    chunk: PolicyChunk
    score: float
    lexical_score: float
    vector_score: float
    matched_terms: list[str]


STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "in",
    "for",
    "is",
    "are",
    "be",
    "with",
    "by",
    "on",
    "from",
    "what",
    "how",
    "why",
    "when",
    "where",
    "which",
    "should",
    "can",
    "do",
    "does",
    "i",
    "me",
    "my",
    "you",
    "your",
    "请",
    "我",
    "的",
    "了",
    "是",
    "吗",
    "么",
    "什么",
    "怎么",
    "如何",
    "一个",
}


QUERY_EXPANSIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("服务请求", ("service", "request", "service request", "311")),
    ("查询状态", ("check", "status", "service request status")),
    ("状态", ("status", "service request status")),
    ("投诉", ("complaint", "report", "problem")),
    ("噪音", ("noise", "neighbor", "residential")),
    ("停车", ("parking", "illegal parking", "blocked driveway")),
    ("垃圾", ("garbage", "sanitation", "trash")),
    ("维修", ("maintenance", "repair")),
    ("公寓", ("apartment", "housing")),
    ("供暖", ("heat", "hot water")),
    ("热水", ("hot water", "heat")),
    ("开放数据", ("open data", "dataset", "metadata")),
    ("数据集", ("dataset", "metadata", "columns")),
    ("字段", ("field", "column", "metadata")),
    ("政策", ("policy", "governance", "standard")),
    ("流程", ("process", "procedure", "request")),
    ("引用", ("citation", "source", "evidence")),
    ("证据", ("evidence", "source", "citation")),
    ("sql", ("sql", "select", "query")),
    ("安全", ("safety", "safe", "guardrail")),
)


TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]+")


def expand_query(question: str) -> str:
    normalized = question.lower()
    additions: list[str] = []
    for phrase, terms in QUERY_EXPANSIONS:
        if phrase.lower() in normalized:
            additions.extend(terms)
    if additions:
        return f"{question} {' '.join(additions)}"
    return question


def tokenize(text: str) -> list[str]:
    raw_tokens = TOKEN_PATTERN.findall(text.lower())
    tokens: list[str] = []
    for token in raw_tokens:
        if token in STOPWORDS:
            continue
        if len(token.strip()) == 0:
            continue
        tokens.append(token)
    return tokens


def _chunk_tokens(chunk: PolicyChunk) -> list[str]:
    heading_tokens = tokenize(chunk.heading or "")
    content_tokens = tokenize(chunk.content)
    return heading_tokens * 3 + content_tokens


def _bm25_score(query_terms: list[str], document_terms: list[str], document_frequency: Counter[str], doc_count: int, avg_doc_len: float) -> float:
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


def _matched_terms(query_terms: list[str], document_terms: list[str]) -> list[str]:
    return sorted(set(query_terms) & set(document_terms))


def retrieve_chunks(db: Session, question: str, top_k: int = 4, candidate_pool: int = 60) -> list[RetrievedChunk]:
    expanded_question = expand_query(question)
    query_terms = tokenize(expanded_question)
    if not query_terms:
        return []

    try:
        query_embedding = embed_query(expanded_question).vectors[0]
    except EmbeddingProviderError:
        query_embedding = []

    chunks = db.query(PolicyChunk).all()
    if not chunks:
        return []

    tokenized_chunks = [_chunk_tokens(chunk) for chunk in chunks]
    doc_count = len(tokenized_chunks)
    avg_doc_len = sum(len(tokens) for tokens in tokenized_chunks) / max(doc_count, 1)
    document_frequency: Counter[str] = Counter()
    for tokens in tokenized_chunks:
        document_frequency.update(set(tokens))

    raw_items: list[tuple[PolicyChunk, list[str], float, float, list[str], float, float]] = []
    max_bm25 = 0.0
    query_term_set = set(query_terms)
    for chunk, chunk_terms in zip(chunks, tokenized_chunks):
        bm25 = _bm25_score(query_terms, chunk_terms, document_frequency, doc_count, avg_doc_len)
        max_bm25 = max(max_bm25, bm25)
        vector = cosine_similarity(query_embedding, chunk.embedding.vector if query_embedding and chunk.embedding else None)
        matched = _matched_terms(query_terms, chunk_terms)
        heading_bonus = _heading_bonus(query_term_set, chunk.heading)
        phrase_bonus = _phrase_bonus(question, chunk.content)
        raw_items.append((chunk, chunk_terms, bm25, vector, matched, heading_bonus, phrase_bonus))

    scored: list[RetrievedChunk] = []
    for chunk, chunk_terms, bm25, vector, matched, heading_bonus, phrase_bonus in raw_items:
        lexical = round(bm25 / max_bm25, 4) if max_bm25 > 0 else 0.0
        match_density = len(matched) / max(1, len(set(query_terms)))
        score = round((0.42 * vector) + (0.42 * lexical) + (0.08 * match_density) + heading_bonus + phrase_bonus, 4)
        if score <= 0:
            continue
        scored.append(
            RetrievedChunk(
                chunk=chunk,
                score=score,
                lexical_score=lexical,
                vector_score=vector,
                matched_terms=matched[:12],
            )
        )

    candidates = sorted(scored, key=lambda item: item.score, reverse=True)[:candidate_pool]
    return candidates[:top_k]
