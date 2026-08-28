# -*- coding: utf-8 -*-
"""Memory persistente com SQLite — IA lembra de tudo entre sessoes.

v2 — Smart Forgetting & Importance Decay:
  - Importância decai exponencialmente com o tempo
  - Acesso recente renova a importância
  - Resumo automático de conversas longas
  - Compactação de memórias antigas pouco acessadas
  - Deduplicação inteligente (merge de memórias similares)
"""
import sqlite3
import json
import logging
import math
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger("greatsage.memory")
DB_PATH = Path(__file__).resolve().parent.parent / "config" / "memory.db"

# Decay: importância reduz 50% a cada N dias por categoria
CATEGORY_DECAY_DAYS = {
    "conversation": 7,
    "fact": 90,
    "code_snippet": 60,
    "preference": 180,
    "task": 30,
    "summary": 120,
    "error_log": 14,
    "learning": 45,
    "correction": 365,  # Correções duram 1 ano (nunca esquece)
    "user_pattern": 90,  # Padrões de uso
}
DEFAULT_DECAY_DAYS = 30

# Mínimo absoluto de importância (nunca chega a zero)
MIN_IMPORTANCE = 0.05

# Parâmetro de compacção: memórias abaixo deste threshold são candidatas a merge
COMPACTION_THRESHOLD = 0.15


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
    fingerprint: str = ""  # hash do conteúdo para dedup


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
                access_count INTEGER DEFAULT 0,
                fingerprint TEXT DEFAULT ''
            )""")
            conn.commit()
            # Ensure fingerprint column exists for older DBs (BEFORE creating index)
            try:
                conn.execute("ALTER TABLE memories ADD COLUMN fingerprint TEXT DEFAULT ''")
                conn.commit()
            except sqlite3.OperationalError:
                pass  # column already exists
            # Now create indexes safely
            conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON memories(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_importance ON memories(importance DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_fingerprint ON memories(fingerprint)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON memories(created_at)")
            conn.commit()

    @staticmethod
    def _fingerprint(content: str) -> str:
        """Gera fingerprint para dedup.ignorando espaços extras e case."""
        normalized = " ".join(content.lower().split())
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()[:12]

    def add(self, category: str, content: str, importance: float = 0.5,
            tags: List[str] = None, metadata: Dict = None) -> int:
        now = datetime.now().isoformat()
        fp = self._fingerprint(content)
        with sqlite3.connect(str(self.db_path)) as conn:
            # Dedup: se fingerprint já existe e importância similar, atualiza em vez de duplicar
            existing = conn.execute(
                "SELECT id, importance, access_count FROM memories WHERE fingerprint = ? LIMIT 1",
                (fp,)).fetchone()
            if existing:
                # Merge: incrementa access_count e eleva importância
                new_imp = min(1.0, max(existing[1], importance) + 0.05)
                conn.execute(
                    "UPDATE memories SET importance = ?, access_count = access_count + 1, "
                    "accessed_at = ? WHERE id = ?",
                    (new_imp, now, existing[0]))
                conn.commit()
                logger.debug(f"Memory dedup: merged into id={existing[0]}")
                return existing[0]

            cursor = conn.execute(
                "INSERT INTO memories (category, content, importance, tags, metadata, "
                "created_at, accessed_at, access_count, fingerprint) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)",
                (category, content, importance, json.dumps(tags or []),
                 json.dumps(metadata or {}), now, now, fp))
            conn.commit()
            return cursor.lastrowid

    def search(self, query: str, category: str = None, limit: int = 10,
               min_importance: float = 0.0, decay: bool = True) -> List[MemoryEntry]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            if category:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE category = ? AND importance >= ? "
                    "AND content LIKE ? ORDER BY importance DESC LIMIT ?",
                    (category, min_importance, f"%{query}%", limit)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE importance >= ? AND content LIKE ? "
                    "ORDER BY importance DESC LIMIT ?",
                    (min_importance, f"%{query}%", limit)).fetchall()
            entries = [self._row_to_entry(r) for r in rows]
            if decay:
                for e in entries:
                    e.importance = self._apply_decay(e)
            return entries

    def get_recent(self, category: str = None, limit: int = 20) -> List[MemoryEntry]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            if category:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE category = ? ORDER BY created_at DESC LIMIT ?",
                    (category, limit)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM memories ORDER BY created_at DESC LIMIT ?",
                    (limit,)).fetchall()
            return [self._row_to_entry(r) for r in rows]

    def get_important(self, limit: int = 20) -> List[MemoryEntry]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM memories ORDER BY importance DESC LIMIT ?",
                (limit,)).fetchall()
            return [self._row_to_entry(r) for r in rows]

    def update_access(self, memory_id: int):
        """Atualiza acesso — renova importancia."""
        now = datetime.now().isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            # Renova importância: média entre atual e 1.0, com boost
            conn.execute(
                "UPDATE memories SET accessed_at = ?, access_count = access_count + 1, "
                "importance = MIN(1.0, importance + 0.05) WHERE id = ?",
                (now, memory_id))
            conn.commit()

    def delete(self, memory_id: int):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()

    def count(self, category: str = None) -> int:
        with sqlite3.connect(str(self.db_path)) as conn:
            if category:
                return conn.execute(
                    "SELECT COUNT(*) FROM memories WHERE category = ?",
                    (category,)).fetchone()[0]
            return conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]

    # ------------------------------------------------------------------
    # Smart Forgetting
    # ------------------------------------------------------------------

    def _apply_decay(self, entry: MemoryEntry) -> float:
        """Aplica decay exponencial na importância baseado na idade."""
        decay_days = CATEGORY_DECAY_DAYS.get(entry.category, DEFAULT_DECAY_DAYS)
        try:
            created = datetime.fromisoformat(entry.created_at)
            age_days = (datetime.now() - created).total_seconds() / 86400
        except Exception:
            return entry.importance
        # Decay exponencial: imp(t) = imp(0) * 0.5^(age/decay_half_life)
        decay_factor = math.pow(0.5, age_days / decay_days)
        decayed = entry.importance * decay_factor
        return max(MIN_IMPORTANCE, decayed)

    def apply_global_decay(self) -> int:
        """Aplica decay global — retorna num de memórias afetadas."""
        count = 0
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT id, category, importance, created_at FROM memories").fetchall()
            updates = []
            for r in rows:
                decay_days = CATEGORY_DECAY_DAYS.get(r["category"], DEFAULT_DECAY_DAYS)
                try:
                    created = datetime.fromisoformat(r["created_at"])
                    age_days = (datetime.now() - created).total_seconds() / 86400
                except Exception:
                    continue
                decayed = r["importance"] * math.pow(0.5, age_days / decay_days)
                decayed = max(MIN_IMPORTANCE, round(decayed, 4))
                if abs(decayed - r["importance"]) > 0.001:
                    updates.append((decayed, r["id"]))
            if updates:
                conn.executemany(
                    "UPDATE memories SET importance = ? WHERE id = ?", updates)
                conn.commit()
                count = len(updates)
                logger.info(f"Global decay: {count} memórias atualizadas")
        return count

    def compact(self, min_age_days: int = 90) -> dict:
        """Compactação inteligente: merge memórias similares e remove lixo."""
        stats = {"merged": 0, "deleted": 0, "compacted": 0}
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            # 1) Remove memórias com importância < threshold E antigas
            cutoff = (datetime.now() - timedelta(days=min_age_days)).isoformat()
            trash = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE importance < ? AND created_at < ?",
                (COMPACTION_THRESHOLD, cutoff)).fetchone()[0]
            if trash > 0:
                conn.execute(
                    "DELETE FROM memories WHERE importance < ? AND created_at < ?",
                    (COMPACTION_THRESHOLD, cutoff))
                stats["deleted"] = trash
            # 2) Remove duplicatas por fingerprint (mantém o mais acessado)
            dupes = conn.execute(
                "SELECT fingerprint, COUNT(*) as cnt FROM memories "
                "WHERE fingerprint != '' GROUP BY fingerprint HAVING cnt > 1"
            ).fetchall()
            for d in dupes:
                keep = conn.execute(
                    "SELECT id FROM memories WHERE fingerprint = ? "
                    "ORDER BY access_count DESC, importance DESC LIMIT 1",
                    (d["fingerprint"],)).fetchone()
                if keep:
                    conn.execute(
                        "DELETE FROM memories WHERE fingerprint = ? AND id != ?",
                        (d["fingerprint"], keep["id"]))
                    stats["merged"] += d["cnt"] - 1
            conn.commit()
        logger.info(f"Compact: {stats}")
        return stats

    def get_context_for_prompt(self, query: str, max_tokens: int = 800) -> str:
        """Gera contexto de memória para injeção no prompt do LLM."""
        entries = self.search(query, limit=5, min_importance=0.1)
        if not entries:
            return ""
        parts = []
        for e in entries:
            imp_label = "[ALTA]" if e.importance >= 0.7 else "[MÉDIA]" if e.importance >= 0.4 else "[BAIXA]"
            parts.append(f"{imp_label} {e.content[:200]}")
        context = "\n".join(parts)
        if len(context) > max_tokens:
            context = context[:max_tokens] + "..."
        return f"Memória relevante:\n{context}"

    def _row_to_entry(self, row) -> MemoryEntry:
        return MemoryEntry(
            id=row["id"], category=row["category"], content=row["content"],
            importance=row["importance"], tags=json.loads(row["tags"]),
            metadata=json.loads(row["metadata"]), created_at=row["created_at"],
            accessed_at=row["accessed_at"], access_count=row["access_count"],
            fingerprint=row["fingerprint"] if "fingerprint" in row.keys() else "")

    def stats(self) -> Dict:
        with sqlite3.connect(str(self.db_path)) as conn:
            total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            categories = conn.execute(
                "SELECT category, COUNT(*), AVG(importance) FROM memories GROUP BY category"
            ).fetchall()
            avg = conn.execute("SELECT AVG(importance) FROM memories").fetchone()[0] or 0
            high = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE importance >= 0.7").fetchone()[0]
            low = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE importance < 0.15").fetchone()[0]
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
        return {
            "total": total,
            "categories": {c: {"count": n, "avg_importance": round(a or 0, 2)}
                            for c, n, a in categories},
            "avg_importance": round(avg, 2),
            "high_importance": high,
            "low_importance": low,
            "db_size_mb": round(db_size / (1024*1024), 2),
        }

    def clear(self, category: str = None):
        with sqlite3.connect(str(self.db_path)) as conn:
            if category:
                conn.execute("DELETE FROM memories WHERE category = ?", (category,))
            else:
                conn.execute("DELETE FROM memories")
            conn.commit()

    # ------------------------------------------------------------------
    # Learning from Corrections (v3)
    # ------------------------------------------------------------------

    def record_correction(self, wrong_answer: str, correct_answer: str,
                          topic: str = "") -> int:
        """Registra quando o usuário corrige a IA — ela NUNCA esquece."""
        content = (f"CORREÇÃO: Quando o usuário perguntou sobre '{topic}', "
                   f"eu errei. Resposta errada: {wrong_answer[:200]}. "
                   f"Resposta correta: {correct_answer[:200]}")
        return self.add(
            category="correction",
            content=content,
            importance=0.95,  # Máxima importância — correções são ouro
            tags=["correction", topic] if topic else ["correction"],
            metadata={"wrong": wrong_answer[:500], "correct": correct_answer[:500], "topic": topic},
        )

    def get_corrections_for_prompt(self, query: str, max_tokens: int = 600) -> str:
        """Busca correções relevantes para injetar no prompt do LLM."""
        entries = self.search(query, category="correction", limit=3, min_importance=0.5)
        if not entries:
            return ""
        parts = ["═══ CORREÇÕES ANTERIORES (NÃO REPITA ESTES ERROS) ═══"]
        for e in entries:
            parts.append(f"• {e.content[:300]}")
        context = "\n".join(parts)
        if len(context) > max_tokens:
            context = context[:max_tokens] + "..."
        return context

    def record_user_pattern(self, action: str, details: str = ""):
        """Registra padrão de uso do usuário para sugestões proativas."""
        content = f"Padrão: {action} — {details}" if details else f"Padrão: {action}"
        return self.add(
            category="user_pattern",
            content=content,
            importance=0.4,
            tags=["pattern", action],
            metadata={"action": action, "details": details},
        )

    def get_user_patterns(self, limit: int = 10) -> List[MemoryEntry]:
        """Retorna padrões de uso recentes do usuário."""
        return self.get_recent(category="user_pattern", limit=limit)

    def get_correction_stats(self) -> Dict:
        """Estatísticas de aprendizado por correções."""
        with sqlite3.connect(str(self.db_path)) as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE category = 'correction'").fetchone()[0]
            topics = conn.execute(
                "SELECT tags FROM memories WHERE category = 'correction'"
            ).fetchall()
            topic_counts = {}
            for row in topics:
                try:
                    tags = json.loads(row[0])
                    for t in tags:
                        if t != "correction":
                            topic_counts[t] = topic_counts.get(t, 0) + 1
                except Exception:
                    pass
        return {
            "total_corrections": total,
            "topics_learned": topic_counts,
            "most_corrected": max(topic_counts, key=topic_counts.get) if topic_counts else "none",
        }
