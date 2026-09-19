"""
memory/vector_store.py — Semantic vector memory for Friday 2.0
Uses ChromaDB (local) + SentenceTransformer (all-MiniLM-L6-v2, ~80MB)
Falls back gracefully if dependencies are not installed.
"""
import os
import sys
from typing import List, Dict, Any, Optional

# Determine base directory
if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS
else:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

data_dir = os.path.join(base_dir, "data")
chroma_dir = os.path.join(data_dir, "chroma_db")
os.makedirs(chroma_dir, exist_ok=True)

_chroma_client = None
_chroma_collection = None
_embed_model = None
_available = False


def _init_vector_store():
    global _chroma_client, _chroma_collection, _embed_model, _available
    if _available:
        return
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer

        _embed_model = SentenceTransformer('all-MiniLM-L6-v2')
        _chroma_client = chromadb.PersistentClient(path=chroma_dir)
        _chroma_collection = _chroma_client.get_or_create_collection(
            name="friday_memories",
            metadata={"hnsw:space": "cosine"}
        )
        _available = True
        print(f"[VectorStore] ChromaDB + SentenceTransformer ready. {_chroma_collection.count()} docs indexed.")
    except ImportError:
        print("[VectorStore] chromadb/sentence-transformers not installed — semantic search disabled.")
    except Exception as e:
        print(f"[VectorStore] Init failed: {e} — semantic search disabled.")


def upsert_vector(memory_id: int, text: str, metadata: dict):
    """Embed and upsert a memory into ChromaDB."""
    if not _available:
        return
    try:
        embedding = _embed_model.encode(text, normalize_embeddings=True).tolist()
        _chroma_collection.upsert(
            ids=[str(memory_id)],
            embeddings=[embedding],
            documents=[text],
            metadatas=[{k: str(v) if v is not None else "" for k, v in metadata.items()}]
        )
    except Exception as e:
        print(f"[VectorStore] Upsert error: {e}")


def delete_vector(memory_id: int):
    """Remove a memory vector by ID."""
    if not _available:
        return
    try:
        _chroma_collection.delete(ids=[str(memory_id)])
    except Exception:
        pass


def semantic_search(query: str, n_results: int = 5, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Search memories by semantic similarity.
    Returns list of dicts with 'id', 'text', 'score', 'metadata'.
    """
    if not _available or not _chroma_collection or _chroma_collection.count() == 0:
        return []
    try:
        embedding = _embed_model.encode(query, normalize_embeddings=True).tolist()
        where = {"category": category} if category else None
        results = _chroma_collection.query(
            query_embeddings=[embedding],
            n_results=min(n_results, _chroma_collection.count()),
            where=where,
            include=["documents", "distances", "metadatas"]
        )
        out = []
        for i, doc_id in enumerate(results["ids"][0]):
            out.append({
                "id": int(doc_id),
                "text": results["documents"][0][i],
                "score": round(1.0 - results["distances"][0][i], 4),  # cosine sim
                "metadata": results["metadatas"][0][i],
            })
        return out
    except Exception as e:
        print(f"[VectorStore] Search error: {e}")
        return []


def is_available() -> bool:
    return _available


# Initialize on module load (non-blocking — if it fails, we fall back to FTS5)
_init_vector_store()
