import re
from collections import Counter, defaultdict
from itertools import combinations

from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload

from app.db.models import PolicyChunk


KA_PATTERN = re.compile(r"\bKA-\d{5}\b", re.IGNORECASE)

BOROUGH_ALIASES = {
    "manhattan": "borough:manhattan",
    "brooklyn": "borough:brooklyn",
    "queens": "borough:queens",
    "bronx": "borough:bronx",
    "the bronx": "borough:bronx",
    "staten island": "borough:staten_island",
}

AGENCY_ALIASES = {
    "nypd": "agency:nypd",
    "department of sanitation": "agency:dsny",
    "dsny": "agency:dsny",
    "department of transportation": "agency:dot",
    "dot": "agency:dot",
    "housing preservation": "agency:hpd",
    "hpd": "agency:hpd",
    "department of buildings": "agency:dob",
    "dob": "agency:dob",
    "department of environmental protection": "agency:dep",
    "dep": "agency:dep",
    "department of health": "agency:dohmh",
    "dohmh": "agency:dohmh",
}

TOPIC_PATTERNS = {
    "topic:service_request_status": ("service request status", "check status", "\u67e5\u8be2\u72b6\u6001"),
    "topic:illegal_parking": ("illegal parking", "\u8fdd\u89c4\u505c\u8f66", "\u505c\u8f66"),
    "topic:blocked_driveway": ("blocked driveway", "\u5835\u4f4f\u8f66\u9053"),
    "topic:noise": ("noise", "\u566a\u97f3"),
    "topic:apartment_maintenance": ("apartment maintenance", "\u516c\u5bd3\u7ef4\u4fee"),
    "topic:heat_hot_water": ("heat or hot water", "hot water", "\u4f9b\u6696", "\u70ed\u6c34"),
    "topic:open_data": ("open data", "dataset metadata", "\u5f00\u653e\u6570\u636e"),
    "topic:safe_sql": ("safe sql", "read-only select", "drop delete update insert"),
    "topic:human_approval": ("human approval", "human-in-the-loop", "approval before"),
}


def entity_label(entity_id: str) -> str:
    if entity_id.startswith("nyc311_article:"):
        return entity_id.split(":", 1)[1].upper()
    return entity_id.split(":", 1)[-1].replace("_", " ").title()


def extract_text_entities(text: str) -> set[str]:
    normalized = text.lower()
    entities = {f"nyc311_article:{match.group(0).upper()}" for match in KA_PATTERN.finditer(text)}
    for phrase, entity_id in BOROUGH_ALIASES.items():
        if phrase in normalized:
            entities.add(entity_id)
    for phrase, entity_id in AGENCY_ALIASES.items():
        if phrase in normalized:
            entities.add(entity_id)
    for entity_id, phrases in TOPIC_PATTERNS.items():
        if any(phrase in normalized for phrase in phrases):
            entities.add(entity_id)
    return entities


def build_knowledge_graph(db: Session, max_chunks: int = 800) -> dict:
    chunks = (
        db.query(PolicyChunk)
        .options(joinedload(PolicyChunk.document))
        .order_by(PolicyChunk.id.asc())
        .limit(max(1, max_chunks))
        .all()
    )
    node_counts: Counter[str] = Counter()
    edge_counts: Counter[tuple[str, str]] = Counter()
    example_documents: dict[str, set[str]] = defaultdict(set)

    for chunk in chunks:
        document = chunk.document
        text = " ".join(
            [
                document.title if document else "",
                document.source_path if document and document.source_path else "",
                chunk.heading or "",
                chunk.content[:2000],
            ]
        )
        entities = sorted(extract_text_entities(text))
        if not entities:
            continue
        node_counts.update(entities)
        for entity_id in entities:
            if document:
                example_documents[entity_id].add(document.title)
        for left, right in combinations(entities, 2):
            edge_counts[(left, right)] += 1

    nodes = [
        {
            "id": entity_id,
            "label": entity_label(entity_id),
            "type": entity_id.split(":", 1)[0],
            "mentions": count,
            "example_documents": sorted(example_documents[entity_id])[:3],
        }
        for entity_id, count in node_counts.most_common(80)
    ]
    edges = [
        {
            "source": left,
            "target": right,
            "weight": weight,
        }
        for (left, right), weight in edge_counts.most_common(120)
    ]
    return {
        "nodes": nodes,
        "edges": edges,
        "chunks_scanned": len(chunks),
    }
