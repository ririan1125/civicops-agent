import math
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import PolicyChunk


@dataclass
class RetrievedChunk:
    chunk: PolicyChunk
    score: float


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
    "我",
    "的",
    "是",
    "吗",
    "什么",
}


def tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]", text.lower())
    return {token for token in tokens if token not in STOPWORDS and len(token.strip()) > 0}


def retrieve_chunks(db: Session, question: str, top_k: int = 4) -> list[RetrievedChunk]:
    question_tokens = tokenize(question)
    if not question_tokens:
        return []
    chunks = db.query(PolicyChunk).all()
    scored: list[RetrievedChunk] = []
    for chunk in chunks:
        chunk_tokens = tokenize(chunk.content + " " + (chunk.heading or ""))
        if not chunk_tokens:
            continue
        overlap = len(question_tokens & chunk_tokens)
        if overlap == 0:
            continue
        score = overlap / math.sqrt(len(question_tokens) * len(chunk_tokens))
        scored.append(RetrievedChunk(chunk=chunk, score=round(score, 4)))
    return sorted(scored, key=lambda item: item.score, reverse=True)[:top_k]
