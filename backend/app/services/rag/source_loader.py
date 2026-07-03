from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.core.config import get_settings


@dataclass(frozen=True)
class DocumentSource:
    title: str
    source_path: str
    content: str
    source_type: str


@dataclass(frozen=True)
class RemoteSource:
    title: str
    url: str
    source_type: str
    required: bool = True
    max_chars: int = 24000
    notes: str | None = None


@dataclass
class SourceLoadResult:
    sources: list[DocumentSource]
    warnings: list[str] = field(default_factory=list)


REMOTE_SOURCES: tuple[RemoteSource, ...] = (
    RemoteSource(
        title="NYC311 Service Request Status",
        url="https://portal.311.nyc.gov/article/?kanumber=KA-01066",
        source_type="html",
    ),
    RemoteSource(
        title="NYC311 Service Requests",
        url="https://portal.311.nyc.gov/article/?kanumber=KA-03116",
        source_type="html",
    ),
    RemoteSource(
        title="NYC311 Check Service Request Status Page",
        url="https://portal.311.nyc.gov/check-status/",
        source_type="html",
    ),
    RemoteSource(
        title="NYC 311 Service Requests Dataset Metadata",
        url="https://data.cityofnewyork.us/api/views/erm2-nwe9",
        source_type="socrata_json",
    ),
    RemoteSource(
        title="NYC Open Data Technical Standards Manual",
        url="https://cityofnewyork.github.io/opendatatsm/",
        source_type="html",
    ),
    RemoteSource(
        title="NYC Open Data City Standards",
        url="https://cityofnewyork.github.io/opendatatsm/citystandards.html",
        source_type="html",
    ),
    RemoteSource(
        title="NYC Open Data City Policies",
        url="https://cityofnewyork.github.io/opendatatsm/citypolicies.html",
        source_type="html",
    ),
    RemoteSource(
        title="NYC Open Data Technical Standards Manual PDF",
        url="https://opendata.cityofnewyork.us/wp-content/uploads/NYC_OpenData_TechnicalStandardsManual.pdf",
        source_type="pdf",
        required=False,
        notes="Official PDF source can return 403 to backend clients; the GitHub Pages manual above is indexed as the stable fallback.",
    ),
    RemoteSource(
        title="NYC Open Data Quality Standards PDF",
        url="https://opendata.cityofnewyork.us/wp-content/uploads/OpenDataQualityStandards_Review-Process.pdf",
        source_type="pdf",
        required=False,
        notes="Optional official PDF source. Reindexing continues if the city site blocks backend PDF download.",
    ),
)


LOCAL_SOURCE_PATHS: tuple[tuple[str, str], ...] = (
    ("Project README", "README.md"),
    ("CivicOps Agent Architecture", "docs/ARCHITECTURE.md"),
    ("CivicOps Agent Chinese Project Overview", "docs/PROJECT_OVERVIEW_CN.md"),
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def sample_policy_dir() -> Path:
    return repo_root() / "sample_data" / "policies"


def available_remote_sources() -> list[dict[str, Any]]:
    return [
        {
            "title": source.title,
            "url": source.url,
            "source_type": source.source_type,
            "required": source.required,
            "notes": source.notes,
        }
        for source in REMOTE_SOURCES
    ]


def _compact_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _markdown_title_from_path(path: Path) -> str:
    first_heading = ""
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("#"):
                first_heading = line.lstrip("#").strip()
                break
    except OSError:
        first_heading = ""
    return first_heading or path.stem.replace("_", " ").replace("-", " ").title()


def _load_local_policy_sources() -> list[DocumentSource]:
    directory = sample_policy_dir()
    if not directory.exists():
        return []

    sources: list[DocumentSource] = []
    for path in sorted(directory.glob("*.md")):
        content = path.read_text(encoding="utf-8", errors="ignore")
        sources.append(
            DocumentSource(
                title=_markdown_title_from_path(path),
                source_path=str(path),
                content=content,
                source_type="local_markdown",
            )
        )
    return sources


def _load_local_project_sources() -> list[DocumentSource]:
    root = repo_root()
    sources: list[DocumentSource] = []
    for title, relative_path in LOCAL_SOURCE_PATHS:
        path = root / relative_path
        if not path.exists():
            continue
        sources.append(
            DocumentSource(
                title=title,
                source_path=str(path),
                content=path.read_text(encoding="utf-8", errors="ignore"),
                source_type="project_markdown",
            )
        )
    return sources


def _extract_html_markdown(html: str, title: str, url: str, max_chars: int) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "header", "footer"]):
        tag.decompose()

    body = (
        soup.find(id="page-wrapper")
        or soup.find("main")
        or soup.find("article")
        or soup.find(attrs={"role": "main"})
        or soup.body
        or soup
    )
    blocks = [f"# {title}", f"Source URL: {url}"]
    for element in body.find_all(["h1", "h2", "h3", "h4", "p", "li", "dt", "dd"]):
        text = _compact_text(element.get_text(" ", strip=True))
        if not text or len(text) < 3:
            continue
        if element.name in {"h1", "h2"}:
            blocks.append(f"\n## {text}")
        elif element.name in {"h3", "h4"}:
            blocks.append(f"\n### {text}")
        elif element.name in {"li", "dt", "dd"}:
            blocks.append(f"- {text}")
        else:
            blocks.append(text)

    markdown = _compact_text("\n".join(blocks))
    return markdown[:max_chars]


def _format_socrata_dataset_metadata(payload: dict[str, Any], title: str, url: str, max_chars: int) -> str:
    metadata = payload.get("metadata") or {}
    custom_fields = metadata.get("custom_fields") or {}
    columns = payload.get("columns") or []
    blocks = [
        f"# {title}",
        f"Source URL: {url}",
        f"Dataset name: {payload.get('name', 'unknown')}",
        f"Rows updated at: {payload.get('rowsUpdatedAt', 'unknown')}",
        f"Description: {_compact_text(str(payload.get('description') or 'No description provided.'))}",
    ]
    if custom_fields:
        blocks.append("\n## Metadata")
        blocks.append(json.dumps(custom_fields, ensure_ascii=False, indent=2)[:4000])

    blocks.append("\n## API Columns")
    for column in columns:
        field_name = column.get("fieldName") or column.get("name")
        display_name = column.get("name")
        data_type = column.get("dataTypeName")
        description = _compact_text(str(column.get("description") or ""))
        blocks.append(f"- `{field_name}` / {display_name}: {data_type}. {description}")
    return _compact_text("\n".join(blocks))[:max_chars]


def _extract_pdf_markdown(content: bytes, title: str, url: str, max_chars: int) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(content))
    blocks = [f"# {title}", f"Source URL: {url}"]
    for page_number, page in enumerate(reader.pages[:30], start=1):
        page_text = _compact_text(page.extract_text() or "")
        if page_text:
            blocks.append(f"\n## Page {page_number}\n{page_text}")
        if sum(len(block) for block in blocks) >= max_chars:
            break
    return _compact_text("\n".join(blocks))[:max_chars]


def _fetch_remote_source(client: httpx.Client, source: RemoteSource) -> DocumentSource:
    response = client.get(source.url)
    response.raise_for_status()

    if source.source_type == "html":
        content = _extract_html_markdown(response.text, source.title, source.url, source.max_chars)
    elif source.source_type == "socrata_json":
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Socrata metadata endpoint returned a non-object payload.")
        content = _format_socrata_dataset_metadata(payload, source.title, source.url, source.max_chars)
    elif source.source_type == "pdf":
        content_type = response.headers.get("content-type", "")
        if "pdf" not in content_type.lower() and not response.content.startswith(b"%PDF"):
            raise ValueError(f"Expected PDF content but received {content_type or 'unknown content type'}.")
        content = _extract_pdf_markdown(response.content, source.title, source.url, source.max_chars)
    else:
        raise ValueError(f"Unsupported remote source type: {source.source_type}")

    return DocumentSource(
        title=source.title,
        source_path=source.url,
        content=content,
        source_type=f"remote_{source.source_type}",
    )


def load_document_sources(include_remote: bool = False) -> SourceLoadResult:
    settings = get_settings()
    sources = _load_local_policy_sources() + _load_local_project_sources()
    warnings: list[str] = []
    if not include_remote:
        return SourceLoadResult(sources=sources, warnings=warnings)

    headers = {
        "User-Agent": "civicops-agent/1.0 (+https://github.com/ririan1125/civicops-agent)",
        "Accept": "text/html,application/json,application/pdf;q=0.9,*/*;q=0.8",
    }
    with httpx.Client(timeout=settings.rag_remote_timeout_seconds, follow_redirects=True, headers=headers) as client:
        for remote_source in REMOTE_SOURCES:
            try:
                sources.append(_fetch_remote_source(client, remote_source))
            except Exception as exc:
                message = f"{remote_source.title}: {exc}"
                if remote_source.required:
                    warnings.append(f"required remote source skipped: {message}")
                else:
                    warnings.append(f"optional remote source skipped: {message}")

    return SourceLoadResult(sources=sources, warnings=warnings)
