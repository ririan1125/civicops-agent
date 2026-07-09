from collections import Counter

from app.services.rag.text_processing import tokenize


def sparse_terms_for_text(heading: str | None, content: str, max_terms: int = 80) -> dict[str, int]:
    terms = tokenize(f"{heading or ''} {heading or ''} {heading or ''} {content}")
    counts = Counter(terms)
    return dict(counts.most_common(max_terms))
