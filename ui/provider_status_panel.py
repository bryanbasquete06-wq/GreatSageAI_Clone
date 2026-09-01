"""
Elívea — Real-Time Provider Status Panel
=========================================
Displays live status of all free API providers with:
  - Green/yellow/red health indicators per provider
  - Animated token usage progress bars
  - RPM/RPD metrics with capacity warnings
  - Combined capacity summary header
  - Auto-refresh every 5 seconds

100% PySide6/Qt custom paint — matches holographic dark/gold theme.
"""
from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, pyqtSignal
    from PySide6.QtGui import (
        QPainter, QPen, QBrush, QColor, QFont, QRadialGradient,
        QLinearGradient, QPainterPath,
    )
    from PySide6.QtWidgets import QWidget, QFrame, QSizePolicy
except ImportError:
    from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, pyqtSignal
    from PyQt6.QtGui import (
        QPainter, QPen, QBrush, QColor, QFont, QRadialGradient,
        QLinearGradient, QPainterPath,
    )
    from PyQt6.QtWidgets import QWidget, QFrame, QSizePolicy


# ── Theme Constants ──────────────────────────────────────────────────────────

BG = "#0a0a0a"
PANEL = "#111111"
BORDER_DIM = "#1a1a1a"
GOLD = "#FFD700"
GOLD_DIM = "#b8960f"
GOLD_BRIGHT = "#ffe44d"
TEXT = "#ffffff"
TEXT_DIM = "#666666"
TEXT_MED = "#999999"
GREEN = "#4ade80"
GREEN_DIM = "#22633e"
YELLOW = "#facc15"
YELLOW_DIM = "#635209"
RED = "#f87171"
RED_DIM = "#631f1f"
CYAN = "#00e5ff"
PANEL_GLOW = "#1a1700"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _alpha(color: str, a: int) -> QColor:
    c = QColor(color)
    c.setAlpha(a)
    return c


def _font(size: int, bold: bool = True, mono: bool = True) -> QFont:
    name = "Consolas" if mono else "Segoe UI"
    return QFont(name, size, QFont.Weight.Bold if bold else QFont.Weight.Normal)


def _health_color(available: bool, error_rate: float) -> str:
    """Determine indicator color: green/yellow/red."""
    if not available:
        return RED
    if error_rate >= 0.5:
        return RED
    if error_rate >= 0.2:
        return YELLOW
    return GREEN


def _usage_color(pct: float) -> str:
    """Color for usage bar based on percentage."""
    if pct >= 0.85:
        return RED
    if pct >= 0.55:
        return YELLOW
    return GREEN


def _lerp_color(a: str, b: str, t: float) -> str:
    """Linearly interpolate between two hex colors."""
    ca, cb = QColor(a), QColor(b)
    r = int(ca.red() + (cb.red() - ca.red()) * t)
    g = int(ca.green() + (cb.green() - ca.green()) * t)
    bl = int(ca.blue() + (cb.blue() - ca.blue()) * t)
    return f"#{r:02x}{g:02x}{bl:02x}"


# ── Provider Data Model ─────────────────────────────────────────────────────

class _ProviderRow:
    """Internal model for a single provider's display state."""
    __slots__ = (
        "name", "tier", "available", "quality", "rpm_limit", "rpd_limit",
        "requests_today", "total_tokens", "avg_latency", "error_rate",
        "context_window", "usage_rpm", "usage_rpd", "health_color",
        "_smooth_rpm", "_smooth_rpd", "_pulse_t",
    )

    def __init__(self):
        self.name: str = ""
        self.tier: str = ""
        self.available: bool = False
        self.quality: str = "0%"
        self.rpm_limit: int = 0
        self.rpd_limit: int = 0
        self.requests_today: int = 0
        self.total_tokens: int = 0
        self.avg_latency: str = "0ms"
        self.error_rate: str = "0%"
        self.context_window: str = "0"
        self.usage_rpm: float = 0.0
        self.usage_rpd: float = 0.0
        self.health_color: str = RED
        self._smooth_rpm: float = 0.0
        self._smooth_rpd: float = 0.0
        self._pulse_t: float = 0.0

    def update_from_dict(self, data: Dict[str, Any], name: str):
        """Update from router status dict entry."""
        self.name = name
        self.tier = data.get("tier", "")
        self.available = data.get("available", False)
        self.quality = data.get("quality", "0%")
        self.rpm_limit = data.get("rpm_limit", 0)
        self.rpd_limit = data.get("rpd_limit", 0)
        self.requests_today = data.get("requests_today", 0)
        self.total_tokens = data.get("total_tokens", 0)
        self.avg_latency = data.get("avg_latency", "0ms")
        self.error_rate = data.get("error_rate", "0%")
        self.context_window = data.get("context_window", "0")

        # Calculate usage percentages
        self.usage_rpm = (self.requests_today / max(self.rpm_limit, 1)) if self.rpm_limit > 0 else 0.0
        self.usage_rpd = (self.requests_today / max(self.rpd_limit, 1)) if self.rpd_limit > 0 else 0.0

        # Parse error rate for health color
        try:
            er = float(self.error_rate.rstrip("%")) / 100.0
        except (ValueError, AttributeError):
            er = 0.0
        self.health_color = _health_color(self.available, er)

    def animate(self, dt: float):
        """Smooth animated transitions for bars."""
        target_rpm = min(self.usage_rpm, 1.0)
        target_rpd = min(self.usage_rpd, 1.0)
        speed = 0.12
        self._smooth_rpm += (target_rpm - self._smooth_rpm) * speed
        self._smooth_rpd += (target_rpd - self._smooth_rpd) * speed
        if self.available:
            self._pulse_t += dt * 2.5


# ── Main Widget ──────────────────────────────────────────────────────────────

class ProviderStatusPanel(QFrame):
    """
    Real-time provider status panel for the right sidebar.

    Features:
      - Green/yellow/red health dot per provider
      - Animated horizontal usage bars (RPM + RPD)
      - Combined capacity summary at top
      - Auto-refresh every 5 seconds from MultiProviderRouter
      - Smooth animated transitions
      - Pulse animation on active providers
    """

    sig_detail_requested = pyqtSignal(str)  # emits provider name on click

    # Tier display config: (icon, label, sort_order)
    TIER_CONFIG = {
        "BLAZING": ("⚡", "BLZ"),
        "FAST":    ("🔹", "FST"),
        "BASIC":   ("◇", "BSC"),
        "LOCAL":   ("🏠", "LOC"),
    }

    # Provider display names (friendly)
    DISPLAY_NAMES = {
        "groq":       "Groq",
        "gemini":     "Gemini",
        "cerebras":   "Cerebras",
        "openrouter": "OpenRouter",
        "mistral":    "Mistral",
        "nvidia_nim": "NVIDIA NIM",
        "cloudflare": "Cloudflare",
        "ovhcloud":   "OVHcloud",
        "siliconflow":"SiliconFlow",
        "huggingface":"HuggingFace",
        "ollama":     "Ollama (local)",
        "kilo_code":  "Kilo Code",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ProviderStatusPanel")
        self.setMinimumHeight(320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setStyleSheet(f"""
            QFrame#ProviderStatusPanel {{
                background: rgba(10,10,10,220);
                border: 1px solid rgba(255,215,0,25);
                border-radius: 12px;
            }}
        """)

        # Data
        self._providers: List[_ProviderRow] = []
        self._capacity: Dict[str, str] = {}
        self._total_requests: int = 0
        self._total_tokens: int = 0
        self._available_count: int = 0
        self._total_count: int = 0
        self._last_update: float = 0.0
        self._animation_t: float = 0.0
        self._last_tick: float = time.time()
        self._hover_idx: int = -1

        # Auto-refresh timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(5000)  # 5 seconds
        self._refresh()

    # ── Data Refresh ─────────────────────────────────────────────────────

    def _refresh(self):
        """Pull status from the MultiProviderRouter singleton."""
        try:
            from core.multi_provider_router import get_router
            router = get_router()
            status = router.get_status()
            self._update_from_status(status)
        except Exception:
            # Graceful degradation — show empty state
            pass

    def _update_from_status(self, status: Dict[str, Any]):
        """Parse router status dict into display rows."""
        self._total_count = status.get("total_providers", 0)
        self._available_count = status.get("available_providers", 0)
        self._total_requests = status.get("total_requests_today", 0)
        self._total_tokens = status.get("total_tokens_today", 0)
        self._capacity = status.get("capacity", {})

        providers_data = status.get("providers", {})

        # Merge with existing rows to preserve smooth animation state
        existing = {row.name: row for row in self._providers}
        new_rows = []
        for name, data in providers_data.items():
            if name in existing:
                row = existing[name]
                row.update_from_dict(data, name)
            else:
                row = _ProviderRow()
                row.update_from_dict(data, name)
            new_rows.append(row)

        # Sort: available first, then by tier priority
        tier_order = {"BLAZING": 0, "FAST": 1, "BASIC": 2, "LOCAL": 3}
        new_rows.sort(key=lambda r: (
            0 if r.available else 1,
            tier_order.get(r.tier, 9),
            r.name,
        ))

        self._providers = new_rows
        self._last_update = time.time()
        self.update()

    # ── Animation ────────────────────────────────────────────────────────

    def _tick(self):
        """Called by paintEvent to advance animations."""
        now = time.time()
        dt = now - self._last_tick
        self._last_tick = now
        self._animation_t += dt
        for row in self._providers:
            row.animate(dt)

    # ── Mouse Interaction ────────────────────────────────────────────────

    def mouseMoveEvent(self, event):
        y = event.position().y() if hasattr(event, 'position') else event.y()
        idx = self._hit_test(y)
        if idx != self._hover_idx:
            self._hover_idx = idx
            self.update()

    def mousePressEvent(self, event):
        y = event.position().y() if hasattr(event, 'position') else event.y()
        idx = self._hit_test(y)
        if idx >= 0 and idx < len(self._providers):
            self.sig_detail_requested.emit(self._providers[idx].name)

    def leaveEvent(self, event):
        self._hover_idx = -1
        self.update()

    def _hit_test(self, y: float) -> int:
        """Return provider index at y coordinate, or -1."""
        header_h = 72  # summary header height
        row_h = 48     # per-provider row height
        start_y = header_h + 8
        if y < start_y:
            return -1
        idx = int((y - start_y) / row_h)
        if 0 <= idx < len(self._providers):
            return idx
        return -1

    # ── Paint ────────────────────────────────────────────────────────────

    def paintEvent(self, _):
        self._tick()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W = self.width()
        H = self.height()

        # ── Background ──
        p.fillRect(0, 0, W, H, _alpha(PANEL, 200))

        # ── Header: Title + Combined Capacity ──
        self._paint_header(p, W)

        # ── Provider Rows ──
        header_h = 72
        row_h = 48
        y = header_h + 8

        for i, row in enumerate(self._providers):
            if y + row_h > H:
                break
            is_hover = (i == self._hover_idx)
            self._paint_provider_row(p, 8, y, W - 16, row_h, row, is_hover)
            y += row_h

        # ── Empty state ──
        if not self._providers:
            p.setFont(_font(9, bold=False))
            p.setPen(QPen(_alpha(TEXT_DIM, 150)))
            p.drawText(
                QRectF(0, header_h + 30, W, 30),
                Qt.AlignmentFlag.AlignCenter,
                "Aguardando dados dos providers...",
            )

    def _paint_header(self, p: QPainter, W: int):
        """Paint the header with title and combined capacity."""
        # Title bar with subtle gradient
        title_grad = QLinearGradient(0, 0, W, 0)
        title_grad.setColorAt(0.0, _alpha(GOLD, 25))
        title_grad.setColorAt(0.5, _alpha(GOLD, 8))
        title_grad.setColorAt(1.0, _alpha(GOLD, 25))
        p.fillRect(0, 0, W, 32, QBrush(title_grad))

        # Title
        p.setFont(_font(9))
        p.setPen(QPen(_alpha(GOLD, 220)))
        p.drawText(QRectF(10, 6, W - 20, 14), Qt.AlignmentFlag.AlignLeft, "🌐 Providers")

        # Status badge
        status_text = f"{self._available_count}/{self._total_count}"
        status_color = GREEN if self._available_count > 0 else RED
        badge_x = W - 52
        p.setBrush(QBrush(_alpha(status_color, 40)))
        p.setPen(QPen(_alpha(status_color, 120), 1))
        p.drawRoundedRect(QRectF(badge_x, 5, 42, 16), 8, 8)
        p.setFont(_font(7))
        p.setPen(QPen(_alpha(status_color, 220)))
        p.drawText(QRectF(badge_x, 5, 42, 16), Qt.AlignmentFlag.AlignCenter, status_text)

        # Capacity summary row
        y_sum = 34
        p.setFont(_font(7, bold=False))
        p.setPen(QPen(_alpha(TEXT_DIM, 140)))

        cap_parts = []
        if self._capacity:
            rpm = self._capacity.get("combined_rpm", "~0")
            rpd = self._capacity.get("combined_rpd", "~0")
            tpd = self._capacity.get("combined_tpd", "~0")
            cap_parts = [
                f"RPM: {rpm}",
                f"RPD: {rpd}",
                f"TPD: {tpd}",
            ]

        if self._total_tokens > 0:
            cap_parts.append(f"Tokens: {self._total_tokens:,}")

        cap_text = "  │  ".join(cap_parts) if cap_parts else "Sem dados de capacidade"
        p.drawText(QRectF(10, y_sum, W - 20, 12), Qt.AlignmentFlag.AlignLeft, cap_text)

        # Separator line
        p.setPen(QPen(_alpha(GOLD_DIM, 40), 1))
        p.drawLine(10, 68, W - 10, 68)

    def _paint_provider_row(self, p: QPainter, x: int, y: int, w: int, h: int,
                             row: _ProviderRow, is_hover: bool):
        """Paint a single provider row with health dot, name, bars, metrics."""
        # Hover background
        if is_hover:
            p.fillRect(x, y, w, h, _alpha(GOLD, 12))

        # ── Health indicator dot ──
        dot_x = x + 10
        dot_y = y + h // 2
        dot_r = 5

        # Outer glow pulse for active providers
        if row.available:
            pulse = (math.sin(row._pulse_t) * 0.3 + 0.7)
            glow_r = dot_r + 4
            p.setBrush(QBrush(_alpha(row.health_color, int(25 * pulse))))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(dot_x, dot_y), glow_r, glow_r)

        # Solid dot
        p.setBrush(QBrush(_alpha(row.health_color, 230)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(dot_x, dot_y), dot_r, dot_r)

        # ── Provider name + tier ──
        name_x = dot_x + 14
        display_name = self.DISPLAY_NAMES.get(row.name, row.name.title())
        tier_icon, tier_label = self.TIER_CONFIG.get(row.tier, ("◇", row.tier[:3]))

        p.setFont(_font(8))
        p.setPen(QPen(_alpha(TEXT, 220)))
        p.drawText(
            QRectF(name_x, y + 2, 130, 14),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            display_name,
        )

        # Tier badge
        tier_x = name_x + p.fontMetrics().horizontalAdvance(display_name) + 6
        tier_color = {
            "BLAZING": GOLD_BRIGHT,
            "FAST": CYAN,
            "BASIC": TEXT_MED,
            "LOCAL": TEXT_DIM,
        }.get(row.tier, TEXT_DIM)
        p.setFont(_font(6))
        p.setPen(QPen(_alpha(tier_color, 180)))
        p.drawText(
            QRectF(tier_x, y + 3, 40, 12),
            Qt.AlignmentFlag.AlignLeft,
            f"{tier_icon}{tier_label}",
        )

        # ── Quality badge ──
        p.setFont(_font(7, bold=False))
        p.setPen(QPen(_alpha(TEXT_DIM, 130)))
        p.drawText(
            QRectF(name_x, y + 17, 130, 10),
            Qt.AlignmentFlag.AlignLeft,
            f"Q:{row.quality}  L:{row.avg_latency}  E:{row.error_rate}",
        )

        # ── Usage bars (right side) ──
        bar_x = x + w - 130
        bar_w = 120
        bar_h = 6
        bar_spacing = 12

        # RPM bar
        rpm_pct = min(row._smooth_rpm, 1.0)
        self._paint_usage_bar(p, bar_x, y + 6, bar_w, bar_h, rpm_pct,
                              f"RPM {row.requests_today}/{row.rpm_limit}")

        # RPD bar (only if limit > 0)
        if row.rpd_limit > 0:
            rpd_pct = min(row._smooth_rpd, 1.0)
            self._paint_usage_bar(p, bar_x, y + 6 + bar_spacing + 6, bar_w, bar_h,
                                  rpd_pct, f"RPD {row.requests_today}/{row.rpd_limit}")
        else:
            # Show token count instead
            p.setFont(_font(6, bold=False))
            p.setPen(QPen(_alpha(TEXT_DIM, 120)))
            p.drawText(
                QRectF(bar_x, y + 6 + bar_spacing + 2, bar_w, 10),
                Qt.AlignmentFlag.AlignLeft,
                f"Tokens: {row.total_tokens:,}",
            )

    def _paint_usage_bar(self, p: QPainter, x: int, y: int, w: int, h: int,
                          pct: float, label: str):
        """Paint an animated usage bar with label and glow."""
        # Background track
        p.setBrush(QBrush(_alpha(BORDER_DIM, 120)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(x, y, w, h), 3, 3)

        # Usage fill
        fill_w = max(2, w * pct)
        bar_color = _usage_color(pct)

        # Glow behind the fill
        glow_grad = QLinearGradient(x, y - 4, x, y + h + 4)
        glow_grad.setColorAt(0.0, _alpha(bar_color, 0))
        glow_grad.setColorAt(0.5, _alpha(bar_color, int(30 * pct)))
        glow_grad.setColorAt(1.0, _alpha(bar_color, 0))
        p.setBrush(QBrush(glow_grad))
        p.drawRoundedRect(QRectF(x, y - 4, fill_w, h + 8), 3, 3)

        # Main fill bar
        bar_grad = QLinearGradient(x, y, x + fill_w, y)
        bar_grad.setColorAt(0.0, _alpha(bar_color, 160))
        bar_grad.setColorAt(1.0, _alpha(bar_color, 220))
        p.setBrush(QBrush(bar_grad))
        p.drawRoundedRect(QRectF(x, y, fill_w, h), 3, 3)

        # Highlight line on top of bar
        if fill_w > 4:
            p.setPen(QPen(_alpha(bar_color, 100), 1))
            p.drawLine(int(x + 1), y + 1, int(x + fill_w - 1), y + 1)

        # Label below bar
        p.setFont(_font(5, bold=False))
        p.setPen(QPen(_alpha(TEXT_DIM, 120)))
        pct_val = int(pct * 100)
        p.drawText(
            QRectF(x, y + h + 1, w, 8),
            Qt.AlignmentFlag.AlignLeft,
            f"{label} ({pct_val}%)",
        )
