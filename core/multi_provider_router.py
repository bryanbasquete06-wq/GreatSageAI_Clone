#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elívea — Smart Multi-Provider Router
==========================================
Roteador inteligente que distribui chamadas LLM entre 12+ APIs gratuitas
para maximizar capacidade de tokens sem perder qualidade.

Filosofia: O QI (system prompt + persona + raciocínio) é O MESMO.
O que muda é QUAL provider processa — escolhido por:
  1. Complexidade da query (rápido vs inteligente)
  2. Budget restante do provider (tokens/minuto, req/dia)
  3. Latência atual do provider
  4. Tipo de tarefa (código, chat, análise, tradução)

APIs Gratuitas Suportadas (sem cartão de crédito):
  - Groq         → 30 RPM, 6K TPM, 1000 RPD (mais rápido do mundo)
  - Gemini       → 15 RPM, 1500 RPD (mais generoso em contexto)
  - Cerebras     → 5 RPM, 30K TPM, 1M tokens/dia (mais tokens/dia)
  - OpenRouter   → 20 RPM, 50 RPD free models (20+ modelos grátis)
  - Mistral      → Free mode, ~1 RPS, 500K TPM (código + reasoning)
  - NVIDIA NIM   → 40 RPM, 10K RPD (100+ modelos)
  - Cloudflare   → 10K neurons/dia (75+ modelos)
  - OVHcloud     → 2 RPM anonymo (EU, sem signup)
  - SiliconFlow  → 1000 RPM, 50K TPM (Qwen free)
  - Kilo Code    → 200 req/hr free (auto-router)
  - Ollama       → Local, ilimitado (se disponível)
  - HuggingFace  → Rate-limited free tier
"""

import os
import json
import time
import math
import logging
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

logger = logging.getLogger("elvea.router")

# ═══════════════════════════════════════════════════════════════
# PROVIDER REGISTRY — Todos os providers gratuitos
# ═══════════════════════════════════════════════════════════════

class ProviderTier(Enum):
    """Nível de inteligência do provider."""
    FAST = "fast"            # Resposta rápida, raciocínio simples
    SMART = "smart"          # Bom equilíbrio velocidade/inteligência
    INTELLIGENT = "intelligent"  # Máxima inteligência, pode ser mais lento
    CODE = "code"            # Otimizado para código
    LOCAL = "local"          # Local (Ollama), ilimitado mas menor


@dataclass
class FreeProvider:
    """Definição de um provider gratuito."""
    name: str
    tier: ProviderTier
    base_url: str
    # Rate limits
    rpm: int = 0           # Requests per minute
    rpd: int = 0           # Requests per day
    tpm: int = 0           # Tokens per minute
    tpd: int = 0           # Tokens per day
    # Modelos suportados (preferidos → fallback)
    models: List[str] = field(default_factory=list)
    # API format
    api_format: str = "openai"  # openai | gemini | custom
    api_key_env: str = ""       # Variable name for API key
    # Quality scores (0-1, ajustado por uso)
    quality_score: float = 0.8
    # Context window
    context_window: int = 128000
    # Max output tokens
    max_output: int = 4096
    # Features
    supports_streaming: bool = True
    supports_system_prompt: bool = True
    requires_card: bool = False
    # Estado atual
    enabled: bool = True


# ═══════════════════════════════════════════════════════════════
# REGISTRY — Todos os 12+ providers gratuitos
# ═══════════════════════════════════════════════════════════════

PROVIDER_REGISTRY: List[FreeProvider] = [
    # ── GROQ (Ultra-rápido, LPU hardware) ──
    FreeProvider(
        name="groq",
        tier=ProviderTier.FAST,
        base_url="https://api.groq.com/openai/v1",
        rpm=30, rpd=1000, tpm=6000, tpd=0,
        models=[
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "qwen/qwen3.6-27b",
        ],
        api_key_env="GROQ_API_KEY",
        quality_score=0.85,
        context_window=131072,
        max_output=65536,
    ),

    # ── GEMINI (Mais generoso, contexto 1M) ──
    FreeProvider(
        name="gemini",
        tier=ProviderTier.SMART,
        base_url="https://generativelanguage.googleapis.com/v1beta",
        rpm=15, rpd=1500, tpm=0, tpd=0,
        models=[
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-3.5-flash",
            "gemini-3.6-flash",
        ],
        api_format="gemini",
        api_key_env="GOOGLE_API_KEY",
        quality_score=0.88,
        context_window=1000000,  # 1M tokens!
        max_output=65536,
    ),

    # ── CEREBRAS (Mais tokens/dia, wafer-scale) ──
    FreeProvider(
        name="cerebras",
        tier=ProviderTier.SMART,
        base_url="https://api.cerebras.ai/v1",
        rpm=5, rpd=0, tpm=30000, tpd=1000000,
        models=[
            "gpt-oss-120b",
            "llama-3.3-70b",
        ],
        api_key_env="CEREBRAS_API_KEY",
        quality_score=0.82,
        context_window=128000,
        max_output=65536,
    ),

    # ── OPENROUTER (Aggregator, 20+ free models) ──
    FreeProvider(
        name="openrouter",
        tier=ProviderTier.SMART,
        base_url="https://openrouter.ai/api/v1",
        rpm=20, rpd=50, tpm=0, tpd=0,
        models=[
            "nvidia/nemotron-3-super-120b-a12b:free",
            "openai/gpt-oss-20b:free",
            "cohere/north-mini-code:free",
            "google/gemma-4-26b-a4b-it:free",
            "poolside/laguna-s-2.1:free",
            "meta-llama/llama-3.3-70b-instruct",
        ],
        api_format="openai",
        api_key_env="OPENROUTER_API_KEY",
        quality_score=0.80,
        context_window=262000,
        max_output=65536,
    ),

    # ── MISTRAL (Free mode, 500K TPM, bom para código) ──
    FreeProvider(
        name="mistral",
        tier=ProviderTier.CODE,
        base_url="https://api.mistral.ai/v1",
        rpm=60, rpd=0, tpm=500000, tpd=0,
        models=[
            "mistral-small-latest",
            "mistral-medium-latest",
            "codestral-latest",
            "ministral-8b-latest",
        ],
        api_format="openai",
        api_key_env="MISTRAL_API_KEY",
        quality_score=0.84,
        context_window=256000,
        max_output=32768,
    ),

    # ── NVIDIA NIM (100+ modelos, free tier generoso) ──
    FreeProvider(
        name="nvidia_nim",
        tier=ProviderTier.INTELLIGENT,
        base_url="https://integrate.api.nvidia.com/v1",
        rpm=40, rpd=10000, tpm=0, tpd=0,
        models=[
            "nvidia/nemotron-3-super-120b-a12b",
            "nvidia/nemotron-3-ultra-550b-a55b",
            "meta/llama-3.3-70b-instruct",
            "openai/gpt-oss-120b",
        ],
        api_format="openai",
        api_key_env="NVIDIA_API_KEY",
        quality_score=0.87,
        context_window=1000000,
        max_output=262000,
    ),

    # ── CLOUDFLARE WORKERS AI (10K neurons/dia, 75+ modelos) ──
    FreeProvider(
        name="cloudflare",
        tier=ProviderTier.FAST,
        base_url="https://api.cloudflare.com/client/v4",
        rpm=0, rpd=0, tpm=0, tpd=10000,  # 10K neurons/day
        models=[
            "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
            "@cf/openai/gpt-oss-120b",
            "@cf/google/gemma-4-26b-a4b-it",
            "@cf/deepseek-ai/deepseek-r1-distill-qwen-32b",
        ],
        api_format="cloudflare",
        api_key_env="CLOUDFLARE_API_KEY",
        quality_score=0.78,
        context_window=128000,
        max_output=8192,
    ),

    # ── OVHcloud (EU, anônimo, sem signup) ──
    FreeProvider(
        name="ovhcloud",
        tier=ProviderTier.SMART,
        base_url="https://oai.endpoints.kepler.ai.cloud.ovh.net/v1",
        rpm=2, rpd=0, tpm=0, tpd=0,  # 2 RPM per model
        models=[
            "Qwen3.5-397B-A17B",
            "gpt-oss-120b",
            "Meta-Llama-3_3-70B-Instruct",
            "Qwen3.6-27B",
        ],
        api_format="openai",
        api_key_env="",  # Anônimo, sem key!
        quality_score=0.75,
        context_window=131072,
        max_output=32768,
    ),

    # ── SILICONFLOW (1000 RPM, Qwen free) ──
    FreeProvider(
        name="siliconflow",
        tier=ProviderTier.SMART,
        base_url="https://api.siliconflow.cn/v1",
        rpm=1000, rpd=0, tpm=50000, tpd=0,
        models=[
            "Qwen/Qwen3-8B",
        ],
        api_format="openai",
        api_key_env="SILICONFLOW_API_KEY",
        quality_score=0.72,
        context_window=128000,
        max_output=8192,
    ),

    # ── KILO CODE (Auto-router, 200 req/hr) ──
    FreeProvider(
        name="kilo_code",
        tier=ProviderTier.INTELLIGENT,
        base_url="https://api.kilo.ai/api/gateway",
        rpm=200, rpd=0, tpm=0, tpd=0,
        models=[
            "kilo-auto/free",
            "nvidia/nemotron-3-ultra-550b-a55b:free",
            "stepfun/step-3.7-flash:free",
        ],
        api_format="openai",
        api_key_env="KILO_API_KEY",
        quality_score=0.83,
        context_window=1000000,
        max_output=65536,
    ),

    # ── HUGGING FACE (Rate-limited free) ──
    FreeProvider(
        name="huggingface",
        tier=ProviderTier.FAST,
        base_url="https://router.huggingface.co/v1",
        rpm=0, rpd=0, tpm=0, tpd=0,  # credit-metered
        models=[
            "meta-llama/Meta-Llama-3.1-8B-Instruct",
            "gemma-3-4b-it",
            "Qwen/Qwen2.5-7B-Instruct",
        ],
        api_format="openai",
        api_key_env="HUGGINGFACE_API_KEY",
        quality_score=0.70,
        context_window=131072,
        max_output=4096,
    ),

    # ── OLLAMA (Local, ilimitado) ──
    FreeProvider(
        name="ollama",
        tier=ProviderTier.LOCAL,
        base_url="http://localhost:11434",
        rpm=0, rpd=0, tpm=0, tpd=0,  # Ilimitado
        models=[
            "llama3.1:8b",
            "qwen2.5:7b",
            "codellama:7b",
        ],
        api_format="ollama",
        api_key_env="",
        quality_score=0.65,
        context_window=8192,
        max_output=4096,
        requires_card=False,
    ),
]


# ═══════════════════════════════════════════════════════════════
# TOKEN BUDGET MANAGER
# ═══════════════════════════════════════════════════════════════

@dataclass
class ProviderBudget:
    """Estado de budget de um provider."""
    name: str
    requests_minute: deque = field(default_factory=lambda: deque(maxlen=100))
    requests_day: int = 0
    tokens_minute: int = 0
    tokens_day: int = 0
    last_reset_minute: float = 0
    last_reset_day: float = 0
    # Stats
    total_requests: int = 0
    total_tokens: int = 0
    total_errors: int = 0
    avg_latency_ms: float = 0
    _latency_sum: float = 0
    _latency_count: int = 0

    def record_request(self, tokens: int = 0, latency_ms: float = 0, error: bool = False):
        """Registra uma requisição."""
        now = time.time()
        self.requests_minute.append(now)
        self.total_requests += 1
        self.tokens_minute += tokens
        self.tokens_day += tokens
        self.total_tokens += tokens
        if error:
            self.total_errors += 1
        if latency_ms > 0:
            self._latency_sum += latency_ms
            self._latency_count += 1
            self.avg_latency_ms = self._latency_sum / self._latency_count
        # Reset minute counter
        if now - self.last_reset_minute > 60:
            self.requests_minute = deque(
                [t for t in self.requests_minute if now - t < 60],
                maxlen=100
            )
            self.tokens_minute = sum(1 for _ in self.requests_minute)  # approximate
            self.last_reset_minute = now
        # Reset daily counter
        if now - self.last_reset_day > 86400:
            self.requests_day = 0
            self.tokens_day = 0
            self.last_reset_day = now

    def requests_in_last_minute(self) -> int:
        now = time.time()
        return sum(1 for t in self.requests_minute if now - t < 60)

    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.total_errors / self.total_requests

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "total_requests": self.total_requests,
            "total_tokens": self.total_tokens,
            "total_errors": self.total_errors,
            "error_rate": f"{self.error_rate():.1%}",
            "avg_latency_ms": f"{self.avg_latency_ms:.0f}",
            "requests_last_min": self.requests_in_last_minute(),
        }


# ═══════════════════════════════════════════════════════════════
# QUERY COMPLEXITY CLASSIFIER
# ═══════════════════════════════════════════════════════════════

class QueryComplexity(Enum):
    """Nível de complexidade de uma query."""
    TRIVIAL = 1     # "oi", "obrigado", sim/não
    SIMPLE = 2      # Pergunta factual simples
    MODERATE = 3    # Explicação, resumo, tradução
    COMPLEX = 4     # Análise profunda, código longo, raciocínio
    EXPERT = 5      # Problema multi-step, arquitetura, pesquisa


def classify_query_complexity(query: str, context: str = "") -> QueryComplexity:
    """
    Classifica a complexidade de uma query do usuário.
    Retorna o nível para decidir QUAL provider usar.
    """
    q = query.lower().strip()
    q_len = len(q)

    # ── TRIVIAL: Saudação, agradecimento, confirmação ──
    trivial_patterns = [
        r"^(oi|olá|ola|hey|hi|hello|eai|eai?|obg|obrigad[oa]|beleza|blz|ok|sim|não|nao|tchau|bye)$",
        r"^(obrigad[oa] (pela?|pelo) )",
        r"^(valeu|vlw|fuck|porra|caralho)$",
    ]
    for p in trivial_patterns:
        if __import__("re").match(p, q):
            return QueryComplexity.TRIVIAL

    # ── SIMPLE: Pergunta direta, curta, factual ──
    if q_len < 60 and "?" in q:
        return QueryComplexity.SIMPLE

    # ── MODERATE: Explicação, resumo, instrução ──
    moderate_keywords = [
        "explique", "explique me", "resuma", "resumo", "como funciona",
        "qual é", "qual a", "o que é", "traduza", "traduzir",
        "escreva", "gere", "crie", "defina",
    ]
    if any(k in q for k in moderate_keywords) or (q_len < 200 and q_len > 60):
        return QueryComplexity.MODERATE

    # ── COMPLEX: Código, análise, debug, refatoração ──
    complex_keywords = [
        "código", "codigo", "refatore", "refator", "debug", "analise",
        "analise", "otimize", "otimiz", "arquitetura", "sistema",
        "implemente", "implementar", "implementa", "programa",
        "função", "funcao", "classe", "método", "metodo",
        "script", "pipeline", "algoritmo", "banco de dados",
        "deploy", "servidor", "api", "endpoint", "rota",
        "shadow", "time machine", "deep dev", "timemachine",
    ]
    if any(k in q for k in complex_keywords):
        return QueryComplexity.COMPLEX

    # ── EXPERT: Multi-step, arquitetura, pesquisa avançada ──
    expert_keywords = [
        "padrão de projeto", "design pattern",
        "refatoração completa", "migração completa",
        "escalabilidade horizontal", "escalabilidade vertical",
        "benchmark detalhado", "comparação detalhada",
        "implemente um sistema completo", "crie uma arquitetura",
        "plano completo", "roadmap completo", "estratégia completa",
        "microsserviços", "distributed system",
    ]
    if any(k in q for k in expert_keywords) or q_len > 500:
        return QueryComplexity.EXPERT

    # Default baseado no tamanho
    if q_len > 300:
        return QueryComplexity.COMPLEX
    elif q_len > 100:
        return QueryComplexity.MODERATE
    else:
        return QueryComplexity.SIMPLE


# ═══════════════════════════════════════════════════════════════
# SMART ROUTER
# ═══════════════════════════════════════════════════════════════

class MultiProviderRouter:
    """
    Roteador inteligente multi-provider.

    A mesma IA (QI) roda em QUALQUER provider.
    O system prompt, persona e raciocínio são idênticos.
    O que muda é QUAL provider processa — escolhido por:
      1. Complexidade da query
      2. Budget restante do provider
      3. Qualidade média do provider
      4. Latência atual

    Capacidade total (soma de todos os free tiers):
      - ~130+ RPM combinados
      - ~1.5M+ tokens/dia (Cerebras 1M + Gemini + Groq + outros)
      - ~15,000+ requests/dia
    """

    # Mapeamento: complexidade → tiers preferidos
    COMPLEXITY_TO_TIERS = {
        QueryComplexity.TRIVIAL: [ProviderTier.FAST, ProviderTier.LOCAL],
        QueryComplexity.SIMPLE: [ProviderTier.FAST, ProviderTier.SMART],
        QueryComplexity.MODERATE: [ProviderTier.SMART, ProviderTier.FAST],
        QueryComplexity.COMPLEX: [ProviderTier.INTELLIGENT, ProviderTier.SMART, ProviderTier.CODE],
        QueryComplexity.EXPERT: [ProviderTier.INTELLIGENT, ProviderTier.SMART, ProviderTier.CODE],
    }

    def __init__(self, data_dir: str = "config/smart_data"):
        self.providers = PROVIDER_REGISTRY
        self.budgets: Dict[str, ProviderBudget] = {}
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._budget_file = self.data_dir / "provider_budgets.json"
        self._init_budgets()
        self._load_saved_budgets()
        logger.info(f"MultiProviderRouter inicializado com {len(self.providers)} providers")

    def _init_budgets(self):
        """Inicializa budget para cada provider."""
        for p in self.providers:
            if p.name not in self.budgets:
                self.budgets[p.name] = ProviderBudget(name=p.name)

    def _load_saved_budgets(self):
        """Carrega budgets salvos do disco."""
        try:
            if self._budget_file.exists():
                data = json.loads(self._budget_file.read_text(encoding="utf-8"))
                for name, stats in data.items():
                    if name in self.budgets:
                        b = self.budgets[name]
                        b.total_requests = stats.get("total_requests", 0)
                        b.total_tokens = stats.get("total_tokens", 0)
                        b.total_errors = stats.get("total_errors", 0)
        except Exception as e:
            logger.debug(f"Budget load error: {e}")

    def save_budgets(self):
        """Salva budgets no disco."""
        try:
            data = {name: b.to_dict() for name, b in self.budgets.items()}
            self._budget_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            logger.debug(f"Budget save error: {e}")

    # ── Core routing logic ──

    def _is_provider_available(self, provider: FreeProvider) -> bool:
        """Verifica se um provider está disponível e dentro do budget."""
        # Check if has API key (or doesn't need one)
        if provider.api_key_env and provider.name != "ovhcloud":
            key = os.getenv(provider.api_key_env, "")
            if not key:
                # Also check .env file
                env_path = Path(".env")
                if env_path.exists():
                    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
                        line = line.strip()
                        if line.startswith(f"{provider.api_key_env}="):
                            key = line.split("=", 1)[1].strip().strip("\"'")
                            break
                if not key:
                    return False

        # Ollama: check if running
        if provider.name == "ollama":
            try:
                import socket
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.5)
                result = s.connect_ex(("127.0.0.1", 11434)) == 0
                s.close()
                return result
            except Exception:
                return False

        # OVHcloud: anonymous, always available
        if provider.name == "ovhcloud":
            return True

        # Check budget
        budget = self.budgets.get(provider.name)
        if budget and provider.rpm > 0:
            if budget.requests_in_last_minute() >= provider.rpm:
                return False
        if budget and provider.rpd > 0 and budget.requests_day >= provider.rpd:
            return False

        # Check error rate (if >50%, skip)
        if budget and budget.error_rate() > 0.5 and budget.total_requests > 5:
            return False

        return True

    def _score_provider(
        self,
        provider: FreeProvider,
        complexity: QueryComplexity,
        estimated_tokens: int = 0,
    ) -> float:
        """
        Calcula score de um provider para uma query.
        Score mais alto = melhor candidato.
        """
        score = 0.0

        # 1. Tier match (0-40 points)
        preferred_tiers = self.COMPLEXITY_TO_TIERS.get(complexity, [ProviderTier.SMART])
        if provider.tier in preferred_tiers:
            tier_idx = preferred_tiers.index(provider.tier)
            score += 40 - (tier_idx * 10)  # First choice gets 40, second 30, etc.

        # 2. Quality score (0-25 points)
        score += provider.quality_score * 25

        # 3. Budget headroom (0-20 points)
        budget = self.budgets.get(provider.name)
        if budget:
            if provider.rpm > 0:
                usage_ratio = budget.requests_in_last_minute() / provider.rpm
                score += (1 - usage_ratio) * 20
            else:
                score += 20  # No limit = full score
        else:
            score += 20  # No budget data = full score

        # 4. Latency bonus (0-10 points)
        if budget and budget.avg_latency_ms > 0:
            # Faster = better (Groq ~200ms is ideal, >5s is bad)
            latency_score = max(0, 10 - (budget.avg_latency_ms / 500))
            score += latency_score
        else:
            score += 5  # Unknown latency = middle

        # 5. Error penalty (-10 to 0)
        if budget:
            score -= budget.error_rate() * 10

        # 6. Context window bonus for complex queries
        if complexity in (QueryComplexity.COMPLEX, QueryComplexity.EXPERT):
            if provider.context_window >= 256000:
                score += 5
            elif provider.context_window >= 128000:
                score += 3

        return score

    def select_provider(
        self,
        query: str = "",
        context: str = "",
        preferred_tier: Optional[ProviderTier] = None,
        force_provider: Optional[str] = None,
    ) -> Tuple[FreeProvider, str]:
        """
        Seleciona o melhor provider para a query.

        Returns:
            (provider, reason) — provider escolhido e motivo
        """
        with self._lock:
            # Force specific provider
            if force_provider:
                for p in self.providers:
                    if p.name == force_provider and self._is_provider_available(p):
                        return p, f"Forçado: {force_provider}"
                logger.warning(f"Provider forçado '{force_provider}' não disponível, usando auto")

            # Classify complexity
            complexity = classify_query_complexity(query, context)
            estimated_tokens = len(query) // 4  # ~4 chars per token

            # Get available providers
            available = [
                p for p in self.providers
                if self._is_provider_available(p) and p.enabled
            ]

            if not available:
                logger.error("Nenhum provider disponível!")
                # Return first provider as fallback
                return self.providers[0], "Fallback: nenhum disponível"

            # Score each provider
            scored = [
                (p, self._score_provider(p, complexity, estimated_tokens))
                for p in available
            ]
            scored.sort(key=lambda x: x[1], reverse=True)

            best = scored[0]
            runner_up = scored[1] if len(scored) > 1 else None

            reason = (
                f"Query={complexity.name}, Provider={best[0].name} "
                f"(score={best[1]:.1f}, tier={best[0].tier.value})"
            )
            if runner_up:
                reason += f" | Runner-up: {runner_up[0].name} ({runner_up[1]:.1f})"

            logger.info(f"Router: {reason}")
            return best[0], reason

    def select_fallback_chain(
        self,
        query: str = "",
        context: str = "",
        max_providers: int = 5,
    ) -> List[FreeProvider]:
        """
        Retorna cadeia de fallback ordenada por score.
        Usa quando o provider primário falha.
        """
        complexity = classify_query_complexity(query, context)
        estimated_tokens = len(query) // 4

        available = [
            p for p in self.providers
            if self._is_provider_available(p) and p.enabled
        ]

        scored = [
            (p, self._score_provider(p, complexity, estimated_tokens))
            for p in available
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        return [p for p, s in scored[:max_providers]]

    # ── Request execution ──

    def route_request(
        self,
        messages: List[Dict[str, str]],
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        stream: bool = False,
        preferred_tier: Optional[ProviderTier] = None,
        force_provider: Optional[str] = None,
    ) -> Tuple[str, str, Dict]:
        """
        Roteia uma requisição LLM pelo melhor provider.

        Returns:
            (response_text, provider_name, metadata)
        """
        query = messages[-1]["content"] if messages else ""
        context = " ".join(m["content"][:100] for m in messages[-3:]) if messages else ""

        # Select primary + fallback chain
        primary, reason = self.select_provider(query, context, preferred_tier, force_provider)
        fallbacks = self.select_fallback_chain(query, context, max_providers=4)

        # Remove primary from fallbacks if present
        fallback_names = [p.name for p in fallbacks if p.name != primary.name]

        # Try providers in order
        all_to_try = [primary] + [p for p in fallbacks if p.name != primary.name]
        last_error = ""
        metadata = {
            "complexity": classify_query_complexity(query, context).name,
            "primary": primary.name,
            "reason": reason,
            "attempted": [],
        }

        for provider in all_to_try[:5]:  # Max 5 attempts
            t0 = time.time()
            try:
                response = self._execute_request(
                    provider, messages, system, max_tokens, temperature, stream
                )
                latency = (time.time() - t0) * 1000

                # Record success
                budget = self.budgets.get(provider.name)
                if budget:
                    tokens_est = len(response) // 4 if response else 0
                    budget.record_request(tokens=tokens_est, latency_ms=latency)

                metadata["attempted"].append({
                    "provider": provider.name,
                    "success": True,
                    "latency_ms": f"{latency:.0f}",
                })
                metadata["final_provider"] = provider.name
                metadata["total_latency_ms"] = f"{latency:.0f}"

                # Save budget periodically
                if budget and budget.total_requests % 10 == 0:
                    self.save_budgets()

                return response, provider.name, metadata

            except Exception as e:
                latency = (time.time() - t0) * 1000
                last_error = str(e)
                budget = self.budgets.get(provider.name)
                if budget:
                    budget.record_request(error=True, latency_ms=latency)

                metadata["attempted"].append({
                    "provider": provider.name,
                    "success": False,
                    "error": last_error[:100],
                })
                logger.warning(f"Router: {provider.name} falhou: {last_error[:80]}")
                continue

        # All providers failed
        metadata["final_provider"] = "offline"
        metadata["error"] = last_error
        return (
            f"Todos os {len(all_to_try)} providers gratuitos falharam. "
            f"Último erro: {last_error[:200]}. "
            f"Providers tentados: {', '.join(p.name for p in all_to_try)}. "
            f"Verifique suas chaves de API e conexão.",
            "offline",
            metadata,
        )

    def _execute_request(
        self,
        provider: FreeProvider,
        messages: List[Dict[str, str]],
        system: str,
        max_tokens: int,
        temperature: float,
        stream: bool,
    ) -> str:
        """Executa uma requisição em um provider específico."""
        import requests as req

        headers = {"Content-Type": "application/json"}

        # API key
        if provider.api_key_env:
            key = os.getenv(provider.api_key_env, "")
            if not key:
                # Try .env
                env_path = Path(".env")
                if env_path.exists():
                    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
                        line = line.strip()
                        if line.startswith(f"{provider.api_key_env}="):
                            key = line.split("=", 1)[1].strip().strip("\"'")
                            break
            if key:
                headers["Authorization"] = f"Bearer {key}"

        # Build messages
        api_messages = []
        if system and provider.supports_system_prompt:
            api_messages.append({"role": "system", "content": system})
        api_messages.extend(messages)

        # OpenAI-compatible format (most providers)
        if provider.api_format == "openai":
            url = f"{provider.base_url}/chat/completions"
            payload = {
                "model": provider.models[0] if provider.models else "default",
                "messages": api_messages,
                "max_tokens": min(max_tokens, provider.max_output),
                "temperature": temperature,
                "stream": False,  # Non-streaming for simplicity
            }

            resp = req.post(url, json=payload, headers=headers, timeout=60)

            if resp.status_code == 200:
                data = resp.json()
                if "choices" in data and data["choices"]:
                    return data["choices"][0]["message"]["content"] or ""
                elif "error" in data:
                    raise Exception(data["error"].get("message", str(data["error"])))
            elif resp.status_code == 429:
                raise Exception(f"Rate limited ({resp.status_code})")
            elif resp.status_code >= 500:
                raise Exception(f"Server error ({resp.status_code})")
            else:
                try:
                    err = resp.json().get("error", {}).get("message", resp.text[:200])
                except Exception:
                    err = resp.text[:200]
                raise Exception(f"HTTP {resp.status_code}: {err}")

        # Gemini format
        elif provider.api_format == "gemini":
            return self._execute_gemini(provider, api_messages, system, max_tokens, temperature, headers)

        # Cloudflare Workers AI
        elif provider.api_format == "cloudflare":
            return self._execute_cloudflare(provider, api_messages, max_tokens, temperature, headers)

        # Ollama
        elif provider.api_format == "ollama":
            return self._execute_ollama(provider, api_messages, max_tokens, temperature)

        else:
            raise Exception(f"Formato API não suportado: {provider.api_format}")

    def _execute_gemini(
        self, provider: FreeProvider, messages: List[Dict],
        system: str, max_tokens: int, temperature: float, headers: Dict
    ) -> str:
        """Executa via Google Gemini API."""
        import requests as req

        model = provider.models[0] if provider.models else "gemini-2.5-flash"
        api_key = os.getenv(provider.api_key_env, "")
        if not api_key:
            env_path = Path(".env")
            if env_path.exists():
                for line in env_path.read_text(encoding="utf-8-sig").splitlines():
                    line = line.strip()
                    if line.startswith(f"{provider.api_key_env}="):
                        api_key = line.split("=", 1)[1].strip().strip("\"'")
                        break

        url = f"{provider.base_url}/models/{model}:generateContent?key={api_key}"

        contents = []
        for msg in messages:
            role = "model" if msg.get("role") == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": min(max_tokens, provider.max_output),
                "temperature": temperature,
            },
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}

        resp = req.post(url, json=payload, timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                return "".join(p.get("text", "") for p in parts)
            raise Exception("Gemini: resposta vazia")
        else:
            err = resp.json().get("error", {}).get("message", resp.text[:200])
            raise Exception(f"Gemini HTTP {resp.status_code}: {err}")

    def _execute_cloudflare(
        self, provider: FreeProvider, messages: List[Dict],
        max_tokens: int, temperature: float, headers: Dict
    ) -> str:
        """Executa via Cloudflare Workers AI."""
        import requests as req

        account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
        api_token = os.getenv(provider.api_key_env, "")
        model = provider.models[0] if provider.models else "@cf/meta/llama-3.3-70b-instruct-fp8-fast"

        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
        headers["Authorization"] = f"Bearer {api_token}"

        payload = {
            "messages": messages,
            "max_tokens": min(max_tokens, provider.max_output),
            "temperature": temperature,
        }

        resp = req.post(url, json=payload, headers=headers, timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success"):
                result = data.get("result", {})
                return result.get("response", "") or result.get("choices", [{}])[0].get("message", {}).get("content", "")
            raise Exception(f"Cloudflare error: {data.get('errors', ['unknown'])}")
        else:
            raise Exception(f"Cloudflare HTTP {resp.status_code}")

    def _execute_ollama(
        self, provider: FreeProvider, messages: List[Dict],
        max_tokens: int, temperature: float
    ) -> str:
        """Executa via Ollama local."""
        import requests as req

        model = provider.models[0] if provider.models else "llama3.1:8b"
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": min(max_tokens, provider.max_output),
            },
        }

        resp = req.post(f"{provider.base_url}/api/chat", json=payload, timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("message", {}).get("content", "")
        else:
            raise Exception(f"Ollama HTTP {resp.status_code}")

    # ── Streaming support ──

    def route_stream(
        self,
        messages: List[Dict[str, str]],
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        """
        Stream de resposta via melhor provider.
        Yields tokens um por um.
        """
        query = messages[-1]["content"] if messages else ""
        context = " ".join(m["content"][:100] for m in messages[-3:]) if messages else ""

        primary, reason = self.select_provider(query, context)
        fallbacks = self.select_fallback_chain(query, context, max_providers=3)

        all_to_try = [primary] + [p for p in fallbacks if p.name != primary.name]

        for provider in all_to_try[:3]:
            if provider.api_format == "openai" and provider.supports_streaming:
                try:
                    yield from self._stream_openai(provider, messages, system, max_tokens, temperature)
                    return
                except Exception as e:
                    logger.warning(f"Stream {provider.name} falhou: {e}")
                    continue
            elif provider.api_format == "gemini" and provider.supports_streaming:
                try:
                    yield from self._stream_gemini(provider, messages, system, max_tokens, temperature)
                    return
                except Exception as e:
                    logger.warning(f"Stream {provider.name} falhou: {e}")
                    continue

        # Fallback: non-streaming
        text, provider_name, _ = self.route_request(messages, system, max_tokens, temperature)
        yield text

    def _stream_openai(self, provider, messages, system, max_tokens, temperature):
        """Stream via OpenAI-compatible API."""
        import requests as req

        headers = {"Content-Type": "application/json"}
        if provider.api_key_env:
            key = os.getenv(provider.api_key_env, "")
            if key:
                headers["Authorization"] = f"Bearer {key}"

        api_messages = []
        if system:
            api_messages.append({"role": "system", "content": system})
        api_messages.extend(messages)

        payload = {
            "model": provider.models[0],
            "messages": api_messages,
            "max_tokens": min(max_tokens, provider.max_output),
            "temperature": temperature,
            "stream": True,
        }

        url = f"{provider.base_url}/chat/completions"
        resp = req.post(url, json=payload, headers=headers, timeout=120, stream=True)

        if resp.status_code != 200:
            raise Exception(f"Stream HTTP {resp.status_code}")

        for line in resp.iter_lines():
            if line:
                line = line.decode("utf-8", errors="ignore")
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue

    def _stream_gemini(self, provider, messages, system, max_tokens, temperature):
        """Stream via Gemini API."""
        import requests as req

        api_key = os.getenv(provider.api_key_env, "")
        model = provider.models[0]
        url = f"{provider.base_url}/models/{model}:streamGenerateContent?alt=sse&key={api_key}"

        contents = []
        for msg in messages:
            role = "model" if msg.get("role") == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": min(max_tokens, provider.max_output),
                "temperature": temperature,
            },
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}

        resp = req.post(url, json=payload, timeout=120, stream=True)
        if resp.status_code != 200:
            raise Exception(f"Gemini stream HTTP {resp.status_code}")

        for line in resp.iter_lines():
            if line:
                line = line.decode("utf-8", errors="ignore")
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            for p in parts:
                                if p.get("text"):
                                    yield p["text"]
                    except json.JSONDecodeError:
                        continue

    # ── Status & Diagnostics ──

    def get_status(self) -> Dict[str, Any]:
        """Retorna status completo de todos os providers."""
        status = {
            "total_providers": len(self.providers),
            "available_providers": 0,
            "total_requests_today": 0,
            "total_tokens_today": 0,
            "providers": {},
            "capacity": {},
        }

        for p in self.providers:
            available = self._is_provider_available(p)
            budget = self.budgets.get(p.name, ProviderBudget(name=p.name))

            status["providers"][p.name] = {
                "available": available,
                "tier": p.tier.value,
                "quality": f"{p.quality_score:.0%}",
                "rpm_limit": p.rpm,
                "rpd_limit": p.rpd,
                "context_window": f"{p.context_window:,}",
                "requests_today": budget.requests_day,
                "total_requests": budget.total_requests,
                "total_tokens": budget.total_tokens,
                "avg_latency": f"{budget.avg_latency_ms:.0f}ms",
                "error_rate": f"{budget.error_rate():.0%}",
            }

            if available:
                status["available_providers"] += 1
            status["total_requests_today"] += budget.requests_day
            status["total_tokens_today"] += budget.total_tokens

        # Calculate combined capacity
        total_rpm = sum(p.rpm for p in self.providers if self._is_provider_available(p))
        total_rpd = sum(p.rpd for p in self.providers if self._is_provider_available(p) and p.rpd > 0)
        total_tpd = sum(p.tpd for p in self.providers if self._is_provider_available(p) and p.tpd > 0)

        status["capacity"] = {
            "combined_rpm": f"~{total_rpm}",
            "combined_rpd": f"~{total_rpd if total_rpd else 'ilimitado (varies)'}",
            "combined_tpd": f"~{total_tpd:,} tokens" if total_tpd else "varies by provider",
            "free_models_available": sum(len(p.models) for p in self.providers if self._is_provider_available(p)),
        }

        return status

    def get_status_text(self) -> str:
        """Retorna status formatado para exibição."""
        status = self.get_status()
        lines = [
            "═══ Multi-Provider Router Status ═══",
            f"Providers ativos: {status['available_providers']}/{status['total_providers']}",
            f"Requisições hoje: {status['total_requests_today']}",
            f"Tokens hoje: {status['total_tokens_today']:,}",
            "",
            "── Capacidade Combinada ──",
            f"  RPM total: {status['capacity']['combined_rpm']}",
            f"  RPD total: {status['capacity']['combined_rpd']}",
            f"  TPD total: {status['capacity']['combined_tpd']}",
            f"  Modelos gratuitos: {status['capacity']['free_models_available']}",
            "",
            "── Providers ──",
        ]
        for name, info in status["providers"].items():
            icon = "🟢" if info["available"] else "🔴"
            lines.append(
                f"  {icon} {name:12s} | {info['tier']:12s} | "
                f"Q:{info['quality']} | "
                f"R:{info['total_requests']} | "
                f"T:{info['total_tokens']:,} | "
                f"L:{info['avg_latency']} | "
                f"E:{info['error_rate']}"
            )

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════

_router_instance: Optional[MultiProviderRouter] = None
_router_lock = threading.Lock()


def get_router() -> MultiProviderRouter:
    """Retorna instância global do router (singleton)."""
    global _router_instance
    if _router_instance is None:
        with _router_lock:
            if _router_instance is None:
                _router_instance = MultiProviderRouter()
    return _router_instance
