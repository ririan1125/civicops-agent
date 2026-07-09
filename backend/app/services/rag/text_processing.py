import re


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
    "\u8bf7",
    "\u6211",
    "\u7684",
    "\u4e86",
    "\u662f",
    "\u5417",
    "\u4e48",
    "\u4ec0\u4e48",
    "\u600e\u4e48",
    "\u5982\u4f55",
    "\u4e00\u4e2a",
}


TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]+")


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
