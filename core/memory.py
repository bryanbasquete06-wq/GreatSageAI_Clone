#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Great Sage AI — Memória Inteligente (v2)
==========================================
- Resumo automático de conversas
- Busca semântica por similaridade
- Aprendizado de preferências
- Persistência entre sessões
"""

import json
import re
import time
import math
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from collections import Counter

logger = logging.getLogger("greatsage.memory")


def _tokenize(text: str) -> List[str]:
    """Simple tokenizer for Portuguese."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    return [w for w in text.split() if len(w) > 2]


def _tfidf_similarity(query: str, document: str) -> float:
    """Simple TF-IDF cosine similarity without sklearn."""
    q_tokens = _tokenize(query)
    d_tokens = _tokenize(document)

    if not q_tokens or not d_tokens:
        return 0.0

    # Term frequency
    q_tf = Counter(q_tokens)
    d_tf = Counter(d_tokens)

    # All unique terms
    all_terms = set(q_tokens) | set(d_tokens)

    # Cosine similarity
    dot_product = sum(q_tf.get(t, 0) * d_tf.get(t, 0) for t in all_terms)
    q_norm = math.sqrt(sum(v**2 for v in q_tf.values()))
    d_norm = math.sqrt(sum(v**2 for v in d_tf.values()))

    if q_norm == 0 or d_norm == 0:
        return 0.0

    return dot_product / (q_norm * d_norm)


class Memory:
    """Gerencia memória de longo prazo da IA — v2 inteligente."""

    def __init__(self, memory_dir: str = "memory"):
        self.dir = Path(memory_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

        self.chat_file = self.dir / "chat_history.json"
        self.user_file = self.dir / "user_profile.json"
        self.facts_file = self.dir / "facts.json"
        self.summaries_file = self.dir / "summaries.json"
        self.preferences_file = self.dir / "learned_preferences.json"

        # Carrega dados
        self.chat_history = self._load_json(self.chat_file, [])
        self.user_profile = self._load_json(self.user_file, {
            "name": "Mestre",
            "preferences": {},
            "first_seen": datetime.now().isoformat(),
        })
        self.facts = self._load_json(self.facts_file, [])
        self.summaries = self._load_json(self.summaries_file, [])
        self.learned_preferences = self._load_json(self.preferences_file, {})

        # Limites
        self.max_history = 200
        self.max_summaries = 50

        # Auto-summarize periodically
        self._message_count = len(self.chat_history)
        self._summarize_threshold = 30  # Summarize every 30 messages

    def _load_json(self, path: Path, default):
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Error loading {path}: {e}")
        return default

    def _save_json(self, path: Path, data):
        try:
            path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"Error saving {path}: {e}")

    # ═══ CHAT HISTORY ═══════════════════════════════════════════════

    def add_message(self, role: str, content: str, meta: Optional[Dict] = None):
        """Adiciona mensagem e aprende preferências automaticamente."""
        msg = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        if meta:
            msg["meta"] = meta

        self.chat_history.append(msg)
        self._message_count += 1

        # Learn preferences from user messages
        if role == "user":
            self._learn_preferences(content)

        # Auto-summarize periodically
        if self._message_count >= self._summarize_threshold:
            self._auto_summarize()

        # Limit size
        if len(self.chat_history) > self.max_history:
            old = self.chat_history[:50]
            backup_file = self.dir / f"backup_{int(time.time())}.json"
            self._save_json(backup_file, old)
            self.chat_history = self.chat_history[50:]

        self._save_json(self.chat_file, self.chat_history)

    def get_recent_messages(self, count: int = 20) -> List[Dict]:
        return self.chat_history[-count:]

    def get_context_messages(self, max_tokens: int = 8000) -> List[Dict]:
        """Retorna mensagens do contexto com resumo se disponível."""
        messages = []
        total_chars = 0
        limit = max_tokens * 4

        # Add relevant summaries as context
        if self.summaries:
            recent_summaries = self.summaries[-3:]  # Last 3 summaries
            summary_text = "\n".join(s["summary"] for s in recent_summaries)
            summary_msg = {
                "role": "system",
                "content": f"Resumo de conversas anteriores:\n{summary_text}"
            }
            total_chars += len(summary_text)
            messages.append(summary_msg)

        # Add recent messages
        for msg in reversed(self.chat_history):
            msg_len = len(msg["content"])
            if total_chars + msg_len > limit:
                break
            messages.insert(-1 if messages else 0, msg)
            total_chars += msg_len

        return messages

    def clear_history(self):
        if self.chat_history:
            backup = self.dir / f"backup_{int(time.time())}.json"
            self._save_json(backup, self.chat_history)
        self.chat_history = []
        self._save_json(self.chat_file, self.chat_history)

    # ═══ SMART SUMMARIZATION ═════════════════════════════════════════

    def _auto_summarize(self):
        """Auto-summarize old messages to save context space."""
        if len(self.chat_history) < 20:
            return

        # Take oldest 20 messages for summarization
        old_messages = self.chat_history[:20]
        summary = self._create_summary(old_messages)

        if summary:
            self.summaries.append({
                "summary": summary,
                "timestamp": datetime.now().isoformat(),
                "message_count": len(old_messages),
            })

            # Keep only recent summaries
            if len(self.summaries) > self.max_summaries:
                self.summaries = self.summaries[-self.max_summaries:]

            self._save_json(self.summaries_file, self.summaries)

            # Remove summarized messages (keep last 10 for continuity)
            self.chat_history = self.chat_history[10:]
            self._save_json(self.chat_file, self.chat_history)

            logger.info(f"Auto-summarized {len(old_messages)} messages")

    def _create_summary(self, messages: List[Dict]) -> str:
        """Create a summary from messages (extractive approach)."""
        user_msgs = [m["content"] for m in messages if m["role"] == "user"]
        assistant_msgs = [m["content"] for m in messages if m["role"] == "assistant"]

        if not user_msgs:
            return ""

        # Extract key topics
        topics = []
        for msg in user_msgs:
            # Extract sentences
            sentences = re.split(r'[.!?]+', msg)
            for s in sentences:
                s = s.strip()
                if len(s) > 10:
                    topics.append(s[:100])

        # Create summary
        summary_parts = []
        if topics:
            summary_parts.append(f"Tópicos discutidos: {'; '.join(topics[:5])}")

        # Extract key facts from assistant responses
        facts = []
        for msg in assistant_msgs:
            if len(msg) > 50:
                # Take first sentence as key point
                first_sentence = re.split(r'[.!?]+', msg)[0].strip()
                if len(first_sentence) > 10:
                    facts.append(first_sentence[:100])

        if facts:
            summary_parts.append(f"Pontos-chave: {'; '.join(facts[:3])}")

        return " | ".join(summary_parts) if summary_parts else ""

    def get_relevant_summaries(self, query: str, top_k: int = 3) -> List[str]:
        """Search summaries by semantic similarity."""
        if not self.summaries:
            return []

        scored = []
        for s in self.summaries:
            sim = _tfidf_similarity(query, s["summary"])
            scored.append((sim, s["summary"]))

        scored.sort(reverse=True)
        return [summary for _, summary in scored[:top_k]]

    # ═══ SEMANTIC SEARCH ═════════════════════════════════════════════

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """Search chat history by semantic similarity."""
        results = []
        query_lower = query.lower()

        for msg in self.chat_history:
            # Quick keyword match
            if query_lower in msg["content"].lower():
                results.append({"score": 1.0, "message": msg})
                continue

            # TF-IDF similarity
            sim = _tfidf_similarity(query, msg["content"])
            if sim > 0.1:
                results.append({"score": sim, "message": msg})

        results.sort(key=lambda x: x["score"], reverse=True)
        return [r["message"] for r in results[:top_k]]

    # ═══ USER PROFILE & LEARNING ═════════════════════════════════════

    def get_user_name(self) -> str:
        return self.user_profile.get("name", "Mestre")

    def set_user_name(self, name: str):
        self.user_profile["name"] = name
        self._save_json(self.user_file, self.user_profile)

    def set_preference(self, key: str, value):
        self.user_profile.setdefault("preferences", {})[key] = value
        self._save_json(self.user_file, self.user_profile)

    def get_preference(self, key: str, default=None):
        return self.user_profile.get("preferences", {}).get(key, default)

    def _learn_preferences(self, text: str):
        """Learn user preferences from messages."""
        text_lower = text.lower()

        # Learn language preference
        if any(w in text_lower for w in ["em ingles", "in english", "english please"]):
            self.learned_preferences["language"] = "en"
        elif any(w in text_lower for w in ["em portugues", "portugues", "pt-br"]):
            self.learned_preferences["language"] = "pt-BR"

        # Learn topic interests
        topics = {
            "programacao": ["python", "javascript", "code", "coding", "programa"],
            "tecnologia": ["tech", "ia", "ai", "machine learning", "deep learning"],
            "jogos": ["game", "jogo", "gaming", "steam", "playstation"],
            "musica": ["musica", "music", "spotify", "playlist"],
            "filmes": ["filme", "movie", "netflix", "serie"],
        }

        for topic, keywords in topics.items():
            if any(k in text_lower for k in keywords):
                count = self.learned_preferences.get(f"interest_{topic}", 0)
                self.learned_preferences[f"interest_{topic}"] = count + 1

        # Learn response style preference
        if any(w in text_lower for w in ["resumo", "curto", "brief", "short"]):
            self.learned_preferences["response_style"] = "concise"
        elif any(w in text_lower for w in ["detalhado", "detailed", "explica", "explain"]):
            self.learned_preferences["response_style"] = "detailed"

        self._save_json(self.preferences_file, self.learned_preferences)

    def get_learned_context(self) -> str:
        """Get learned preferences as context for the LLM."""
        if not self.learned_preferences:
            return ""

        parts = []

        # Language
        lang = self.learned_preferences.get("language")
        if lang:
            parts.append(f"Idioma preferido: {lang}")

        # Top interests
        interests = {k.replace("interest_", ""): v
                    for k, v in self.learned_preferences.items()
                    if k.startswith("interest_")}
        if interests:
            top = sorted(interests.items(), key=lambda x: x[1], reverse=True)[:3]
            parts.append(f"Assuntos de interesse: {', '.join(t[0] for t in top)}")

        # Response style
        style = self.learned_preferences.get("response_style")
        if style:
            parts.append(f"Estilo de resposta preferido: {style}")

        return "\n".join(parts) if parts else ""

    # ═══ FACTS ═══════════════════════════════════════════════════════

    def remember(self, fact: str, category: str = "general"):
        self.facts.append({
            "fact": fact,
            "category": category,
            "timestamp": datetime.now().isoformat(),
        })
        self._save_json(self.facts_file, self.facts)

    def recall(self, query: str = "", category: str = "") -> List[Dict]:
        results = []
        for f in self.facts:
            if category and f.get("category") != category:
                continue
            if query:
                sim = _tfidf_similarity(query, f.get("fact", ""))
                if sim > 0.05 or query.lower() in f.get("fact", "").lower():
                    results.append({"score": sim, "fact": f})
            else:
                results.append({"score": 0.5, "fact": f})

        results.sort(key=lambda x: x["score"], reverse=True)
        return [r["fact"] for r in results]

    def get_all_facts(self) -> List[Dict]:
        return self.facts

    def build_memory_context(self) -> str:
        """Build memory context for LLM."""
        parts = []

        # Learned preferences
        prefs = self.get_learned_context()
        if prefs:
            parts.append(f"Preferências aprendidas:\n{prefs}")

        # Recent facts
        if self.facts:
            recent_facts = self.facts[-10:]
            facts_text = "\n".join(f"  • {f['fact']}" for f in recent_facts)
            parts.append(f"Fatos importantes:\n{facts_text}")

        # User profile
        name = self.get_user_name()
        if name != "Mestre":
            parts.append(f"Nome do usuário: {name}")

        return "\n\n".join(parts)
