#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Intelligence Engine v2 — Adaptive Context Enrichment
=====================================================
Major upgrade: adaptive prompting, dynamic few-shot from history,
deeper topic classification, entity tracking, multi-layer reasoning,
response style adaptation, and proactive suggestion generation.
"""

from __future__ import annotations

import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════════════
# Reasoning Templates — 7 layers of depth
# ═══════════════════════════════════════════════════════════════════════════════

COT_TEMPLATES: Dict[str, Dict[str, str]] = {
    "comprehension": {
        "directive": "Analise o contexto completo antes de responder. Identifique: (1) o que foi pedido, (2) dados disponiveis, (3) restricoes implicitas.",
        "trigger_words": ["o que", "qual", "explique", "como"],
    },
    "analysis": {
        "directive": "Analise sistematicamente: causa raiz, efeitos colaterais, trade-offs. Considere: performance, manutenibilidade, seguranca, escalabilidade.",
        "trigger_words": ["por que", "analise", "avaliar", "comparar"],
    },
    "synthesis": {
        "directive": "Sintetize informacoes dispersas em uma resposta coesa. Priorize: claridade, praticidade, completude.",
        "trigger_words": ["resuma", "sintetize", "combine", "junte"],
    },
    "meta_cognition": {
        "directive": "Antes de responder, verifique: (1) tenho certeza disso? (2) ha algo que posso estar esquecendo? (3) a resposta e proporcional a pergunta?",
        "trigger_words": ["tem certeza", "confia", "verifique", "check"],
    },
    "adaptation": {
        "directive": "Adapte profundidade e tom: iniciante=analogias, intermediario=detalhes tecnicos, expert=arquitetura avancada.",
        "trigger_words": ["ensine", "aprenda", "tutorial", "guia"],
    },
    "creative": {
        "directive": "Pense fora da caixa: solucoes nao-convencionais, analogias criativas, abordagens inovadoras. Mas mantenha factibilidade.",
        "trigger_words": ["crie", "invente", "imagine", "projete"],
    },
    "critical": {
        "directive": "Analise criticamente: riscos, vulnerabilidades, pontos cegos, falsas premissas. Seja rigoroso mas construtivo.",
        "trigger_words": ["critique", "avalie", "revisao", "review"],
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# Topic Classification — 15 categories with weighted keywords
# ═══════════════════════════════════════════════════════════════════════════════

TOPIC_KEYWORDS: Dict[str, Dict[str, float]] = {
    "code_generation": {
        "crie": 2, "gere": 2, "escreva": 2, "implemente": 2, "code": 2,
        "write": 2, "generate": 2, "criar": 1, "build": 1, "make": 1,
        "funcao": 1, "classe": 1, "class": 1, "function": 1, "def ": 1,
        "api": 1, "endpoint": 1, "route": 1, "component": 1, "script": 1,
    },
    "debugging": {
        "bug": 2, "erro": 2, "error": 2, "crash": 2, "quebrou": 2,
        "nao funciona": 2, "not working": 2, "debug": 2, "traceback": 2,
        "exception": 1, "TypeError": 1, "ValueError": 1, "KeyError": 1,
        "corrija": 1, "fix": 1, "resolve": 1,
    },
    "architecture": {
        "arquitetura": 3, "architecture": 3, "design": 2, "padrao": 2,
        "pattern": 2, "refator": 2, "refactor": 2, "SOLID": 2,
        "escalabilidade": 1, "scalability": 1, "desacoplamento": 1,
        "dependency injection": 1, "factory": 1, "observer": 1,
    },
    "explanation": {
        "o que e": 2, "como funciona": 2, "explique": 2, "explain": 2,
        "por que": 1, "qual a diferenca": 2, "tutorial": 1, "ensine": 1,
        "demonstre": 1, "mostre": 1, "exemplo": 1,
    },
    "performance": {
        "performance": 3, "velocidade": 2, "speed": 2, "otimizar": 2,
        "optimize": 2, "lento": 2, "slow": 2, "rapido": 1, "fast": 1,
        "latencia": 1, "latency": 1, "cache": 1, "memoria": 1,
    },
    "security": {
        "seguranca": 3, "security": 3, "vulnerabilidade": 2, "vulnerability": 2,
        "exploit": 2, "auth": 1, "jwt": 1, "oauth": 1, "crypt": 1,
        "hash": 1, "password": 1, "token": 1, "xss": 1, "csrf": 1,
    },
    "testing": {
        "teste": 2, "test": 2, "coverage": 2, "cobertura": 2, "mock": 1,
        "stub": 1, "fixture": 1, "assert": 1, "pytest": 1, "unittest": 1,
        "tdd": 1, "bdd": 1, "integration test": 1,
    },
    "data": {
        "banco": 2, "database": 2, "sql": 2, "nosql": 2, "query": 2,
        "select": 1, "insert": 1, "migration": 1, "schema": 1,
        "postgres": 1, "mysql": 1, "mongo": 1, "redis": 1,
    },
    "devops": {
        "docker": 2, "kubernetes": 2, "k8s": 2, "ci/cd": 2, "deploy": 2,
        "pipeline": 1, "container": 1, "aws": 1, "azure": 1, "gcp": 1,
        "terraform": 1, "ansible": 1, "nginx": 1,
    },
    "frontend": {
        "react": 2, "vue": 2, "angular": 2, "svelte": 2, "html": 1,
        "css": 1, "javascript": 1, "typescript": 1, "jsx": 1, "tsx": 1,
        "component": 1, "ui": 1, "ux": 1, "responsivo": 1,
    },
    "ai_ml": {
        "machine learning": 3, "deep learning": 3, "neural": 2,
        "model": 1, "training": 1, "inference": 1, "llm": 2,
        "embedding": 1, "vector": 1, "prompt": 1, "fine-tune": 2,
    },
    "system_admin": {
        "status": 2, "sistema": 2, "monitor": 2, "disk": 1, "ram": 1,
        "processos": 1, "log": 1, "backup": 1, "restore": 1,
    },
    "refactoring": {
        "limpe": 2, "clean": 2, "organize": 2, "organizar": 2,
        "simplifique": 2, "simplify": 2, "dead code": 1,
        "code smell": 1, "technical debt": 1,
    },
    "planning": {
        "planeje": 2, "plan": 2, "estrategia": 2, "strategy": 2,
        "roadmap": 1, "milestone": 1, "sprint": 1, "backlog": 1,
        "priorize": 1, "estime": 1,
    },
    "creative": {
        "crie": 1, "invente": 1, "imagine": 1, "projete": 1,
        "desenhe": 1, "desenvolva": 1, "conceito": 1, "ideia": 1,
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# Few-Shot Examples — dynamic selection based on topic + user level
# ═══════════════════════════════════════════════════════════════════════════════

FEW_SHOT_EXAMPLES: Dict[str, Dict[str, str]] = {
    "code_generation": {
        "beginner": (
            "\n[EXEMPLO] Input: 'crie uma funcao soma'\n"
            "Output: Funcao simples com docstring, type hints, e exemplo de uso."
        ),
        "intermediate": (
            "\n[EXEMPLO] Input: 'crie uma API REST para usuarios'\n"
            "Output: FastAPI com CRUD, validacao Pydantic, tratamento de erros, testes."
        ),
        "expert": (
            "\n[EXEMPLO] Input: 'crie um microservico de autenticacao'\n"
            "Output: Arquitetura hexagonal, JWT com refresh tokens, rate limiting, audit log."
        ),
    },
    "debugging": {
        "beginner": (
            "\n[EXEMPLO] Input: 'NameError: name x is not defined'\n"
            "Output: 'Voce esqueceu de definir x antes de usa-la. Exemplo: x = 5'"
        ),
        "intermediate": (
            "\n[EXEMPLO] Input: 'ImportError circular'\n"
            "Output: Refatorar imports, usar import dentro da funcao, ou criar modulo separado."
        ),
        "expert": (
            "\n[EXEMPLO] Input: 'Memory leak no worker pool'\n"
            "Output: Analise de GC references, weakref pattern, context manager para cleanup."
        ),
    },
    "architecture": {
        "intermediate": (
            "\n[EXEMPLO] Input: 'Como organizar um projeto FastAPI grande?'\n"
            "Output: Estrutura por dominio, dependency injection, port/adapter pattern."
        ),
        "expert": (
            "\n[EXEMPLO] Input: 'Monolito vs microservicos?'\n"
            "Output: Analise de trade-offs: latencia, complexidade operacional, time coupling."
        ),
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# Entity Extraction Patterns
# ═══════════════════════════════════════════════════════════════════════════════

ENTITY_PATTERNS = {
    "file": re.compile(r'[\w/\\]+\.(?:py|js|ts|jsx|tsx|java|go|rs|cpp|html|css|json|yaml|yml|toml)'),
    "class_name": re.compile(r'\b([A-Z][a-zA-Z]+(?:Engine|Manager|Service|Handler|Controller|Factory|Adapter|Provider|Router|Guard))\b'),
    "function_call": re.compile(r'\b([a-z_][a-z0-9_]*)\s*\('),
    "technology": re.compile(r'\b(Python|JavaScript|TypeScript|Rust|Go|Java|C\+\+|React|Vue|Angular|FastAPI|Flask|Django|Docker|Kubernetes|PostgreSQL|MySQL|MongoDB|Redis|Git|GitHub|VSCode|PySide6|PyQt6)\b'),
    "concept": re.compile(r'\b(SOLID|DRY|KISS|YAGNI|REST|GraphQL|gRPC|JWT|OAuth|CI/CD|TDD|BDD|MVC|MVVM)\b'),
}


@dataclass
class UserProfile:
    """Detected user profile for adaptation."""
    level: str = "intermediate"  # beginner, intermediate, expert
    primary_topics: List[str] = field(default_factory=list)
    communication_style: str = "formal"  # formal, casual, technical
    preferred_language: str = "pt-BR"
    response_depth: str = "medium"  # short, medium, detailed


@dataclass
class EnrichmentResult:
    """Result of context enrichment."""
    enriched_prompt: str = ""
    topic: str = ""
    reasoning_layer: str = ""
    entities_found: List[str] = field(default_factory=list)
    user_profile: Optional[UserProfile] = None
    confidence: float = 0.0


class IntelligenceEngine:
    """
    Adaptive intelligence engine that learns and adapts.
    v2: Deeper topic classification, dynamic few-shot, entity tracking,
    user profiling, multi-layer reasoning, proactive suggestions.
    """

    def __init__(self):
        self._topic_history: List[Tuple[float, str]] = []
        self._entity_cache: Dict[str, int] = Counter()
        self._user_profile = UserProfile()
        self._conversation_patterns: Dict[str, int] = Counter()
        self._question_count = 0
        self._code_count = 0
        self._explanation_count = 0

    def enrich_context(self, system_prompt: str, user_message: str,
                      history: Optional[List[Dict]] = None,
                      session_turns: Optional[List[Dict]] = None) -> str:
        """
        Main enrichment method. Adds intelligence layers to the system prompt.
        """
        enriched = system_prompt
        now = time.time()

        # 1. Deep topic classification (weighted scoring)
        topic, confidence = self._classify_topic_deep(user_message)
        if topic:
            self._topic_history.append((now, topic))
            if len(self._topic_history) > 50:
                self._topic_history = self._topic_history[-50:]

        # 2. Update user profile from patterns
        self._update_user_profile(user_message, topic)

        # 3. Multi-layer reasoning selection
        reasoning_layer = self._select_reasoning_layer(topic, user_message)
        if reasoning_layer:
            enriched += f"\n\n[RACIOCINIO AVANCADO] {reasoning_layer}"

        # 4. Dynamic few-shot based on topic + user level
        few_shot = self._get_dynamic_few_shot(topic, self._user_profile.level)
        if few_shot:
            enriched += few_shot

        # 5. Entity extraction and context injection
        entities = self._extract_entities(user_message)
        if entities:
            entity_context = self._build_entity_context(entities)
            enriched += f"\n[ENTIDADES] {entity_context}"

        # 6. Topic-specific directives
        if topic and topic in TOPIC_KEYWORDS:
            enriched += f"\n[TOPICO] Tarefa: {topic} (confianca: {confidence:.0%})"
            enriched += self._get_topic_directive(topic)

        # 7. User profile adaptation
        if self._user_profile.level:
            enriched += f"\n[NIVEL] Usuario: {self._user_profile.level} — adapte profundidade."

        # 8. Session awareness
        if session_turns and len(session_turns) > 3:
            enriched += self._build_session_context(session_turns)

        # 9. Proactive suggestions
        suggestions = self._generate_proactive_suggestions(topic, user_message, history)
        if suggestions:
            enriched += f"\n[SUGESTOES] {suggestions}"

        # 10. Anti-hallucination directives
        enriched += "\n[INTEGRIDADE] Verifique fatos antes de afirmar. Cite fontes quando possivel. Se incerto, diga."

        return enriched

    def get_user_profile(self) -> UserProfile:
        """Get the detected user profile."""
        return self._user_profile

    def get_topic_trend(self) -> List[str]:
        """Get recent topic trend."""
        return [t for _, t in self._topic_history[-10:]]

    # ═══════════════════════════════════════════════════════════════════════
    # Deep Topic Classification
    # ═══════════════════════════════════════════════════════════════════════

    def _classify_topic_deep(self, text: str) -> Tuple[str, float]:
        """
        Weighted topic classification with confidence score.
        Returns (topic, confidence).
        """
        text_lower = text.lower()
        scores: Dict[str, float] = {}

        for topic, keywords in TOPIC_KEYWORDS.items():
            score = 0.0
            for keyword, weight in keywords.items():
                if keyword in text_lower:
                    score += weight
            if score > 0:
                scores[topic] = score

        if not scores:
            return "general", 0.3

        best_topic = max(scores, key=scores.get)
        max_score = scores[best_topic]
        total_score = sum(scores.values())
        confidence = min(1.0, max_score / max(total_score, 1))

        return best_topic, confidence

    # ═══════════════════════════════════════════════════════════════════════
    # Multi-Layer Reasoning
    # ═══════════════════════════════════════════════════════════════════════

    def _select_reasoning_layer(self, topic: str, text: str) -> str:
        """Select the best reasoning layer for this query."""
        text_lower = text.lower()

        # Check each layer's trigger words
        best_layer = None
        best_score = 0

        for layer_name, layer_data in COT_TEMPLATES.items():
            score = sum(1 for tw in layer_data["trigger_words"] if tw in text_lower)
            if score > best_score:
                best_score = score
                best_layer = layer_name

        # Fallback based on topic
        if not best_layer:
            topic_layer_map = {
                "code_generation": "creative",
                "debugging": "analysis",
                "architecture": "analysis",
                "explanation": "comprehension",
                "performance": "analysis",
                "security": "critical",
                "testing": "critical",
                "refactoring": "meta_cognition",
            }
            best_layer = topic_layer_map.get(topic, "")

        if best_layer and best_layer in COT_TEMPLATES:
            return COT_TEMPLATES[best_layer]["directive"]
        return ""

    # ═══════════════════════════════════════════════════════════════════════
    # Dynamic Few-Shot
    # ═══════════════════════════════════════════════════════════════════════

    def _get_dynamic_few_shot(self, topic: str, user_level: str) -> str:
        """Get few-shot example adapted to topic and user level."""
        if topic not in FEW_SHOT_EXAMPLES:
            return ""

        topic_examples = FEW_SHOT_EXAMPLES[topic]
        # Try exact level, then fallback
        example = topic_examples.get(user_level) or topic_examples.get("intermediate") or ""
        return example

    # ═══════════════════════════════════════════════════════════════════════
    # User Profiling
    # ═══════════════════════════════════════════════════════════════════════

    def _update_user_profile(self, text: str, topic: str):
        """Update user profile based on interaction patterns."""
        self._conversation_patterns[topic] += 1

        # Detect level from language complexity
        text_lower = text.lower()
        expert_signals = ["arquitetura", "design pattern", "solid", "dependency injection",
                         "microservico", "kubernetes", "terraform", "concorrencia"]
        beginner_signals = ["o que e", "como faz", "tutorial", "basico", "simples", "ajuda"]

        expert_count = sum(1 for s in expert_signals if s in text_lower)
        beginner_count = sum(1 for s in beginner_signals if s in text_lower)

        if expert_count > beginner_count and expert_count > 0:
            self._user_profile.level = "expert"
        elif beginner_count > expert_count and beginner_count > 0:
            self._user_profile.level = "beginner"
        elif len(self._conversation_patterns) > 5:
            self._user_profile.level = "intermediate"

        # Detect communication style
        if "?" in text or any(w in text_lower for w in ["por favor", "obrigado", "desculpa"]):
            self._user_profile.communication_style = "formal"
        elif any(w in text_lower for w in ["faz", "manda", "bora", "vamo"]):
            self._user_profile.communication_style = "casual"
        else:
            self._user_profile.communication_style = "technical"

        # Update primary topics
        self._user_profile.primary_topics = [
            t for t, _ in self._conversation_patterns.most_common(5)
        ]

    # ═══════════════════════════════════════════════════════════════════════
    # Entity Extraction
    # ═══════════════════════════════════════════════════════════════════════

    def _extract_entities(self, text: str) -> List[Tuple[str, str]]:
        """Extract entities with types."""
        entities = []
        for etype, pattern in ENTITY_PATTERNS.items():
            for match in pattern.finditer(text):
                name = match.group(1) if match.lastindex else match.group()
                if len(name) > 1:
                    entities.append((name, etype))
                    self._entity_cache[name] += 1
        return entities[:10]

    def _build_entity_context(self, entities: List[Tuple[str, str]]) -> str:
        """Build context string from entities."""
        parts = []
        for name, etype in entities:
            count = self._entity_cache.get(name, 1)
            freq = "frequente" if count > 3 else "recente" if count > 1 else "novo"
            parts.append(f"{name} ({etype}, {freq})")
        return "; ".join(parts)

    # ═══════════════════════════════════════════════════════════════════════
    # Topic Directives
    # ═══════════════════════════════════════════════════════════════════════

    def _get_topic_directive(self, topic: str) -> str:
        """Get specific directive for the topic."""
        directives = {
            "code_generation": " Gere codigo completo, funcional, production-ready. Inclua tratamento de erros, type hints, docstrings.",
            "debugging": " Diagnostique a causa raiz. Verifique: imports, tipos, escopo, concorrencia, dependencias.",
            "architecture": " Analise trade-offs: complexidade vs flexibilidade, performance vs manutenibilidade.",
            "explanation": " Use analogias, exemplos concretos, e uma progressao logica (simples -> complexo).",
            "performance": " Identifique gargalos primeiro. Mece: profiling, complexidade algoritmica, I/O.",
            "security": " Aplique OWASP Top 10. Verifique: autenticacao, autorizacao, validacao, criptografia.",
            "testing": " Gere testes: unitarios (mocks), integracao (endpoints), edge cases, error paths.",
            "data": " Considere: normalizacao, indices, transacoes, ACID, query optimization.",
            "devops": " Inclua: multi-stage build, health checks, resource limits, logging, monitoring.",
            "frontend": " Considere: responsividade, acessibilidade (a11y), performance, UX.",
            "ai_ml": " Considere: dados de treino, overfitting, metricas, deploy, monitoring.",
            "refactoring": " Aplique SOLID, DRY, KISS. Identifique code smells e anti-patterns.",
            "planning": " Decomponha em tarefas atomicas com estimativas realistas e dependencias.",
        }
        return directives.get(topic, "")

    # ═══════════════════════════════════════════════════════════════════════
    # Session Context
    # ═══════════════════════════════════════════════════════════════════════

    def _build_session_context(self, session_turns: List[Dict]) -> str:
        """Build session context from recent turns."""
        # Extract recent topics
        recent_topics = []
        for turn in session_turns[-5:]:
            if isinstance(turn, dict) and "content" in turn:
                topic, _ = self._classify_topic_deep(turn["content"])
                if topic and topic != "general":
                    recent_topics.append(topic)

        if recent_topics:
            unique_topics = list(dict.fromkeys(recent_topics))  # preserve order, dedup
            return f"\n[SESSAO] Topicos recentes: {', '.join(unique_topics[:5])}"
        return ""

    # ═══════════════════════════════════════════════════════════════════════
    # Proactive Suggestions
    # ═══════════════════════════════════════════════════════════════════════

    def _generate_proactive_suggestions(self, topic: str, text: str,
                                        history: Optional[List[Dict]]) -> str:
        """Generate proactive suggestions based on context."""
        suggestions = []

        # After code generation, suggest testing
        if topic == "code_generation" and self._code_count > 0:
            suggestions.append("Apos gerar codigo, sugira testes automaticos.")

        # After debugging, suggest prevention
        if topic == "debugging":
            suggestions.append("Apos resolver o bug, sugira como prevenir no futuro.")

        # After architecture discussion, suggest implementation steps
        if topic == "architecture":
            suggestions.append("Apos discutir arquitetura, sugira proximos passos de implementacao.")

        # After explanation, suggest practice
        if topic == "explanation":
            suggestions.append("Apos explicar, sugira um exercicio pratico.")

        return " ".join(suggestions[:2])
