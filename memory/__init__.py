from typing import List, Dict, Any
from .db import memory_db, MemoryDB
import re

from .extractor import memory_extractor, MemoryExtractor
from .fast_extractor import (
    extract_fast as _fast_extract,
    is_available as _fast_available,
    extract_relationships as _extract_relationships,
)
from .summarizer import maybe_compress_history
from .feedback_log import log_interaction, log_feedback, get_stats as feedback_stats


def remember_user_statement(text: str) -> List[Dict[str, Any]]:
    """
    Intelligently extracts and persists durable memories found in the text.
    Uses fast local extraction (regex/NER) with fallback to LLM extractor.
    Stored in SQLite with automatic FTS5 full-text indexing.
    """
    # 1. Fast local extraction
    fast_results = _fast_extract(text)

    # 2. LLM extraction if fast found nothing and text is substantial enough
    if not fast_results and len(text) > 8:
        fast_results = memory_extractor.extract_entities(text)

    saved = []
    for item in fast_results:
        record = memory_db.upsert_memory(
            category=item.get("category", "fact"),
            key=item.get("key", "note"),
            value=item.get("value", ""),
            date_time=item.get("date_time"),
            context=item.get("context", text)
        )
        if record:
            saved.append(record)
    return saved


def search_memories_semantic(query: str, category: str = None, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Fast memory search using SQLite FTS5 full-text search with keyword fallback.
    """
    return memory_db.search_memories(query, category=category, limit=limit)


def remember_relationship(subject: str, predicate: str, object_: str, context: str = "") -> List[Dict[str, Any]]:
    """Persist a typed relationship as a knowledge-graph edge."""
    record = memory_db.add_relation(subject=subject, predicate=predicate, object_=object_, context=context)
    return [record] if record else []


def search_relationships(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Search the relation knowledge graph for related entities."""
    return memory_db.search_relations(query, limit=limit)


def extract_relationships(text: str) -> List[tuple]:
    """Fast local relationship extraction -> [(subject, predicate, object)] tuples."""
    clean = text.strip()
    found = []
    if not clean or len(clean) < 6:
        return found
    patterns = [
        (r"([A-Z][a-z]+)\s+works\s+(?:at|for)\s+([A-Z][a-z]+(?:\.?[a-z]+)?)", "employer"),
        (r"([A-Z][a-z]+)\s+lives\s+(?:in|near)\s+([A-Z][a-z]+(?:\.?[a-z]+)?)", "location"),
        (r"([A-Z][a-z]+)\s+likes?\s+(?:to\s+)?([A-Z][a-z]+)", "likes"),
        (r"([A-Z][a-z]+)\s+hates?\s+(?:to\s+)?([A-Z][a-z]+)", "dislikes"),
    ]
    for pattern, pred in patterns:
        for m in re.finditer(pattern, clean):
            subj = m.group(1).strip().lower()
            obj = m.group(2).strip().lower()
            if subj and obj and subj != obj:
                found.append((subj, pred, obj))
    return found


def remember_relationships(text: str) -> List[Dict[str, Any]]:
    """Auto-extract and persist clear relationships into the knowledge graph."""
    saved = []
    for subj, pred, obj in _extract_relationships(text):
        record = memory_db.add_relation(subject=subj, predicate=pred, object_=obj, context=text)
        if record:
            saved.append(record)
    return saved


__all__ = [
    "memory_db",
    "MemoryDB",
    "memory_extractor",
    "MemoryExtractor",
    "remember_user_statement",
    "remember_relationship",
    "remember_relationships",
    "search_memories_semantic",
    "search_relationships",
    "maybe_compress_history",
    "log_interaction",
    "log_feedback",
    "feedback_stats",
]
