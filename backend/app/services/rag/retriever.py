import math
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import PolicyChunk
from app.services.rag.embeddings import cosine_similarity, embed_query


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
    "what",
    "how",
    "should",
    "i",
    "me",
    "my",
    "我",
    "的",
    "是",
    "吗",
    "么",
    "什么",
    "怎么",
    "如何",
    "一下",
}


def tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]", text.lower())
    return {token for token in tokens if token not in STOPWORDS and len(token.strip()) > 0}


def _lexical_score(question_tokens: set[str], chunk_tokens: set[str]) -> tuple[float, list[str]]:
    if not question_tokens or not chunk_tokens:
        return 0.0, []
    matched = sorted(question_tokens & chunk_tokens)
    if not matched:
        return 0.0, []
    score = len(matched) / math.sqrt(len(question_tokens) * len(chunk_tokens))
    return round(score, 4), matched


def _heading_bonus(question_tokens: set[str], heading: str | None) -> float:
    if not heading:
        return 0.0
    heading_tokens = tokenize(heading)
    if not heading_tokens:
        return 0.0
    return 0.05 if question_tokens & heading_tokens else 0.0


def _phrase_bonus(question: str, content: str) -> float:
    normalized_question = "".join(re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]", question.lower()))
    normalized_content = "".join(re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]", content.lower()))
    if len(normalized_question) >= 4 and normalized_question in normalized_content:
        return 0.08
    return 0.0


def retrieve_chunks(db: Session, question: str, top_k: int = 4, candidate_pool: int = 20) -> list[RetrievedChunk]:
    question_tokens = tokenize(question)
    if not question_tokens:
        return []
    query_embedding = embed_query(question).vectors[0]
    chunks = db.query(PolicyChunk).all()
    scored: list[RetrievedChunk] = []
    for chunk in chunks:
        chunk_tokens = tokenize(chunk.content + " " + (chunk.heading or ""))
        lexical, matched_terms = _lexical_score(question_tokens, chunk_tokens)
        vector = cosine_similarity(query_embedding, chunk.embedding.vector if chunk.embedding else None)
        bonus = _heading_bonus(question_tokens, chunk.heading) + _phrase_bonus(question, chunk.content)
        score = round((0.55 * vector) + (0.35 * lexical) + bonus, 4)
        if score <= 0:
            continue
        scored.append(
            RetrievedChunk(
                chunk=chunk,
                score=score,
                lexical_score=lexical,
                vector_score=vector,
                matched_terms=matched_terms,
            )
        )
    candidates = sorted(scored, key=lambda item: item.score, reverse=True)[:candidate_pool]
    return candidates[:top_k]
