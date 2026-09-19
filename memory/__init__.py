from typing import List, Dict, Any
from .db import memory_db, MemoryDB
from .extractor import memory_extractor, MemoryExtractor
from .fast_extractor import extract_fast as _fast_extract, is_available as _fast_available
from .vector_store import upsert_vector, semantic_search, is_available as _vector_available
from .summarizer import maybe_compress_history
from .feedback_log import log_interaction, log_feedback, get_stats as feedback_stats


def remember_user_statement(text: str) -> List[Dict[str, Any]]:
    """
    Intelligently extracts and persists any durable memories found in the text.
    Strategy:
      1. Fast local extraction (spaCy NER + regex) — <5ms, no API call
      2. If fast extractor found nothing, fall through to LLM extractor (async background)
      3. Each saved memory is also embedded into ChromaDB for semantic search
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
            # 3. Embed into vector store for semantic recall
            if _vector_available():
                embed_text = f"{record.get('category', '')} {record.get('key', '').replace('_', ' ')}: {record.get('value', '')}"
                upsert_vector(
                    memory_id=record.get("id", 0),
                    text=embed_text,
                    metadata={
                        "category": record.get("category", ""),
                        "key": record.get("key", ""),
                        "value": record.get("value", ""),
                    }
                )
    return saved


def search_memories_semantic(query: str, category: str = None, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Hybrid memory search: semantic (ChromaDB) + keyword (FTS5/LIKE fallback).
    Merges and deduplicates results.
    """
    results = []
    seen_ids = set()

    # 1. Semantic search (if available)
    if _vector_available():
        sem_results = semantic_search(query, n_results=limit, category=category)
        for r in sem_results:
            mem_id = r.get("id")
            if mem_id and mem_id not in seen_ids:
                seen_ids.add(mem_id)
                # Fetch full record from DB
                full = memory_db.search_memories(r["metadata"].get("key", query), category=category, limit=1)
                if full:
                    results.append({**full[0], "_score": r.get("score", 0), "_method": "semantic"})

    # 2. FTS5 / keyword fallback
    kw_results = memory_db.search_memories(query, category=category, limit=limit)
    for r in kw_results:
        if r.get("id") not in seen_ids:
            seen_ids.add(r["id"])
            results.append({**r, "_method": "keyword"})

    return results[:limit]


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
