#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Great Sage AI — 9Router (Multi-Provider Token Rotation)
========================================================
Tokens infinitos via rotação inteligente entre 10+ providers gratuitos.

Cada provider free tier tem limite de tokens/minuto (TPM). O 9Router:
  1. Rastreia uso de tokens por provider por janela de tempo
  2. Quando um provider atinge seu limite, rotaciona automaticamente
  3. Rotea por capability: código → provider de código, chat → provider de chat
  4. Mergeia respostas de forma transparente
  5. Fallback cascata: se todos os cloud falharem → Ollama local → RAG offline

Providers suportados (todos free tier):
  Groq | Gemini | OpenRouter | Cerebras | DeepSeek | SambaNova |
  Mistral | Together AI | Fireworks | Cohere | HuggingFace | Ollama

Estratégia de rotação:
  - Round-robin com peso (preferência por providers rápidos e de alta qualidade)
  - Token budget tracking por provider
  - Cooldown automático quando rate-limited
  - Warm-up: providers em cooldown são reavaliados periodicamente
"""

from __future__ import annotations

import os
import json
import time
import logging
import threading
import hashlib
from pathlib import Path
from typing import Optional, Generator, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logger = logging.getLogger("greatsage.nine_router")


# =========================================================================
# Provider capabilities & free tier limits
# =========================================================================

class ProviderTier(Enum):
    """Quality tiers for routing decisions."""
    PREMIUM = "premium"    # Best quality, fastest (Groq 120B, Gemini)
    HIGH = "high"          # Great quality (Cerebras, DeepSeek, Mistral)
    STANDARD = "standard"  # Good quality (OpenRouter, Together, SambaNova)
    LOCAL = "local"        # Unlimited but slower (Ollama)
    OFFLINE = "offline"    # No network needed (RAG, local knowledge)


@dataclass
class ProviderProfile:
    """Complete profile of a provider including capabilities, limits, and stats."""
    name: str
    tier: ProviderTier
    base_url: str = ""
    api_key_env: str = ""           # env var name for API key
    api_key_aliases: list = None    # alternative env var names
    models: dict = field(default_factory=dict)  # {task_type: model_name}
    fallback_models: list = field(default_factory=list)
    tpm_limit: int = 30000          # tokens per minute (free tier estimate)
    rpm_limit: int = 30             # requests per minute
    max_tokens: int = 4096          # max output tokens
    supports_streaming: bool = True
    supports_vision: bool = False
    supports_code: bool = True
    latency_ms_avg: float = 500     # average latency
    priority: int = 0               # lower = preferred
    # Runtime stats
    total_tokens_used: int = 0
    total_requests: int = 0
    errors: int = 0
    last_used: float = 0.0
    last_error: float = 0.0
    cooldown_until: float = 0.0     # timestamp when cooldown expires
    tokens_in_window: int = 0       # tokens used in current window
    window_start: float = 0.0       # start of current window

    def __post_init__(self):
        if self.api_key_aliases is None:
            self.api_key_aliases = []


# =========================================================================
# Provider registry — all 12 providers
# =========================================================================

PROVIDER_REGISTRY: List[ProviderProfile] = [
    ProviderProfile(
        name="groq",
        tier=ProviderTier.PREMIUM,
        base_url="https://api.groq.com/openai/v1",
        api_key_env="GROQ_API_KEY",
        models={
            "chat": "openai/gpt-oss-120b",
            "code": "openai/gpt-oss-120b",
            "fast": "openai/gpt-oss-20b",
            "reasoning": "qwen/qwen3-32b",
        },
        fallback_models=["openai/gpt-oss-20b", "qwen/qwen3-32b", "meta-llama/llama-4-maverick-17b-128e-instruct"],
        tpm_limit=30000, rpm_limit=30, max_tokens=4096,
        latency_ms_avg=300, priority=0,
    ),
    ProviderProfile(
        name="gemini",
        tier=ProviderTier.PREMIUM,
        base_url="https://generativelanguage.googleapis.com/v1beta",
        api_key_env="GOOGLE_API_KEY",
        api_key_aliases=["GEMINI_API_KEY", "GOOGLE_GENERATIVE_AI_API_KEY"],
        models={
            "chat": "gemini-3.6-flash",
            "code": "gemini-3.6-flash",
            "fast": "gemini-3.5-flash",
            "vision": "gemini-3.6-flash",
        },
        fallback_models=["gemini-3.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite"],
        tpm_limit=60000, rpm_limit=60, max_tokens=8192,
        supports_vision=True, latency_ms_avg=400, priority=1,
    ),
    ProviderProfile(
        name="cerebras",
        tier=ProviderTier.HIGH,
        base_url="https://api.cerebras.ai/v1",
        api_key_env="CEREBRAS_API_KEY",
        models={
            "chat": "llama-3.3-70b",
            "code": "llama-3.3-70b",
            "fast": "llama-3.1-8b",
        },
        fallback_models=["llama-3.1-8b"],
        tpm_limit=30000, rpm_limit=30, max_tokens=4096,
        latency_ms_avg=200, priority=2,  # fastest provider
    ),
    ProviderProfile(
        name="deepseek",
        tier=ProviderTier.HIGH,
        base_url="https://api.deepseek.com/v1",
        api_key_env="DEEPSEEK_API_KEY",
        models={
            "chat": "deepseek-chat",
            "code": "deepseek-coder",
            "reasoning": "deepseek-reasoner",
        },
        tpm_limit=30000, rpm_limit=60, max_tokens=4096,
        supports_code=True, latency_ms_avg=600, priority=3,
    ),
    ProviderProfile(
        name="sambanova",
        tier=ProviderTier.HIGH,
        base_url="https://api.sambanova.ai/v1",
        api_key_env="SAMBANOVA_API_KEY",
        models={
            "chat": "Meta-Llama-3.3-70B-Instruct",
            "code": "Meta-Llama-3.3-70B-Instruct",
            "fast": "Meta-Llama-3.1-8B-Instruct",
        },
        fallback_models=["Meta-Llama-3.1-8B-Instruct"],
        tpm_limit=30000, rpm_limit=30, max_tokens=4096,
        latency_ms_avg=350, priority=4,
    ),
    ProviderProfile(
        name="mistral",
        tier=ProviderTier.HIGH,
        base_url="https://api.mistral.ai/v1",
        api_key_env="MISTRAL_API_KEY",
        models={
            "chat": "mistral-large-latest",
            "code": "codestral-latest",
            "fast": "mistral-small-latest",
        },
        tpm_limit=30000, rpm_limit=30, max_tokens=4096,
        supports_code=True, latency_ms_avg=500, priority=5,
    ),
    ProviderProfile(
        name="together",
        tier=ProviderTier.STANDARD,
        base_url="https://api.together.xyz/v1",
        api_key_env="TOGETHER_API_KEY",
        models={
            "chat": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "code": "codellama/CodeLlama-34b-Instruct-hf",
            "fast": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        },
        fallback_models=["meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"],
        tpm_limit=30000, rpm_limit=60, max_tokens=4096,
        latency_ms_avg=500, priority=6,
    ),
    ProviderProfile(
        name="fireworks",
        tier=ProviderTier.STANDARD,
        base_url="https://api.fireworks.ai/inference/v1",
        api_key_env="FIREWORKS_API_KEY",
        models={
            "chat": "accounts/fireworks/models/llama-v3p3-70b-instruct",
            "code": "accounts/fireworks/models/codellama-34b-instruct",
            "fast": "accounts/fireworks/models/llama-v3p1-8b-instruct",
        },
        tpm_limit=30000, rpm_limit=60, max_tokens=4096,
        latency_ms_avg=450, priority=7,
    ),
    ProviderProfile(
        name="openrouter",
        tier=ProviderTier.STANDARD,
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        models={
            "chat": "meta-llama/llama-3.3-70b-instruct",
            "code": "meta-llama/llama-3.3-70b-instruct",
            "fast": "openai/gpt-4o-mini",
        },
        fallback_models=["openai/gpt-4o-mini", "meta-llama/llama-3.1-8b-instruct"],
        tpm_limit=200, rpm_limit=20, max_tokens=4096,  # free tier is very limited
        latency_ms_avg=800, priority=8,
    ),
    ProviderProfile(
        name="cohere",
        tier=ProviderTier.STANDARD,
        base_url="https://api.cohere.com/v2",
        api_key_env="COHERE_API_KEY",
        models={
            "chat": "command-a-03-2025",
            "fast": "command-r-plus",
        },
        tpm_limit=30000, rpm_limit=30, max_tokens=4096,
        latency_ms_avg=600, priority=9,
    ),
    ProviderProfile(
        name="huggingface",
        tier=ProviderTier.STANDARD,
        base_url="https://api-inference.huggingface.co/v1",
        api_key_env="HUGGINGFACE_API_KEY",
        api_key_aliases=["HF_API_KEY", "HF_TOKEN"],
        models={
            "chat": "meta-llama/Llama-3.3-70B-Instruct",
            "fast": "meta-llama/Llama-3.1-8B-Instruct",
        },
        tpm_limit=30000, rpm_limit=10, max_tokens=4096,
        latency_ms_avg=1200, priority=10,
    ),
    ProviderProfile(
        name="ollama",
        tier=ProviderTier.LOCAL,
        base_url="http://localhost:11434",
        models={
            "chat": "llama3.1:8b",
            "code": "codellama:13b",
            "fast": "llama3.2:3b",
        },
        tpm_limit=999999999, rpm_limit=999999999, max_tokens=4096,
        latency_ms_avg=2000, priority=99,
    ),
]


# =========================================================================
# Token budget tracker
# =========================================================================

_WINDOW_SEC = 60.0  # 1-minute rolling window for TPM tracking


class TokenBudget:
    """Tracks token usage per provider within rolling time windows."""

    def __init__(self):
        self._lock = threading.Lock()
        self._provider_usage: Dict[str, List[Tuple[float, int]]] = defaultdict(list)
        # (timestamp, tokens_used) pairs

    def record(self, provider: str, tokens: int):
        """Record token usage for a provider."""
        now = time.time()
        with self._lock:
            self._provider_usage[provider].append((now, tokens))
            self._cleanup(provider, now)

    def used_in_window(self, provider: str) -> int:
        """Total tokens used by provider in current window."""
        now = time.time()
        with self._lock:
            self._cleanup(provider, now)
            return sum(t for _, t in self._provider_usage[provider])

    def remaining(self, provider: str, limit: int) -> int:
        """Remaining token budget for this provider."""
        return max(0, limit - self.used_in_window(provider))

    def _cleanup(self, provider: str, now: float):
        """Remove entries older than the window."""
        cutoff = now - _WINDOW_SEC
        entries = self._provider_usage[provider]
        self._provider_usage[provider] = [(ts, t) for ts, t in entries if ts > cutoff]


# =========================================================================
# 9Router — the main router
# =========================================================================

@dataclass
class RoutingDecision:
    """What the 9Router decided for a request."""
    provider: str
    model: str
    tier: ProviderTier
    task_type: str  # chat, code, fast, reasoning, vision
    reason: str     # why this provider was chosen
    budget_remaining: int
    fallback_chain: List[str]  # other providers to try if this fails


class NineRouter:
    """
    Multi-provider token rotation for effectively infinite tokens.

    Usage:
        router = NineRouter()
        decision = router.route(task_type="code")
        # Use decision.provider and decision.model
        router.record_usage("groq", tokens_used=500)
        router.record_error("gemini")  # auto-cooldown
    """

    def __init__(self, env_path: str = ".env"):
        self._providers = {p.name: p for p in PROVIDER_REGISTRY}
        self._budget = TokenBudget()
        self._env = self._load_env(env_path)
        self._lock = threading.Lock()
        self._active_provider = "groq"  # current primary
        self._round_robin_idx = 0

        # Resolve API keys
        self._resolve_keys()

        # Stats
        self._total_rotations = 0
        self._total_tokens = 0

        logger.info(f"9Router initialized: {self.available_count} providers available")

    def _load_env(self, env_path: str) -> Dict[str, str]:
        """Load .env file."""
        env = {}
        for p in [Path(env_path), Path(__file__).resolve().parent.parent / ".env", Path(".env")]:
            try:
                if p.exists():
                    for line in p.read_text(encoding="utf-8-sig").splitlines():
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            if k not in env:
                                env[k] = v.strip().strip("\"'")
                    if env:
                        break
            except Exception:
                continue
        # Also check os.environ
        for p_name in list(PROVIDER_REGISTRY):
            pass
        return env

    def _resolve_keys(self):
        """Resolve API keys for all providers from env/SecretManager."""
        for name, profile in self._providers.items():
            key = self._get_key(profile)
            profile._api_key = key  # stash for later use

    def _get_key(self, profile: ProviderProfile) -> str:
        """Get API key from multiple sources."""
        # 1) SecretManager
        for mod_path in ("core.secret_manager", "GreatSageAI_Clone.core.secret_manager"):
            try:
                mod = __import__(mod_path, fromlist=["secrets"])
                sm = getattr(mod, "secrets", None)
                if sm:
                    for env_name in [profile.api_key_env] + (profile.api_key_aliases or []):
                        v = sm.get(env_name)
                        if v:
                            return v
                break
            except Exception:
                continue

        # 2) .env
        for env_name in [profile.api_key_env] + (profile.api_key_aliases or []):
            if self._env.get(env_name):
                return self._env[env_name]

        # 3) os.environ
        for env_name in [profile.api_key_env] + (profile.api_key_aliases or []):
            v = os.getenv(env_name, "")
            if v:
                return v

        return ""

    # ------------------------------------------------------------------
    # Routing intelligence
    # ------------------------------------------------------------------

    def route(self, task_type: str = "chat", prefer_tier: ProviderTier = None) -> RoutingDecision:
        """
        Route a request to the best available provider.

        task_type: "chat" | "code" | "fast" | "reasoning" | "vision"
        prefer_tier: optionally prefer a specific quality tier
        """
        now = time.time()
        candidates = []

        for name, profile in self._providers.items():
            key = getattr(profile, "_api_key", "")
            is_local = profile.tier == ProviderTier.LOCAL and name == "ollama"

            # Skip providers without keys (except local Ollama)
            if not key and not is_local:
                continue

            # Skip providers in cooldown
            if now < profile.cooldown_until:
                continue

            # Check token budget
            budget = self._budget.remaining(name, profile.tpm_limit)
            if budget <= 100:  # less than 100 tokens remaining → skip
                continue

            # Get model for this task type
            model = profile.models.get(task_type) or profile.models.get("chat", "")
            if not model:
                continue

            # Calculate score
            score = self._score_provider(profile, task_type, budget, prefer_tier)
            candidates.append((score, name, model, budget))

        if not candidates:
            # Fallback: try Ollama, then offline
            if self._ollama_available():
                return RoutingDecision(
                    provider="ollama", model=self._providers["ollama"].models.get("chat", "llama3.1:8b"),
                    tier=ProviderTier.LOCAL, task_type=task_type,
                    reason="All cloud providers unavailable — falling back to local Ollama",
                    budget_remaining=999999999, fallback_chain=["offline"],
                )
            return RoutingDecision(
                provider="offline", model="offline",
                tier=ProviderTier.OFFLINE, task_type=task_type,
                reason="All providers unavailable — offline mode",
                budget_remaining=0, fallback_chain=[],
            )

        # Sort by score (higher = better)
        candidates.sort(key=lambda x: x[0], reverse=True)
        best = candidates[0]

        # Build fallback chain from remaining candidates
        fallback_chain = [c[1] for c in candidates[1:4]]  # top 3 alternatives

        return RoutingDecision(
            provider=best[1],
            model=best[2],
            tier=self._providers[best[1]].tier,
            task_type=task_type,
            reason=self._routing_reason(best[1], task_type, len(candidates)),
            budget_remaining=best[3],
            fallback_chain=fallback_chain,
        )

    def _score_provider(self, profile: ProviderProfile, task_type: str,
                        budget: int, prefer_tier: ProviderTier = None) -> float:
        """Score a provider for a given request. Higher = better."""
        score = 100.0

        # Tier preference
        if prefer_tier and profile.tier == prefer_tier:
            score += 50
        elif profile.tier == ProviderTier.PREMIUM:
            score += 30
        elif profile.tier == ProviderTier.HIGH:
            score += 20
        elif profile.tier == ProviderTier.STANDARD:
            score += 10

        # Task capability
        if task_type == "code" and profile.supports_code:
            score += 15
        if task_type == "vision" and profile.supports_vision:
            score += 20

        # Latency preference (faster = better)
        latency_bonus = max(0, (2000 - profile.latency_ms_avg) / 50)
        score += latency_bonus

        # Budget health (more remaining = better)
        budget_ratio = budget / max(1, profile.tpm_limit)
        score += budget_ratio * 20

        # Penalize error-prone providers
        if profile.total_requests > 5:
            error_rate = profile.errors / profile.total_requests
            score -= error_rate * 50

        # Penalize recently-used (encourage rotation)
        time_since_use = time.time() - profile.last_used if profile.last_used > 0 else 300
        if time_since_use < 10:
            score -= 10  # slight penalty for very recent use
        elif time_since_use > 60:
            score += 5  # bonus for "fresh" providers

        # Priority tiebreaker
        score -= profile.priority * 0.5

        return score

    def _routing_reason(self, provider: str, task_type: str, candidate_count: int) -> str:
        """Generate a human-readable reason for the routing decision."""
        p = self._providers[provider]
        budget = self._budget.remaining(provider, p.tpm_limit)
        return (f"{provider} ({p.tier.value}) selected — "
                f"{budget:,} tokens remaining, "
                f"{candidate_count} providers available")

    def _ollama_available(self) -> bool:
        """Check if Ollama is running."""
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.3)
            up = s.connect_ex(("127.0.0.1", 11434)) == 0
            s.close()
            return up
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Usage tracking
    # ------------------------------------------------------------------

    def record_usage(self, provider: str, tokens: int):
        """Record token usage after a successful request."""
        with self._lock:
            self._budget.record(provider, tokens)
            if provider in self._providers:
                p = self._providers[provider]
                p.total_tokens_used += tokens
                p.total_requests += 1
                p.last_used = time.time()
                p.tokens_in_window = self._budget.used_in_window(provider)
            self._total_tokens += tokens

    def record_error(self, provider: str, cooldown_sec: float = 30.0):
        """Record an error and apply cooldown."""
        with self._lock:
            if provider in self._providers:
                p = self._providers[provider]
                p.errors += 1
                p.last_error = time.time()
                p.cooldown_until = time.time() + cooldown_sec
                self._total_rotations += 1
                logger.warning(f"9Router: {provider} error — cooldown {cooldown_sec}s")

    def record_rotation(self, from_provider: str, to_provider: str, reason: str):
        """Record a rotation event."""
        with self._lock:
            self._total_rotations += 1
            logger.info(f"9Router: rotated {from_provider} → {to_provider} ({reason})")

    # ------------------------------------------------------------------
    # Stats & status
    # ------------------------------------------------------------------

    @property
    def available_count(self) -> int:
        """Number of currently available providers."""
        now = time.time()
        count = 0
        for name, profile in self._providers.items():
            key = getattr(profile, "_api_key", "")
            is_local = profile.tier == ProviderTier.LOCAL and name == "ollama"
            if (key or is_local) and now >= profile.cooldown_until:
                budget = self._budget.remaining(name, profile.tpm_limit)
                if budget > 100 or is_local:
                    count += 1
        return count

    def get_status(self) -> Dict[str, Any]:
        """Get full router status for UI/telemetry."""
        now = time.time()
        providers = {}
        for name, p in self._providers.items():
            key = getattr(p, "_api_key", "")
            budget = self._budget.remaining(name, p.tpm_limit) if key else 0
            providers[name] = {
                "tier": p.tier.value,
                "model": list(p.models.values())[0] if p.models else "",
                "available": (bool(key) or name == "ollama") and now >= p.cooldown_until,
                "has_key": bool(key),
                "tokens_remaining": budget,
                "tpm_limit": p.tpm_limit,
                "total_tokens": p.total_tokens_used,
                "total_requests": p.total_requests,
                "errors": p.errors,
                "cooldown": max(0, p.cooldown_until - now),
                "error_rate": f"{p.errors / max(1, p.total_requests) * 100:.1f}%",
                "latency_avg_ms": p.latency_ms_avg,
            }
        return {
            "active_provider": self._active_provider,
            "available_count": self.available_count,
            "total_providers": len(self._providers),
            "total_tokens": self._total_tokens,
            "total_rotations": self._total_rotations,
            "providers": providers,
        }

    def get_token_budget_summary(self) -> str:
        """Human-readable summary of token budgets."""
        lines = ["9Router Token Budgets:"]
        for name, p in self._providers.items():
            key = getattr(p, "_api_key", "")
            if not key and name != "ollama":
                continue
            budget = self._budget.remaining(name, p.tpm_limit)
            pct = (budget / max(1, p.tpm_limit)) * 100
            bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
            status = "🟢" if p.cooldown_until <= time.time() else "🔴"
            lines.append(f"  {status} {name:12s} [{bar}] {pct:5.1f}% ({budget:,}/{p.tpm_limit:,})")
        total_remaining = sum(
            self._budget.remaining(n, p.tpm_limit)
            for n, p in self._providers.items()
            if getattr(p, "_api_key", "") or n == "ollama"
        )
        lines.append(f"\n  📊 Total remaining: ~{total_remaining:,} tokens/min across all providers")
        lines.append(f"  🔄 Rotations: {self._total_rotations} | Total tokens: {self._total_tokens:,}")
        return "\n".join(lines)


# =========================================================================
# Integration wrapper — drop-in replacement for LLMEngine routing
# =========================================================================

class NineRouterBridge:
    """
    Bridges 9Router decisions to the existing LLMProvider/LLMEngine system.
    Used by great_sage_app.py to transparently upgrade from single-provider
    to multi-provider rotation.
    """

    def __init__(self, llm_engine=None, env_path: str = ".env"):
        self.router = NineRouter(env_path=env_path)
        self._llm_engine = llm_engine
        self._provider_map: Dict[str, Any] = {}  # name -> LLMProvider instance
        self._build_provider_map()

    def _build_provider_map(self):
        """Build mapping from 9Router names to LLMProvider instances."""
        if not self._llm_engine:
            return
        for p in self._llm_engine.providers:
            self._provider_map[p.name] = p

    def route_and_query(self, messages: List[Dict], system: str = "",
                        task_type: str = "chat", **kwargs) -> "LLMResponse":
        """Route to best provider and query with automatic fallback."""
        decision = self.router.route(task_type=task_type)
        all_providers = [decision.provider] + decision.fallback_chain

        last_error = ""
        for provider_name in all_providers:
            # Try 9Router provider first
            p = self._provider_map.get(provider_name)
            if p and p.available:
                response = p.chat(messages, system, **kwargs)
                if response.success:
                    self.router.record_usage(provider_name, response.tokens_used)
                    return response
                last_error = response.error
                self.router.record_error(provider_name)
                self.router.record_rotation(provider_name,
                    decision.fallback_chain[0] if decision.fallback_chain else "offline",
                    f"error: {last_error[:50]}")
                continue

            # Try direct HTTP for providers not in LLMEngine
            profile = self.router._providers.get(provider_name)
            if profile and getattr(profile, "_api_key", ""):
                response = self._direct_query(profile, messages, system, **kwargs)
                if response and response.success:
                    self.router.record_usage(provider_name, response.tokens_used)
                    return response
                self.router.record_error(provider_name)

        # All failed — return offline fallback
        from core.llm import LLMResponse
        return LLMResponse(
            text="Todos os providers falharam. Modo offline ativo.",
            provider="offline", model="offline",
            success=False, error=last_error,
        )

    def route_and_stream(self, messages: List[Dict], system: str = "",
                         task_type: str = "chat", **kwargs) -> Generator[str, None, None]:
        """Route to best provider and stream with automatic fallback."""
        decision = self.router.route(task_type=task_type)
        all_providers = [decision.provider] + decision.fallback_chain

        for provider_name in all_providers:
            p = self._provider_map.get(provider_name)
            if p and p.available:
                try:
                    yielded = False
                    total_tokens = 0
                    for tok in p.stream(messages, system, **kwargs):
                        if tok and "[ERRO" not in tok and "❌" not in tok:
                            yielded = True
                            total_tokens += len(tok.split())  # rough estimate
                            yield tok
                        elif tok and ("[ERRO" in tok or "❌" in tok):
                            break
                    if yielded:
                        self.router.record_usage(provider_name, total_tokens)
                        return
                except Exception as e:
                    logger.warning(f"9Router stream {provider_name} failed: {e}")
                    self.router.record_error(provider_name)
                    continue

            # Try direct HTTP streaming
            profile = self.router._providers.get(provider_name)
            if profile and getattr(profile, "_api_key", ""):
                try:
                    total = 0
                    for tok in self._direct_stream(profile, messages, system, **kwargs):
                        total += len(tok.split()) if tok else 0
                        yield tok
                    if total > 0:
                        self.router.record_usage(provider_name, total)
                        return
                except Exception:
                    self.router.record_error(provider_name)

        yield "\n[9Router] Todos os providers esgotaram. Modo offline."

    def _direct_query(self, profile: ProviderProfile, messages: List[Dict],
                      system: str = "", **kwargs) -> Optional["LLMResponse"]:
        """Direct HTTP query for providers not in LLMEngine."""
        try:
            import requests
            from core.llm import LLMResponse

            t0 = time.time()
            msgs = []
            if system:
                msgs.append({"role": "system", "content": system})
            msgs.extend(messages)

            model = profile.models.get("chat", "")
            headers = {
                "Authorization": f"Bearer {getattr(profile, '_api_key', '')}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model,
                "messages": msgs,
                "max_tokens": kwargs.get("max_tokens", profile.max_tokens),
                "temperature": kwargs.get("temperature", 0.7),
            }

            resp = requests.post(
                f"{profile.base_url}/chat/completions",
                headers=headers, json=payload, timeout=60,
            )
            data = resp.json()
            latency = (time.time() - t0) * 1000

            if "choices" in data and data["choices"]:
                text = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {}).get("total_tokens", 0)
                return LLMResponse(text=text, provider=profile.name, model=model,
                                   tokens_used=tokens, latency_ms=latency)
            else:
                error = data.get("error", {}).get("message", "Unknown")
                return LLMResponse(text="", provider=profile.name, model=model,
                                   latency_ms=latency, success=False, error=error)
        except Exception as e:
            logger.debug(f"9Router direct query {profile.name} failed: {e}")
            return None

    def _direct_stream(self, profile: ProviderProfile, messages: List[Dict],
                       system: str = "", **kwargs) -> Generator[str, None, None]:
        """Direct HTTP streaming for providers not in LLMEngine."""
        try:
            import requests

            msgs = []
            if system:
                msgs.append({"role": "system", "content": system})
            msgs.extend(messages)

            model = profile.models.get("chat", "")
            headers = {
                "Authorization": f"Bearer {getattr(profile, '_api_key', '')}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model,
                "messages": msgs,
                "max_tokens": kwargs.get("max_tokens", profile.max_tokens),
                "temperature": kwargs.get("temperature", 0.7),
                "stream": True,
            }

            resp = requests.post(
                f"{profile.base_url}/chat/completions",
                headers=headers, json=payload, timeout=120, stream=True,
            )

            for line in resp.iter_lines():
                if line:
                    try:
                        data = json.loads(line.decode("utf-8").removeprefix("data: "))
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                        if data.get("choices", [{}])[0].get("finish_reason"):
                            break
                    except (json.JSONDecodeError, IndexError, KeyError):
                        continue
        except Exception as e:
            logger.debug(f"9Router direct stream {profile.name} failed: {e}")
            yield f"\n[ERRO {profile.name}] {e}"

    def get_status(self) -> Dict[str, Any]:
        """Get full status including 9Router metrics."""
        return self.router.get_status()

    def get_budget_summary(self) -> str:
        """Human-readable budget summary."""
        return self.router.get_token_budget_summary()
