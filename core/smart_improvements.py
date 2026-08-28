# -*- coding: utf-8 -*-
"""
Great Sage AI — Smart Improvements v1 (20 Features)
====================================================
20 melhorias seguras que NÃO modificam código existente.
Cada feature é independente, com try/except, e pode ser desligada.

Features:
 1. Semantic Search — busca por significado, não só palavras-chave
 2. Session Memory — lembra o contexto da sessão atual
 3. Learning Dashboard — mostra o que a IA aprendeu
 4. Error Learning — registra erros e como foram corrigidos
 5. Code Pattern Learning — aprende padrões de código preferidos
 6. Voice Command Learning — aprende comandos de voz que funcionam
 7. Smart Reminders — lembretes baseados em conversa
 8. Conversation Summaries — resumo automático de conversas longas
 9. Mood Tracking — rastreia humor do usuário ao longo do tempo
10. Response Feedback — rastreia quais respostas foram boas
11. Smart Defaults — lembra preferências do usuário
12. Code Snippet Cache — cache de snippets de código usados
13. Conversation Branching — permite explorar caminhos diferentes
14. Proactive Code Review — sugere review de código automaticamente
15. Smart File Recommendations — recomenda arquivos relevantes
16. Adaptive Response Length — ajusta comprimento da resposta
17. Personality Learning — aprende o estilo preferido do usuário
18. Knowledge Graph — constrói relações entre conceitos
19. Smart Aliases — aprende atalhos para comandos
20. Health Monitoring — monitora saúde do sistema continuamente
"""

from __future__ import annotations

import json
import time
import logging
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger("greatsage.smart")

# ── Config ───────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).resolve().parent.parent / "config" / "smart_data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. SEMANTIC SEARCH — busca por significado
# ═══════════════════════════════════════════════════════════════════════════════

# Sinônimos e termos relacionados para busca semântica
SYNONYM_MAP = {
    "python": ["py", "pip", "django", "flask", "fastapi", "script"],
    "javascript": ["js", "node", "react", "vue", "angular", "typescript", "ts"],
    "bug": ["erro", "problema", "issue", "falha", "crash", "exception"],
    "código": ["code", "programa", "script", "arquivo", "fonte"],
    "database": ["banco", "db", "sql", "mysql", "postgres", "sqlite", "mongo"],
    "api": ["endpoint", "rota", "url", "webhook", "rest", "graphql"],
    "deploy": ["publicar", "hosting", "servidor", "cloud", "aws", "azure"],
    "docker": ["container", "compose", "image", "kubernetes", "k8s"],
    "git": ["github", "repositório", "commit", "branch", "merge", "pull request"],
    "rede": ["network", "wifi", "ip", "dns", "firewall", "proxy"],
    "áudio": ["audio", "som", "voz", "microfone", "alto-falante", "tts"],
    "imagem": ["image", "foto", "png", "jpg", "screenshot", "ícone"],
    "segurança": ["security", "senha", "criptografia", "hash", "token"],
    "performance": ["velocidade", "otimização", "rapidez", "lentidão", "cache"],
    "erro": ["error", "exception", "traceback", "stacktrace", "falha"],
}


def semantic_search(query: str, memory, limit: int = 5) -> list:
    """Busca memórias expandindo a query com sinônimos."""
    try:
        # Busca original
        results = memory.search(query, limit=limit)

        # Expande com sinônimos
        query_lower = query.lower()
        expanded_terms = set()
        for term, synonyms in SYNONYM_MAP.items():
            if term in query_lower or any(s in query_lower for s in synonyms):
                expanded_terms.update(synonyms)
                expanded_terms.add(term)

        # Busca expandida (só se houver sinônimos)
        if expanded_terms and len(results) < limit:
            for term in list(expanded_terms)[:3]:
                extra = memory.search(term, limit=2)
                for e in extra:
                    if e.id not in {r.id for r in results}:
                        results.append(e)

        return results[:limit]
    except Exception as e:
        logger.debug(f"Semantic search error: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# 2. SESSION MEMORY — contexto da sessão atual
# ═══════════════════════════════════════════════════════════════════════════════

class SessionMemory:
    """Lembra o contexto da sessão atual (não persiste entre reinícios)."""

    def __init__(self, max_turns: int = 50):
        self.turns: List[Dict] = []
        self.max_turns = max_turns
        self.topics: Dict[str, int] = defaultdict(int)
        self.user_name: str = ""
        self.started_at: float = time.time()

    def add_turn(self, role: str, content: str):
        self.turns.append({
            "role": role,
            "content": content[:500],
            "ts": time.time(),
        })
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]

        # Track topics
        words = content.lower().split()
        for w in words:
            if len(w) > 4:
                self.topics[w] += 1

    def get_recent_context(self, n: int = 5) -> str:
        recent = self.turns[-n:]
        return "\n".join(f"{t['role']}: {t['content'][:100]}" for t in recent)

    def get_dominant_topics(self, top_n: int = 5) -> List[str]:
        sorted_topics = sorted(self.topics.items(), key=lambda x: x[1], reverse=True)
        return [t[0] for t in sorted_topics[:top_n]]

    def get_session_duration(self) -> float:
        return time.time() - self.started_at

    def to_prompt_context(self) -> str:
        if not self.turns:
            return ""
        topics = self.get_dominant_topics()
        duration = int(self.get_session_duration() / 60)
        return (f"Contexto da sessão: {len(self.turns)} trocas, "
                f"{duration}min, temas: {', '.join(topics[:3])}")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. LEARNING DASHBOARD — mostra o que a IA aprendeu
# ═══════════════════════════════════════════════════════════════════════════════

class LearningDashboard:
    """Dashboard de aprendizado — mostra estatísticas de melhoria."""

    def __init__(self, memory=None):
        self.memory = memory

    def get_dashboard(self) -> Dict:
        stats = {
            "corrections": {},
            "patterns": {},
            "memory": {},
            "session": {},
            "suggestions": {},
        }

        try:
            if self.memory:
                stats["corrections"] = self.memory.get_correction_stats()
                stats["memory"] = self.memory.stats()
        except Exception:
            pass

        return stats

    def format_dashboard(self) -> str:
        d = self.get_dashboard()
        lines = ["═══ DASHBOARD DE APRENDIZADO ═══", ""]

        # Corrections
        corr = d.get("corrections", {})
        lines.append(f"📚 Correções registradas: {corr.get('total_corrections', 0)}")
        if corr.get("most_corrected") and corr["most_corrected"] != "none":
            lines.append(f"   Tema mais corrigido: {corr['most_corrected']}")
        lines.append("")

        # Memory
        mem = d.get("memory", {})
        lines.append(f"🧠 Memórias totais: {mem.get('total', 0)}")
        lines.append(f"   Importância média: {mem.get('avg_importance', 0):.2f}")
        lines.append(f"   Alta importância: {mem.get('high_importance', 0)}")
        lines.append("")

        # Categories
        cats = mem.get("categories", {})
        if cats:
            lines.append("📊 Categorias:")
            for cat, info in cats.items():
                lines.append(f"   {cat}: {info['count']} (imp: {info['avg_importance']:.2f})")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. ERROR LEARNING — registra erros e como foram corrigidos
# ═══════════════════════════════════════════════════════════════════════════════

class ErrorLearner:
    """Aprende com erros — registra o que deu errado e como foi resolvido."""

    def __init__(self, memory=None):
        self.memory = memory
        self._error_log = DATA_DIR / "error_log.jsonl"

    def record_error(self, error_type: str, error_msg: str, context: str = "",
                     resolution: str = ""):
        entry = {
            "ts": time.time(),
            "type": error_type,
            "message": error_msg[:300],
            "context": context[:200],
            "resolution": resolution[:200],
        }
        try:
            with self._error_log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

        # Also store in memory for LLM access
        if self.memory:
            content = (f"ERRO: {error_type} — {error_msg[:150]}. "
                       f"Contexto: {context[:100]}. "
                       f"Solução: {resolution[:100]}" if resolution else "")
            if content:
                self.memory.add("error_log", content, importance=0.6,
                                tags=["error", error_type])

    def get_recent_errors(self, limit: int = 5) -> List[Dict]:
        errors = []
        try:
            if self._error_log.exists():
                lines = self._error_log.read_text(encoding="utf-8").splitlines()
                for line in lines[-limit:]:
                    if line.strip():
                        errors.append(json.loads(line))
        except Exception:
            pass
        return errors

    def get_error_patterns(self) -> Dict[str, int]:
        patterns = defaultdict(int)
        try:
            for e in self.get_recent_errors(50):
                patterns[e.get("type", "unknown")] += 1
        except Exception:
            pass
        return dict(patterns)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. CODE PATTERN LEARNING — aprende padrões de código
# ═══════════════════════════════════════════════════════════════════════════════

class CodePatternLearner:
    """Aprende padrões de código que o usuário prefere."""

    def __init__(self, memory=None):
        self.memory = memory
        self._patterns_file = DATA_DIR / "code_patterns.json"
        self._patterns = self._load()

    def _load(self) -> Dict:
        try:
            if self._patterns_file.exists():
                return json.loads(self._patterns_file.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {"languages": {}, "styles": {}, "common_snippets": []}

    def _save(self):
        try:
            self._patterns_file.write_text(
                json.dumps(self._patterns, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def learn_from_code(self, code: str, language: str = ""):
        if not language:
            language = self._detect_language(code)
        if language:
            self._patterns["languages"][language] = \
                self._patterns["languages"].get(language, 0) + 1
            self._save()

    def get_preferred_language(self) -> str:
        langs = self._patterns.get("languages", {})
        if not langs:
            return "python"
        return max(langs, key=langs.get)

    def _detect_language(self, code: str) -> str:
        indicators = {
            "python": ["def ", "import ", "from ", "class ", "if __name__"],
            "javascript": ["function ", "const ", "let ", "var ", "=>", "async"],
            "typescript": [": string", ": number", ": boolean", "interface "],
            "html": ["<html", "<div", "<body", "<!DOCTYPE"],
            "css": ["{", "}", "color:", "background:"],
            "bash": ["#!/bin/bash", "#!/bin/sh", "echo ", "if ["],
        }
        for lang, patterns in indicators.items():
            if any(p in code for p in patterns):
                return lang
        return ""


# ═══════════════════════════════════════════════════════════════════════════════
# 6. VOICE COMMAND LEARNING — aprende comandos de voz
# ═══════════════════════════════════════════════════════════════════════════════

class VoiceCommandLearner:
    """Aprende comandos de voz que funcionam e os que falham."""

    def __init__(self, memory=None):
        self.memory = memory
        self._commands_file = DATA_DIR / "voice_commands.json"
        self._commands = self._load()

    def _load(self) -> Dict:
        try:
            if self._commands_file.exists():
                return json.loads(self._commands_file.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {"successful": {}, "failed": {}, "aliases": {}}

    def _save(self):
        try:
            self._commands_file.write_text(
                json.dumps(self._commands, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def record_success(self, command: str, intent: str):
        key = command.lower().strip()
        self._commands["successful"][key] = {
            "intent": intent,
            "count": self._commands["successful"].get(key, {}).get("count", 0) + 1,
            "last_used": time.time(),
        }
        self._save()

    def record_failure(self, command: str, reason: str = ""):
        key = command.lower().strip()
        self._commands["failed"][key] = {
            "reason": reason[:100],
            "count": self._commands["failed"].get(key, {}).get("count", 0) + 1,
        }
        self._save()

    def add_alias(self, shortcut: str, full_command: str):
        self._commands["aliases"][shortcut.lower()] = full_command
        self._save()

    def resolve_alias(self, command: str) -> str:
        return self._commands["aliases"].get(command.lower(), command)

    def get_frequent_commands(self, limit: int = 10) -> List[Dict]:
        cmds = self._commands.get("successful", {})
        sorted_cmds = sorted(cmds.items(), key=lambda x: x[1].get("count", 0), reverse=True)
        return [{"command": k, **v} for k, v in sorted_cmds[:limit]]


# ═══════════════════════════════════════════════════════════════════════════════
# 7. SMART REMINDERS — lembretes baseados em conversa
# ═══════════════════════════════════════════════════════════════════════════════

class SmartReminders:
    """Detecta lembretes em conversas e os gerencia."""

    REMINDER_PATTERNS = [
        "lembra", "lembre", "não esquece", "depois me avisa",
        "amanhã", "próxima semana", "daqui a", "me avisa quando",
        "me cobra", "não deixa passar",
    ]

    def __init__(self, memory=None):
        self.memory = memory
        self._reminders_file = DATA_DIR / "reminders.json"
        self._reminders = self._load()

    def _load(self) -> List[Dict]:
        try:
            if self._reminders_file.exists():
                return json.loads(self._reminders_file.read_text(encoding="utf-8"))
        except Exception:
            pass
        return []

    def _save(self):
        try:
            self._reminders_file.write_text(
                json.dumps(self._reminders, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def detect_reminder(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        for pattern in self.REMINDER_PATTERNS:
            if pattern in text_lower:
                return text
        return None

    def add_reminder(self, text: str, when: str = "later"):
        reminder = {
            "text": text[:200],
            "when": when,
            "created_at": time.time(),
            "active": True,
        }
        self._reminders.append(reminder)
        self._save()

        if self.memory:
            self.memory.add("task", f"Lembrete: {text[:200]}", importance=0.8,
                            tags=["reminder"])

    def get_active_reminders(self) -> List[Dict]:
        return [r for r in self._reminders if r.get("active", True)]

    def check_reminders(self) -> List[str]:
        active = self.get_active_reminders()
        if not active:
            return []
        return [f"📢 Lembrete: {r['text'][:100]}" for r in active[:3]]


# ═══════════════════════════════════════════════════════════════════════════════
# 8. CONVERSATION SUMMARIES — resumo automático
# ═══════════════════════════════════════════════════════════════════════════════

class ConversationSummarizer:
    """Gera resumos automáticos de conversas longas."""

    def __init__(self, memory=None):
        self.memory = memory

    def summarize_session(self, session_memory: 'SessionMemory') -> str:
        if len(session_memory.turns) < 5:
            return ""

        topics = session_memory.get_dominant_topics(5)
        duration = int(session_memory.get_session_duration() / 60)
        n_turns = len(session_memory.turns)

        summary = (f"Sessão de {duration}min com {n_turns} trocas. "
                   f"Temas principais: {', '.join(topics[:3])}.")

        # Store in memory
        if self.memory:
            self.memory.add("summary", summary, importance=0.5, tags=["session_summary"])

        return summary

    def get_context_summary(self, query: str, memory) -> str:
        """Gera resumo contextual para injeção no prompt."""
        try:
            entries = memory.search(query, limit=3, min_importance=0.3)
            if not entries:
                return ""
            parts = []
            for e in entries:
                parts.append(f"• {e.content[:150]}")
            return "Contexto relevante:\n" + "\n".join(parts)
        except Exception:
            return ""


# ═══════════════════════════════════════════════════════════════════════════════
# 9. MOOD TRACKING — rastreia humor ao longo do tempo
# ═══════════════════════════════════════════════════════════════════════════════

class MoodTracker:
    """Rastreia humor do usuário ao longo das sessões."""

    def __init__(self, memory=None):
        self.memory = memory
        self._mood_file = DATA_DIR / "mood_history.json"
        self._history = self._load()

    def _load(self) -> List[Dict]:
        try:
            if self._mood_file.exists():
                data = json.loads(self._mood_file.read_text(encoding="utf-8"))
                return data[-100:]  # keep last 100
        except Exception:
            pass
        return []

    def _save(self):
        try:
            self._mood_file.write_text(
                json.dumps(self._history[-100:], indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def record_mood(self, mood: str, context: str = ""):
        self._history.append({
            "mood": mood,
            "context": context[:100],
            "ts": time.time(),
        })
        self._save()

    def get_mood_trend(self) -> str:
        if not self._history:
            return "neutral"
        recent = self._history[-10:]
        moods = [h["mood"] for h in recent]
        # Most common mood
        from collections import Counter
        most_common = Counter(moods).most_common(1)
        return most_common[0][0] if most_common else "neutral"

    def get_mood_summary(self) -> str:
        trend = self.get_mood_trend()
        total = len(self._history)
        return f"Humor predominante: {trend} (baseado em {total} registros)"


# ═══════════════════════════════════════════════════════════════════════════════
# 10. RESPONSE FEEDBACK — rastreia qualidade das respostas
# ═══════════════════════════════════════════════════════════════════════════════

class ResponseFeedback:
    """Rastreia quais respostas foram boas e quais foram corrigidas."""

    def __init__(self, memory=None):
        self.memory = memory
        self._feedback_file = DATA_DIR / "response_feedback.json"
        self._feedback = self._load()

    def _load(self) -> Dict:
        try:
            if self._feedback_file.exists():
                return json.loads(self._feedback_file.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {"good": 0, "corrected": 0, "avg_length": 0, "total": 0}

    def _save(self):
        try:
            self._feedback_file.write_text(
                json.dumps(self._feedback, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def record_good_response(self, length: int):
        self._feedback["good"] = self._feedback.get("good", 0) + 1
        self._feedback["total"] = self._feedback.get("total", 0) + 1
        total = self._feedback["total"]
        avg = self._feedback.get("avg_length", 0)
        self._feedback["avg_length"] = (avg * (total - 1) + length) / total
        self._save()

    def record_correction(self):
        self._feedback["corrected"] = self._feedback.get("corrected", 0) + 1
        self._feedback["total"] = self._feedback.get("total", 0) + 1
        self._save()

    def get_quality_score(self) -> float:
        total = self._feedback.get("total", 0)
        if total == 0:
            return 0.5
        good = self._feedback.get("good", 0)
        return good / total

    def get_preferred_length(self) -> int:
        return int(self._feedback.get("avg_length", 200))


# ═══════════════════════════════════════════════════════════════════════════════
# 11. SMART DEFAULTS — preferências do usuário
# ═══════════════════════════════════════════════════════════════════════════════

class SmartDefaults:
    """Lembra e aplica preferências do usuário automaticamente."""

    def __init__(self, memory=None):
        self.memory = memory
        self._defaults_file = DATA_DIR / "user_defaults.json"
        self._defaults = self._load()

    def _load(self) -> Dict:
        try:
            if self._defaults_file.exists():
                return json.loads(self._defaults_file.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {
            "language": "pt-BR",
            "response_style": "conversational",
            "code_style": "clean",
            "verbosity": "medium",
            "favorite_language": "python",
        }

    def _save(self):
        try:
            self._defaults_file.write_text(
                json.dumps(self._defaults, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def get(self, key: str, default=None):
        return self._defaults.get(key, default)

    def set(self, key: str, value: str):
        self._defaults[key] = value
        self._save()

    def learn_from_interaction(self, text: str):
        text_lower = text.lower()
        # Detect language preference
        if any(w in text_lower for w in ["em inglês", "in english", "translate"]):
            self.set("language", "en")
        elif any(w in text_lower for w in ["em português", "em pt", "português"]):
            self.set("language", "pt-BR")
        # Detect verbosity preference
        if any(w in text_lower for w in ["curto", "rápido", "resumo", "breve"]):
            self.set("verbosity", "short")
        elif any(w in text_lower for w in ["detalhado", "completo", "explica"]):
            self.set("verbosity", "detailed")

    def to_prompt_context(self) -> str:
        parts = []
        if self._defaults.get("language") != "pt-BR":
            parts.append(f"Idioma preferido: {self._defaults['language']}")
        if self._defaults.get("verbosity") == "short":
            parts.append("Preferência: respostas curtas")
        elif self._defaults.get("verbosity") == "detailed":
            parts.append("Preferência: respostas detalhadas")
        return " | ".join(parts) if parts else ""


# ═══════════════════════════════════════════════════════════════════════════════
# 12. CODE SNIPPET CACHE — cache de código
# ═══════════════════════════════════════════════════════════════════════════════

class CodeSnippetCache:
    """Cache de snippets de código usados frequentemente."""

    def __init__(self):
        self._cache_file = DATA_DIR / "snippet_cache.json"
        self._cache = self._load()

    def _load(self) -> Dict:
        try:
            if self._cache_file.exists():
                return json.loads(self._cache_file.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save(self):
        try:
            # Keep only top 50 snippets
            sorted_cache = sorted(
                self._cache.items(),
                key=lambda x: x[1].get("uses", 0),
                reverse=True,
            )[:50]
            self._cache = dict(sorted_cache)
            self._cache_file.write_text(
                json.dumps(self._cache, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def add(self, code: str, language: str, description: str = ""):
        key = hashlib.md5(code.encode()).hexdigest()[:8]
        self._cache[key] = {
            "code": code[:1000],
            "language": language,
            "description": description[:100],
            "uses": self._cache.get(key, {}).get("uses", 0) + 1,
            "last_used": time.time(),
        }
        self._save()

    def find_similar(self, query: str, limit: int = 3) -> List[Dict]:
        results = []
        query_lower = query.lower()
        for key, snippet in self._cache.items():
            desc = snippet.get("description", "").lower()
            lang = snippet.get("language", "").lower()
            if query_lower in desc or query_lower in lang:
                results.append(snippet)
        return results[:limit]


# ═══════════════════════════════════════════════════════════════════════════════
# 13-20. Remaining features (lightweight implementations)
# ═══════════════════════════════════════════════════════════════════════════════

class ConversationBranching:
    """Permite explorar caminhos diferentes numa conversa."""
    def __init__(self):
        self.branches: Dict[str, List[Dict]] = {}
        self.current_branch = "main"

    def create_branch(self, name: str, from_turn: int = -1):
        if self.current_branch in self.branches:
            self.branches[name] = list(self.branches[self.current_branch][:from_turn])
        else:
            self.branches[name] = []
        self.current_branch = name

    def add_turn(self, role: str, content: str):
        if self.current_branch not in self.branches:
            self.branches[self.current_branch] = []
        self.branches[self.current_branch].append({"role": role, "content": content})

    def get_branch_names(self) -> List[str]:
        return list(self.branches.keys())


class ProactiveCodeReview:
    """Sugere review de código automaticamente."""
    def __init__(self, memory=None):
        self.memory = memory

    def should_review(self, code: str) -> bool:
        indicators = ["def ", "class ", "function ", "async ", "try:", "except"]
        return any(ind in code for ind in indicators) and len(code) > 100

    def get_review_prompt(self, code: str, language: str = "") -> str:
        return (f"Analise este código e sugira 3 melhorias concisas:\n"
                f"```{language}\n{code[:500]}\n```")


class SmartFileRecommendations:
    """Recomenda arquivos relevantes baseado no contexto."""
    def __init__(self):
        self._access_log: Dict[str, int] = defaultdict(int)

    def record_access(self, filepath: str):
        self._access_log[filepath] += 1

    def get_relevant_files(self, context: str, limit: int = 5) -> List[str]:
        context_words = set(context.lower().split())
        scored = []
        for path, count in self._access_log.items():
            path_words = set(path.lower().replace("/", " ").replace(".", " ").split())
            overlap = len(context_words & path_words)
            scored.append((path, overlap * count))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [s[0] for s in scored[:limit]]


class AdaptiveResponseLength:
    """Ajusta comprimento da resposta baseado no comportamento do usuário."""
    def __init__(self):
        self._response_lengths: List[int] = []
        self._user_feedback: List[str] = []

    def record_response(self, length: int):
        self._response_lengths.append(length)
        if len(self._response_lengths) > 50:
            self._response_lengths = self._response_lengths[-50:]

    def record_feedback(self, feedback: str):
        self._user_feedback.append(feedback)
        if len(self._user_feedback) > 20:
            self._user_feedback = self._user_feedback[-20:]

    def get_preferred_length(self) -> str:
        short_count = sum(1 for f in self._user_feedback if "curto" in f.lower())
        long_count = sum(1 for f in self._user_feedback if "detalhado" in f.lower())
        if short_count > long_count:
            return "short"
        elif long_count > short_count:
            return "detailed"
        return "medium"


class PersonalityLearning:
    """Aprende o estilo preferido do usuário."""
    def __init__(self):
        self._styles: Dict[str, int] = defaultdict(int)

    def record_style(self, style: str):
        self._styles[style] += 1

    def get_preferred_style(self) -> str:
        if not self._styles:
            return "balanced"
        return max(self._styles, key=self._styles.get)


class KnowledgeGraph:
    """Constrói relações entre conceitos."""
    def __init__(self):
        self._graph: Dict[str, List[str]] = defaultdict(list)
        self._file = DATA_DIR / "knowledge_graph.json"
        self._load()

    def _load(self):
        try:
            if self._file.exists():
                data = json.loads(self._file.read_text(encoding="utf-8"))
                self._graph = defaultdict(list, data)
        except Exception:
            pass

    def _save(self):
        try:
            self._file.write_text(
                json.dumps(dict(self._graph), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def add_relation(self, concept_a: str, concept_b: str):
        if concept_b not in self._graph[concept_a]:
            self._graph[concept_a].append(concept_b)
        if concept_a not in self._graph[concept_b]:
            self._graph[concept_b].append(concept_a)
        self._save()

    def get_related(self, concept: str) -> List[str]:
        return self._graph.get(concept, [])

    def find_path(self, start: str, end: str, max_depth: int = 3) -> List[str]:
        visited = set()
        queue = [(start, [start])]
        while queue:
            node, path = queue.pop(0)
            if node == end:
                return path
            if len(path) > max_depth:
                continue
            if node in visited:
                continue
            visited.add(node)
            for neighbor in self._graph.get(node, []):
                queue.append((neighbor, path + [neighbor]))
        return []


class SmartAliases:
    """Aprende atalhos para comandos."""
    def __init__(self):
        self._aliases: Dict[str, str] = {}
        self._file = DATA_DIR / "smart_aliases.json"
        self._load()

    def _load(self):
        try:
            if self._file.exists():
                self._aliases = json.loads(self._file.read_text(encoding="utf-8"))
        except Exception:
            pass

    def _save(self):
        try:
            self._file.write_text(
                json.dumps(self._aliases, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def add_alias(self, shortcut: str, full: str):
        self._aliases[shortcut.lower()] = full
        self._save()

    def resolve(self, text: str) -> str:
        return self._aliases.get(text.lower().strip(), text)

    def get_aliases(self) -> Dict[str, str]:
        return dict(self._aliases)


class HealthMonitor:
    """Monitora saúde do sistema continuamente."""
    def __init__(self):
        self._checks: Dict[str, Dict] = {}

    def check_provider(self, name: str, available: bool, latency_ms: float = 0):
        self._checks[name] = {
            "available": available,
            "latency_ms": latency_ms,
            "last_check": time.time(),
        }

    def check_mic(self, available: bool, name: str = ""):
        self._checks["microphone"] = {
            "available": available,
            "name": name,
            "last_check": time.time(),
        }

    def check_speaker(self, available: bool):
        self._checks["speaker"] = {
            "available": available,
            "last_check": time.time(),
        }

    def get_health_report(self) -> str:
        lines = ["═══ SAÚDE DO SISTEMA ═══"]
        for name, info in self._checks.items():
            status = "✓" if info.get("available") else "✗"
            latency = f" ({info['latency_ms']:.0f}ms)" if info.get("latency_ms") else ""
            lines.append(f"  {status} {name}{latency}")
        return "\n".join(lines)

    def get_overall_health(self) -> float:
        if not self._checks:
            return 0.5
        available = sum(1 for c in self._checks.values() if c.get("available"))
        return available / len(self._checks)
