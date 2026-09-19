import os
import sys
import sqlite3
import datetime
from typing import List, Dict, Optional, Any

# Determine base directory
if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS
else:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

data_dir = os.path.join(base_dir, "data")
os.makedirs(data_dir, exist_ok=True)
db_path = os.path.join(data_dir, "friday_memory.db")


class MemoryDB:
    def __init__(self, path: str = db_path):
        self.path = path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Main storage table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    date_time TEXT,
                    context TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Unique index on category + key to allow seamless upserts
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_category_key 
                ON memories (category, key);
            """)

            # FTS5 virtual table for full-text searching
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                    category,
                    key,
                    value,
                    date_time,
                    context,
                    content='memories',
                    content_rowid='id'
                );
            """)

            # Synchronization triggers for FTS5
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                    INSERT INTO memory_fts(rowid, category, key, value, date_time, context)
                    VALUES (new.id, new.category, new.key, new.value, new.date_time, new.context);
                END;
            """)
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                    INSERT INTO memory_fts(memory_fts, rowid, category, key, value, date_time, context)
                    VALUES('delete', old.id, old.category, old.key, old.value, old.date_time, old.context);
                END;
            """)
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                    INSERT INTO memory_fts(memory_fts, rowid, category, key, value, date_time, context)
                    VALUES('delete', old.id, old.category, old.key, old.value, old.date_time, old.context);
                    INSERT INTO memory_fts(rowid, category, key, value, date_time, context)
                    VALUES (new.id, new.category, new.key, new.value, new.date_time, new.context);
                END;
            """)
            conn.commit()

    def upsert_memory(
        self,
        category: str,
        key: str,
        value: str,
        date_time: Optional[str] = None,
        context: str = ""
    ) -> Dict[str, Any]:
        """Insert or update a memory entity based on (category, key)."""
        clean_cat = category.strip().lower()
        clean_key = key.strip().lower()
        clean_val = value.strip()
        clean_dt = date_time.strip() if date_time else None
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO memories (category, key, value, date_time, context, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(category, key) DO UPDATE SET
                    value = excluded.value,
                    date_time = COALESCE(excluded.date_time, memories.date_time),
                    context = excluded.context,
                    updated_at = excluded.updated_at
            """, (clean_cat, clean_key, clean_val, clean_dt, context, now_str, now_str))
            conn.commit()
            
            # Fetch the upserted record
            cursor.execute(
                "SELECT * FROM memories WHERE category = ? AND key = ?",
                (clean_cat, clean_key)
            )
            row = cursor.fetchone()
            return dict(row) if row else {}

    def search_memories(self, query: str, category: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Search memories using FTS5 match with LIKE fallback."""
        clean_query = query.strip()
        if not clean_query:
            return []

        results = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Try FTS5 search
            try:
                # Sanitize query for FTS5 syntax
                fts_query = " ".join([f'"{w}"' for w in clean_query.split() if w.isalnum()])
                if fts_query:
                    if category:
                        sql = """
                            SELECT m.*, rank FROM memory_fts f
                            JOIN memories m ON m.id = f.rowid
                            WHERE memory_fts MATCH ? AND m.category = ?
                            ORDER BY rank LIMIT ?
                        """
                        cursor.execute(sql, (fts_query, category.strip().lower(), limit))
                    else:
                        sql = """
                            SELECT m.*, rank FROM memory_fts f
                            JOIN memories m ON m.id = f.rowid
                            WHERE memory_fts MATCH ?
                            ORDER BY rank LIMIT ?
                        """
                        cursor.execute(sql, (fts_query, limit))
                    results = [dict(r) for r in cursor.fetchall()]
            except Exception:
                pass

            # 2. Fallback to SQL LIKE substring search if FTS returned nothing
            if not results:
                like_term = f"%{clean_query}%"
                if category:
                    sql = """
                        SELECT * FROM memories 
                        WHERE category = ? AND (key LIKE ? OR value LIKE ? OR context LIKE ? OR date_time LIKE ?)
                        ORDER BY updated_at DESC LIMIT ?
                    """
                    cursor.execute(sql, (category.strip().lower(), like_term, like_term, like_term, like_term, limit))
                else:
                    sql = """
                        SELECT * FROM memories 
                        WHERE key LIKE ? OR value LIKE ? OR context LIKE ? OR date_time LIKE ? OR category LIKE ?
                        ORDER BY updated_at DESC LIMIT ?
                    """
                    cursor.execute(sql, (like_term, like_term, like_term, like_term, like_term, limit))
                results = [dict(r) for r in cursor.fetchall()]

        return results

    def get_user_profile(self) -> str:
        """Returns summarized user identity and preferences for system prompt context injection."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT category, key, value, date_time FROM memories 
                WHERE category IN ('identity', 'personal_info', 'preference')
                ORDER BY category, key
            """)
            rows = cursor.fetchall()
            if not rows:
                return ""
            
            lines = []
            for r in rows:
                lines.append(f"- {r['key'].replace('_', ' ').title()}: {r['value']}")
            return "\n".join(lines)

    def list_all_memories(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all memories, optionally filtered by category."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if category:
                cursor.execute(
                    "SELECT * FROM memories WHERE category = ? ORDER BY updated_at DESC",
                    (category.strip().lower(),)
                )
            else:
                cursor.execute("SELECT * FROM memories ORDER BY category, updated_at DESC")
            return [dict(r) for r in cursor.fetchall()]

    def delete_memory(self, target: str) -> bool:
        """Delete a memory by numeric ID or matching key."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if target.isdigit():
                cursor.execute("DELETE FROM memories WHERE id = ?", (int(target),))
            else:
                cursor.execute("DELETE FROM memories WHERE key = ? OR key LIKE ?", (target.lower(), f"%{target.lower()}%"))
            conn.commit()
            return cursor.rowcount > 0


# Global database instance
memory_db = MemoryDB()
