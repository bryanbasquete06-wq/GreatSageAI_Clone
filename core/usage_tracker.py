# -*- coding: utf-8 -*-
"""
Great Sage AI — Usage Tracker
================================
Monitora requests, tokens e latencia por provider em tempo real.
Mostra limites diarios, usage percent, e projecao de quandog vai bater o limite.
"""
from __future__ import annotations

import json
import time
import threading
from pathlib import Path
from datetime import datetime, date
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict


# ── Free Tier Limits (por provider) ───────────────────────
PROVIDER_LIMITS: dict[str, dict] = {
    "groq": {
        "rpm": 30,           # requests per minute
        "rpd": 14400,        # requests per day
        "tpm": 6000,         # tokens per minute
        "tpd_input": 500000, # tokens per day input
        "tpd_output": 100000, # tokens per day output
    },
    "gemini": {
        "rpm": 15,
        "rpd": 1500,
        "tpm": 32000,
        "tpd_input": 1000000,
        "tpd_output": 500000,
    },
    "cerebras": {
        "rpm": 30,
        "rpd": 1000,
        "tpm": 6000,
        "tpd_input": 500000,
        "tpd_output": 100000,
    },
    "sambanova": {
        "rpm": 100,
        "rpd": 10000,
        "tpm": 20000,
        "tpd_input": 500000,
        "tpd_output": 100000,
    },
    "openrouter": {
        "rpm": 20,
        "rpd": 200,
        "tpm": 20000,
        "tpd_input": 1000000,
        "tpd_output": 1000000,
    },
    "mistral": {
        "rpm": 30,
        "rpd": 1000,
        "tpm": 10000,
        "tpd_input": 500000,
        "tpd_output": 100000,
    },
    "together": {
        "rpm": 60,
        "rpd": 1000,
        "tpm": 20000,
        "tpd_input": 1000000,
        "tpd_output": 500000,
    },
    "fireworks": {
        "rpm": 60,
        "rpd": 1000,
        "tpm": 20000,
        "tpd_input": 500000,
        "tpd_output": 500000,
    },
    "cohere": {
        "rpm": 30,
        "rpd": 1000,
        "tpm": 10000,
        "tpd_input": 500000,
        "tpd_output": 100000,
    },
    "deepseek": {
        "rpm": 30,
        "rpd": 1000,
        "tpm": 10000,
        "tpd_input": 500000,
        "tpd_output": 100000,
    },
    "huggingface": {
        "rpm": 30,
        "rpd": 1000,
        "tpm": 10000,
        "tpd_input": 500000,
        "tpd_output": 100000,
    },
    "ollama": {
        "rpm": 999999,
        "rpd": 999999,
        "tpm": 999999,
        "tpd_input": 999999,
        "tpd_output": 999999,
    },
    "9router": {
        "rpm": 999999,
        "rpd": 999999,
        "tpm": 999999,
        "tpd_input": 999999,
        "tpd_output": 999999,
    },
}


@dataclass
class ProviderUsage:
    """Usage stats for a single provider."""
    name: str
    requests_minute: int = 0
    requests_day: int = 0
    tokens_minute: int = 0
    tokens_input_day: int = 0
    tokens_output_day: int = 0
    total_requests: int = 0
    total_tokens: int = 0
    errors: int = 0
    avg_latency_ms: float = 0.0
    _latencies: list = field(default_factory=list)
    _minute_reset: float = 0.0
    _day_reset: str = ""

    def get_limit(self, key: str) -> int:
        return PROVIDER_LIMITS.get(self.name, {}).get(key, 0)

    def request_pct(self) -> float:
        rpd = self.get_limit("rpd")
        return min(100.0, (self.requests_day / rpd * 100) if rpd else 0)

    def token_input_pct(self) -> float:
        tpd = self.get_limit("tpd_input")
        return min(100.0, (self.tokens_input_day / tpd * 100) if tpd else 0)

    def token_output_pct(self) -> float:
        tpd = self.get_limit("tpd_output")
        return min(100.0, (self.tokens_output_day / tpd * 100) if tpd else 0)

    def rpm_pct(self) -> float:
        rpm = self.get_limit("rpm")
        return min(100.0, (self.requests_minute / rpm * 100) if rpm else 0)

    def is_limited(self) -> bool:
        return self.request_pct() >= 95 or self.token_input_pct() >= 95

    def time_until_reset(self) -> str:
        """Estimate when daily usage resets."""
        now = datetime.now()
        reset = datetime(now.year, now.month, now.day, 0, 0, 0)
        if now.hour >= 0:
            reset = reset.replace(day=now.day + 1) if now.day < 28 else reset
        delta = reset - now
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        return f"{hours}h {minutes}m"


class UsageTracker:
    """Singleton tracker for all providers."""

    _instance: Optional["UsageTracker"] = None
    _lock = threading.Lock()
    _data_path = Path(__file__).resolve().parent.parent / "data" / "usage.json"

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._providers: dict[str, ProviderUsage] = {}
        self._today = date.today().isoformat()
        self._total_requests = 0
        self._total_tokens = 0
        self._session_start = time.time()
        self._load()

    # ── Record usage ───────────────────────────────────────

    def record_request(self, provider: str, input_tokens: int = 0,
                       output_tokens: int = 0, latency_ms: float = 0.0,
                       error: bool = False):
        """Record a single request to a provider."""
        self._maybe_reset()
        p = self._get_provider(provider)
        now = time.time()

        # Minute window
        if now - p._minute_reset > 60:
            p.requests_minute = 0
            p.tokens_minute = 0
            p._minute_reset = now
        p.requests_minute += 1
        p.tokens_minute += input_tokens + output_tokens

        # Daily
        p.requests_day += 1
        p.tokens_input_day += input_tokens
        p.tokens_output_day += output_tokens

        # Totals
        p.total_requests += 1
        p.total_tokens += input_tokens + output_tokens
        self._total_requests += 1
        self._total_tokens += input_tokens + output_tokens

        # Latency
        if latency_ms > 0:
            p._latencies.append(latency_ms)
            if len(p._latencies) > 100:
                p._latencies = p._latencies[-100:]
            p.avg_latency_ms = sum(p._latencies) / len(p._latencies)

        if error:
            p.errors += 1

        # Auto-save every 10 requests
        if self._total_requests % 10 == 0:
            self._save()

    # ── Read usage ─────────────────────────────────────────

    def get_provider(self, name: str) -> ProviderUsage:
        return self._get_provider(name)

    def get_all_providers(self) -> dict[str, ProviderUsage]:
        return dict(self._providers)

    def get_summary(self) -> dict:
        """Get overall usage summary."""
        uptime = time.time() - self._session_start
        hours = uptime / 3600
        return {
            "total_requests": self._total_requests,
            "total_tokens": self._total_tokens,
            "requests_per_hour": self._total_requests / hours if hours > 0 else 0,
            "tokens_per_hour": self._total_tokens / hours if hours > 0 else 0,
            "uptime_hours": round(hours, 2),
            "active_providers": sum(
                1 for p in self._providers.values() if p.requests_day > 0
            ),
            "providers_with_capacity": sum(
                1 for p in self._providers.values() if not p.is_limited()
            ),
            "date": self._today,
        }

    def get_combined_daily_pct(self) -> dict:
        """Combined usage across all providers (for the combined view)."""
        total_rpd = sum(p.get_limit("rpd") for p in self._providers.values())
        total_rpd_used = sum(p.requests_day for p in self._providers.values())
        total_tpd_in = sum(p.get_limit("tpd_input") for p in self._providers.values())
        total_tpd_in_used = sum(p.tokens_input_day for p in self._providers.values())
        return {
            "requests_pct": min(100, total_rpd_used / total_rpd * 100) if total_rpd else 0,
            "tokens_pct": min(100, total_tpd_in_used / total_tpd_in * 100) if total_tpd_in else 0,
            "total_rpd": total_rpd,
            "total_rpd_used": total_rpd_used,
            "total_tpd": total_tpd_in,
            "total_tpd_used": total_tpd_in_used,
        }

    # ── Internal ───────────────────────────────────────────

    def _get_provider(self, name: str) -> ProviderUsage:
        if name not in self._providers:
            self._providers[name] = ProviderUsage(name=name)
        p = self._providers[name]
        self._maybe_reset()
        return p

    def _maybe_reset(self):
        today = date.today().isoformat()
        if today != self._today:
            for p in self._providers.values():
                p.requests_day = 0
                p.tokens_input_day = 0
                p.tokens_output_day = 0
                p.errors = 0
            self._today = today
            self._save()

    def _save(self):
        try:
            self._data_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "date": self._today,
                "total_requests": self._total_requests,
                "total_tokens": self._total_tokens,
                "session_start": self._session_start,
                "providers": {},
            }
            for name, p in self._providers.items():
                data["providers"][name] = {
                    "requests_day": p.requests_day,
                    "tokens_input_day": p.tokens_input_day,
                    "tokens_output_day": p.tokens_output_day,
                    "total_requests": p.total_requests,
                    "total_tokens": p.total_tokens,
                    "errors": p.errors,
                    "avg_latency_ms": p.avg_latency_ms,
                }
            self._data_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass

    def _load(self):
        try:
            if self._data_path.exists():
                data = json.loads(self._data_path.read_text(encoding="utf-8"))
                if data.get("date") == self._today:
                    self._total_requests = data.get("total_requests", 0)
                    self._total_tokens = data.get("total_tokens", 0)
                    self._session_start = data.get("session_start", time.time())
                    for name, pdata in data.get("providers", {}).items():
                        p = self._get_provider(name)
                        p.requests_day = pdata.get("requests_day", 0)
                        p.tokens_input_day = pdata.get("tokens_input_day", 0)
                        p.tokens_output_day = pdata.get("tokens_output_day", 0)
                        p.total_requests = pdata.get("total_requests", 0)
                        p.total_tokens = pdata.get("total_tokens", 0)
                        p.errors = pdata.get("errors", 0)
                        p.avg_latency_ms = pdata.get("avg_latency_ms", 0.0)
        except Exception:
            pass
