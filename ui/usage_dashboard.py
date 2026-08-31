# -*- coding: utf-8 -*-
"""
Elívea — Usage Dashboard Widget
========================================
Widget Qt que mostra uso real-time de todos os providers:
  - Barras de progresso por provider (requests + tokens)
  - Limites diarios com projecao
  - Latencia media
  - Alertas quando proximo do limite
"""
from __future__ import annotations

import math
import time
from typing import Optional

try:
    from PySide6.QtCore import Qt, QTimer, Signal
    from PySide6.QtGui import QColor, QFont, QPainter, QLinearGradient, QPen
    from PySide6.QtWidgets import (
        QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
        QProgressBar, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
    )
except ImportError:
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal as Signal
    from PyQt6.QtGui import QColor, QFont, QPainter, QLinearGradient, QPen
    from PyQt6.QtWidgets import (
        QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
        QProgressBar, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
    )

from core.usage_tracker import UsageTracker, PROVIDER_LIMITS


# ── Colors ──────────────────────────────────────────────
_COLOR_BG = "#0a0e1a"
_COLOR_PANEL = "#111827"
_COLOR_BORDER = "#1e3a5f"
_COLOR_TEXT = "#e2e8f0"
_COLOR_TEXT_DIM = "#64748b"
_COLOR_GOLD = "#f59e0b"
_COLOR_GREEN = "#10b981"
_COLOR_YELLOW = "#eab308"
_COLOR_RED = "#ef4444"
_COLOR_BLUE = "#3b82f6"
_COLOR_CYAN = "#06b6d4"


def _pct_color(pct: float) -> str:
    if pct < 50:
        return _COLOR_GREEN
    elif pct < 75:
        return _COLOR_YELLOW
    elif pct < 90:
        return "#f97316"  # orange
    return _COLOR_RED


class ProviderBar(QWidget):
    """Single provider usage bar with label and progress."""

    def __init__(self, provider_name: str, parent=None):
        super().__init__(parent)
        self._name = provider_name
        self._limits = PROVIDER_LIMITS.get(provider_name, {})
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(2)

        # Header row: name + requests / limit
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        self._label_name = QLabel(self._name.upper())
        self._label_name.setStyleSheet(
            f"color: {_COLOR_CYAN}; font-size: 10px; font-weight: bold; "
            "font-family: Consolas, monospace;"
        )
        self._label_name.setFixedWidth(100)
        header.addWidget(self._label_name)

        self._label_requests = QLabel("0 / 0")
        self._label_requests.setStyleSheet(
            f"color: {_COLOR_TEXT}; font-size: 10px; font-family: Consolas, monospace;"
        )
        self._label_requests.setAlignment(Qt.AlignmentFlag.AlignRight)
        header.addWidget(self._label_requests)

        self._label_pct = QLabel("0%")
        self._label_pct.setStyleSheet(
            f"color: {_COLOR_GREEN}; font-size: 10px; font-weight: bold; "
            "font-family: Consolas, monospace;"
        )
        self._label_pct.setFixedWidth(45)
        self._label_pct.setAlignment(Qt.AlignmentFlag.AlignRight)
        header.addWidget(self._label_pct)

        layout.addLayout(header)

        # Progress bar
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setFixedHeight(8)
        self._bar.setTextVisible(False)
        self._bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #1e293b;
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {_COLOR_GREEN};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self._bar)

        # Detail row: latency + tokens
        detail = QHBoxLayout()
        detail.setContentsMargins(100, 0, 0, 0)

        self._label_latency = QLabel("0ms")
        self._label_latency.setStyleSheet(
            f"color: {_COLOR_TEXT_DIM}; font-size: 9px; font-family: Consolas, monospace;"
        )
        detail.addWidget(self._label_latency)

        self._label_tokens = QLabel("0 tokens")
        self._label_tokens.setStyleSheet(
            f"color: {_COLOR_TEXT_DIM}; font-size: 9px; font-family: Consolas, monospace;"
        )
        detail.addWidget(self._label_tokens)

        self._label_status = QLabel("")
        self._label_status.setStyleSheet(
            f"color: {_COLOR_GREEN}; font-size: 9px; font-weight: bold; "
            "font-family: Consolas, monospace;"
        )
        detail.addWidget(self._label_status)

        layout.addLayout(detail)

    def update_data(self, usage):
        """Update with ProviderUsage data."""
        pct = usage.request_pct()
        color = _pct_color(pct)

        rpd = usage.get_limit("rpd")
        self._label_requests.setText(f"{usage.requests_day:,} / {rpd:,}")
        self._label_pct.setText(f"{pct:.0f}%")
        self._label_pct.setStyleSheet(
            f"color: {color}; font-size: 10px; font-weight: bold; "
            "font-family: Consolas, monospace;"
        )
        self._bar.setValue(int(pct))
        self._bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #1e293b;
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 4px;
            }}
        """)

        lat = usage.avg_latency_ms
        self._label_latency.setText(f"{lat:.0f}ms avg" if lat > 0 else "no data")
        tok = usage.tokens_input_day + usage.tokens_output_day
        self._label_tokens.setText(f"{tok:,} tokens")

        if usage.is_limited():
            self._label_status.setText("LIMITED")
            self._label_status.setStyleSheet(
                f"color: {_COLOR_RED}; font-size: 9px; font-weight: bold; "
                "font-family: Consolas, monospace;"
            )
        elif usage.errors > 0:
            self._label_status.setText(f"{usage.errors} err")
            self._label_status.setStyleSheet(
                f"color: {_COLOR_YELLOW}; font-size: 9px; font-weight: bold; "
                "font-family: Consolas, monospace;"
            )
        else:
            self._label_status.setText("OK")
            self._label_status.setStyleSheet(
                f"color: {_COLOR_GREEN}; font-size: 9px; font-weight: bold; "
                "font-family: Consolas, monospace;"
            )


class UsageDashboard(QWidget):
    """Full usage dashboard widget — embed in main window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tracker = UsageTracker()
        self._bars: dict[str, ProviderBar] = {}
        self._setup_ui()
        self._start_timer()

    def _setup_ui(self):
        self.setStyleSheet(f"background-color: {_COLOR_BG};")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 8, 12, 8)
        main_layout.setSpacing(8)

        # ── Title ──
        title = QLabel("USAGE TRACKER")
        title.setStyleSheet(
            f"color: {_COLOR_GOLD}; font-size: 14px; font-weight: bold; "
            "font-family: Consolas, monospace; letter-spacing: 2px;"
        )
        main_layout.addWidget(title)

        # ── Summary panel ──
        self._summary_frame = QFrame()
        self._summary_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {_COLOR_PANEL};
                border: 1px solid {_COLOR_BORDER};
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        summary_layout = QHBoxLayout(self._summary_frame)
        summary_layout.setSpacing(20)

        self._stat_requests = self._create_stat("TOTAL REQUESTS", "0")
        self._stat_tokens = self._create_stat("TOTAL TOKENS", "0")
        self._stat_rph = self._create_stat("REQ/HOUR", "0")
        self._stat_tph = self._create_stat("TOKENS/HOUR", "0")
        self._stat_active = self._create_stat("ACTIVE", "0/0")
        self._stat_uptime = self._create_stat("UPTIME", "0h")

        for w in [self._stat_requests, self._stat_tokens, self._stat_rph,
                  self._stat_tph, self._stat_active, self._stat_uptime]:
            summary_layout.addWidget(w)

        main_layout.addWidget(self._summary_frame)

        # ── Combined bar ──
        self._combined_frame = QFrame()
        self._combined_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {_COLOR_PANEL};
                border: 1px solid {_COLOR_BORDER};
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        combined_layout = QVBoxLayout(self._combined_frame)
        combined_layout.setContentsMargins(12, 8, 12, 8)

        self._label_combined = QLabel("COMBINED CAPACITY")
        self._label_combined.setStyleSheet(
            f"color: {_COLOR_CYAN}; font-size: 11px; font-weight: bold; "
            "font-family: Consolas, monospace;"
        )
        combined_layout.addWidget(self._label_combined)

        self._bar_combined = QProgressBar()
        self._bar_combined.setRange(0, 100)
        self._bar_combined.setValue(0)
        self._bar_combined.setFixedHeight(12)
        self._bar_combined.setTextVisible(True)
        self._bar_combined.setStyleSheet(f"""
            QProgressBar {{
                background-color: #1e293b;
                border: none;
                border-radius: 6px;
                color: white;
                font-size: 10px;
                font-family: Consolas, monospace;
            }}
            QProgressBar::chunk {{
                background-color: {_COLOR_GREEN};
                border-radius: 6px;
            }}
        """)
        combined_layout.addWidget(self._bar_combined)

        self._label_reset = QLabel("Resets in: --")
        self._label_reset.setStyleSheet(
            f"color: {_COLOR_TEXT_DIM}; font-size: 9px; font-family: Consolas, monospace;"
        )
        combined_layout.addWidget(self._label_reset)

        main_layout.addWidget(self._combined_frame)

        # ── Per-provider scrollable list ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: #1e293b;
                width: 6px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background-color: #475569;
                border-radius: 3px;
                min-height: 20px;
            }}
        """)

        providers_widget = QWidget()
        providers_widget.setStyleSheet("background-color: transparent;")
        self._providers_layout = QVBoxLayout(providers_widget)
        self._providers_layout.setContentsMargins(0, 0, 0, 0)
        self._providers_layout.setSpacing(6)

        # Create bars for known providers
        for name in sorted(PROVIDER_LIMITS.keys()):
            bar = ProviderBar(name)
            self._bars[name] = bar
            self._providers_layout.addWidget(bar)

        self._providers_layout.addStretch()
        scroll.setWidget(providers_widget)
        main_layout.addWidget(scroll)

    def _create_stat(self, label: str, value: str) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: {_COLOR_TEXT_DIM}; font-size: 8px; font-family: Consolas, monospace;"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

        val = QLabel(value)
        val.setObjectName("value")
        val.setStyleSheet(
            f"color: {_COLOR_TEXT}; font-size: 14px; font-weight: bold; "
            "font-family: Consolas, monospace;"
        )
        val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(val)

        return w

    def _update_stat(self, widget: QWidget, value: str):
        lbl = widget.findChild(QLabel, "value")
        if lbl:
            lbl.setText(value)

    def _start_timer(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(2000)  # refresh every 2s

    def _refresh(self):
        summary = self._tracker.get_summary()
        combined = self._tracker.get_combined_daily_pct()

        # Update summary stats
        self._update_stat(self._stat_requests, f"{summary['total_requests']:,}")
        self._update_stat(self._stat_tokens, f"{summary['total_tokens']:,}")
        self._update_stat(self._stat_rph, f"{summary['requests_per_hour']:.0f}")
        self._update_stat(self._stat_tph, f"{summary['tokens_per_hour']:.0f}")
        active = summary["active_providers"]
        capacity = summary["providers_with_capacity"]
        self._update_stat(self._stat_active, f"{active}/{capacity}")
        hrs = summary["uptime_hours"]
        self._update_stat(self._stat_uptime, f"{hrs:.1f}h")

        # Combined bar
        pct = combined["requests_pct"]
        color = _pct_color(pct)
        self._bar_combined.setValue(int(pct))
        self._bar_combined.setFormat(
            f"{combined['total_rpd_used']:,} / {combined['total_rpd']:,} requests"
        )
        self._bar_combined.setStyleSheet(f"""
            QProgressBar {{
                background-color: #1e293b;
                border: none;
                border-radius: 6px;
                color: white;
                font-size: 10px;
                font-family: Consolas, monospace;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 6px;
            }}
        """)

        # Per-provider bars
        all_usage = self._tracker.get_all_providers()
        for name, bar in self._bars.items():
            usage = all_usage.get(name)
            if usage:
                bar.update_data(usage)
                bar.show()
            else:
                bar.hide()
