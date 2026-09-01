"""
Elívea — Provider Health Monitor
==================================
Automatic health monitoring for all free API providers.

Features:
  - Tracks per-provider health: success rate, latency, error streaks
  - Auto-removes providers after N consecutive failures
  - Exponential backoff recovery (30s → 60s → 120s → 5min)
  - Circuit breaker pattern (open → half-open → closed)
  - All-down alerts with notification callbacks
  - Health score 0-100 per provider
  - History tracking for trend analysis
  - Thread-safe operations
"""
from __future__ import annotations

import json
import math
import time
from collections import defaultdict, deque
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, Tuple


# ── Constants ────────────────────────────────────────────────────────────────

# Circuit breaker states
class CircuitState(Enum):
    CLOSED = "closed"        # Normal operation
    HALF_OPEN = "half_open"  # Testing recovery
    OPEN = "open"            # Removed from rotation

# Configuration
MAX_CONSECUTIVE_ERRORS = 5       # Errors before circuit opens
HALF_OPEN_MAX_ATTEMPTS = 2       # Test attempts in half-open
HEALTH_WINDOW_SIZE = 50          # Last N requests to evaluate
HEALTH_CHECK_INTERVAL = 30       # Seconds between proactive health pings
MIN_HEALTH_SCORE = 30            # Below this → circuit opens
RECOVERY_BASE_DELAY = 30.0       # Base delay for exponential backoff (seconds)
RECOVERY_MAX_DELAY = 300.0       # Max backoff delay (5 minutes)
ALERT_COOLDOWN = 300.0           # Don't re-alert within 5 minutes
HISTORY_MAX_ENTRIES = 200        # Max health history entries per provider


# ── Provider Health Model ────────────────────────────────────────────────────

class ProviderHealth:
    """Tracks health state for a single provider."""

    __slots__ = (
        "name", "state", "consecutive_errors", "total_requests",
        "total_errors", "total_tokens", "recent_results",  # deque of (success, latency_ms, timestamp)
        "last_success", "last_error", "circuit_opened_at",
        "recovery_attempts", "current_backoff", "health_score",
        "avg_latency_ms", "success_rate", "last_health_check",
    )

    def __init__(self, name: str):
        self.name = name
        self.state = CircuitState.CLOSED
        self.consecutive_errors = 0
        self.total_requests = 0
        self.total_errors = 0
        self.total_tokens = 0
        self.recent_results: deque = deque(maxlen=HEALTH_WINDOW_SIZE)
        self.last_success = 0.0
        self.last_error = 0.0
        self.circuit_opened_at = 0.0
        self.recovery_attempts = 0
        self.current_backoff = RECOVERY_BASE_DELAY
        self.health_score = 100.0
        self.avg_latency_ms = 0.0
        self.success_rate = 1.0
        self.last_health_check = 0.0

    def record_success(self, latency_ms: float = 0.0, tokens: int = 0):
        """Record a successful request."""
        now = time.time()
        self.recent_results.append((True, latency_ms, now))
        self.total_requests += 1
        self.total_tokens += tokens
        self.consecutive_errors = 0
        self.last_success = now

        # If circuit was open/half-open, close it (recovery successful)
        if self.state != CircuitState.CLOSED:
            self.state = CircuitState.CLOSED
            self.recovery_attempts = 0
            self.current_backoff = RECOVERY_BASE_DELAY

        self._recalculate()

    def record_error(self, error_msg: str = ""):
        """Record a failed request."""
        now = time.time()
        self.recent_results.append((False, 0.0, now))
        self.total_requests += 1
        self.total_errors += 1
        self.consecutive_errors += 1
        self.last_error = now

        self._recalculate()

        # Open circuit if too many consecutive errors
        if self.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            self._open_circuit()

    def _open_circuit(self):
        """Open the circuit breaker — remove from rotation."""
        self.state = CircuitState.OPEN
        self.circuit_opened_at = time.time()
        self.recovery_attempts = 0
        self.current_backoff = RECOVERY_BASE_DELAY

    def _recalculate(self):
        """Recalculate health score from recent results."""
        if not self.recent_results:
            self.health_score = 100.0
            self.success_rate = 1.0
            self.avg_latency_ms = 0.0
            return

        successes = sum(1 for r in self.recent_results if r[0])
        self.success_rate = successes / len(self.recent_results)

        # Latency (only from successes)
        latencies = [r[1] for r in self.recent_results if r[0] and r[1] > 0]
        self.avg_latency_ms = sum(latencies) / len(latencies) if latencies else 0.0

        # Health score: 0-100
        # - Success rate: 0-60 points
        # - Latency penalty: 0-20 points (fast = full, slow = penalized)
        # - Consecutive errors: 0-20 points
        sr_score = self.success_rate * 60.0

        if self.avg_latency_ms > 0:
            # Perfect at <200ms, 0 at >5000ms
            latency_score = max(0, 20.0 * (1.0 - (self.avg_latency_ms - 200) / 4800))
        else:
            latency_score = 20.0

        error_penalty = min(20.0, self.consecutive_errors * 4.0)
        streak_bonus = 20.0 - error_penalty

        self.health_score = max(0.0, min(100.0, sr_score + latency_score + streak_bonus))

    def can_use(self) -> bool:
        """Check if this provider can be used for routing."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if enough time has passed for half-open test
            elapsed = time.time() - self.circuit_opened_at
            if elapsed >= self.current_backoff:
                self.state = CircuitState.HALF_OPEN
                return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            return True  # Allow limited test requests

        return False

    def record_recovery_attempt(self):
        """Record that a half-open test request was made."""
        if self.state == CircuitState.HALF_OPEN:
            self.recovery_attempts += 1
            # If too many attempts failed, reopen
            if self.recovery_attempts >= HALF_OPEN_MAX_ATTEMPTS:
                self._open_circuit()

    def get_status(self) -> Dict[str, Any]:
        """Get full status for display."""
        now = time.time()
        cooldown_remaining = 0.0
        if self.state == CircuitState.OPEN:
            elapsed = now - self.circuit_opened_at
            cooldown_remaining = max(0, self.current_backoff - elapsed)
        elif self.state == CircuitState.HALF_OPEN:
            cooldown_remaining = 0  # In testing phase

        return {
            "name": self.name,
            "state": self.state.value,
            "health_score": round(self.health_score, 1),
            "success_rate": f"{self.success_rate * 100:.1f}%",
            "avg_latency_ms": round(self.avg_latency_ms, 0),
            "consecutive_errors": self.consecutive_errors,
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "total_tokens": self.total_tokens,
            "recovery_attempts": self.recovery_attempts,
            "cooldown_seconds": round(cooldown_remaining, 1),
            "last_success_ago": self._time_ago(self.last_success),
            "last_error_ago": self._time_ago(self.last_error),
        }

    def _time_ago(self, ts: float) -> str:
        if ts == 0:
            return "never"
        diff = time.time() - ts
        if diff < 60:
            return f"{diff:.0f}s ago"
        elif diff < 3600:
            return f"{diff / 60:.0f}m ago"
        elif diff < 86400:
            return f"{diff / 3600:.1f}h ago"
        else:
            return f"{diff / 86400:.1f}d ago"


# ── Health Monitor ───────────────────────────────────────────────────────────

class ProviderHealthMonitor:
    """
    Monitors health of all providers with circuit breaker pattern.

    Lifecycle:
      1. Request succeeds → record_success() → health improves
      2. Request fails → record_error() → health degrades
      3. Consecutive errors ≥ 5 → circuit OPENS → provider removed
      4. After backoff delay → circuit HALF-OPEN → test request
      5. Test succeeds → circuit CLOSED → provider restored
      6. Test fails → circuit OPENS again with doubled backoff
    """

    def __init__(self, data_dir: str = "config/smart_data"):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._history_file = self._data_dir / "provider_health.json"
        self._lock = Lock()
        self._providers: Dict[str, ProviderHealth] = {}
        self._alert_callbacks: List[Callable[[str, Dict], None]] = []
        self._last_all_down_alert = 0.0
        self._alert_cooldown = ALERT_COOLDOWN
        self._all_down_alerted = False
        self._history: List[Dict] = []  # Global health history
        self._load_history()

    # ── Provider Registration ────────────────────────────────────────────

    def get_provider(self, name: str) -> ProviderHealth:
        """Get or create health tracker for a provider."""
        if name not in self._providers:
            with self._lock:
                if name not in self._providers:
                    self._providers[name] = ProviderHealth(name)
        return self._providers[name]

    def register_providers(self, names: List[str]):
        """Register all providers upfront."""
        for name in names:
            self.get_provider(name)

    # ── Recording ────────────────────────────────────────────────────────

    def record_success(self, provider: str, latency_ms: float = 0.0, tokens: int = 0):
        """Record a successful request."""
        health = self.get_provider(provider)
        health.record_success(latency_ms, tokens)
        self._check_all_down_recovery()

    def record_error(self, provider: str, error_msg: str = ""):
        """Record a failed request."""
        health = self.get_provider(provider)
        health.record_error(error_msg)

        # Check if provider just got removed
        if health.state == CircuitState.OPEN:
            logger.info(f"[HealthMonitor] Circuit OPENED for {provider} "
                       f"(consecutive errors: {health.consecutive_errors})")

        # Check if ALL providers are down
        self._check_all_down()

    # ── Circuit Breaker Queries ──────────────────────────────────────────

    def is_available(self, provider: str) -> bool:
        """Check if a provider is available for routing."""
        health = self.get_provider(provider)
        return health.can_use()

    def get_available_providers(self, all_names: List[str]) -> List[str]:
        """Filter provider names to only those currently available."""
        return [name for name in all_names if self.is_available(name)]

    def force_recover(self, provider: str):
        """Force a provider back into rotation (manual override)."""
        with self._lock:
            health = self.get_provider(provider)
            health.state = CircuitState.CLOSED
            health.consecutive_errors = 0
            health.recovery_attempts = 0
            health.current_backoff = RECOVERY_BASE_DELAY
            logger.info(f"[HealthMonitor] Force-recovered {provider}")

    def force_recover_all(self):
        """Force all providers back into rotation."""
        with self._lock:
            for health in self._providers.values():
                if health.state != CircuitState.CLOSED:
                    health.state = CircuitState.CLOSED
                    health.consecutive_errors = 0
                    health.recovery_attempts = 0
                    health.current_backoff = RECOVERY_BASE_DELAY
            self._all_down_alerted = False
            logger.info("[HealthMonitor] Force-recovered ALL providers")

    # ── All-Down Alert System ────────────────────────────────────────────

    def _check_all_down(self):
        """Check if all providers are down and fire alert."""
        with self._lock:
            available = [h for h in self._providers.values() if h.can_use()]
            if not available and self._providers:
                now = time.time()
                if not self._all_down_alerted or (now - self._last_all_down_alert > self._alert_cooldown):
                    self._all_down_alerted = True
                    self._last_all_down_alert = now
                    self._fire_alert("ALL_PROVIDERS_DOWN", {
                        "message": "Todos os providers estão indisponíveis!",
                        "providers": {h.name: h.state.value for h in self._providers.values()},
                    })

    def _check_all_down_recovery(self):
        """Check if we recovered from all-down state."""
        with self._lock:
            if self._all_down_alerted:
                available = [h for h in self._providers.values() if h.can_use()]
                if available:
                    self._all_down_alerted = False
                    self._fire_alert("PROVIDERS_RECOVERED", {
                        "message": f"Providers recuperados: {[h.name for h in available]}",
                        "count": len(available),
                    })

    def register_alert_callback(self, callback: Callable[[str, Dict], None]):
        """Register a callback for health alerts."""
        self._alert_callbacks.append(callback)

    def _fire_alert(self, alert_type: str, data: Dict):
        """Fire an alert to all registered callbacks."""
        data["type"] = alert_type
        data["timestamp"] = time.time()
        for cb in self._alert_callbacks:
            try:
                cb(alert_type, data)
            except Exception:
                pass
        # Also log to history
        self._history.append(data)
        if len(self._history) > 100:
            self._history = self._history[-100:]
        self._save_history()

    # ── Health Dashboard ─────────────────────────────────────────────────

    def get_all_status(self) -> Dict[str, Any]:
        """Get complete health status for all providers."""
        with self._lock:
            providers = {}
            closed = 0
            half_open = 0
            open_count = 0

            for name, health in sorted(self._providers.items()):
                status = health.get_status()
                providers[name] = status

                if health.state == CircuitState.CLOSED:
                    closed += 1
                elif health.state == CircuitState.HALF_OPEN:
                    half_open += 1
                else:
                    open_count += 1

            total = len(self._providers)
            avg_health = (
                sum(h.health_score for h in self._providers.values()) / total
                if total > 0 else 0
            )

            return {
                "total_providers": total,
                "healthy": closed,
                "testing": half_open,
                "down": open_count,
                "avg_health_score": round(avg_health, 1),
                "all_down": self._all_down_alerted,
                "providers": providers,
                "recent_alerts": self._history[-10:],
            }

    def format_health_text(self) -> str:
        """Format health status as readable text."""
        data = self.get_all_status()

        lines = [
            "═══ 🏥 Provider Health Monitor ═══",
            f"Total: {data['total_providers']} providers",
            f"Saudáveis: {data['healthy']} | Testando: {data['testing']} | Down: {data['down']}",
            f"Score médio: {data['avg_health_score']}/100",
            "",
        ]

        if data["all_down"]:
            lines.append("⚠️  ALERTA: TODOS OS PROVIDERS ESTÃO DOWN!")
            lines.append("")

        lines.append("── Detalhes por Provider ──")
        for name, info in data["providers"].items():
            state_icon = {
                "closed": "🟢",
                "half_open": "🟡",
                "open": "🔴",
            }.get(info["state"], "⚪")

            score = info["health_score"]
            score_color = "🟢" if score >= 70 else "🟡" if score >= 40 else "🔴"

            lines.append(
                f"  {state_icon} {name:14s} "
                f"Score: {score_color}{score:5.1f} "
                f"SR: {info['success_rate']:>5s} "
                f"L: {info['avg_latency_ms']:>5.0f}ms "
                f"Err: {info['consecutive_errors']}"
            )

            if info["state"] == "open":
                lines.append(
                    f"     ⏳ Recovery em {info['cooldown_seconds']:.0f}s "
                    f"(tentativa {info['recovery_attempts']})"
                )

        if data["recent_alerts"]:
            lines.append("")
            lines.append("── Alertas Recentes ──")
            for alert in data["recent_alerts"][-5:]:
                ts = time.strftime("%H:%M", time.localtime(alert.get("timestamp", 0)))
                lines.append(f"  [{ts}] {alert.get('type', '?')}: {alert.get('message', '?')}")

        return "\n".join(lines)

    # ── History Persistence ──────────────────────────────────────────────

    def _load_history(self):
        """Load health history from disk."""
        try:
            if self._history_file.exists():
                data = json.loads(self._history_file.read_text(encoding="utf-8"))
                self._history = data.get("alerts", [])
                # Restore provider states
                for name, state_data in data.get("providers", {}).items():
                    h = self.get_provider(name)
                    h.consecutive_errors = state_data.get("consecutive_errors", 0)
                    h.total_requests = state_data.get("total_requests", 0)
                    h.total_errors = state_data.get("total_errors", 0)
                    h.health_score = state_data.get("health_score", 100.0)
        except Exception:
            pass

    def _save_history(self):
        """Save health history to disk."""
        try:
            data = {
                "alerts": self._history[-100:],
                "providers": {
                    name: {
                        "consecutive_errors": h.consecutive_errors,
                        "total_requests": h.total_requests,
                        "total_errors": h.total_errors,
                        "health_score": h.health_score,
                    }
                    for name, h in self._providers.items()
                },
                "last_updated": time.time(),
            }
            self._history_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass


# ── Logging ──────────────────────────────────────────────────────────────────

import logging
logger = logging.getLogger("elvea.health_monitor")


# ── Global Instance ──────────────────────────────────────────────────────────

_monitor_instance: Optional[ProviderHealthMonitor] = None
_monitor_lock = Lock()


def get_health_monitor() -> ProviderHealthMonitor:
    """Get or create the global health monitor singleton."""
    global _monitor_instance
    if _monitor_instance is None:
        with _monitor_lock:
            if _monitor_instance is None:
                _monitor_instance = ProviderHealthMonitor()
    return _monitor_instance
