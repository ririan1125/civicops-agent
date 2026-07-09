import re
from dataclasses import dataclass


@dataclass
class TextChunk:
    heading: str | None
    content: str
    token_count: int
    parent_heading: str | None = None
    section_path: list[str] | None = None


def _estimate_tokens(text: str) -> int:
    return max(1, len(re.findall(r"\w+|[\u4e00-\u9fff]", text)))


def chunk_markdown(text: str, max_chars: int = 900, overlap: int = 120) -> list[TextChunk]:
    lines = text.splitlines()
    chunks: list[TextChunk] = []
    heading: str | None = None
    section_stack: list[tuple[int, str]] = []
    buffer = ""

    def flush() -> None:
        nonlocal buffer
        content = buffer.strip()
        if content:
            section_path = [title for _, title in section_stack]
            parent_heading = section_path[-2] if len(section_path) >= 2 else None
            chunks.append(
                TextChunk(
                    heading=heading,
                    content=content,
                    token_count=_estimate_tokens(content),
                    parent_heading=parent_heading,
                    section_path=section_path,
                )
            )
        buffer = ""

    for line in lines:
        if line.startswith("#"):
            flush()
            level = len(line) - len(line.lstrip("#"))
            heading = line.lstrip("#").strip()
            section_stack = [(existing_level, title) for existing_level, title in section_stack if existing_level < level]
            section_stack.append((level, heading))
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
