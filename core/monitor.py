#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elívea — Dashboard de Monitoramento
============================================
Graficos de uso, performance, estatisticas.
"""

import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field

logger = logging.getLogger("elvea.monitor")


@dataclass
class UsageEntry:
    timestamp: str
    provider: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0
    success: bool = True
    query_type: str = "chat"  # chat, command, voice, code


class Monitor:
    """Tracks and visualizes AI usage metrics."""

    def __init__(self, data_dir: str = "memory"):
        self.dir = Path(data_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.usage_file = self.dir / "usage_history.json"
        self.sessions_file = self.dir / "sessions.json"

        self.usage_history: List[Dict] = self._load_json(self.usage_file, [])
        self.sessions: List[Dict] = self._load_json(self.sessions_file, [])

        self._current_session_start = datetime.now().isoformat()
        self._session_queries = 0
        self._session_tokens = 0

    def _load_json(self, path: Path, default):
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return default

    def _save_json(self, path: Path, data):
        try:
            path.write_text(
                json.dumps(data[-1000:], indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"Error saving: {e}")

    def record_usage(self, provider: str, tokens_in: int = 0, tokens_out: int = 0,
                     latency_ms: float = 0, success: bool = True,
                     query_type: str = "chat"):
        """Record a usage entry."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "provider": provider,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "latency_ms": latency_ms,
            "success": success,
            "query_type": query_type,
        }
        self.usage_history.append(entry)
        self._session_queries += 1
        self._session_tokens += tokens_in + tokens_out

        self._save_json(self.usage_file, self.usage_history)

    def end_session(self):
        """End current session and save stats."""
        session = {
            "start": self._current_session_start,
            "end": datetime.now().isoformat(),
            "queries": self._session_queries,
            "tokens": self._session_tokens,
        }
        self.sessions.append(session)
        self._save_json(self.sessions_file, self.sessions)

        self._current_session_start = datetime.now().isoformat()
        self._session_queries = 0
        self._session_tokens = 0

    # ═══ STATS ═══════════════════════════════════════════════════════

    def get_session_stats(self) -> str:
        """Get current session statistics."""
        duration = (datetime.now() - datetime.fromisoformat(
            self._current_session_start)).total_seconds() / 60

        return (f"**Sessao Atual:**\n"
                f"  Duracao: {duration:.1f} minutos\n"
                f"  Consultas: {self._session_queries}\n"
                f"  Tokens: {self._session_tokens:,}")

    def get_daily_stats(self, days: int = 7) -> str:
        """Get usage stats for the last N days."""
        now = datetime.now()
        cutoff = now - timedelta(days=days)

        daily = {}
        for entry in self.usage_history:
            try:
                ts = datetime.fromisoformat(entry["timestamp"])
                if ts >= cutoff:
                    day = ts.strftime("%d/%m")
                    if day not in daily:
                        daily[day] = {"queries": 0, "tokens": 0, "errors": 0}
                    daily[day]["queries"] += 1
                    daily[day]["tokens"] += entry.get("tokens_in", 0) + entry.get("tokens_out", 0)
                    if not entry.get("success", True):
                        daily[day]["errors"] += 1
            except Exception:
                continue

        if not daily:
            return "Nenhum dado de uso nas ultimas 24 horas."

        parts = [f"**Uso Diario (ultimos {days} dias):**\n"]

        # Simple bar chart
        max_queries = max(d["queries"] for d in daily.values()) if daily else 1
        for day, stats in sorted(daily.items()):
            bar_len = int(20 * stats["queries"] / max(max_queries, 1))
            bar = "█" * bar_len + "░" * (20 - bar_len)
            parts.append(f"{day} |{bar}| {stats['queries']}q {stats['tokens']:,}t")

        return "\n".join(parts)

    def get_provider_stats(self) -> str:
        """Get stats per provider."""
        providers = {}
        for entry in self.usage_history:
            p = entry.get("provider", "unknown")
            if p not in providers:
                providers[p] = {"queries": 0, "tokens": 0, "latency": 0, "errors": 0}
            providers[p]["queries"] += 1
            providers[p]["tokens"] += entry.get("tokens_in", 0) + entry.get("tokens_out", 0)
            providers[p]["latency"] += entry.get("latency_ms", 0)
            if not entry.get("success", True):
                providers[p]["errors"] += 1

        if not providers:
            return "Nenhum dado de provider."

        parts = ["**Performance por Provider:**\n"]
        for p, stats in sorted(providers.items(), key=lambda x: x[1]["queries"], reverse=True):
            avg_lat = stats["latency"] / stats["queries"] if stats["queries"] > 0 else 0
            error_rate = (stats["errors"] / stats["queries"] * 100) if stats["queries"] > 0 else 0
            parts.append(
                f"**{p}:**\n"
                f"  Consultas: {stats['queries']} | "
                f"Tokens: {stats['tokens']:,} | "
                f"Latencia: {avg_lat:.0f}ms | "
                f"Erros: {error_rate:.1f}%"
            )

        return "\n".join(parts)

    def get_query_type_stats(self) -> str:
        """Get stats by query type."""
        types = {}
        for entry in self.usage_history:
            qt = entry.get("query_type", "chat")
            if qt not in types:
                types[qt] = 0
            types[qt] += 1

        if not types:
            return "Nenhum dado."

        parts = ["**Tipos de Consulta:**\n"]
        total = sum(types.values())
        for qt, count in sorted(types.items(), key=lambda x: x[1], reverse=True):
            pct = count / total * 100
            bar_len = int(15 * count / max(types.values()))
            bar = "█" * bar_len
            parts.append(f"  {qt:12s} {bar} {count} ({pct:.0f}%)")

        return "\n".join(parts)

    def get_full_dashboard(self) -> str:
        """Get complete dashboard with all metrics."""
        parts = ["**Dashboard de Monitoramento**\n"]

        parts.append(self.get_session_stats())
        parts.append("")
        parts.append(self.get_daily_stats(7))
        parts.append("")
        parts.append(self.get_provider_stats())
        parts.append("")
        parts.append(self.get_query_type_stats())

        # Total stats
        total_queries = len(self.usage_history)
        total_tokens = sum(
            e.get("tokens_in", 0) + e.get("tokens_out", 0)
            for e in self.usage_history
        )
        total_sessions = len(self.sessions)

        parts.append(f"\n**Totais Gerais:**")
        parts.append(f"  Consultas: {total_queries:,}")
        parts.append(f"  Tokens: {total_tokens:,}")
        parts.append(f"  Sessoes: {total_sessions}")

        return "\n".join(parts)
