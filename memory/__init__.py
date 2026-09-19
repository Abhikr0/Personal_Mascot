from typing import List, Dict, Any
from .db import memory_db, MemoryDB
from .extractor import memory_extractor, MemoryExtractor
from .fast_extractor import extract_fast as _fast_extract, is_available as _fast_available
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


__all__ = [
    "memory_db",
    "MemoryDB",
    "memory_extractor",
    "MemoryExtractor",
    "remember_user_statement",
    "search_memories_semantic",
    "maybe_compress_history",
    "log_interaction",
    "log_feedback",
    "feedback_stats",
]
