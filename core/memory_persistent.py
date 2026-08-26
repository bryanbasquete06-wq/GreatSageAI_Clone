# -*- coding: utf-8 -*-
"""Memory persistente com SQLite — IA lembra de tudo entre sessoes."""
import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger("greatsage.memory")
DB_PATH = Path(__file__).resolve().parent.parent / "config" / "memory.db"

@dataclass
class MemoryEntry:
    id: int = 0
    category: str = "conversation"
    content: str = ""
    importance: float = 0.5
    tags: List[str] = None
    metadata: Dict = None
    created_at: str = ""
    accessed_at: str = ""
    access_count: int = 0

class PersistentMemory:
    def __init__(self, db_path: Path = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                importance REAL DEFAULT 0.5,
                tags TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                accessed_at TEXT NOT NULL,
                access_count INTEGER DEFAULT 0
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON memories(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_importance ON memories(importance DESC)")
            conn.commit()

    def add(self, category: str, content: str, importance: float = 0.5,
            tags: List[str] = None, metadata: Dict = None) -> int:
        now = datetime.now().isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                "INSERT INTO memories (category, content, importance, tags, metadata, created_at, accessed_at, access_count) VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
                (category, content, importance, json.dumps(tags or []), json.dumps(metadata or {}), now, now))
            conn.commit()
            return cursor.lastrowid

    def search(self, query: str, category: str = None, limit: int = 10, min_importance: float = 0.0) -> List[MemoryEntry]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            if category:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE category = ? AND importance >= ? AND content LIKE ? ORDER BY importance DESC LIMIT ?",
                    (category, min_importance, f"%{query}%", limit)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE importance >= ? AND content LIKE ? ORDER BY importance DESC LIMIT ?",
                    (min_importance, f"%{query}%", limit)).fetchall()
            return [self._row_to_entry(r) for r in rows]

    def get_recent(self, category: str = None, limit: int = 20) -> List[MemoryEntry]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            if category:
                rows = conn.execute("SELECT * FROM memories WHERE category = ? ORDER BY created_at DESC LIMIT ?", (category, limit)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM memories ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            return [self._row_to_entry(r) for r in rows]

    def get_important(self, limit: int = 20) -> List[MemoryEntry]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM memories ORDER BY importance DESC LIMIT ?", (limit,)).fetchall()
            return [self._row_to_entry(r) for r in rows]

    def update_access(self, memory_id: int):
        now = datetime.now().isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("UPDATE memories SET accessed_at = ?, access_count = access_count + 1 WHERE id = ?", (now, memory_id))
            conn.commit()

    def delete(self, memory_id: int):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()

    def count(self, category: str = None) -> int:
        with sqlite3.connect(str(self.db_path)) as conn:
            if category:
                return conn.execute("SELECT COUNT(*) FROM memories WHERE category = ?", (category,)).fetchone()[0]
            return conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]

    def _row_to_entry(self, row) -> MemoryEntry:
        return MemoryEntry(
            id=row["id"], category=row["category"], content=row["content"],
            importance=row["importance"], tags=json.loads(row["tags"]),
            metadata=json.loads(row["metadata"]), created_at=row["created_at"],
            accessed_at=row["accessed_at"], access_count=row["access_count"])

    def stats(self) -> Dict:
        with sqlite3.connect(str(self.db_path)) as conn:
            total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            categories = conn.execute("SELECT category, COUNT(*) FROM memories GROUP BY category").fetchall()
            avg = conn.execute("SELECT AVG(importance) FROM memories").fetchone()[0] or 0
        return {
            "total": total,
            "categories": {c: n for c, n in categories},
            "avg_importance": round(avg, 2),
            "db_size_mb": round(self.db_path.stat().st_size / (1024*1024), 2) if self.db_path.exists() else 0,
        }

    def clear(self, category: str = None):
        with sqlite3.connect(str(self.db_path)) as conn:
            if category:
                conn.execute("DELETE FROM memories WHERE category = ?", (category,))
            else:
                conn.execute("DELETE FROM memories")
            conn.commit()
