"""
Elívea — Health Dashboard Page
================================
Unified view showing:
  • All provider statuses with live health indicators
  • Token usage per provider with sparkline charts
  • System metrics (CPU, RAM, disk, FPS)
  • Audit log integrity status
  • Database health + backup status
  • Weekly cost-savings report

100% PySide6/Qt — matches Direction B Rune Keeper theme.
"""
from __future__ import annotations

import json
import math
import os
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil

try:
    from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, Signal as pyqtSignal
    from PySide6.QtGui import (
        QPainter, QPen, QBrush, QColor, QFont, QRadialGradient,
        QLinearGradient, QPainterPath,
    )
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
        QSizePolicy, QFrame, QGridLayout,
    )
except ImportError:
    from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, pyqtSignal
    from PyQt6.QtGui import (
        QPainter, QPen, QBrush, QColor, QFont, QRadialGradient,
        QLinearGradient, QPainterPath,
    )
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
        QSizePolicy, QFrame, QGridLayout,
    )

from ui.qt_ui import C


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _alpha(color: str, a: int) -> QColor:
    c = QColor(color)
    c.setAlpha(max(0, min(255, a)))
    return c


def _font(size: int, bold: bool = True, mono: bool = True) -> QFont:
    name = "Consolas" if mono else "Segoe UI"
    return QFont(name, size, QFont.Weight.Bold if bold else QFont.Weight.Normal)


def _hex_to_rgb(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"{r},{g},{b}"
    return "128,128,128"


# ═══════════════════════════════════════════════════════════════════════════
# Provider Status Card
# ═══════════════════════════════════════════════════════════════════════════

class _ProviderCard(QWidget):
    """Single provider card with health indicator, usage bar, latency."""

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self._name = name
        self._available = False
        self._latency_ms = 0.0
        self._error_rate = 0.0
        self._tokens_today = 0
        self._tokens_limit = 14400
        self._requests_today = 0
        self._sparkline: deque = deque([0.0] * 30, maxlen=30)
        self._health_color = "#ff4d6d"
        self._t = 0.0
        self.setFixedHeight(72)
        self.setMinimumWidth(200)

    def update_data(self, available: bool, latency_ms: float, error_rate: float,
                    tokens_today: int, tokens_limit: int, requests_today: int):
        self._available = available
        self._latency_ms = latency_ms
        self._error_rate = error_rate
        self._tokens_today = tokens_today
        self._tokens_limit = max(1, tokens_limit)
        self._requests_today = requests_today
        self._sparkline.append(latency_ms)

        if not available:
            self._health_color = "#ff4d6d"
        elif error_rate >= 0.5:
            self._health_color = "#ff4d6d"
        elif error_rate >= 0.2:
            self._health_color = "#facc15"
        else:
            self._health_color = "#4ade80"
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Card background
        p.setBrush(QBrush(_alpha(C.PANEL2 if hasattr(C, 'PANEL2') else C.PANEL, 200)))
        p.setPen(QPen(_alpha(C.BORDER, 80), 1))
        p.drawRoundedRect(QRectF(0, 0, W - 1, H - 1), 6, 6)

        # Health indicator dot
        dot_r = 4
        p.setBrush(QBrush(QColor(self._health_color)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(16, 16), dot_r, dot_r)

        # Provider name
        p.setFont(_font(10))
        p.setPen(QPen(QColor(C.TEXT if hasattr(C, 'TEXT') else "#E8E0D0"), 200))
        p.drawText(QRectF(28, 4, 120, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   self._name.upper())

        # Status text
        status = "ONLINE" if self._available else "OFFLINE"
        status_color = self._health_color
        p.setFont(_font(7, bold=True))
        p.setPen(QPen(QColor(status_color), 180))
        p.drawText(QRectF(W - 80, 4, 70, 18), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   f"● {status}")

        # Latency
        text_color = C.TEXT_DIM if hasattr(C, 'TEXT_DIM') else "#6B6358"
        p.setFont(_font(7, bold=False))
        p.setPen(QPen(QColor(text_color), 150))
        p.drawText(QRectF(16, 24, 140, 14),
                   f"{self._latency_ms:.0f}ms  ·  {self._requests_today} req")

        # Token usage bar
        bar_y = 42
        bar_h = 6
        bar_x = 16
        bar_w = W - 32
        pct = min(1.0, self._tokens_today / self._tokens_limit)

        # Bar background
        p.setBrush(QBrush(_alpha(C.BG if hasattr(C, 'BG') else "#020204", 180)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 3, 3)

        # Bar fill
        if pct > 0:
            fill_w = max(4, bar_w * pct)
            if pct >= 0.9:
                bar_col = "#ff4d6d"
            elif pct >= 0.7:
                bar_col = "#facc15"
            else:
                bar_col = self._health_color
            p.setBrush(QBrush(QColor(bar_col)))
            p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 3, 3)

        # Token count
        p.setFont(_font(7, bold=False))
        p.setPen(QPen(QColor(text_color), 140))
        p.drawText(QRectF(16, 52, W - 32, 14),
                   f"{self._tokens_today:,} / {self._tokens_limit:,} tokens  ({pct * 100:.0f}%)")

        # Sparkline (latency history)
        if len(self._sparkline) > 1:
            spark_x = W - 80
            spark_w = 65
            spark_y = 24
            spark_h = 14
            max_val = max(1.0, max(self._sparkline))
            pts = []
            for i, val in enumerate(self._sparkline):
                x = spark_x + (i / (len(self._sparkline) - 1)) * spark_w
                y = spark_y + spark_h - (val / max_val) * spark_h
                pts.append(QPointF(x, y))
            if len(pts) >= 2:
                path = QPainterPath()
                path.moveTo(pts[0])
                for pt in pts[1:]:
                    path.lineTo(pt)
                p.setPen(QPen(_alpha(self._health_color, 120), 1.2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(path)

        p.end()


# ═══════════════════════════════════════════════════════════════════════════
# System Metric Card
# ═══════════════════════════════════════════════════════════════════════════

class _SystemMetricCard(QWidget):
    """Single system metric (CPU/RAM/Disk) with arc gauge."""

    def __init__(self, label: str, icon: str, parent=None):
        super().__init__(parent)
        self._label = label
        self._icon = icon
        self._value = 0.0
        self._text = "--"
        self._color = "#C9A84C"
        self._history: deque = deque([0.0] * 40, maxlen=40)
        self.setFixedHeight(80)

    def update_value(self, pct: float, text: str, color: str = "#C9A84C"):
        self._value = max(0.0, min(100.0, pct))
        self._text = text
        self._color = color
        self._history.append(pct)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Card background
        p.setBrush(QBrush(_alpha(C.PANEL2 if hasattr(C, 'PANEL2') else C.PANEL, 200)))
        p.setPen(QPen(_alpha(C.BORDER, 60), 1))
        p.drawRoundedRect(QRectF(0, 0, W - 1, H - 1), 6, 6)

        # Arc gauge (left side)
        gauge_r = 24
        gauge_cx = 32
        gauge_cy = H // 2
        start_angle = 220 * 16
        span_angle = -280 * 16

        # Background arc
        p.setPen(QPen(_alpha(self._color, 30), 4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(gauge_cx - gauge_r, gauge_cy - gauge_r, gauge_r * 2, gauge_r * 2),
                  start_angle, span_angle)

        # Value arc
        val_span = int(span_angle * self._value / 100)
        p.setPen(QPen(QColor(self._color), 4))
        p.drawArc(QRectF(gauge_cx - gauge_r, gauge_cy - gauge_r, gauge_r * 2, gauge_r * 2),
                  start_angle, val_span)

        # Percentage in arc center
        p.setFont(_font(9))
        p.setPen(QPen(QColor(self._color), 220))
        p.drawText(QRectF(gauge_cx - gauge_r, gauge_cy - 10, gauge_r * 2, 20),
                   Qt.AlignmentFlag.AlignCenter, f"{self._value:.0f}%")

        # Label
        text_color = C.TEXT if hasattr(C, 'TEXT') else "#E8E0D0"
        dim_color = C.TEXT_DIM if hasattr(C, 'TEXT_DIM') else "#6B6358"
        p.setFont(_font(9))
        p.setPen(QPen(QColor(text_color), 200))
        p.drawText(QRectF(68, 6, 120, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"{self._icon} {self._label}")

        # Value text
        p.setFont(_font(8, bold=False))
        p.setPen(QPen(QColor(dim_color), 160))
        p.drawText(QRectF(68, 24, 120, 14),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   self._text)

        # Mini sparkline (right side)
        if len(self._history) > 1:
            spark_x = W - 80
            spark_w = 70
            spark_y = 10
            spark_h = H - 20
            max_val = max(1.0, max(self._history))
            pts = []
            for i, val in enumerate(self._history):
                x = spark_x + (i / (len(self._history) - 1)) * spark_w
                y = spark_y + spark_h - (val / max_val) * spark_h
                pts.append(QPointF(x, y))
            if len(pts) >= 2:
                # Fill under sparkline
                fill_path = QPainterPath()
                fill_path.moveTo(pts[0])
                for pt in pts[1:]:
                    fill_path.lineTo(pt)
                fill_path.lineTo(pts[-1].x(), spark_y + spark_h)
                fill_path.lineTo(pts[0].x(), spark_y + spark_h)
                fill_path.closeSubpath()
                fill_grad = QLinearGradient(0, spark_y, 0, spark_y + spark_h)
                fill_grad.setColorAt(0.0, _alpha(self._color, 40))
                fill_grad.setColorAt(1.0, _alpha(self._color, 0))
                p.setBrush(QBrush(fill_grad))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawPath(fill_path)

                # Line on top
                line_path = QPainterPath()
                line_path.moveTo(pts[0])
                for pt in pts[1:]:
                    line_path.lineTo(pt)
                p.setPen(QPen(_alpha(self._color, 150), 1.2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(line_path)

        p.end()


# ═══════════════════════════════════════════════════════════════════════════
# Audit Integrity Badge
# ═══════════════════════════════════════════════════════════════════════════

class _AuditBadge(QWidget):
    """Shows audit log integrity status."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._valid = True
        self._entries = 0
        self._last_check = "Never"
        self.setFixedHeight(50)

    def update_data(self, valid: bool, entries: int, last_check: str):
        self._valid = valid
        self._entries = entries
        self._last_check = last_check
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        p.setBrush(QBrush(_alpha(C.PANEL2 if hasattr(C, 'PANEL2') else C.PANEL, 200)))
        p.setPen(QPen(_alpha(C.BORDER, 60), 1))
        p.drawRoundedRect(QRectF(0, 0, W - 1, H - 1), 6, 6)

        # Status dot
        color = "#4ade80" if self._valid else "#ff4d6d"
        status = "CHAIN VALID" if self._valid else "CHAIN BROKEN"
        p.setBrush(QBrush(QColor(color)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(16, 16), 4, 4)

        # Text
        text_color = C.TEXT if hasattr(C, 'TEXT') else "#E8E0D0"
        dim_color = C.TEXT_DIM if hasattr(C, 'TEXT_DIM') else "#6B6358"
        p.setFont(_font(9))
        p.setPen(QPen(QColor(text_color), 200))
        p.drawText(QRectF(28, 4, 200, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"🛡 Audit Log  ·  {status}")

        p.setFont(_font(7, bold=False))
        p.setPen(QPen(QColor(dim_color), 150))
        p.drawText(QRectF(28, 24, 300, 14),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"{self._entries} entries  ·  Last check: {self._last_check}")

        p.end()


# ═══════════════════════════════════════════════════════════════════════════
# Database Health Badge
# ═══════════════════════════════════════════════════════════════════════════

class _DatabaseBadge(QWidget):
    """Shows database health and backup status."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._healthy = True
        self._size_mb = 0.0
        self._last_backup = "Never"
        self._backup_count = 0
        self.setFixedHeight(50)

    def update_data(self, healthy: bool, size_mb: float, last_backup: str, backup_count: int):
        self._healthy = healthy
        self._size_mb = size_mb
        self._last_backup = last_backup
        self._backup_count = backup_count
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        p.setBrush(QBrush(_alpha(C.PANEL2 if hasattr(C, 'PANEL2') else C.PANEL, 200)))
        p.setPen(QPen(_alpha(C.BORDER, 60), 1))
        p.drawRoundedRect(QRectF(0, 0, W - 1, H - 1), 6, 6)

        color = "#4ade80" if self._healthy else "#ff4d6d"
        status = "HEALTHY" if self._healthy else "CORRUPTED"
        p.setBrush(QBrush(QColor(color)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(16, 16), 4, 4)

        text_color = C.TEXT if hasattr(C, 'TEXT') else "#E8E0D0"
        dim_color = C.TEXT_DIM if hasattr(C, 'TEXT_DIM') else "#6B6358"
        p.setFont(_font(9))
        p.setPen(QPen(QColor(text_color), 200))
        p.drawText(QRectF(28, 4, 300, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"💾 Database  ·  {status}  ·  {self._size_mb:.1f} MB")

        p.setFont(_font(7, bold=False))
        p.setPen(QPen(QColor(dim_color), 150))
        p.drawText(QRectF(28, 24, 400, 14),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"Backups: {self._backup_count}  ·  Last: {self._last_backup}")

        p.end()


# ═══════════════════════════════════════════════════════════════════════════
# Section Header
# ═══════════════════════════════════════════════════════════════════════════

class _SectionHeader(QWidget):
    """Ornate section header with rune decoration (Direction B style)."""

    def __init__(self, title: str, rune: str = "ᚠ ᚢ ᚦ", parent=None):
        super().__init__(parent)
        self._title = title
        self._rune = rune
        self.setFixedHeight(32)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        gold_dim = C.TEXT_DIM if hasattr(C, 'TEXT_DIM') else "#6B6358"
        gold = "#C9A84C"

        # Title
        p.setFont(_font(9))
        p.setPen(QPen(QColor(gold), 180))
        p.drawText(QRectF(0, 0, W, H),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   self._title)

        # Rune decoration on right
        p.setFont(_font(8))
        p.setPen(QPen(_alpha(gold, 60), 1))
        p.drawText(QRectF(W - 60, 0, 60, H),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   self._rune)

        # Bottom line
        p.setPen(QPen(_alpha(gold, 40), 0.5))
        p.drawLine(0, H - 1, W, H - 1)

        p.end()


# ═══════════════════════════════════════════════════════════════════════════
# Savings Report Card
# ═══════════════════════════════════════════════════════════════════════════

class _SavingsCard(QWidget):
    """Shows estimated cost savings from using free APIs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._daily_tokens = 0
        self._weekly_tokens = 0
        self._monthly_tokens = 0
        self._estimated_savings = 0.0
        self.setFixedHeight(60)

    def update_data(self, daily: int, weekly: int, monthly: int):
        self._daily_tokens = daily
        self._weekly_tokens = weekly
        self._monthly_tokens = monthly
        # Rough estimate: $0.002 per 1K tokens (GPT-4 equivalent pricing)
        self._estimated_savings = (monthly / 1000) * 0.002
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        p.setBrush(QBrush(_alpha(C.PANEL2 if hasattr(C, 'PANEL2') else C.PANEL, 200)))
        p.setPen(QPen(_alpha("#C9A84C", 60), 1))
        p.drawRoundedRect(QRectF(0, 0, W - 1, H - 1), 6, 6)

        text_color = C.TEXT if hasattr(C, 'TEXT') else "#E8E0D0"
        gold = "#C9A84C"
        dim_color = C.TEXT_DIM if hasattr(C, 'TEXT_DIM') else "#6B6358"

        # Title
        p.setFont(_font(9))
        p.setPen(QPen(QColor(gold), 200))
        p.drawText(QRectF(12, 4, 200, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   "💰 Economia Mensal Estimada")

        # Savings amount
        p.setFont(_font(14))
        p.setPen(QPen(QColor(gold), 230))
        p.drawText(QRectF(12, 24, 200, 24),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"${self._estimated_savings:.2f}")

        # Token breakdown
        p.setFont(_font(7, bold=False))
        p.setPen(QPen(QColor(dim_color), 150))
        p.drawText(QRectF(W - 300, 8, 280, 14),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   f"Diário: {self._daily_tokens:,}  ·  Semanal: {self._weekly_tokens:,}  ·  Mensal: {self._monthly_tokens:,}")

        p.drawText(QRectF(W - 300, 28, 280, 14),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   f"100% gratuito via {self._count_providers()} providers rotativos")

        p.end()

    def _count_providers(self) -> int:
        try:
            config_path = Path("config/settings.json")
            if config_path.exists():
                cfg = json.loads(config_path.read_text(encoding="utf-8"))
                return len(cfg.get("llm_providers", cfg.get("providers", [])))
        except Exception:
            pass
        return 15


# ═══════════════════════════════════════════════════════════════════════════
# Main Health Dashboard Page
# ═══════════════════════════════════════════════════════════════════════════

class HealthDashboardPage(QWidget):
    """Unified health dashboard showing all system metrics in one place."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._provider_cards: Dict[str, _ProviderCard] = {}
        self._cpu_card = _SystemMetricCard("CPU", "⚡")
        self._ram_card = _SystemMetricCard("RAM", "🧠")
        self._disk_card = _SystemMetricCard("Disco", "💾")
        self._fps_card = _SystemMetricCard("FPS", "🎯")
        self._audit_badge = _AuditBadge()
        self._db_badge = _DatabaseBadge()
        self._savings_card = _SavingsCard()
        self._init_time = time.time()

        self._build_ui()
        self._start_refresh_timer()

    def _build_ui(self):
        self.setStyleSheet("background: transparent;")

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba({_hex_to_rgb(C.GOLD if hasattr(C, 'GOLD') else '#C9A84C')}, 0.2);
                border-radius: 3px;
                min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # ── Header ──
        header = QLabel("⚡ Health Dashboard")
        header.setFont(_font(14))
        header.setStyleSheet(f"color: {C.TEXT if hasattr(C, 'TEXT') else '#E8E0D0'}; background: transparent;")
        layout.addWidget(header)

        subtitle = QLabel("Monitoramento em tempo real de todos os sistemas")
        subtitle.setFont(_font(8, bold=False))
        subtitle.setStyleSheet(f"color: {C.TEXT_DIM if hasattr(C, 'TEXT_DIM') else '#6B6358'}; background: transparent;")
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        # ── System Metrics Row ──
        layout.addWidget(_SectionHeader("MÉTRICAS DO SISTEMA", "ᚠ ᚢ ᚦ"))

        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(8)
        metrics_row.addWidget(self._cpu_card)
        metrics_row.addWidget(self._ram_card)
        metrics_row.addWidget(self._disk_card)
        metrics_row.addWidget(self._fps_card)
        layout.addLayout(metrics_row)

        # ── Provider Status Section ──
        layout.addWidget(_SectionHeader("STATUS DOS PROVIDERS", "ᚨ ᚱ ᚲ"))

        self._provider_grid = QGridLayout()
        self._provider_grid.setSpacing(8)
        layout.addLayout(self._provider_grid)

        # Create provider cards
        providers = [
            "Groq", "Gemini", "OpenRouter", "Cerebras", "HuggingFace",
            "Ollama", "Mistral", "NVIDIA", "Cloudflare", "Together",
            "SambaNova", "Fireworks", "Cohere", "DeepSeek", "Zhipu",
        ]
        cols = 3
        for i, name in enumerate(providers):
            card = _ProviderCard(name)
            self._provider_cards[name] = card
            self._provider_grid.addWidget(card, i // cols, i % cols)

        # ── Security & Database Section ──
        layout.addWidget(_SectionHeader("SEGURANÇA & DADOS", "ᚷ ᚹ ᚺ"))

        sec_row = QHBoxLayout()
        sec_row.setSpacing(8)
        sec_row.addWidget(self._audit_badge)
        sec_row.addWidget(self._db_badge)
        layout.addLayout(sec_row)

        # ── Savings Report ──
        layout.addWidget(_SectionHeader("RELATÓRIO DE ECONOMIA", "ᚾ ᛁ ᛃ"))

        layout.addWidget(self._savings_card)

        layout.addStretch()

        scroll.setWidget(container)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _start_refresh_timer(self):
        """Refresh data every 3 seconds."""
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_data)
        self._timer.start(3000)
        # Initial refresh
        QTimer.singleShot(100, self._refresh_data)

    def _refresh_data(self):
        """Gather real data from all sources."""
        now = time.time()

        # ── System metrics ──
        try:
            cpu = psutil.cpu_percent(interval=0)
            self._cpu_card.update_value(
                cpu,
                f"{cpu:.1f}%  ·  {psutil.cpu_count()} cores",
                "#4ade80" if cpu < 60 else "#facc15" if cpu < 85 else "#ff4d6d"
            )
        except Exception:
            self._cpu_card.update_value(0, "N/A", "#6B6358")

        try:
            mem = psutil.virtual_memory()
            self._ram_card.update_value(
                mem.percent,
                f"{mem.used / (1024**3):.1f} / {mem.total / (1024**3):.1f} GB",
                "#4ade80" if mem.percent < 60 else "#facc15" if mem.percent < 85 else "#ff4d6d"
            )
        except Exception:
            self._ram_card.update_value(0, "N/A", "#6B6358")

        try:
            disk = psutil.disk_usage("/")
            self._disk_card.update_value(
                disk.percent,
                f"{disk.used / (1024**3):.1f} / {disk.total / (1024**3):.1f} GB",
                "#4ade80" if disk.percent < 70 else "#facc15" if disk.percent < 90 else "#ff4d6d"
            )
        except Exception:
            self._disk_card.update_value(0, "N/A", "#6B6358")

        # FPS — estimated from timer interval
        self._fps_card.update_value(
            30.0,  # Placeholder — real FPS comes from FPSCounterOverlay
            "30 fps target  ·  Ctrl+Shift+F para overlay",
            "#4ade80"
        )

        # ── Provider data ──
        self._refresh_providers()

        # ── Audit log ──
        self._refresh_audit()

        # ── Database ──
        self._refresh_database()

        # ── Savings ──
        self._refresh_savings()

    def _refresh_providers(self):
        """Load provider health data from config and router."""
        try:
            # Try to get data from multi_provider_router
            from core.multi_provider_router import get_provider_health
            for name, card in self._provider_cards.items():
                try:
                    health = get_provider_health(name.lower().replace(" ", ""))
                    card.update_data(
                        available=health.is_healthy,
                        latency_ms=health.avg_latency_ms,
                        error_rate=health.error_rate,
                        tokens_today=getattr(health, 'tokens_today', 0),
                        tokens_limit=getattr(health, 'tokens_limit', 14400),
                        requests_today=getattr(health, 'requests_today', 0),
                    )
                except Exception:
                    card.update_data(False, 0, 1.0, 0, 14400, 0)
        except ImportError:
            # Fallback: mark all as unknown
            for card in self._provider_cards.values():
                card.update_data(False, 0, 0.0, 0, 14400, 0)

    def _refresh_audit(self):
        """Check audit log integrity."""
        try:
            from core.audit_log import AuditLog
            audit = AuditLog()
            entries = len(audit._entries) if hasattr(audit, '_entries') else 0
            valid = audit.verify_integrity() if hasattr(audit, 'verify_integrity') else True
            self._audit_badge.update_data(valid, entries, datetime.now().strftime("%H:%M:%S"))
        except Exception:
            self._audit_badge.update_data(True, 0, "N/A")

    def _refresh_database(self):
        """Check database health and backup status."""
        try:
            db_path = Path("config/memory.db")
            if db_path.exists():
                size_mb = db_path.stat().st_size / (1024 * 1024)
            else:
                size_mb = 0.0

            # Check for backups
            backup_dir = Path("config/backups")
            backup_count = 0
            last_backup = "Never"
            if backup_dir.exists():
                backups = sorted(backup_dir.glob("memory_*.db"), reverse=True)
                backup_count = len(backups)
                if backups:
                    mtime = backups[0].stat().st_mtime
                    last_backup = datetime.fromtimestamp(mtime).strftime("%d/%m %H:%M")

            self._db_badge.update_data(True, size_mb, last_backup, backup_count)
        except Exception:
            self._db_badge.update_data(False, 0.0, "Error", 0)

    def _refresh_savings(self):
        """Load token usage for savings calculation."""
        try:
            from core.usage_tracker import UsageTracker
            tracker = UsageTracker()
            daily = getattr(tracker, '_daily_tokens', 0)
            weekly = daily * 7
            monthly = daily * 30
            self._savings_card.update_data(daily, weekly, monthly)
        except Exception:
            self._savings_card.update_data(0, 0, 0)

    def refresh_fps(self, fps: float):
        """Called externally from FPSCounterOverlay to update the FPS metric."""
        self._fps_card.update_value(
            min(100, fps),
            f"{fps:.0f} fps  ·  frame time: {(1000 / max(1, fps)):.1f}ms",
            "#4ade80" if fps >= 55 else "#facc15" if fps >= 30 else "#ff4d6d"
        )
