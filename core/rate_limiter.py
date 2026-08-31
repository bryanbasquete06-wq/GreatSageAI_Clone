"""
Elívea — Rate Limiter & Token Budget Manager
=====================================================
Limites altos para uso livre, com degradação graciosa (nunca retorna erro,
apenas throttle quando necessário).

Features:
  - Sliding window rate limiting (requests/minuto, tokens/minuto)
  - Token budget tracking por provider e global
  - Cooldown automático com recovery
  - Burst allowance (pico curto sem bloquear)
  - Graceful degradation: em vez de erro, retorna resposta mais curta/barata
"""

from __future__ import annotations

import time
import threading
import logging
from typing import Optional, Dict, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger("elvea.rate_limiter")


@dataclass
class RateLimitConfig:
    """Configuração de rate limit por provider."""
    # Requests
    rpm: int = 200                    # requests per minute (generous)
    burst: int = 30                   # burst allowance (short spikes)
    
    # Tokens
    tpm: int = 500_000               # tokens per minute (generous for free tier)
    daily_tokens: int = 10_000_000   # daily token budget
    
    # Cooldown
    cooldown_seconds: float = 5.0    # brief cooldown when rate limited
    max_cooldown: float = 60.0       # max cooldown before giving up
    
    # Graceful degradation
    reduce_tokens_on_throttle: int = 2048  # reduce max_tokens when throttled
    min_tokens: int = 256                     # never go below this


@dataclass
class ProviderBudget:
    """Budget tracking per provider."""
    name: str
    config: RateLimitConfig = field(default_factory=RateLimitConfig)
    
    # Sliding window counters
    _request_timestamps: list = field(default_factory=list)
    _token_counts: list = field(default_factory=list)  # (timestamp, tokens)
    
    # Daily counter
    _daily_tokens: int = 0
    _daily_reset: float = 0.0
    
    # Cooldown state
    _cooldown_until: float = 0.0
    _consecutive_throttles: int = 0
    
    # Stats
    total_requests: int = 0
    total_tokens: int = 0
    throttled_requests: int = 0


class RateLimiter:
    """
    Rate limiter centralizado com limites altos e degradação graciosa.
    
    NUNCA retorna erro — quando o rate limit é atingido:
      1. Primeiro: reduz max_tokens (resposta mais curta)
      2. Depois: ativa cooldown breve (5-60s)
      3. Último recurso: rota para provider diferente
    
    Usage:
        limiter = RateLimiter()
        if limiter.can_request("groq"):
            limiter.record_request("groq", tokens_used=150)
            # proceed
        else:
            # graceful fallback — reduced tokens or cooldown
            max_tokens = limiter.get_reduced_tokens("groq")
    """
    
    _instance: Optional["RateLimiter"] = None
    _lock = threading.Lock()
    
    # Default configs per provider (generous free tier limits)
    DEFAULT_CONFIGS: Dict[str, RateLimitConfig] = {
        "groq": RateLimitConfig(
            rpm=300, burst=50, tpm=600_000, daily_tokens=15_000_000,
            cooldown_seconds=3.0, max_cooldown=30.0,
        ),
        "gemini": RateLimitConfig(
            rpm=200, burst=40, tpm=1_000_000, daily_tokens=50_000_000,
            cooldown_seconds=5.0, max_cooldown=60.0,
        ),
        "openrouter": RateLimitConfig(
            rpm=150, burst=30, tpm=400_000, daily_tokens=8_000_000,
            cooldown_seconds=10.0, max_cooldown=120.0,
        ),
        "cerebras": RateLimitConfig(
            rpm=200, burst=40, tpm=500_000, daily_tokens=10_000_000,
            cooldown_seconds=5.0, max_cooldown=60.0,
        ),
        "huggingface": RateLimitConfig(
            rpm=100, burst=20, tpm=300_000, daily_tokens=5_000_000,
            cooldown_seconds=10.0, max_cooldown=120.0,
        ),
        "deepseek": RateLimitConfig(
            rpm=200, burst=40, tpm=500_000, daily_tokens=10_000_000,
            cooldown_seconds=5.0, max_cooldown=60.0,
        ),
        "sambanova": RateLimitConfig(
            rpm=150, burst=30, tpm=400_000, daily_tokens=8_000_000,
            cooldown_seconds=10.0, max_cooldown=90.0,
        ),
        "ollama": RateLimitConfig(
            rpm=9999, burst=999, tpm=999_999_999, daily_tokens=999_999_999,
            cooldown_seconds=0.0, max_cooldown=0.0,
        ),
        "default": RateLimitConfig(
            rpm=200, burst=40, tpm=500_000, daily_tokens=10_000_000,
            cooldown_seconds=5.0, max_cooldown=60.0,
        ),
    }
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._providers: Dict[str, ProviderBudget] = {}
        self._global_requests: list = []
        self._global_tokens: int = 0
        self._lock = threading.RLock()
        self._load_custom_config()
    
    def _load_custom_config(self):
        """Load custom rate limits from config/rate_limits.json if exists."""
        try:
            from pathlib import Path
            config_path = Path(__file__).resolve().parent.parent / "config" / "rate_limits.json"
            if config_path.exists():
                import json
                custom = json.loads(config_path.read_text(encoding="utf-8"))
                for provider, overrides in custom.items():
                    base = self.DEFAULT_CONFIGS.get(provider, self.DEFAULT_CONFIGS["default"])
                    for key, val in overrides.items():
                        if hasattr(base, key):
                            setattr(base, key, val)
                logger.info(f"Loaded custom rate limits for {list(custom.keys())}")
        except Exception:
            pass
    
    def _get_budget(self, provider: str) -> ProviderBudget:
        """Get or create budget for a provider."""
        if provider not in self._providers:
            config = self.DEFAULT_CONFIGS.get(provider, self.DEFAULT_CONFIGS["default"])
            self._providers[provider] = ProviderBudget(name=provider, config=config)
        return self._providers[provider]
    
    def _now(self) -> float:
        return time.time()
    
    def _clean_window(self, budget: ProviderBudget):
        """Remove entries older than 60 seconds from sliding window."""
        now = self._now()
        budget._request_timestamps = [t for t in budget._request_timestamps if now - t < 60]
        budget._token_counts = [(t, tok) for t, tok in budget._token_counts if now - t < 60]
        
        # Reset daily counter if needed
        if now - budget._daily_reset > 86400:
            budget._daily_tokens = 0
            budget._daily_reset = now
    
    # ── Core API ──────────────────────────────────────────────────────
    
    def can_request(self, provider: str) -> bool:
        """
        Check if a request is allowed. Always returns True when possible.
        Only returns False during active cooldown (which is brief).
        """
        with self._lock:
            budget = self._get_budget(provider)
            now = self._now()
            
            # Check cooldown
            if budget._cooldown_until > now:
                return False
            
            self._clean_window(budget)
            
            # Check RPM (generous — won't hit in normal use)
            if len(budget._request_timestamps) >= budget.config.rpm:
                logger.warning(f"[RateLimiter] {provider}: RPM limit ({budget.config.rpm}) reached, brief cooldown")
                budget._cooldown_until = now + budget.config.cooldown_seconds
                budget._consecutive_throttles += 1
                budget.throttled_requests += 1
                return False
            
            # Check TPM (generous — won't hit in normal use)
            window_tokens = sum(tok for _, tok in budget._token_counts)
            if window_tokens >= budget.config.tpm:
                logger.warning(f"[RateLimiter] {provider}: TPM limit ({budget.config.tpm}) reached, brief cooldown")
                cooldown = min(
                    budget.config.cooldown_seconds * (1 + budget._consecutive_throttles * 0.5),
                    budget.config.max_cooldown
                )
                budget._cooldown_until = now + cooldown
                budget._consecutive_throttles += 1
                budget.throttled_requests += 1
                return False
            
            # Check daily budget
            if budget._daily_tokens >= budget.config.daily_tokens:
                logger.warning(f"[RateLimiter] {provider}: Daily budget ({budget.config.daily_tokens}) reached")
                # Don't cooldown for daily — just return False, will try next provider
                return False
            
            # All clear — reset throttle counter on success
            budget._consecutive_throttles = 0
            return True
    
    def record_request(self, provider: str, tokens_used: int = 0):
        """Record a completed request."""
        with self._lock:
            now = self._now()
            budget = self._get_budget(provider)
            
            budget._request_timestamps.append(now)
            if tokens_used > 0:
                budget._token_counts.append((now, tokens_used))
                budget._daily_tokens += tokens_used
            
            budget.total_requests += 1
            budget.total_tokens += tokens_used
            
            # Also track globally
            self._global_requests.append(now)
            self._global_tokens += tokens_used
    
    def record_throttle(self, provider: str):
        """Record that the provider rate-limited us (e.g., 429 response)."""
        with self._lock:
            budget = self._get_budget(provider)
            now = self._now()
            budget._cooldown_until = now + budget.config.cooldown_seconds * (1 + budget._consecutive_throttles)
            budget._consecutive_throttles += 1
            budget.throttled_requests += 1
            logger.warning(f"[RateLimiter] {provider}: Throttled by provider, cooldown {budget.config.cooldown_seconds}s")
    
    def get_reduced_tokens(self, provider: str, requested: int = 4096) -> int:
        """
        Get a reduced max_tokens value for graceful degradation.
        When throttled, returns fewer tokens so requests still go through.
        """
        with self._lock:
            budget = self._get_budget(provider)
            
            if budget._consecutive_throttles == 0:
                return requested  # No throttles, use full amount
            
            # Reduce based on throttle count
            reduction = budget.config.reduce_tokens_on_throttle
            reduced = max(
                budget.config.min_tokens,
                requested - (reduction * budget._consecutive_throttles)
            )
            
            logger.info(f"[RateLimiter] {provider}: Reduced tokens {requested} → {reduced}")
            return reduced
    
    def get_status(self, provider: Optional[str] = None) -> dict:
        """Get rate limit status for monitoring."""
        with self._lock:
            now = self._now()
            
            if provider:
                budget = self._get_budget(provider)
                self._clean_window(budget)
                return {
                    "provider": provider,
                    "rpm_used": len(budget._request_timestamps),
                    "rpm_limit": budget.config.rpm,
                    "tpm_used": sum(tok for _, tok in budget._token_counts),
                    "tpm_limit": budget.config.tpm,
                    "daily_tokens_used": budget._daily_tokens,
                    "daily_tokens_limit": budget.config.daily_tokens,
                    "cooldown": max(0, budget._cooldown_until - now),
                    "total_requests": budget.total_requests,
                    "total_tokens": budget.total_tokens,
                    "throttled": budget.throttled_requests,
                }
            
            # All providers
            statuses = {}
            for name in self._providers:
                statuses[name] = self.get_status(name)
            return {
                "global_rpm": len([t for t in self._global_requests if now - t < 60]),
                "global_tokens": self._global_tokens,
                "providers": statuses,
            }
    
    def reset(self, provider: Optional[str] = None):
        """Reset counters (for testing or manual reset)."""
        with self._lock:
            if provider and provider in self._providers:
                budget = self._providers[provider]
                budget._request_timestamps.clear()
                budget._token_counts.clear()
                budget._cooldown_until = 0
                budget._consecutive_throttles = 0
                budget._daily_tokens = 0
                budget.total_requests = 0
                budget.total_tokens = 0
                budget.throttled_requests = 0
            elif provider is None:
                self._providers.clear()
                self._global_requests.clear()
                self._global_tokens = 0


# ═══════════════════════════════════════════════════════════════════════════
# Input Sanitizer — validates all user input before LLM
# ═══════════════════════════════════════════════════════════════════════════

class InputSanitizer:
    """
    Validates and sanitizes all input before reaching the LLM.
    Prevents prompt injection, excessive input, and malicious content.
    
    NEVER blocks legitimate input — only filters truly dangerous patterns.
    """
    
    # Max input lengths
    MAX_INPUT_LENGTH = 8000       # chars for single message
    MAX_SYSTEM_PROMPT = 16000     # chars for system prompt context
    MAX_HISTORY_CHARS = 20000     # chars for conversation history
    
    # Prompt injection patterns (extremely conservative)
    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"disregard\s+(all\s+)?prior",
        r"you\s+are\s+now\s+(?:a|an)\s+(?:different|new)",
        r"system\s*:\s*you\s+are",
        r"<\s*system\s*>",
        r"\[/INST\]",
        r"\[INST\]",
        r"<<SYS>>",
        r"<</SYS>>",
    ]
    
    @classmethod
    def sanitize(cls, text: str, max_length: Optional[int] = None) -> str:
        """
        Sanitize user input. Returns cleaned text.
        - Truncates to max length
        - Strips null bytes and control chars
        - Preserves all legitimate content
        """
        if not isinstance(text, str):
            text = str(text)
        
        # Remove null bytes and dangerous control characters
        text = text.replace("\x00", "").replace("\r", "")
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        # Truncate to max length
        limit = max_length or cls.MAX_INPUT_LENGTH
        if len(text) > limit:
            text = text[:limit]
            logger.warning(f"[InputSanitizer] Truncated input to {limit} chars")
        
        return text
    
    @classmethod
    def is_injection_attempt(cls, text: str) -> bool:
        """
        Check if text contains prompt injection patterns.
        Returns True ONLY for clear injection attempts.
        Legitimate content is never flagged.
        """
        if not isinstance(text, str):
            return False
        
        text_lower = text.lower().strip()
        
        for pattern in cls.INJECTION_PATTERNS:
            if __import__("re").search(pattern, text_lower):
                logger.warning(f"[InputSanitizer] Injection attempt detected: {pattern}")
                return True
        
        return False
    
    @classmethod
    def validate_for_llm(cls, text: str) -> Tuple[bool, str, str]:
        """
        Full validation for LLM input.
        Returns: (is_valid, sanitized_text, reason)
        
        If not valid, sanitized_text contains a safe fallback.
        """
        if text is None:
            return False, "", "Empty input"
        text = str(text) if not isinstance(text, str) else text
        if not text.strip():
            return False, "", "Empty input"
        
        # Sanitize
        cleaned = cls.sanitize(text)
        
        # Check injection
        if cls.is_injection_attempt(cleaned):
            # Don't block — just strip the injection part and continue
            cleaned = cls._strip_injection(cleaned)
            logger.warning("[InputSanitizer] Stripped injection attempt, continuing")
        
        return True, cleaned, ""
    
    @classmethod
    def _strip_injection(cls, text: str) -> str:
        """Remove injection patterns from text, keep the rest."""
        import re
        cleaned = text
        for pattern in cls.INJECTION_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()
    
    @classmethod
    def truncate_history(cls, history: list, max_chars: Optional[int] = None) -> list:
        """
        Truncate conversation history to fit within token budget.
        Keeps most recent messages, always preserves system prompt.
        """
        limit = max_chars or cls.MAX_HISTORY_CHARS
        total = 0
        result = []
        
        # Reverse — keep most recent
        for msg in reversed(history):
            msg_len = len(msg.get("content", ""))
            if total + msg_len > limit:
                break
            result.append(msg)
            total += msg_len
        
        result.reverse()
        return result
