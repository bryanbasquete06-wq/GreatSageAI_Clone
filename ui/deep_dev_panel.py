#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deep Dev Panel Widget — Holographic Engineering Interface
===========================================================
Floating sidebar panel for the Elívea UI with the same Tensura aesthetic.
Three modes: Panel (structured prompts), Shadow Dev (autonomous), Time Machine (git regression).
"""

from __future__ import annotations

import math
import time
from typing import Callable, Optional

try:
    from PySide6.QtCore import (
        QEasingCurve, QPointF, QPropertyAnimation, QRectF, QSize, Qt,
        QTimer, Signal as pyqtSignal,
    )
    from PySide6.QtGui import (
        QBrush, QColor, QFont, QPainter, QPainterPath, QPen,
        QRadialGradient, QLinearGradient,
    )
    from PySide6.QtWidgets import (
        QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QLineEdit,
        QPushButton, QScrollArea, QSizePolicy, QSplitter, QTextEdit,
        QVBoxLayout, QWidget,
    )
except ImportError:
    from PyQt6.QtCore import (
        QEasingCurve, QPointF, QPropertyAnimation, QRectF, QSize, Qt,
        QTimer, pyqtSignal,
    )
    from PyQt6.QtGui import (
        QBrush, QColor, QFont, QPainter, QPainterPath, QPen,
        QRadialGradient, QLinearGradient,
    )
    from PyQt6.QtWidgets import (
        QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QLineEdit,
        QPushButton, QScrollArea, QSizePolicy, QSplitter, QTextEdit,
        QVBoxLayout, QWidget,
    )

from ui.qt_ui import C
from ui.professional_widgets import _alpha, _font


# ═══════════════════════════════════════════════════════════════════════════════
# Deep Dev Panel Widget
# ═══════════════════════════════════════════════════════════════════════════════

class DeepDevPanelWidget(QWidget):
    """
    Floating holographic panel for Deep Dev operations.
    Same Tensura aesthetic as the main UI — dark glass, gold accents, rune decorations.
    """

    sig_close = pyqtSignal()
    sig_execute = pyqtSignal(str)      # Command to execute
    sig_approve = pyqtSignal()          # User approved changes
    sig_discard = pyqtSignal()          # User discarded changes

    MODES = ["Painel", "Shadow Dev", "Time Machine"]
    MODE_ICONS = ["◈", "◉", "⧖"]

    def __init__(self, parent=None):
        super().__init__(parent)

        # State
        self._mode = 0  # 0=Panel, 1=Shadow, 2=TimeMachine
        self._phase = "IDLE"
        self._output_text = ""
        self._diff_text = ""
        self._has_changes = False
        self._sandbox_branch = ""
        self._pulse_t = 0.0

        # Callbacks
        self._on_execute: Optional[Callable] = None
        self._on_approve: Optional[Callable] = None
        self._on_discard: Optional[Callable] = None
        self._on_mode_change: Optional[Callable] = None

        self._build_ui()
        self._start_animation()

    def _build_ui(self):
        """Build the holographic panel UI."""
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header with rune decoration ──
        self.header = _DeepDevHeader(self)
        self.header.setFixedHeight(52)
        self.header.sig_close.connect(self.sig_close.emit)
        layout.addWidget(self.header)

        # ── Mode Tabs ──
        self.tab_bar = _DeepDevTabBar(self)
        self.tab_bar.setFixedHeight(38)
        self.tab_bar.on_mode_changed.connect(self._on_tab_changed)
        layout.addWidget(self.tab_bar)

        # ── Content Area ──
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 4, 8, 4)
        content_layout.setSpacing(4)

        # Status indicator
        self.status_label = QLabel("IDLE")
        self.status_label.setFont(_font(8, bold=True, mono=True))
        self.status_label.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; padding: 2px 8px;")
        content_layout.addWidget(self.status_label)

        # Prompt input
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Descreva a tarefa de engenharia...")
        self.prompt_input.setFont(_font(10, bold=False))
        self.prompt_input.setMinimumHeight(36)
        self.prompt_input.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(0,0,0,0.4);
                border: 1px solid rgba({_hex_to_rgb(C.BORDER)},0.5);
                border-radius: 8px;
                color: {C.TEXT};
                padding: 4px 12px;
                selection-background-color: {C.PRI};
            }}
            QLineEdit:focus {{
                border: 1px solid {C.PRI};
            }}
        """)
        self.prompt_input.returnPressed.connect(self._on_submit)
        content_layout.addWidget(self.prompt_input)

        # Action buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self.run_btn = self._make_btn("EXECUTAR", C.GOLD, self._on_submit)
        btn_row.addWidget(self.run_btn)

        self.approve_btn = self._make_btn("APLICAR", C.GREEN, self._on_approve_clicked)
        self.approve_btn.hide()
        btn_row.addWidget(self.approve_btn)

        self.discard_btn = self._make_btn("DESCARTAR", C.RED, self._on_discard_clicked)
        self.discard_btn.hide()
        btn_row.addWidget(self.discard_btn)

        content_layout.addLayout(btn_row)

        # Output area (styled QTextEdit)
        self.output_area = QTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setFont(_font(9, bold=False, mono=True))
        self.output_area.setStyleSheet(f"""
            QTextEdit {{
                background: rgba(0,0,0,0.5);
                border: 1px solid rgba({_hex_to_rgb(C.BORDER)},0.3);
                border-radius: 6px;
                color: {C.TEXT};
                padding: 6px;
                selection-background-color: {C.PRI};
            }}
            QScrollBar:vertical {{
                width: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba({_hex_to_rgb(C.GOLD)},0.2);
                border-radius: 2px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)
        content_layout.addWidget(self.output_area, stretch=1)

        # Diff area (hidden by default)
        self.diff_label = QLabel("DIFF")
        self.diff_label.setFont(_font(8, bold=True, mono=True))
        self.diff_label.setStyleSheet(f"color: {C.GREEN}; background: transparent; padding: 2px 8px;")
        self.diff_label.hide()
        content_layout.addWidget(self.diff_label)

        self.diff_area = QTextEdit()
        self.diff_area.setReadOnly(True)
        self.diff_area.setFont(_font(9, bold=False, mono=True))
        self.diff_area.setMaximumHeight(200)
        self.diff_area.setStyleSheet(f"""
            QTextEdit {{
                background: rgba(0,20,10,0.6);
                border: 1px solid rgba({_hex_to_rgb(C.GREEN)},0.3);
                border-radius: 6px;
                color: {C.GREEN};
                padding: 6px;
            }}
            QScrollBar:vertical {{
                width: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba({_hex_to_rgb(C.GREEN)},0.2);
                border-radius: 2px;
            }}
        """)
        self.diff_area.hide()
        content_layout.addWidget(self.diff_area, stretch=0)

        layout.addWidget(content, stretch=1)

    def _make_btn(self, text: str, color: str, callback: Callable) -> QPushButton:
        """Create a styled button matching the holographic theme."""
        btn = QPushButton(text)
        btn.setFont(_font(8, bold=True))
        btn.setMinimumHeight(30)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(callback)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba({_hex_to_rgb(color)},0.15);
                border: 1px solid rgba({_hex_to_rgb(color)},0.4);
                border-radius: 6px;
                color: {color};
                padding: 4px 12px;
            }}
            QPushButton:hover {{
                background: rgba({_hex_to_rgb(color)},0.3);
                border: 1px solid {color};
            }}
            QPushButton:pressed {{
                background: rgba({_hex_to_rgb(color)},0.5);
            }}
        """)
        return btn

    def _start_animation(self):
        """Pulse timer for phase indicator."""
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)

    def _tick(self):
        self._pulse_t += 0.05
        if self._phase not in ("IDLE", "READY", "APPLIED", "DISCARDED"):
            self.update()

    # ── Public API ────────────────────────────────────────────────────

    def set_mode(self, mode: int):
        """Switch the active mode tab."""
        self._mode = mode
        self.tab_bar.set_mode(mode)

    def set_phase(self, phase: str):
        """Update the current phase indicator."""
        self._phase = phase
        phase_colors = {
            "IDLE": C.TEXT_DIM, "ANALYZING": C.PRI, "DIAGNOSING": C.PRI,
            "SOLVING": C.GOLD, "WRITING": C.GREEN, "TESTING": C.GREEN,
            "SCANNING": C.PRI, "IDENTIFYING": C.GOLD, "ANALYZING": C.GOLD,
            "GENERATING": C.GREEN, "READY": C.GREEN, "APPLIED": C.GREEN,
            "DISCARDED": C.RED, "ACTIVE": C.PRI, "PASSED": C.GREEN, "FAILED": C.RED,
        }
        color = phase_colors.get(phase, C.TEXT_DIM)
        self.status_label.setText(f"● {phase}")
        self.status_label.setStyleSheet(f"color: {color}; background: transparent; padding: 2px 8px; font-weight: bold;")
        self.update()

    def set_output(self, text: str):
        """Set the output text (markdown-like)."""
        self._output_text = text
        # Convert simple markdown to HTML
        html = self._md_to_html(text)
        self.output_area.setHtml(html)
        self.output_area.verticalScrollBar().setValue(
            self.output_area.verticalScrollBar().maximum()
        )

    def append_output(self, text: str):
        """Append text to the output area."""
        self._output_text += text
        self.output_area.append(self._md_to_html(text))

    def set_diff(self, diff_text: str, added: int = 0, removed: int = 0):
        """Show the diff area with changes."""
        self._diff_text = diff_text
        self._has_changes = bool(diff_text)
        html = self._diff_to_html(diff_text)
        self.diff_area.setHtml(html)
        self.diff_label.setText(f"DIFF  +{added}/-{removed}")
        self.diff_area.show()
        self.diff_label.show()
        self.approve_btn.show()
        self.discard_btn.show()

    def clear_diff(self):
        """Hide the diff area."""
        self._diff_text = ""
        self._has_changes = False
        self.diff_area.hide()
        self.diff_label.hide()
        self.approve_btn.hide()
        self.discard_btn.hide()

    def set_sandbox(self, branch: str):
        """Show sandbox branch info."""
        self._sandbox_branch = branch

    def set_on_execute(self, callback: Callable):
        self._on_execute = callback

    def set_on_approve(self, callback: Callable):
        self._on_approve = callback

    def set_on_discard(self, callback: Callable):
        self._on_discard = callback

    def set_on_mode_change(self, callback: Callable):
        self._on_mode_change = callback

    # ── Internal callbacks ─────────────────────────────────────────────

    def _on_tab_changed(self, mode: int):
        self._mode = mode
        if self._on_mode_change:
            self._on_mode_change(mode)

    def _on_submit(self):
        text = self.prompt_input.text().strip()
        if not text:
            return
        # Route based on mode
        mode_prefixes = {
            0: "",           # Panel — direct command
            1: "/shadow ",   # Shadow Dev
            2: "/timemachine ",  # Time Machine
        }
        prefix = mode_prefixes.get(self._mode, "")
        cmd = prefix + text
        self.prompt_input.clear()
        self.append_output(f"> {text}")
        if self._on_execute:
            self._on_execute(cmd)

    def _on_approve_clicked(self):
        if self._on_approve:
            self._on_approve()
        self.clear_diff()
        self.set_phase("APPLIED")
        self.append_output("\n✓ Alterações aprovadas e aplicadas.")

    def _on_discard_clicked(self):
        if self._on_discard:
            self._on_discard()
        self.clear_diff()
        self.set_phase("DISCARDED")
        self.append_output("\n✗ Alterações descartadas.")

    # ── Rendering helpers ──────────────────────────────────────────────

    def _md_to_html(self, text: str) -> str:
        """Simple markdown to HTML conversion for output display."""
        import re
        lines = text.split("\n")
        html_lines = []
        for line in lines:
            # Headers
            if line.startswith("### "):
                html_lines.append(f'<h3 style="color:{C.GOLD};margin:4px 0">{line[4:]}</h3>')
            elif line.startswith("## "):
                html_lines.append(f'<h2 style="color:{C.GOLD};margin:6px 0">{line[3:]}</h2>')
            elif line.startswith("**") and line.endswith("**"):
                html_lines.append(f'<b style="color:{C.ACC}">{line[2:-2]}</b>')
            elif line.startswith("  • ") or line.startswith("  → "):
                html_lines.append(f'<span style="color:{C.TEXT_MED}">{line}</span>')
            elif line.startswith("• "):
                html_lines.append(f'<span style="color:{C.PRI}">•</span> <span style="color:{C.TEXT}">{line[2:]}</span>')
            elif line.startswith("→ "):
                html_lines.append(f'<span style="color:{C.GREEN}">→</span> <span style="color:{C.TEXT}">{line[2:]}</span>')
            elif line.startswith("```"):
                html_lines.append('<pre style="background:rgba(0,0,0,0.3);padding:4px;border-radius:4px;color:' + C.TEXT_MED + '">')
            else:
                # Inline bold
                line = re.sub(r'\*\*(.+?)\*\*', rf'<b style="color:{C.ACC}">\1</b>', line)
                line = re.sub(r'`(.+?)`', rf'<code style="color:{C.GREEN};background:rgba(0,0,0,0.3);padding:1px 4px;border-radius:3px">\1</code>', line)
                html_lines.append(f'<span style="color:{C.TEXT}">{line}</span>')

        return "<br>".join(html_lines)

    def _diff_to_html(self, diff_text: str) -> str:
        """Convert diff text to colored HTML."""
        lines = diff_text.split("\n")
        html_lines = []
        for line in lines:
            if line.startswith("+") and not line.startswith("+++"):
                html_lines.append(f'<span style="color:{C.GREEN}">{_esc_html(line)}</span>')
            elif line.startswith("-") and not line.startswith("---"):
                html_lines.append(f'<span style="color:{C.RED}">{_esc_html(line)}</span>')
            elif line.startswith("@@"):
                html_lines.append(f'<span style="color:{C.PRI}">{_esc_html(line)}</span>')
            elif line.startswith("---") or line.startswith("+++"):
                html_lines.append(f'<span style="color:{C.TEXT_DIM}"><b>{_esc_html(line)}</b></span>')
            else:
                html_lines.append(f'<span style="color:{C.TEXT_MED}">{_esc_html(line)}</span>')
        return "<br>".join(html_lines)

    def paintEvent(self, _):
        """Custom paint for the glass panel border effect."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Subtle border glow
        pulse = 0.3 + 0.1 * math.sin(self._pulse_t) if self._phase not in ("IDLE", "READY", "APPLIED", "DISCARDED") else 0.2
        border_color = C.PRI if self._phase not in ("IDLE",) else C.BORDER

        p.setPen(QPen(_alpha(border_color, int(80 * pulse * 3)), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(0.5, 0.5, W - 1, H - 1), 8, 8)

        # Top rune line decoration
        rune_alpha = int(60 + 30 * math.sin(self._pulse_t * 0.7))
        p.setPen(QPen(_alpha(C.GOLD, rune_alpha), 0.5))
        p.drawLine(20, 52, W - 20, 52)

        p.end()


# ═══════════════════════════════════════════════════════════════════════════════
# Header Widget
# ═══════════════════════════════════════════════════════════════════════════════

class _DeepDevHeader(QWidget):
    sig_close = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Background
        p.fillRect(0, 0, W, H, _alpha(C.PANEL, 230))

        # Left: icon + title
        p.setFont(_font(11))
        p.setPen(QPen(QColor(C.GOLD), 220))
        p.drawText(QRectF(12, 6, 30, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "◈")

        p.setFont(_font(10))
        p.setPen(QPen(QColor(C.TEXT), 230))
        p.drawText(QRectF(38, 4, 160, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "Deep Dev Panel")

        p.setFont(_font(7, bold=False))
        p.setPen(QPen(QColor(C.TEXT_DIM), 130))
        p.drawText(QRectF(38, 24, 200, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   "Engenharia autônoma · Sandbox · Time Machine")

        # Rune decoration
        p.setFont(_font(8))
        p.setPen(QPen(_alpha(C.ACC, 80), 1))
        p.drawText(QRectF(W - 80, 8, 40, 30), Qt.AlignmentFlag.AlignCenter, "ᚠᚢᚦ")

        # Close button
        p.setPen(QPen(_alpha(C.RED, 120), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(W - 36, 10, 24, 24), 4, 4)
        p.setFont(_font(9))
        p.setPen(QPen(QColor(C.RED), 180))
        p.drawText(QRectF(W - 36, 10, 24, 24), Qt.AlignmentFlag.AlignCenter, "×")

        # Bottom border
        p.setPen(QPen(_alpha(C.BORDER, 80), 1))
        p.drawLine(0, H - 1, W, H - 1)

        p.end()

    def mousePressEvent(self, ev):
        if ev.position().x() > self.width() - 40:
            self.sig_close.emit()


# ═══════════════════════════════════════════════════════════════════════════════
# Tab Bar Widget
# ═══════════════════════════════════════════════════════════════════════════════

class _DeepDevTabBar(QWidget):
    on_mode_changed = pyqtSignal(int)

    MODES = ["◈ Painel", "◉ Shadow", "⧖ Time Machine"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = 0
        self._hover = -1
        self.setStyleSheet("background: transparent;")
        self.setMouseTracking(True)
        self.setMinimumHeight(36)

    def set_mode(self, mode: int):
        self._mode = mode
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        tab_w = W // len(self.MODES)

        for i, label in enumerate(self.MODES):
            x = i * tab_w
            is_active = (i == self._mode)
            is_hover = (i == self._hover)

            # Tab background
            if is_active:
                bg = _alpha(C.PRI, 25)
                border_color = C.PRI
            elif is_hover:
                bg = _alpha(C.PRI, 12)
                border_color = _alpha(C.PRI, 60)
            else:
                bg = _alpha(C.PANEL2, 100)
                border_color = _alpha(C.BORDER, 40)

            p.fillRect(x, 0, tab_w, H, bg)

            # Bottom indicator
            if is_active:
                p.setPen(QPen(QColor(C.PRI), 2))
                p.drawLine(x + 10, H - 1, x + tab_w - 10, H - 1)

            # Text
            color = C.PRI if is_active else (C.TEXT_MED if is_hover else C.TEXT_DIM)
            p.setFont(_font(8, bold=is_active))
            p.setPen(QPen(QColor(color), 200 if is_active else 150))
            p.drawText(QRectF(x, 0, tab_w, H), Qt.AlignmentFlag.AlignCenter, label)

            # Separator
            if i < len(self.MODES) - 1:
                p.setPen(QPen(_alpha(C.BORDER, 30), 1))
                p.drawLine(x + tab_w, 6, x + tab_w, H - 6)

        p.end()

    def mousePressEvent(self, ev):
        tab_w = self.width() // len(self.MODES)
        idx = int(ev.position().x() / tab_w)
        if 0 <= idx < len(self.MODES):
            self._mode = idx
            self.update()
            self.on_mode_changed.emit(idx)

    def mouseMoveEvent(self, ev):
        tab_w = self.width() // len(self.MODES)
        idx = int(ev.position().x() / tab_w)
        if idx != self._hover:
            self._hover = idx
            self.update()

    def leaveEvent(self, _):
        self._hover = -1
        self.update()


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _esc_html(text: str) -> str:
    """Escape HTML entities."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _hex_to_rgb(hex_color: str) -> str:
    """Convert #RRGGBB to 'R,G,B' for rgba() CSS."""
    h = hex_color.lstrip("#")
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"{r},{g},{b}"
    return "128,128,128"
