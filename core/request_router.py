"""
Great Sage AI — Request Understanding Router v2
================================================
Camada leve (zero API) que analisa cada pedido antes do LLM principal:

  • complexidade  → escolhe modelo (20B rápido vs 120B profundo)
  • referências   → detecta follow-ups ("isso", "aquilo", "o que você disse")
  • tipo          → conversa | código | explicação | ação mista
  • enriquecimento → monta contexto estruturado para o LLM entender melhor
  • tópico        → rastreia tópicos da conversa para contexto contínuo
  • urgência      → detecta urgência emocional e prioriza processamento
  • multi-intent  → detecta múltiplas intenções na mesma mensagem
"""

from __future__ import annotations

import re
import time
import unicodedata
from collections import deque
from dataclasses import dataclass, field
from enum import Enum


def _norm(text: str) -> str:
    txt = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in txt if unicodedata.category(c) != "Mn")


class QueryComplexity(str, Enum):
    SIMPLE = "simple"       # saudações, confirmações, perguntas curtas → 20B
    STANDARD = "standard"   # conversa normal → 120B reasoning low
    DEEP = "deep"           # código, análise longa, multi-parte → 120B reasoning medium


class QueryKind(str, Enum):
    CHAT = "chat"
    CODE = "code"
    EXPLAIN = "explain"
    DEBUG = "debug"
    CREATIVE = "creative"
    MIXED = "mixed"
    SYSTEM = "system"       # ações de sistema (abrir, fechar, instalar)
    RESEARCH = "research"   # pesquisa profunda, comparações


class UrgencyLevel(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Heurísticas (todas locais — sem latência de rede)
# ---------------------------------------------------------------------------

_SIMPLE_PATTERNS = (
    r"^(oi|olá|ola|hey|e aí|e ai|bom dia|boa tarde|boa noite|tudo bem|como vai|obrigad|valeu|vlw|ok|certo|entendi|sim|não|nao|legal|show|massa|top)[\s!.?]*$",
    r"^(quem é você|quem e voce|o que você é|o que voce e|se apresente|se apresenta)[\s!.?]*$",
)

_CODE_HINTS = (
    "codigo", "código", "python", "javascript", "typescript", "java", "rust",
    "function", "funcao", "função", "class", "classe", "def ", "import ",
    "debug", "bug", "erro", "exception", "stack trace", "refator", "api",
    "html", "css", "sql", "react", "node", "django", "flask", "fastapi",
    "implement", "implementa", "escrev", "program", "script", "algoritmo",
    "regex", "git", "docker", "compile", "syntax", "variavel", "variável",
    "compilar", "compilacao", "executar", "rodar", "teste", "testar",
)

_EXPLAIN_HINTS = (
    "explica", "explique", "como funciona", "o que é", "o que e", "me fale sobre",
    "me conta", "diferença", "diferenca", "por que", "porque", "definição",
    "definicao", "conceito", "teoria", "história de", "historia de",
    "qual a diferença", "quais são", "quais sao",
)

_DEBUG_HINTS = (
    "debug", "depur", "corrig", "consert", "arrum", "fix", "não funciona",
    "nao funciona", "dá erro", "da erro", "travou", "crash", "falha",
    "stacktrace", "traceback", "exception", "typeerror", "valueerror",
    "nameerror", "attributeerror", "importerror",
)

_CREATIVE_HINTS = (
    "crie", "criar", "invente", "imagine", "escreva um texto", "história",
    "historia", "poema", "roteiro", "brainstorm", "ideias para",
    "fantasi", "sugira", "sugestão", "sugestao",
)

_SYSTEM_HINTS = (
    "abra", "abrir", "feche", "fechar", "instale", "instalar", "desinstale",
    "desinstalar", "execute", "executar", " rode", "rodar", "limpe", "limpar",
    "reinicie", "reiniciar", "desligue", "desligar", "trave", "travar",
    "mute", "mutar", "volume", "conecte", "conectar",
)

_RESEARCH_HINTS = (
    "pesquise", "pesquisar", "compare", "comparar", "analise", "analisar",
    "avalie", "avaliar", "pesquisa", "comparação", "comparacao",
    "estude", "estudar", "investigue", "investigar",
)

_FOLLOWUP_HINTS = (
    "isso", "aquilo", "esse", "essa", "este", "esta", "o mesmo", "o anterior",
    "o que você disse", "o que voce disse", "como você disse", "como voce disse",
    "continua", "continue", "e agora", "e depois disso", "mais detalhes",
    "pode elaborar", "elabora", "detalha", "explica melhor", "e quanto a",
    "e sobre", "e o", "e a", "também", "tambem", "outra coisa", "mudando de assunto",
)

_DEEP_TRIGGERS = (
    "passo a passo", "detalhad", "completo", "profund", "arquitetura",
    "compar", "analise", "análise", "projeto inteiro", "do zero",
    "todas as linguagens", "multipl", "múltipl", "sistema completo",
)

_URGENCY_CRITICAL = (
    "urgente", "imediato", "agora", "rápido", "rapido", "pressa",
    "não funciona", "nao funciona", "caiu", "crashou", "travou",
    "perdi dados", "perdeu dados", "corrompido",
)

_URGENCY_HIGH = (
    "importante", "necessário", "necessario", "preciso disso",
    "quanto antes", "breve", "prioridade",
)


# ---------------------------------------------------------------------------
# Topic tracker (session-level context)
# ---------------------------------------------------------------------------

class TopicTracker:
    """Rastreia tópicos da conversa para roteamento contextual."""

    _TOPIC_KEYWORDS = {
        "python": ("python", "pip", "django", "flask", "fastapi", "pydantic", "numpy", "pandas"),
        "javascript": ("javascript", "js", "node", "react", "vue", "angular", "npm", "typescript", "ts"),
        "web": ("html", "css", "web", "site", "api", "rest", "graphql", "http"),
        "database": ("banco de dados", "database", "sql", "mysql", "postgres", "mongodb", "redis"),
        "devops": ("docker", "kubernetes", "deploy", "ci/cd", "git", "github", "pipeline"),
        "ai_ml": ("machine learning", "deep learning", "ia", "ml", "neural", "llm", "gpt", "transformer"),
        "system": ("windows", "linux", "sistema", "processo", "serviço", "servico", "registro"),
        "security": ("segurança", "seguranca", "criptografia", "hash", "vulnerabilidade", "firewall"),
        "game": ("jogo", "game", "unity", "godot", "unreal", "sprite", "render"),
        "mobile": ("android", "ios", "mobile", "app", "flutter", "react native"),
    }

    def __init__(self, max_history: int = 20):
        self._history: deque[str] = deque(maxlen=max_history)
        self._topic_counts: dict[str, int] = {}
        self._last_update: float = 0

    def update(self, text: str):
        norm = _norm(text)
        self._history.append(norm)
        for topic, keywords in self._TOPIC_KEYWORDS.items():
            if any(kw in norm for kw in keywords):
                self._topic_counts[topic] = self._topic_counts.get(topic, 0) + 1
        self._last_update = time.time()

    def get_dominant_topic(self) -> str | None:
        if not self._topic_counts:
            return None
        return max(self._topic_counts, key=self._topic_counts.get)

    def get_topic_context(self) -> str:
        topic = self.get_dominant_topic()
        if not topic:
            return ""
        count = self._topic_counts.get(topic, 0)
        if count >= 3:
            return f"Tópico dominante da conversa: {topic} (usuário está focado neste assunto)."
        return ""

    def get_recent_topics(self, limit: int = 3) -> list[str]:
        return sorted(self._topic_counts.keys(),
                      key=lambda k: self._topic_counts[k], reverse=True)[:limit]


# ---------------------------------------------------------------------------
# Main router
# ---------------------------------------------------------------------------

@dataclass
class RoutedRequest:
    original: str
    complexity: QueryComplexity = QueryComplexity.STANDARD
    kind: QueryKind = QueryKind.CHAT
    is_followup: bool = False
    suggested_model: str = "openai/gpt-oss-120b"
    reasoning_effort: str = "low"
    max_tokens: int = 1024
    context_hint: str = ""
    enriched_prompt: str = ""
    urgency: UrgencyLevel = UrgencyLevel.NORMAL
    topic: str = ""
    detected_intents: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class RequestRouter:
    FAST_MODEL = "openai/gpt-oss-20b"
    QUALITY_MODEL = "openai/gpt-oss-120b"
    _topic_tracker = TopicTracker()

    @classmethod
    def analyze(cls, prompt: str, recent_history: list[dict] | None = None) -> RoutedRequest:
        """Analisa o pedido e retorna roteamento + prompt enriquecido."""
        clean = prompt.strip()
        norm = _norm(clean)
        result = RoutedRequest(original=clean)

        if not norm:
            return result

        # Update topic tracker
        cls._topic_tracker.update(clean)
        result.topic = cls._topic_tracker.get_dominant_topic() or ""

        result.kind = cls._detect_kind(norm)
        result.is_followup = cls._is_followup(norm)
        result.urgency = cls._detect_urgency(norm)
        result.detected_intents = cls._detect_multi_intent(norm)
        result.complexity = cls._detect_complexity(norm, clean, result.kind, result.is_followup, result.urgency)
        result.suggested_model, result.reasoning_effort, result.max_tokens = cls._route_model(
            result.complexity, result.kind, result.urgency
        )
        result.context_hint = cls._build_context_hint(result)
        result.enriched_prompt = cls._enrich_prompt(clean, result, recent_history or [])
        return result

    @classmethod
    def _detect_kind(cls, norm: str) -> QueryKind:
        scores = {
            QueryKind.CODE: sum(1 for h in _CODE_HINTS if h in norm),
            QueryKind.EXPLAIN: sum(1 for h in _EXPLAIN_HINTS if h in norm),
            QueryKind.DEBUG: sum(1 for h in _DEBUG_HINTS if h in norm),
            QueryKind.CREATIVE: sum(1 for h in _CREATIVE_HINTS if h in norm),
            QueryKind.SYSTEM: sum(1 for h in _SYSTEM_HINTS if h in norm),
            QueryKind.RESEARCH: sum(1 for h in _RESEARCH_HINTS if h in norm),
        }
        best = max(scores, key=scores.get)
        best_score = scores[best]

        # Check for mixed intents
        active = [k for k, v in scores.items() if v >= 1 and k != best]
        if active and best_score <= 2:
            return QueryKind.MIXED

        if best_score >= 2:
            return best
        if best_score == 1:
            return best
        return QueryKind.CHAT

    @classmethod
    def _detect_multi_intent(cls, norm: str) -> list[str]:
        """Detecta múltiplas intenções na mesma mensagem."""
        intents = []
        separators = (" e depois ", " e tambem ", " e também ", " depois ", "; ", " e ")
        for sep in separators:
            if sep in norm:
                parts = norm.split(sep)
                for part in parts:
                    part = part.strip()
                    if len(part) >= 3:
                        for hint_set, name in [
                            (_CODE_HINTS, "code"), (_EXPLAIN_HINTS, "explain"),
                            (_DEBUG_HINTS, "debug"), (_CREATIVE_HINTS, "creative"),
                            (_SYSTEM_HINTS, "system"),
                        ]:
                            if any(h in part for h in hint_set):
                                if name not in intents:
                                    intents.append(name)
        return intents

    @classmethod
    def _detect_urgency(cls, norm: str) -> UrgencyLevel:
        if any(w in norm for w in _URGENCY_CRITICAL):
            return UrgencyLevel.CRITICAL
        if any(w in norm for w in _URGENCY_HIGH):
            return UrgencyLevel.HIGH
        if any(w in norm for w in ("?",)) and len(norm.split()) <= 5:
            return UrgencyLevel.LOW
        return UrgencyLevel.NORMAL

    @classmethod
    def _is_followup(cls, norm: str) -> bool:
        if len(norm.split()) <= 8:
            return any(re.search(r"\b" + re.escape(h) + r"\b", norm) for h in _FOLLOWUP_HINTS)
        return any(h in norm for h in ("o que você disse", "o que voce disse", "continua", "elabora"))

    @classmethod
    def _detect_complexity(
        cls, norm: str, raw: str, kind: QueryKind, is_followup: bool,
        urgency: UrgencyLevel = UrgencyLevel.NORMAL,
    ) -> QueryComplexity:
        for pat in _SIMPLE_PATTERNS:
            if re.match(pat, norm):
                return QueryComplexity.SIMPLE

        word_count = len(norm.split())
        if word_count <= 6 and kind == QueryKind.CHAT and not is_followup:
            return QueryComplexity.SIMPLE

        if kind in (QueryKind.CODE, QueryKind.DEBUG, QueryKind.RESEARCH):
            return QueryComplexity.DEEP

        if kind == QueryKind.MIXED:
            return QueryComplexity.DEEP

        if any(t in norm for t in _DEEP_TRIGGERS):
            return QueryComplexity.DEEP

        if word_count > 40 or norm.count("?") >= 2:
            return QueryComplexity.DEEP

        # Urgency can escalate complexity (urgent + explain = deep)
        if urgency == UrgencyLevel.CRITICAL and kind == QueryKind.EXPLAIN:
            return QueryComplexity.DEEP

        if is_followup and word_count <= 15:
            return QueryComplexity.STANDARD

        return QueryComplexity.STANDARD

    @classmethod
    def _route_model(
        cls, complexity: QueryComplexity, kind: QueryKind,
        urgency: UrgencyLevel = UrgencyLevel.NORMAL,
    ) -> tuple[str, str, int]:
        if complexity == QueryComplexity.SIMPLE:
            return cls.FAST_MODEL, "low", 512

        if complexity == QueryComplexity.DEEP or kind in (QueryKind.CODE, QueryKind.DEBUG, QueryKind.RESEARCH):
            effort = "high" if urgency in (UrgencyLevel.HIGH, UrgencyLevel.CRITICAL) else "medium"
            return cls.QUALITY_MODEL, effort, 4096

        if kind == QueryKind.EXPLAIN:
            return cls.QUALITY_MODEL, "low", 2048

        if kind == QueryKind.MIXED:
            return cls.QUALITY_MODEL, "medium", 4096

        return cls.QUALITY_MODEL, "low", 1024

    @classmethod
    def _build_context_hint(cls, req: RoutedRequest) -> str:
        hints = []
        if req.is_followup:
            hints.append("O Mestre provavelmente se refere ao assunto da conversa anterior — use o histórico.")
        if req.kind == QueryKind.CODE:
            hints.append("Entregue código completo e funcional; não omita partes.")
        elif req.kind == QueryKind.DEBUG:
            hints.append("Identifique a causa raiz do erro e proponha correção concreta com código de exemplo.")
        elif req.kind == QueryKind.EXPLAIN:
            hints.append("Explique com clareza; use exemplos práticos e analogias quando útil.")
        elif req.kind == QueryKind.CREATIVE:
            hints.append("Seja criativa mas mantenha o tom do Grande Sábio — analítica, precisa, elegante.")
        elif req.kind == QueryKind.SYSTEM:
            hints.append("Execute a ação de sistema solicitada; confirme o resultado.")
        elif req.kind == QueryKind.RESEARCH:
            hints.append("Pesquise a fundo, compare opções, e apresente uma análise completa com prós e contras.")
        elif req.kind == QueryKind.MIXED:
            hints.append("A mensagem contém múltiplos pedidos — atenda todos na ordem mencionada.")

        # Topic context
        topic_ctx = cls._topic_tracker.get_topic_context()
        if topic_ctx:
            hints.append(topic_ctx)

        # Urgency
        if req.urgency == UrgencyLevel.CRITICAL:
            hints.append("URGENTE — priorize velocidade e ação imediata.")
        elif req.urgency == UrgencyLevel.HIGH:
            hints.append("Alta prioridade — seja direta e eficiente.")

        return " ".join(hints)

    @classmethod
    def _enrich_prompt(
        cls, clean: str, req: RoutedRequest, recent_history: list[dict]
    ) -> str:
        """Monta o prompt final com contexto de compreensão (invisível ao usuário)."""
        parts = [clean]

        if req.context_hint:
            parts.append(f"\n[Contexto interno — não mencione ao Mestre: {req.context_hint}]")

        if req.detected_intents:
            parts.append(f"\n[Intenções detectadas: {', '.join(req.detected_intents)} — atenda todas]")

        if req.is_followup and recent_history:
            last_turns = recent_history[-3:]  # expanded to 3 turns
            recap = []
            for turn in last_turns:
                if isinstance(turn, dict):
                    u = turn.get("user_speech", "")
                    a = turn.get("assistant_response", "")
                    if u:
                        recap.append(f"Mestre: {u[:200]}")
                    if a:
                        recap.append(f"Você respondeu: {a[:300]}")
            if recap:
                parts.append(
                    "\n[Referência da conversa recente — use para entender 'isso', 'aquilo', etc.]:\n"
                    + "\n".join(recap)
                )

        # Inject topic context for deep requests
        if req.complexity == QueryComplexity.DEEP and req.topic:
            parts.append(f"\n[Tópico recorrente: {req.topic} — mantenha foco neste assunto]")

        return "".join(parts)
