import re
from dataclasses import dataclass


@dataclass
class TextChunk:
    heading: str | None
    content: str
    token_count: int


def _estimate_tokens(text: str) -> int:
    return max(1, len(re.findall(r"\w+|[\u4e00-\u9fff]", text)))


def chunk_markdown(text: str, max_chars: int = 900, overlap: int = 120) -> list[TextChunk]:
    lines = text.splitlines()
    chunks: list[TextChunk] = []
    heading: str | None = None
    buffer = ""

    def flush() -> None:
        nonlocal buffer
        content = buffer.strip()
        if content:
            chunks.append(TextChunk(heading=heading, content=content, token_count=_estimate_tokens(content)))
        buffer = ""

    for line in lines:
        if line.startswith("#"):
            flush()
            heading = line.lstrip("#").strip()
            continue
        candidate = f"{buffer}\n{line}".strip()
        if len(candidate) > max_chars:
            flush()
            if chunks and overlap > 0:
                buffer = chunks[-1].content[-overlap:] + "\n" + line
            else:
                buffer = line
        else:
            buffer = candidate
    flush()
    return chunks
