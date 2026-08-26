"""
Great Sage AI - Persistent Memory & Conversation Archiver
Archives 100% of user speech, queries, assistant responses, and preferences to JSON storage.

v2 improvements:
  - Importance scoring for facts (higher score = more relevant)
  - Smart fact extraction from conversations
  - Context-aware retrieval (relevance ranking)
  - Conversation summarization for long histories
"""

import os
import sys
import json
import re
import threading
import time
from datetime import datetime
from pathlib import Path


class MemoryManager:
    BASE_DIR = Path(__file__).resolve().parent.parent / "config"
    HISTORY_FILE = BASE_DIR / "conversation_history.json"
    FACTS_FILE = BASE_DIR / "user_memory.json"
    _lock = threading.Lock()

    # Keywords that indicate important facts worth remembering
    _IMPORTANCE_KEYWORDS = {
        "high": ["meu nome", "meu email", "minha senha", "meu telefone", "minha cidade",
                 "meu endereço", "minha empresa", "meu cargo", "minha profissão",
                 "gosto de", "não gosto", "prefiro", "odeio", "ama", "adoro"],
        "medium": ["configure", "instale", "baixe", "abra", "feche", "limpe",
                   "otimize", "pesquise", "envie", "salve", "crie", "edite"],
        "low": ["obrigado", "por favor", "ok", "entendi", "beleza", "certo"],
    }

    @classmethod
    def _ensure_files(cls):
        cls.BASE_DIR.mkdir(parents=True, exist_ok=True)
        if not cls.HISTORY_FILE.exists():
            cls.HISTORY_FILE.write_text("[]", encoding="utf-8")
        if not cls.FACTS_FILE.exists():
            cls.FACTS_FILE.write_text("{}", encoding="utf-8")

    @classmethod
    def _calculate_importance(cls, text: str) -> str:
        """Calculate importance level of a fact based on keywords."""
        text_lower = text.lower()
        for level, keywords in cls._IMPORTANCE_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    return level
        return "low"

    @classmethod
    def _extract_facts_from_conversation(cls, user_speech: str, assistant_response: str) -> list[dict]:
        """Extract potential facts from a conversation turn."""
        facts = []
        speech_lower = user_speech.lower()

        # Pattern: "meu nome é X" / "me chamo X"
        name_match = re.search(r'(?:meu nome é|me chamo|sou o?|sou a?)\s+([A-ZÀ-Ú][a-zà-ú]+)', user_speech)
        if name_match:
            facts.append({"key": "nome do usuário", "value": name_match.group(1), "importance": "high"})

        # Pattern: "gosto de X" / "adoro X"
        like_match = re.search(r'(?:gosto de|adoro|amo|curto)\s+(.{3,50})', user_speech, re.IGNORECASE)
        if like_match:
            facts.append({"key": f"gosto de {like_match.group(1).strip()[:30]}", "value": like_match.group(1).strip(), "importance": "medium"})

        # Pattern: "não gosto de X" / "odeio X"
        dislike_match = re.search(r'(?:não gosto de|odeio|detesto)\s+(.{3,50})', user_speech, re.IGNORECASE)
        if dislike_match:
            facts.append({"key": f"não gosta de {dislike_match.group(1).strip()[:30]}", "value": dislike_match.group(1).strip(), "importance": "medium"})

        # Pattern: "prefiro X"
        prefer_match = re.search(r'prefiro\s+(.{3,50})', user_speech, re.IGNORECASE)
        if prefer_match:
            facts.append({"key": f"prefere {prefer_match.group(1).strip()[:30]}", "value": prefer_match.group(1).strip(), "importance": "medium"})

        # Pattern: "trabalho com X" / "sou programador"
        work_match = re.search(r'(?:trabalho com|sou|meu trabalho é)\s+(.{3,50})', user_speech, re.IGNORECASE)
        if work_match:
            facts.append({"key": "profissão/trabalho", "value": work_match.group(1).strip(), "importance": "high"})

        return facts

    @classmethod
    def archive_turn(cls, user_speech: str, assistant_response: str, source: str = "voice") -> dict:
        """Archives a complete interaction turn permanently."""
        cls._ensure_files()
        entry = {
            "id": int(time.time() * 1000),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": source, # "voice" or "text"
            "user_speech": user_speech.strip(),
            "assistant_response": assistant_response.strip()
        }

        with cls._lock:
            try:
                history = json.loads(cls.HISTORY_FILE.read_text(encoding="utf-8"))
            except Exception:
                history = []

            history.append(entry)

            # Keep last 1000 interactions
            if len(history) > 1000:
                history = history[-1000:]

            cls.HISTORY_FILE.write_text(json.dumps(history, indent=4, ensure_ascii=False), encoding="utf-8")

        # Auto-extract facts from conversation
        extracted = cls._extract_facts_from_conversation(user_speech, assistant_response)
        for fact in extracted:
            cls.remember_fact(fact["key"], fact["value"])

        return entry

    @classmethod
    def remember_fact(cls, key: str, value: str, importance: str | None = None) -> str:
        """Stores a persistent user preference or fact with importance scoring."""
        cls._ensure_files()
        with cls._lock:
            try:
                facts = json.loads(cls.FACTS_FILE.read_text(encoding="utf-8"))
            except Exception:
                facts = {}

            fact_key = key.lower().strip()
            fact_importance = importance or cls._calculate_importance(value)

            facts[fact_key] = {
                "value": value.strip(),
                "importance": fact_importance,
                "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "access_count": facts.get(fact_key, {}).get("access_count", 0) if isinstance(facts.get(fact_key), dict) else 0
            }

            cls.FACTS_FILE.write_text(json.dumps(facts, indent=4, ensure_ascii=False), encoding="utf-8")
        return f"[Memória] Fato gravado com sucesso: '{key}' = '{value}' (importância: {fact_importance})"

    @classmethod
    def get_recent_turns(cls, limit: int = 4) -> list[dict]:
        """Últimos turnos do histórico — usados para follow-ups e contexto do LLM."""
        cls._ensure_files()
        try:
            history = json.loads(cls.HISTORY_FILE.read_text(encoding="utf-8"))
            return history[-limit:] if history else []
        except Exception:
            return []

    @classmethod
    def get_recent_history_for_prompt(cls, limit: int = 4) -> str | None:
        """Resumo compacto das últimas interações para injeção no system prompt."""
        turns = cls.get_recent_turns(limit)
        if not turns:
            return None
        lines = ["CONVERSA RECENTE (contexto — use para entender referências como 'isso', 'aquilo'):"]
        for turn in turns:
            u = (turn.get("user_speech") or "")[:250]
            a = (turn.get("assistant_response") or "")[:350]
            if u:
                lines.append(f"- Mestre: {u}")
            if a:
                lines.append(f"- Você: {a}")
        return "\n".join(lines)

    @classmethod
    def get_facts_for_prompt(cls) -> str:
        """Facts sorted by importance for prompt injection."""
        cls._ensure_files()
        try:
            facts = json.loads(cls.FACTS_FILE.read_text(encoding="utf-8"))
            if not facts:
                return ""

            # Sort by importance (high > medium > low) and access count
            importance_order = {"high": 0, "medium": 1, "low": 2}
            sorted_facts = sorted(
                facts.items(),
                key=lambda x: (
                    importance_order.get(x[1].get("importance", "low"), 2),
                    -x[1].get("access_count", 0)
                ) if isinstance(x[1], dict) else (2, 0)
            )

            lines = []
            for k, v in sorted_facts:
                if isinstance(v, dict):
                    value = v.get("value", str(v))
                    importance = v.get("importance", "low")
                    prefix = "" if importance == "high" else "" if importance == "medium" else ""
                    lines.append(f"{prefix} {k}: {value}")
                else:
                    lines.append(f" {k}: {v}")

            return "\n".join(lines)
        except Exception:
            return ""

    @classmethod
    def get_memory_context(cls) -> str:
        """Formats remembered facts for prompt injection with importance indicators."""
        cls._ensure_files()
        lines = []
        try:
            facts = json.loads(cls.FACTS_FILE.read_text(encoding="utf-8"))
            if facts:
                lines.append("Fatos Lembrados do Mestre (ordenados por importância):")
                importance_order = {"high": 0, "medium": 1, "low": 2}
                sorted_facts = sorted(
                    facts.items(),
                    key=lambda x: importance_order.get(x[1].get("importance", "low"), 2) if isinstance(x[1], dict) else 2
                )
                for k, v in sorted_facts:
                    if isinstance(v, dict):
                        value = v.get("value", str(v))
                        importance = v.get("importance", "low")
                        prefix = "" if importance == "high" else "" if importance == "medium" else ""
                        lines.append(f" {prefix} {k}: {value}")
                    else:
                        lines.append(f" {k}: {v}")
        except Exception:
            pass

        try:
            history = json.loads(cls.HISTORY_FILE.read_text(encoding="utf-8"))
            if history:
                lines.append("\nÚltimas Interações do Histórico:")
                for turn in history[-4:]:
                    lines.append(f" * [{turn['timestamp']}] Mestre: {turn['user_speech']}")
                    lines.append(f" Sábio: {turn['assistant_response']}")
        except Exception:
            pass

        return "\n".join(lines)

    @classmethod
    def search_facts(cls, query: str) -> list[dict]:
        """Search facts by relevance to a query."""
        cls._ensure_files()
        try:
            facts = json.loads(cls.FACTS_FILE.read_text(encoding="utf-8"))
            query_lower = query.lower()
            results = []

            for key, value in facts.items():
                if isinstance(value, dict):
                    value_str = value.get("value", str(value))
                    importance = value.get("importance", "low")
                else:
                    value_str = str(value)
                    importance = "low"

                # Simple relevance scoring
                score = 0
                query_words = query_lower.split()
                for word in query_words:
                    if word in key.lower() or word in value_str.lower():
                        score += 1

                if score > 0:
                    results.append({
                        "key": key,
                        "value": value_str,
                        "importance": importance,
                        "relevance": score
                    })

            # Sort by relevance, then importance
            importance_order = {"high": 0, "medium": 1, "low": 2}
            results.sort(key=lambda x: (-x["relevance"], importance_order.get(x["importance"], 2)))
            return results
        except Exception:
            return []

    @classmethod
    def get_full_history_report(cls, limit: int = 15) -> str:
        """Returns formatted report of archived conversations."""
        cls._ensure_files()
        try:
            history = json.loads(cls.HISTORY_FILE.read_text(encoding="utf-8"))
            if not history:
                return "[Histórico] O arquivo de conversa está limpo."

            lines = [f"=== [HISTÓRICO PERMANENTE DE CONVERSAS (Total: {len(history)} registros)] ==="]
            for turn in history[-limit:]:
                lines.append(f"\n[{turn['timestamp']} | Origem: {turn['source'].upper()}]")
                lines.append(f" Usuário: {turn['user_speech']}")
                lines.append(f" Grande Sábio: {turn['assistant_response']}")
            return "\n".join(lines)
        except Exception as e:
            return f"[Erro] Falha ao ler histórico: {e}"

    # ------------------------------------------------------------------
    # Emotional Memory — Memória Emocional entre sessões
    # ------------------------------------------------------------------

    EMOTIONAL_FILE = None

    @classmethod
    def _emotional_path(cls):
        if cls.EMOTIONAL_FILE is None:
            cls.EMOTIONAL_FILE = cls.BASE_DIR / "emotional_memory.json"
        return cls.EMOTIONAL_FILE

    @classmethod
    def _ensure_emotional(cls):
        p = cls._emotional_path()
        if not p.exists():
            p.write_text('{"mood_log": [], "user_patterns": {}, "last_session_mood": "neutral"}', encoding="utf-8")

    @classmethod
    def save_emotional_state(cls, mood: str, context: str = ""):
        """Salva o humor detectado no fim de uma interação."""
        cls._ensure_emotional()
        with cls._lock:
            try:
                data = json.loads(cls._emotional_path().read_text(encoding="utf-8"))
                log = data.get("mood_log", [])
                log.append({
                    "timestamp": datetime.now().isoformat(),
                    "mood": mood,
                    "context": context[:200],
                })
                if len(log) > 50:
                    log = log[-50:]
                data["mood_log"] = log
                data["last_session_mood"] = mood
                cls._emotional_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass

    @classmethod
    def get_emotional_context(cls) -> str:
        """Retorna contexto emocional para o system prompt."""
        cls._ensure_emotional()
        try:
            data = json.loads(cls._emotional_path().read_text(encoding="utf-8"))
            last_mood = data.get("last_session_mood", "neutral")
            log = data.get("mood_log", [])

            mood_names = {
                "happy": "bom humor",
                "frustrated": "frustração",
                "excited": "empolgação",
                "tired": "cansaço",
                "curious": "curiosidade",
                "thankful": "gratidão",
                "urgent": "urgência",
                "neutral": "neutro",
            }

            lines = []
            if last_mood and last_mood != "neutral":
                mood_pt = mood_names.get(last_mood, last_mood)
                lines.append(f"Estado emocional anterior do Mestre: {mood_pt}.")

            if log:
                recent = log[-5:]
                mood_counts = {}
                for entry in recent:
                    m = entry.get("mood", "neutral")
                    mood_counts[m] = mood_counts.get(m, 0) + 1
                dominant = max(mood_counts, key=mood_counts.get) if mood_counts else None
                if dominant and dominant != "neutral":
                    mood_pt = mood_names.get(dominant, dominant)
                    lines.append(f"Tendência emocional recente: {mood_pt}.")

            return "\n".join(lines)
        except Exception:
            return ""

    @classmethod
    def save_user_pattern(cls, pattern_type: str, value: str):
        """Salva um padrão do usuário (horário típico, temas frequentes, etc)."""
        cls._ensure_emotional()
        with cls._lock:
            try:
                data = json.loads(cls._emotional_path().read_text(encoding="utf-8"))
                patterns = data.get("user_patterns", {})
                if pattern_type not in patterns:
                    patterns[pattern_type] = []
                entries = patterns[pattern_type]
                entries.append({"value": value, "timestamp": datetime.now().isoformat()})
                if len(entries) > 20:
                    entries = entries[-20:]
                patterns[pattern_type] = entries
                data["user_patterns"] = patterns
                cls._emotional_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
