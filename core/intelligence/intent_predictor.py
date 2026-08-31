#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Intent Predictor v2
=====================
Major upgrade: multi-turn prediction, ambiguity resolution,
proactive suggestions, fuzzy matching, and learned behavior.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class IntentSuggestion:
    """A single intent prediction."""
    intent: str
    confidence: float
    suggestion: str
    description: str
    category: str
    follow_up: Optional[str] = None


class IntentPredictor:
    """
    Predicts user intent from partial or complete input.
    v2: Multi-turn prediction, ambiguity resolution, fuzzy matching.
    """

    INTENT_MAP = {
        "code": [
            (r"^(crie|gere|escreva|implemente|faça|code|write|generate|criar|build|make)", "code_generate"),
            (r"^(refatore|refactor|limpe|clean|organize|reorganize|simplifique)", "code_refactor"),
            (r"^(teste|test|mock|stub|fixture|coverage)", "code_test"),
            (r"^(debug|corrija|fix|corrige|resolve|trate)", "code_debug"),
            (r"^(analise|analyze|review|revise|check|audit)", "code_review"),
            (r"^(documente|docstring|comente|comment)", "code_document"),
            (r"^(otimize|optimize|performance|cache|lazy)", "code_optimize"),
        ],
        "question": [
            (r"^[\w\s]*\?$", "question"),
            (r"^(o que|qual|quem|como|onde|quando|por que|porque|explain|what|how|why)", "question"),
            (r"^(explique|explana|ensine|teach|demonstre)", "question_explain"),
            (r"^(qual a diferenca|what is the difference|compare|compare)", "question_compare"),
            (r"^(qual o melhor|what is the best|melhor forma)", "question_recommend"),
        ],
        "system": [
            (r"^(status|info|informacoes|sistema)", "system_status"),
            (r"^(hora|data|time|date|hoje)", "system_time"),
            (r"^(ajuda|help|comandos|commands|como usar)", "system_help"),
            (r"^(execute|run|rodar|rode|executar)", "system_execute"),
            (r"^(monitor|dashboard|metrics|metricas)", "system_monitor"),
        ],
        "search": [
            (r"^(pesquise|search|google|buscar|find|procure)", "search"),
            (r"^(noticias|news|atualizacoes|updates)", "search_news"),
            (r"^(documentacao|docs|documentation|manual)", "search_docs"),
        ],
        "deep_dev": [
            (r"^(shadow|deep dev|deepdev)", "deep_dev_shadow"),
            (r"^(time machine|timemachine|quando quebrou|regression)", "deep_dev_timemachine"),
            (r"^(scan|scaneie|verifique-seguranca)", "deep_dev_scan"),
        ],
        "memory": [
            (r"^(lembre|remember|memorize|salve|save)", "memory_save"),
            (r"^(o que voce lembra|what do you remember|memoria)", "memory_recall"),
            (r"^(esqueca|forget|limpe|clear)", "memory_clear"),
        ],
        "creative": [
            (r"^(desenhe|draw|sketch|ilustre)", "creative_draw"),
            (r"^(crie imagem|generate image|gere imagem)", "creative_image"),
            (r"^(piada|joke|humor|engracece)", "creative_joke"),
        ],
    }

    AUTOCOMPLETE: Dict[str, List[str]] = {
        "como": ["como funciona", "como fazer", "como implementar", "como usar", "como corrigir", "como otimizar"],
        "qual": ["qual a melhor", "qual a diferenca", "qual o problema", "qual a solucao", "qual framework"],
        "por": ["por que", "porque", "por favor", "por padrao"],
        "crie": ["crie uma funcao", "crie uma classe", "crie um script", "crie uma API", "crie um teste"],
        "refatore": ["refatore o codigo", "refatore esta funcao", "refatore para usar SOLID"],
        "teste": ["teste esta funcao", "teste unitario", "teste de integracao", "teste edge cases"],
        "execute": ["execute este codigo", "execute o script", "execute o teste", "execute o build"],
        "pesquise": ["pesquise sobre", "pesquise a documentacao", "pesquise exemplos"],
        "status": ["status do sistema", "status dos providers", "status da memoria", "status da IA"],
        "shadow": ["shadow dev analysis", "shadow analysis completo"],
        "time": ["time machine analysis", "quando quebrou"],
        "debug": ["debug this error", "debug o traceback", "debug memory leak"],
        "otimize": ["otimize esta funcao", "otimize performance", "otimize query SQL"],
    }

    def __init__(self):
        self._user_patterns: Dict[str, int] = Counter()
        self._recent_intents: List[str] = []
        self._turn_count = 0
        self._last_intent: Optional[str] = None
        self._session_topics: List[str] = []

    def predict(self, partial_input: str) -> List[IntentSuggestion]:
        """
        Predict intent from partial or complete input.
        v2: Adds multi-turn context, follow-up prediction, ambiguity detection.
        """
        suggestions = []
        text = partial_input.lower().strip()

        if not text:
            return self._get_default_suggestions()

        # 1. Direct pattern matching
        for category, patterns in self.INTENT_MAP.items():
            for pattern, intent in patterns:
                if re.search(pattern, text):
                    suggestions.append(IntentSuggestion(
                        intent=intent, confidence=0.8, suggestion=text,
                        description=f"Detected: {category} -> {intent}",
                        category=category,
                    ))

        # 2. Autocomplete suggestions
        for prefix, completions in self.AUTOCOMPLETE.items():
            if text.startswith(prefix):
                for completion in completions:
                    if completion != text and completion.startswith(text):
                        suggestions.append(IntentSuggestion(
                            intent="autocomplete", confidence=0.6,
                            suggestion=completion, description=f"Complete: {completion}",
                            category="command",
                        ))

        # 3. Fuzzy matching for typos
        fuzzy = self._fuzzy_match(text)
        suggestions.extend(fuzzy)

        # 4. Multi-turn follow-up predictions
        follow_ups = self._predict_follow_up()
        suggestions.extend(follow_ups)

        # 5. Learned patterns from user history
        for pattern, count in self._user_patterns.most_common(5):
            if text.startswith(pattern[:min(len(text), len(pattern))]):
                suggestions.append(IntentSuggestion(
                    intent="learned", confidence=min(0.5, count * 0.08),
                    suggestion=pattern, description=f"Frequently used ({count}x)",
                    category="command",
                ))

        # 6. Context-based suggestions from session
        if self._session_topics:
            last_topic = self._session_topics[-1]
            context_suggestions = self._get_context_suggestions(last_topic, text)
            suggestions.extend(context_suggestions)

        # Deduplicate and sort
        seen = set()
        unique = []
        for s in sorted(suggestions, key=lambda s: s.confidence, reverse=True):
            key = (s.intent, s.suggestion)
            if key not in seen:
                seen.add(key)
                unique.append(s)

        return unique[:5]

    def record_usage(self, text: str):
        """Record user input for learning and multi-turn tracking."""
        self._turn_count += 1
        words = text.strip().split()
        if words:
            prefix = words[0].lower()
            self._user_patterns[prefix] += 1

            # Track recent intents
            for category, patterns in self.INTENT_MAP.items():
                for pattern, intent in patterns:
                    if re.search(pattern, text.lower()):
                        self._recent_intents.append(intent)
                        if len(self._recent_intents) > 20:
                            self._recent_intents = self._recent_intents[-20:]
                        self._last_intent = intent
                        break

            # Track topics
            topic = self._quick_topic(text)
            if topic:
                self._session_topics.append(topic)
                if len(self._session_topics) > 20:
                    self._session_topics = self._session_topics[-20:]

    def get_command_suggestions(self) -> List[Dict[str, str]]:
        """Get all available commands for the Command Palette."""
        return [
            {"cmd": "status", "label": "System Status", "category": "System"},
            {"cmd": "hora", "label": "Current Time", "category": "System"},
            {"cmd": "data", "label": "Current Date", "category": "System"},
            {"cmd": "ajuda", "label": "Help / Commands", "category": "System"},
            {"cmd": "ram", "label": "RAM Usage", "category": "System"},
            {"cmd": "discos", "label": "Disk Info", "category": "System"},
            {"cmd": "processos", "label": "Running Processes", "category": "System"},
            {"cmd": "dashboard", "label": "Activity Dashboard", "category": "System"},
            {"cmd": "deep dev status", "label": "Deep Dev Status", "category": "Deep Dev"},
            {"cmd": "shadow", "label": "Shadow Dev Analysis", "category": "Deep Dev"},
            {"cmd": "time machine", "label": "Time Machine (Regression)", "category": "Deep Dev"},
            {"cmd": "scan secrets", "label": "Scan for Secrets", "category": "Security"},
            {"cmd": "approve shadow", "label": "Approve Shadow Changes", "category": "Deep Dev"},
            {"cmd": "discard shadow", "label": "Discard Shadow Changes", "category": "Deep Dev"},
            {"cmd": "limpar memoria", "label": "Clear Memory", "category": "Memory"},
            {"cmd": "o que voce lembra", "label": "View Memories", "category": "Memory"},
            {"cmd": "plugins", "label": "List Plugins", "category": "Plugins"},
            {"cmd": "monitor", "label": "System Monitor", "category": "Monitoring"},
            {"cmd": "erros", "label": "Error Log", "category": "Monitoring"},
            {"cmd": "screenshot", "label": "Take Screenshot", "category": "Automation"},
            {"cmd": "abrir pasta", "label": "Open Project Folder", "category": "Automation"},
        ]

    # ═══ Private helpers ═══════════════════════════════════════════════════════

    def _fuzzy_match(self, text: str) -> List[IntentSuggestion]:
        """Fuzzy matching for typos and partial commands."""
        suggestions = []
        commands = [s["cmd"] for s in self.get_command_suggestions()]

        for cmd in commands:
            # Simple Levenshtein-like: check if text is prefix or close match
            if len(text) >= 3:
                # Prefix match
                if cmd.startswith(text) and cmd != text:
                    suggestions.append(IntentSuggestion(
                        intent="fuzzy", confidence=0.4, suggestion=cmd,
                        description=f"Did you mean: {cmd}?", category="command",
                    ))
                # Character similarity (simplified)
                common = sum(1 for c in text if c in cmd)
                similarity = common / max(len(text), len(cmd))
                if similarity > 0.7 and cmd != text:
                    suggestions.append(IntentSuggestion(
                        intent="fuzzy", confidence=0.3, suggestion=cmd,
                        description=f"Similar to: {cmd}", category="command",
                    ))

        return suggestions[:2]

    def _predict_follow_up(self) -> List[IntentSuggestion]:
        """Predict likely follow-up based on last intent."""
        follow_ups = {
            "code_generate": [
                ("code_test", "teste o codigo que acabou de ser criado", 0.6),
                ("code_review", "faca um review do codigo", 0.4),
                ("code_document", "adicione docstrings ao codigo", 0.3),
            ],
            "code_debug": [
                ("code_test", "adicione teste para prevenir recorrencia", 0.5),
                ("code_refactor", "refatore para evitar o mesmo problema", 0.3),
            ],
            "code_refactor": [
                ("code_test", "adicione testes para o codigo refatorado", 0.5),
                ("code_review", "revise as mudancas", 0.4),
            ],
            "question_explain": [
                ("code_generate", "crie um exemplo pratico", 0.4),
            ],
        }

        suggestions = []
        if self._last_intent and self._last_intent in follow_ups:
            for intent, desc, conf in follow_ups[self._last_intent]:
                suggestions.append(IntentSuggestion(
                    intent=f"follow_up_{intent}", confidence=conf,
                    suggestion=desc, description=f"Follow-up: {desc}",
                    category="follow_up",
                ))

        return suggestions

    def _get_context_suggestions(self, topic: str, current_input: str) -> List[IntentSuggestion]:
        """Get suggestions based on session topic context."""
        suggestions = []
        topic_suggestions = {
            "python": [
                ("code_generate", "crie um script Python para isso", 0.3),
                ("code_test", "adicione testes com pytest", 0.3),
            ],
            "debugging": [
                ("code_debug", "debug o erro que apareceu", 0.4),
            ],
            "architecture": [
                ("code_refactor", "refatore seguindo este padrao", 0.3),
            ],
        }

        if topic in topic_suggestions:
            for intent, desc, conf in topic_suggestions[topic]:
                if not any(current_input.startswith(prefix)
                          for prefix in ["crie", "teste", "debug", "refatore"]):
                    suggestions.append(IntentSuggestion(
                        intent=f"context_{intent}", confidence=conf,
                        suggestion=desc, description=f"Based on session: {desc}",
                        category="context",
                    ))

        return suggestions

    def _quick_topic(self, text: str) -> str:
        text_lower = text.lower()
        topics = {
            "python": ["python", "pip", "pytest", "fastapi", "flask"],
            "debugging": ["bug", "erro", "error", "crash", "traceback"],
            "architecture": ["arquitetura", "design pattern", "solid", "refactor"],
            "testing": ["teste", "test", "mock", "coverage"],
            "security": ["auth", "jwt", "password", "encryption"],
        }
        for topic, keywords in topics.items():
            if any(kw in text_lower for kw in keywords):
                return topic
        return "general"

    def _get_default_suggestions(self) -> List[IntentSuggestion]:
        return [
            IntentSuggestion("status", 0.3, "status", "Check system status", "system"),
            IntentSuggestion("shadow", 0.2, "shadow", "Run Shadow Dev analysis", "deep_dev"),
            IntentSuggestion("help", 0.2, "ajuda", "Show available commands", "system"),
        ]
