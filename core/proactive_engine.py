# -*- coding: utf-8 -*-
"""
Great Sage AI — Proactive Suggestions Engine
=============================================
Analisa padrões de uso e sugere melhorias sem o usuário pedir.

Exemplos:
- "Notei que você usa Python todo dia. Quer que eu crie um template de projeto?"
- "Você corrigiu 3 vezes hoje sobre Docker. Quer que eu salve um cheat sheet?"
- "Faz 2 horas que você não fala comigo. Precisa de ajuda?"
"""

import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("greatsage.proactive")


@dataclass
class Suggestion:
    text: str
    category: str  # "optimization", "learning", "reminder", "tip", "proactive"
    priority: int = 5  # 1=alta, 10=baixa
    context: str = ""
    suggested_action: str = ""  # o que a IA faria se o usuário aceitar
    created_at: float = field(default_factory=time.time)


class ProactiveEngine:
    """Motor de sugestões proativas — analisa padrões e sugere melhorias."""

    def __init__(self, memory=None):
        self.memory = memory
        self._suggestions: List[Suggestion] = []
        self._last_analysis = 0.0
        self._analysis_interval = 300  # analisa a cada 5 min

    def analyze_and_suggest(self, current_context: str = "") -> List[Suggestion]:
        """Analisa padrões e gera sugestões relevantes."""
        now = time.time()
        if now - self._last_analysis < self._analysis_interval:
            return self._suggestions[-5:]  # retorna as últimas 5

        self._last_analysis = now
        self._suggestions.clear()

        if not self.memory:
            return self._suggestions

        # 1. Analisar correções recentes
        self._analyze_corrections()

        # 2. Analisar padrões de uso
        self._analyze_usage_patterns()

        # 3. Analisar memórias de conversa
        self._analyze_conversation_patterns()

        # 4. Sugestões contextuais
        if current_context:
            self._contextual_suggestions(current_context)

        # 5. Lembretes de produtividade
        self._productivity_reminders()

        # Ordena por prioridade
        self._suggestions.sort(key=lambda s: s.priority)

        logger.debug(f"Proactive: {len(self._suggestions)} sugestões geradas")
        return self._suggestions

    def _analyze_corrections(self):
        """Analisa correções para sugerir cheat sheets, templates, etc."""
        try:
            corrections = self.memory.search(
                "", category="correction", limit=10, min_importance=0.5
            )
            if not corrections:
                return

            # Conta tópicos mais corrigidos
            topic_counts = {}
            for c in corrections:
                for tag in c.tags:
                    if tag != "correction":
                        topic_counts[tag] = topic_counts.get(tag, 0) + 1

            for topic, count in topic_counts.items():
                if count >= 2:
                    self._suggestions.append(Suggestion(
                        text=f"Notei que você me corrigiu {count} vezes sobre '{topic}'. "
                             f"Quer que eu crie um cheat sheet para não errar de novo?",
                        category="learning",
                        priority=3,
                        context=f"{count} correções em {topic}",
                        suggested_action=f"Criar cheat sheet de {topic}",
                    ))
        except Exception:
            pass

    def _analyze_usage_patterns(self):
        """Analisa padrões de uso do usuário."""
        try:
            patterns = self.memory.get_user_patterns(limit=20)
            if not patterns:
                return

            # Conta ações mais frequentes
            action_counts = {}
            for p in patterns:
                action = p.metadata.get("action", "unknown")
                action_counts[action] = action_counts.get(action, 0) + 1

            # Sugere automação para ações repetidas
            for action, count in action_counts.items():
                if count >= 5 and action not in ("chat", "greeting"):
                    self._suggestions.append(Suggestion(
                        text=f"Você fez '{action}' {count} vezes recentemente. "
                             f"Quer que eu automatize isso?",
                        category="optimization",
                        priority=4,
                        context=f"{count}x {action}",
                        suggested_action=f"Automatizar {action}",
                    ))
        except Exception:
            pass

    def _analyze_conversation_patterns(self):
        """Analisa padrões de conversa."""
        try:
            conversations = self.memory.get_recent(category="conversation", limit=10)
            if not conversations:
                return

            # Detecta temas recorrentes
            themes = {}
            for c in conversations:
                words = c.content.lower().split()
                for word in words:
                    if len(word) > 4 and word not in ("para", "como", "porque", "porque", "então", "porque"):
                        themes[word] = themes.get(word, 0) + 1

            # Top temas
            top_themes = sorted(themes.items(), key=lambda x: x[1], reverse=True)[:3]
            for theme, count in top_themes:
                if count >= 3:
                    self._suggestions.append(Suggestion(
                        text=f"Notei que você fala muito sobre '{theme}'. "
                             f"Quer que eu salve isso como preferência?",
                        category="proactive",
                        priority=6,
                        context=f"tema recorrente: {theme}",
                        suggested_action=f"Salvar preferência: {theme}",
                    ))
        except Exception:
            pass

    def _contextual_suggestions(self, context: str):
        """Gera sugestões baseadas no contexto atual."""
        ctx = context.lower()

        # Se está programando
        if any(w in ctx for w in ["código", "python", "javascript", "bug", "erro"]):
            self._suggestions.append(Suggestion(
                text="Estou vendo que você está programando. "
                     "Quer que eu analise o código e sugira melhorias?",
                category="optimization",
                priority=5,
                suggested_action="Analisar código e sugerir melhorias",
            ))

        # Se está estudando
        if any(w in ctx for w in ["estudar", "aprender", "curso", "tutorial"]):
            self._suggestions.append(Suggestion(
                text="Que tal eu te ajudar com um resumo dos pontos principais?",
                category="learning",
                priority=5,
                suggested_action="Criar resumo dos pontos principais",
            ))

    def _productivity_reminders(self):
        """Lembretes de produtividade."""
        try:
            recent = self.memory.get_recent(category="conversation", limit=5)
            if not recent:
                return

            # Última interação
            last_time = datetime.fromisoformat(recent[0].created_at)
            hours_since = (datetime.now() - last_time).total_seconds() / 3600

            if hours_since > 4:
                self._suggestions.append(Suggestion(
                    text=f"Faz {int(hours_since)} horas que não falo com você. "
                         f"Precisa de ajuda com algo?",
                    category="reminder",
                    priority=7,
                ))
        except Exception:
            pass

    def get_suggestion_text(self) -> str:
        """Retorna a melhor sugestão como texto para o LLM."""
        suggestions = self.analyze_and_suggest()
        if not suggestions:
            return ""
        best = suggestions[0]
        return f"[SUGESTÃO PROATIVA] {best.text}"

    def accept_suggestion(self, suggestion: Suggestion):
        """Marca sugestão como aceita — registra para melhorar futuras."""
        if self.memory:
            self.memory.record_user_pattern(
                "accepted_suggestion",
                f"Categoria: {suggestion.category}, Texto: {suggestion.text[:100]}",
            )

    def dismiss_suggestion(self, suggestion: Suggestion):
        """Marca sugestão como dispensada — reduz prioridade futura."""
        if self.memory:
            self.memory.record_user_pattern(
                "dismissed_suggestion",
                f"Categoria: {suggestion.category}",
            )
