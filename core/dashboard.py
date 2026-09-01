#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elivea — Dashboard de Atividade
========================================
Historico, uso de tokens, memoria, logs de erros.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger("elvea.dashboard")


@dataclass
class TokenUsage:
    """Track token usage per provider."""
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    requests: int = 0
    errors: int = 0
    total_latency_ms: float = 0


@dataclass
class ActivityLog:
    """Single activity log entry."""
    timestamp: str
    event_type: str  # message, command, error, voice, system
    details: str
    success: bool = True


class Dashboard:
    """Tracks all AI activity for the dashboard."""

    def __init__(self, data_dir: str = "memory"):
        self.dir = Path(data_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

        self.usage_file = self.dir / "token_usage.json"
        self.activity_file = self.dir / "activity_log.json"
        self.errors_file = self.dir / "error_log.json"

        self.token_usage: Dict[str, TokenUsage] = {}
        self.activity_log: List[Dict] = []
        self.error_log: List[Dict] = []

        self._load_data()

    def _load_data(self):
        try:
            if self.usage_file.exists():
                data = json.loads(self.usage_file.read_text(encoding="utf-8"))
                for k, v in data.items():
                    self.token_usage[k] = TokenUsage(**v)
        except Exception:
            pass

        try:
            if self.activity_file.exists():
                self.activity_log = json.loads(
                    self.activity_file.read_text(encoding="utf-8"))
        except Exception:
            pass

        try:
            if self.errors_file.exists():
                self.error_log = json.loads(
                    self.errors_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    def _save_data(self):
        try:
            usage_dict = {k: {
                "provider": v.provider,
                "model": v.model,
                "input_tokens": v.input_tokens,
                "output_tokens": v.output_tokens,
                "requests": v.requests,
                "errors": v.errors,
                "total_latency_ms": v.total_latency_ms,
            } for k, v in self.token_usage.items()}
            self.usage_file.write_text(
                json.dumps(usage_dict, indent=2, ensure_ascii=False),
                encoding="utf-8")
        except Exception as e:
            logger.error(f"Error saving usage: {e}")

        try:
            # Keep only last 500 activity entries
            self.activity_log = self.activity_log[-500:]
            self.activity_file.write_text(
                json.dumps(self.activity_log, indent=2, ensure_ascii=False),
                encoding="utf-8")
        except Exception as e:
            logger.error(f"Error saving activity: {e}")

        try:
            # Keep only last 100 error entries
            self.error_log = self.error_log[-100:]
            self.errors_file.write_text(
                json.dumps(self.error_log, indent=2, ensure_ascii=False),
                encoding="utf-8")
        except Exception as e:
            logger.error(f"Error saving errors: {e}")

    # ═══ TOKEN TRACKING ═════════════════════════════════════════════

    def record_request(self, provider: str, model: str, input_tokens: int = 0,
                       output_tokens: int = 0, latency_ms: float = 0,
                       success: bool = True):
        """Record an LLM request."""
        key = f"{provider}:{model}"
        if key not in self.token_usage:
            self.token_usage[key] = TokenUsage(provider=provider, model=model)

        usage = self.token_usage[key]
        usage.input_tokens += input_tokens
        usage.output_tokens += output_tokens
        usage.requests += 1
        usage.total_latency_ms += latency_ms
        if not success:
            usage.errors += 1

        self._save_data()

    def get_token_summary(self) -> str:
        """Get formatted token usage summary."""
        if not self.token_usage:
            return "Nenhum uso registrado ainda."

        parts = ["**Uso de Tokens por Provider:**\n"]

        total_in = 0
        total_out = 0
        total_req = 0

        for key, usage in self.token_usage.items():
            avg_latency = (usage.total_latency_ms / usage.requests
                          if usage.requests > 0 else 0)
            parts.append(
                f"**{usage.provider}** ({usage.model}):\n"
                f"  Requests: {usage.requests} | "
                f"Input: {usage.input_tokens:,} | "
                f"Output: {usage.output_tokens:,} | "
                f"Erros: {usage.errors} | "
                f"Latencia media: {avg_latency:.0f}ms"
            )
            total_in += usage.input_tokens
            total_out += usage.output_tokens
            total_req += usage.requests

        parts.append(f"\n**Total:** {total_req} requests | "
                    f"Input: {total_in:,} | Output: {total_out:,}")

        return "\n".join(parts)

    # ═══ ACTIVITY LOG ═══════════════════════════════════════════════

    def log_activity(self, event_type: str, details: str, success: bool = True):
        """Log an activity event."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "details": details[:500],
            "success": success,
        }
        self.activity_log.append(entry)
        self._save_data()

    def log_error(self, error: str, context: str = ""):
        """Log an error."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "error": error[:500],
            "context": context[:200],
        }
        self.error_log.append(entry)
        self._save_data()

    def get_recent_activity(self, count: int = 20) -> str:
        """Get recent activity formatted."""
        if not self.activity_log:
            return "Nenhuma atividade registrada."

        recent = self.activity_log[-count:]
        parts = [f"**Atividade Recente ({len(recent)} ultimas):**\n"]

        for entry in reversed(recent):
            ts = entry.get("timestamp", "")[:19]
            etype = entry.get("type", "?")
            details = entry.get("details", "")[:80]
            success = "OK" if entry.get("success", True) else "ERRO"
            parts.append(f"[{ts}] {etype}: {details} ({success})")

        return "\n".join(parts)

    def get_error_log(self, count: int = 10) -> str:
        """Get recent errors formatted."""
        if not self.error_log:
            return "Nenhum erro registrado. Tudo funcionando perfeitamente."

        recent = self.error_log[-count:]
        parts = [f"**Erros Recentes ({len(recent)}):**\n"]

        for entry in reversed(recent):
            ts = entry.get("timestamp", "")[:19]
            error = entry.get("error", "")[:100]
            context = entry.get("context", "")
            parts.append(f"[{ts}] {error}")
            if context:
                parts.append(f"  Contexto: {context}")

        return "\n".join(parts)

    # ═══ DASHBOARD SUMMARY ═══════════════════════════════════════════

    def get_dashboard_summary(self, memory=None) -> str:
        """Get complete dashboard summary."""
        parts = ["**Dashboard de Atividade do Elívea**\n"]

        # Token usage
        parts.append(self.get_token_summary())

        # Memory stats
        if memory:
            parts.append(f"\n**Memoria:**")
            parts.append(f"  Mensagens: {len(memory.chat_history)}")
            parts.append(f"  Fatos: {len(memory.facts)}")
            parts.append(f"  Resumos: {len(memory.summaries)}")
            parts.append(f"  Preferencias aprendidas: {len(memory.learned_preferences)}")

        # Recent activity
        parts.append(f"\n{self.get_recent_activity(5)}")

        # Errors
        if self.error_log:
            parts.append(f"\n{self.get_error_log(3)}")

        return "\n".join(parts)
