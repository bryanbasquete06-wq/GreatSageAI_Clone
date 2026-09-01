"""
Elívea — Token Usage Tracker & Cost-Savings Report
====================================================
Tracks daily token consumption per provider and generates
weekly cost-savings reports showing how much money free APIs saved.

Data stored in: config/smart_data/token_usage.jsonl
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple


# ── Cost Estimation ──────────────────────────────────────────────────────────
# Pricing per 1M tokens (USD) as of Aug 2026 — used to calculate savings
# Free tier cost = $0, paid equivalent = what you'd pay on the paid tier

PROVIDER_COST_PER_M_TOKENS = {
    # name: (input_cost_per_1M, output_cost_per_1M)
    # Free providers — we estimate what the PAID equivalent would cost
    "groq":        (0.05, 0.10),    # Groq paid: $0.05/$0.10 per 1M
    "gemini":      (0.075, 0.30),   # Gemini paid: $0.075/$0.30 per 1M
    "cerebras":    (0.10, 0.10),    # Cerebras: ~$0.10 per 1M
    "openrouter":  (0.15, 0.60),    # OpenRouter avg: $0.15/$0.60 per 1M
    "mistral":     (0.10, 0.30),    # Mistral paid: $0.10/$0.30 per 1M
    "nvidia_nim":  (0.20, 0.60),    # NVIDIA NIM: ~$0.20/$0.60 per 1M
    "cloudflare":  (0.01, 0.01),    # Cloudflare Workers AI: $0.01 per 1M
    "ovhcloud":    (0.10, 0.10),    # OVHcloud: ~$0.10 per 1M
    "siliconflow": (0.05, 0.10),    # SiliconFlow: ~$0.05/$0.10 per 1M
    "huggingface": (0.20, 0.60),    # HF Inference: $0.20/$0.60 per 1M
    "ollama":      (0.0, 0.0),      # Local — no cost at all
    "kilo_code":   (0.10, 0.30),    # Kilo Code: ~$0.10/$0.30 per 1M
}

# Average cost (blend of input/output) for quick estimation
PROVIDER_AVG_COST_PER_M = {
    name: (inp + out) / 2
    for name, (inp, out) in PROVIDER_COST_PER_M_TOKENS.items()
}

# Common paid alternatives for comparison
PAID_ALTERNATIVES = {
    "chat": {"name": "ChatGPT Plus", "cost_monthly": 20.0, "tokens_monthly": 2_000_000},
    "api":  {"name": "GPT-4o API", "cost_per_1m": 2.50},
    "code": {"name": "Claude Code", "cost_per_1m": 3.00},
}


# ── Tracker ──────────────────────────────────────────────────────────────────

class TokenTracker:
    """
    Tracks token usage per provider per day.

    Features:
      - Logs every request (provider, tokens, timestamp, estimated cost)
      - Daily aggregation per provider
      - Weekly cost-savings report (free vs paid comparison)
      - All-time totals
      - Thread-safe writes
    """

    def __init__(self, data_dir: str = "config/smart_data"):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = self._data_dir / "token_usage.jsonl"
        self._lock = Lock()
        self._cache: List[Dict[str, Any]] = []
        self._cache_loaded = False

    # ── Logging ──────────────────────────────────────────────────────────

    def record(
        self,
        provider: str,
        tokens: int,
        model: str = "",
        task_type: str = "chat",
        latency_ms: float = 0.0,
        success: bool = True,
    ):
        """Record a single token usage event."""
        now = time.time()
        cost_per_m = PROVIDER_AVG_COST_PER_M.get(provider, 0.10)
        estimated_cost = (tokens / 1_000_000) * cost_per_m

        entry = {
            "ts": datetime.now().isoformat(),
            "epoch": now,
            "provider": provider,
            "model": model,
            "tokens": tokens,
            "task_type": task_type,
            "latency_ms": round(latency_ms, 1),
            "success": success,
            "cost_usd": round(estimated_cost, 6),
        }

        with self._lock:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._cache.append(entry)

    # ── Data Loading ─────────────────────────────────────────────────────

    def _load_entries(self) -> List[Dict[str, Any]]:
        """Load all entries from JSONL log."""
        if self._cache_loaded:
            return self._cache

        entries = []
        if self._log_file.exists():
            with open(self._log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        self._cache = entries
        self._cache_loaded = True
        return entries

    def _entries_in_period(self, start: datetime, end: datetime) -> List[Dict]:
        """Filter entries within a time period."""
        entries = self._load_entries()
        result = []
        for e in entries:
            try:
                ts = e.get("epoch", 0)
                if start.timestamp() <= ts <= end.timestamp():
                    result.append(e)
            except (ValueError, TypeError):
                continue
        return result

    # ── Daily Aggregation ────────────────────────────────────────────────

    def get_daily_summary(self, days_back: int = 7) -> Dict[str, Any]:
        """Get daily token usage summary for the last N days."""
        now = datetime.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start = today - timedelta(days=days_back - 1)

        entries = self._entries_in_period(start, now)

        # Aggregate by day
        daily: Dict[str, Dict[str, Any]] = {}
        provider_totals: Dict[str, Dict[str, int]] = defaultdict(lambda: {"tokens": 0, "requests": 0, "cost": 0.0})

        for e in entries:
            try:
                day = e["ts"][:10]  # YYYY-MM-DD
            except (KeyError, IndexError):
                continue

            if day not in daily:
                daily[day] = {"tokens": 0, "requests": 0, "cost": 0.0, "providers": defaultdict(int)}

            daily[day]["tokens"] += e.get("tokens", 0)
            daily[day]["requests"] += 1
            daily[day]["cost"] += e.get("cost_usd", 0)
            daily[day]["providers"][e.get("provider", "unknown")] += e.get("tokens", 0)

            prov = e.get("provider", "unknown")
            provider_totals[prov]["tokens"] += e.get("tokens", 0)
            provider_totals[prov]["requests"] += 1
            provider_totals[prov]["cost"] += e.get("cost_usd", 0)

        # Convert defaultdicts to regular dicts for JSON
        for day_data in daily.values():
            day_data["providers"] = dict(day_data["providers"])

        return {
            "period": {
                "start": start.isoformat(),
                "end": now.isoformat(),
                "days": days_back,
            },
            "daily": dict(daily),
            "provider_totals": dict(provider_totals),
            "total_tokens": sum(d["tokens"] for d in daily.values()),
            "total_requests": sum(d["requests"] for d in daily.values()),
            "total_cost_usd": sum(d["cost"] for d in daily.values()),
        }

    # ── Weekly Cost-Savings Report ───────────────────────────────────────

    def get_weekly_savings_report(self, weeks_back: int = 1) -> Dict[str, Any]:
        """
        Generate a weekly cost-savings report.

        Compares what you USED (free APIs) vs what you'd PAY (ChatGPT Plus, GPT-4o API).
        """
        now = datetime.now()
        # Start of the reporting period (Monday of N weeks ago)
        days_back = weeks_back * 7
        start = (now - timedelta(days=days_back)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        # Align to Monday
        start -= timedelta(days=start.weekday())

        entries = self._entries_in_period(start, now)

        if not entries:
            return self._empty_savings_report(start, now)

        # Per-provider breakdown
        provider_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "tokens": 0, "requests": 0, "cost_usd": 0.0,
            "avg_latency_ms": 0.0, "success_count": 0, "fail_count": 0,
        })

        total_tokens = 0
        total_cost = 0.0
        total_latency = 0.0
        task_breakdown: Dict[str, int] = defaultdict(int)

        for e in entries:
            prov = e.get("provider", "unknown")
            tokens = e.get("tokens", 0)
            cost = e.get("cost_usd", 0)

            provider_stats[prov]["tokens"] += tokens
            provider_stats[prov]["requests"] += 1
            provider_stats[prov]["cost_usd"] += cost
            provider_stats[prov]["avg_latency_ms"] += e.get("latency_ms", 0)
            if e.get("success", True):
                provider_stats[prov]["success_count"] += 1
            else:
                provider_stats[prov]["fail_count"] += 1

            total_tokens += tokens
            total_cost += cost
            total_latency += e.get("latency_ms", 0)
            task_breakdown[e.get("task_type", "chat")] += 1

        # Calculate average latencies
        for prov, stats in provider_stats.items():
            if stats["requests"] > 0:
                stats["avg_latency_ms"] = round(stats["avg_latency_ms"] / stats["requests"], 1)

        # ── Cost comparison ──
        # What you'd pay on ChatGPT Plus ($20/mo for ~2M tokens)
        chatgpt_tokens_per_dollar = 2_000_000 / 20.0  # 100K tokens per dollar
        chatgpt_cost = total_tokens / chatgpt_tokens_per_dollar if total_tokens > 0 else 0

        # What you'd pay on GPT-4o API ($2.50/1M input + $10/1M output ≈ $6.25/1M avg)
        gpt4o_cost_per_m = 6.25
        gpt4o_cost = (total_tokens / 1_000_000) * gpt4o_cost_per_m if total_tokens > 0 else 0

        # What you'd pay on Claude ($3.00/1M input + $15/1M output ≈ $9.00/1M avg)
        claude_cost_per_m = 9.00
        claude_cost = (total_tokens / 1_000_000) * claude_cost_per_m if total_tokens > 0 else 0

        savings_vs_chatgpt = chatgpt_cost - total_cost
        savings_vs_gpt4o = gpt4o_cost - total_cost
        savings_vs_claude = claude_cost - total_cost

        return {
            "period": {
                "start": start.isoformat(),
                "end": now.isoformat(),
                "weeks": weeks_back,
            },
            "summary": {
                "total_tokens": total_tokens,
                "total_requests": len(entries),
                "total_cost_usd": round(total_cost, 4),
                "avg_latency_ms": round(total_latency / len(entries), 1) if entries else 0,
                "providers_used": len(provider_stats),
                "success_rate": f"{sum(s['success_count'] for s in provider_stats.values()) / len(entries) * 100:.1f}%",
            },
            "savings": {
                "vs_chatgpt_plus": {
                    "would_pay": round(chatgpt_cost, 2),
                    "actually_paid": round(total_cost, 4),
                    "saved": round(savings_vs_chatgpt, 2),
                },
                "vs_gpt4o_api": {
                    "would_pay": round(gpt4o_cost, 2),
                    "actually_paid": round(total_cost, 4),
                    "saved": round(savings_vs_gpt4o, 2),
                },
                "vs_claude_api": {
                    "would_pay": round(claude_cost, 2),
                    "actually_paid": round(total_cost, 4),
                    "saved": round(savings_vs_claude, 2),
                },
                "best_savings": round(max(savings_vs_chatgpt, savings_vs_gpt4o, savings_vs_claude), 2),
            },
            "providers": {
                name: {
                    "tokens": stats["tokens"],
                    "requests": stats["requests"],
                    "cost_usd": round(stats["cost_usd"], 4),
                    "avg_latency_ms": stats["avg_latency_ms"],
                    "success_rate": f"{stats['success_count'] / max(stats['requests'], 1) * 100:.0f}%",
                }
                for name, stats in sorted(
                    provider_stats.items(),
                    key=lambda x: x[1]["tokens"], reverse=True,
                )
            },
            "tasks": dict(task_breakdown),
        }

    def _empty_savings_report(self, start: datetime, end: datetime) -> Dict:
        """Empty report when no data is available."""
        return {
            "period": {"start": start.isoformat(), "end": end.isoformat()},
            "summary": {
                "total_tokens": 0, "total_requests": 0,
                "total_cost_usd": 0, "avg_latency_ms": 0,
                "providers_used": 0, "success_rate": "N/A",
            },
            "savings": {
                "vs_chatgpt_plus": {"would_pay": 0, "actually_paid": 0, "saved": 0},
                "vs_gpt4o_api": {"would_pay": 0, "actually_paid": 0, "saved": 0},
                "vs_claude_api": {"would_pay": 0, "actually_paid": 0, "saved": 0},
                "best_savings": 0,
            },
            "providers": {},
            "tasks": {},
        }

    # ── Text Report Formatting ───────────────────────────────────────────

    def format_usage_text(self, days: int = 7) -> str:
        """Format daily usage summary as readable text."""
        data = self.get_daily_summary(days)

        lines = [
            f"═══ 📊 Token Usage (últimos {days} dias) ═══",
            "",
            f"Total: {data['total_tokens']:,} tokens em {data['total_requests']} requests",
            f"Custo estimado (free): ${data['total_cost_usd']:.4f}",
            "",
            "── Uso Diário ──",
        ]

        for day in sorted(data["daily"].keys()):
            d = data["daily"][day]
            bar_len = min(30, d["tokens"] // max(data["total_tokens"], 1) * 30)
            bar = "█" * bar_len + "░" * (30 - bar_len)
            lines.append(f"  {day}: {bar} {d['tokens']:,} tok ({d['requests']} req)")

        lines.append("")
        lines.append("── Por Provider ──")
        for prov, stats in sorted(data["provider_totals"].items(), key=lambda x: x[1]["tokens"], reverse=True):
            pct = stats["tokens"] / max(data["total_tokens"], 1) * 100
            lines.append(
                f"  {prov:14s} {stats['tokens']:>10,} tok  "
                f"{stats['requests']:>4} req  "
                f"${stats['cost']:.4f}  "
                f"({pct:.0f}%)"
            )

        return "\n".join(lines)

    def format_savings_text(self, weeks: int = 1) -> str:
        """Format weekly savings report as readable text."""
        data = self.get_weekly_savings_report(weeks)

        if data["summary"]["total_tokens"] == 0:
            return (
                "═══ 💰 Cost Savings Report ═══\n\n"
                "Nenhum dado de uso registrado ainda.\n"
                "Use o Elívea normalmente e volte aqui\n"
                "na próxima semana para ver seus savings!"
            )

        s = data["summary"]
        sv = data["savings"]

        lines = [
            "═══ 💰 Cost Savings Report ═══",
            f"Período: {data['period']['start'][:10]} → {data['period']['end'][:10]}",
            "",
            f"📈 Uso Total:",
            f"  Tokens: {s['total_tokens']:,}",
            f"  Requests: {s['total_requests']}",
            f"  Providers ativos: {s['providers_used']}",
            f"  Latência média: {s['avg_latency_ms']:.0f}ms",
            f"  Taxa de sucesso: {s['success_rate']}",
            f"  Custo real (free): ${s['total_cost_usd']:.4f}",
            "",
            "═══ 💸 Quanto Você Economizou ═══",
            "",
        ]

        comparisons = [
            ("ChatGPT Plus ($20/mo)", sv["vs_chatgpt_plus"]),
            ("GPT-4o API ($6.25/1M)", sv["vs_gpt4o_api"]),
            ("Claude API ($9.00/1M)", sv["vs_claude_api"]),
        ]

        for label, comp in comparisons:
            saved = comp["saved"]
            would = comp["would_pay"]
            lines.append(f"  vs {label}:")
            lines.append(f"    Pagaria:     ${would:>8.2f}")
            lines.append(f"    Pagou:       ${comp['actually_paid']:>8.4f}")
            lines.append(f"    Economia:    ${saved:>8.2f} {'✅' if saved > 0 else '—'}")
            lines.append("")

        lines.append(f"🏆 Total economizado: ${sv['best_savings']:.2f}")

        # Provider breakdown
        if data["providers"]:
            lines.append("")
            lines.append("── Providers Utilizados ──")
            for name, stats in data["providers"].items():
                lines.append(
                    f"  {name:14s} {stats['tokens']:>10,} tok  "
                    f"${stats['cost_usd']:.4f}  "
                    f"L:{stats['avg_latency_ms']:.0f}ms  "
                    f"{stats['success_rate']}"
                )

        return "\n".join(lines)


# ── Global Instance ──────────────────────────────────────────────────────────

_tracker_instance: Optional[TokenTracker] = None
_tracker_lock = Lock()


def get_token_tracker() -> TokenTracker:
    """Get or create the global TokenTracker singleton."""
    global _tracker_instance
    if _tracker_instance is None:
        with _tracker_lock:
            if _tracker_instance is None:
                _tracker_instance = TokenTracker()
    return _tracker_instance
