#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elívea — Command Palette (Ctrl+K)
===================================
Floating search overlay for commands, files, and actions.
Inspired by VS Code / JetBrains command palettes with Tensura holographic aesthetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

# PySide6 / PyQt6 compat
try:
    from PySide6.QtCore import (
        Qt, QTimer, Signal, QPropertyAnimation, QEasingCurve, QRectF,
    )
    from PySide6.QtGui import (
        QColor, QFont, QPainter, QPainterPath, QPen, QBrush,
        QLinearGradient, QKeySequence, QShortcut,
    )
    from PySide6.QtWidgets import (
        QApplication, QFrame, QGraphicsOpacityEffect, QHBoxLayout,
        QLabel, QLineEdit, QMainWindow, QPushButton, QScrollArea,
        QSizePolicy, QVBoxLayout, QWidget,
    )
    _QT_API = "PySide6"
except ImportError:
    from PyQt6.QtCore import (
        Qt, QTimer, pyqtSignal as Signal, QPropertyAnimation, QEasingCurve, QRectF,
    )
    from PyQt6.QtGui import (
        QColor, QFont, QPainter, QPainterPath, QPen, QBrush,
        QLinearGradient, QKeySequence, QShortcut,
    )
    from PyQt6.QtWidgets import (
        QApplication, QFrame, QGraphicsOpacityEffect, QHBoxLayout,
        QLabel, QLineEdit, QMainWindow, QPushButton, QScrollArea,
        QSizePolicy, QVBoxLayout, QWidget,
    )
    _QT_API = "PyQt6"


# ── Palette color constants (matches Tensura Gold theme) ────────────────────
class _C:
    BG        = "#060913"
    PANEL     = "#131008"
    PANEL2    = "#1d180c"
    GHOST     = "#332708"
    BORDER    = "#5c4708"
    BORDER_B  = "#a8801c"
    PRI       = "#ffd24a"
    ACC       = "#ffedb0"
    GOLD      = "#ffe27a"
    GREEN     = "#7dff9e"
    RED       = "#ff4d6d"
    TEXT      = "#fff3d6"
    TEXT_DIM  = "#9d8a5a"
    TEXT_MED  = "#e0c98a"


# ── Command data ────────────────────────────────────────────────────────────
@dataclass
class PaletteCommand:
    """A single command entry in the palette."""
    id: str
    label: str
    description: str
    category: str
    shortcut: str = ""
    icon: str = "⚡"
    action: Optional[Callable] = None


def get_all_commands() -> List[PaletteCommand]:
    """Returns the full list of available commands."""
    return [
        # System
        PaletteCommand("status", "System Status", "Show complete system telemetry", "System", icon="📊"),
        PaletteCommand("hora", "Current Time", "Show current time", "System", icon="⏰"),
        PaletteCommand("data", "Current Date", "Show current date", "System", icon="📅"),
        PaletteCommand("ajuda", "Help", "Show all available commands", "System", "F1", icon="❓"),
        PaletteCommand("ram", "RAM Usage", "Show memory usage", "System", icon="💾"),
        PaletteCommand("discos", "Disk Info", "Show disk information", "System", icon="💿"),
        PaletteCommand("processos", "Running Processes", "List running processes", "System", icon="⚙️"),
        PaletteCommand("intel", "Intelligence Status", "Show 6 AI systems status", "System", icon="🧠"),
        PaletteCommand("dashboard", "Activity Dashboard", "Show usage dashboard", "System", icon="📈"),
        PaletteCommand("meu ip", "My IP", "Show public IP address", "System", icon="🌐"),

        # Deep Dev
        PaletteCommand("deep dev status", "Deep Dev Status", "Status of Deep Dev systems", "Deep Dev", icon="🔬"),
        PaletteCommand("shadow", "Shadow Dev", "Run autonomous bug analysis", "Deep Dev", icon="👤"),
        PaletteCommand("time machine", "Time Machine", "Git regression investigation", "Deep Dev", icon="⏰"),
        PaletteCommand("scan secrets", "Scan Secrets", "Scan for sensitive data in code", "Deep Dev", icon="🔐"),
        PaletteCommand("approve shadow", "Approve Shadow", "Apply Shadow Dev changes", "Deep Dev", icon="✅"),
        PaletteCommand("discard shadow", "Discard Shadow", "Discard Shadow Dev changes", "Deep Dev", icon="❌"),

        # Usage & Savings
        PaletteCommand("usage", "Token Usage", "Show token usage last 7 days", "System", icon="📊"),
        PaletteCommand("savings", "Cost Savings", "Weekly savings vs paid APIs", "System", icon="💰"),
        PaletteCommand("router", "Provider Status", "Show all free API providers", "System", icon="🔄"),
        PaletteCommand("capacity", "Combined Capacity", "Total RPM/RPD/TPD", "System", icon="⚡"),

        # Memory
        PaletteCommand("o que voce lembra", "View Memories", "Show stored memories", "Memory", icon="🔮"),
        PaletteCommand("limpar memória", "Clear Memory", "Clear conversation history", "Memory", icon="🧹"),

        # Code
        PaletteCommand("execute print(2+2)", "Execute Code", "Run Python code snippet", "Code", icon="▶️"),
        PaletteCommand("refatore", "Refactor", "Ask to refactor code", "Code", icon="🔧"),
        PaletteCommand("teste", "Test", "Generate unit tests", "Code", icon="🧪"),
        PaletteCommand("debug", "Debug", "Debug an error", "Code", icon="🐛"),

        # Web
        PaletteCommand("pesquise ", "Web Search", "Search the internet", "Web", icon="🔍"),
        PaletteCommand("noticias ", "News", "Search for news", "Web", icon="📰"),

        # Config
        PaletteCommand("theme", "Change Theme", "Cycle through themes", "Config", icon="🎨"),
        PaletteCommand("voice", "Change Voice", "Cycle through voices", "Config", icon="🎙️"),
        PaletteCommand("config", "Open Config", "Open settings panel", "Config", icon="⚙️"),
        PaletteCommand("monitor", "Monitor", "Show system monitor", "Config", icon="📡"),

        # Fun
        PaletteCommand("piada", "Tell a Joke", "Tell a programming joke", "Fun", icon="😄"),
        PaletteCommand("quem é você", "Who Are You", "Elívea self-introduction", "Fun", icon="⚔️"),

        # Digest
        PaletteCommand("digest", "Weekly Digest", "Show weekly activity & AI performance report", "System", icon="📊"),
    ]


# ── Command Item Widget ─────────────────────────────────────────────────────
class CommandItemWidget(QFrame):
    """A single command row in the palette."""
    clicked = Signal(str)  # emits command id

    def __init__(self, cmd: PaletteCommand, parent=None):
        super().__init__(parent)
        self.cmd = cmd
        self._selected = False
        self.setFixedHeight(48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("background: transparent; border: none;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 4, 16, 4)
        layout.setSpacing(12)

        # Icon
        self.icon_label = QLabel(cmd.icon)
        self.icon_label.setFixedWidth(28)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet(f"color: {_C.PRI}; font-size: 18px; background: transparent; border: none;")
        layout.addWidget(self.icon_label)

        # Text column
        text_col = QVBoxLayout()
        text_col.setSpacing(0)
        text_col.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel(cmd.label)
        self.label.setStyleSheet(f"color: {_C.TEXT}; font-size: 14px; font-weight: 600; background: transparent; border: none;")
        text_col.addWidget(self.label)

        self.desc = QLabel(cmd.description)
        self.desc.setStyleSheet(f"color: {_C.TEXT_DIM}; font-size: 11px; background: transparent; border: none;")
        text_col.addWidget(self.desc)

        layout.addLayout(text_col, 1)

        # Category badge
        self.badge = QLabel(cmd.category)
        self.badge.setStyleSheet(
            f"color: {_C.TEXT_DIM}; font-size: 10px; padding: 2px 8px; "
            f"background: {_C.GHOST}; border: 1px solid {_C.BORDER}; border-radius: 8px;"
        )
        layout.addWidget(self.badge)

        # Shortcut hint
        if cmd.shortcut:
            self.shortcut_label = QLabel(cmd.shortcut)
            self.shortcut_label.setStyleSheet(
                f"color: {_C.TEXT_DIM}; font-size: 11px; font-family: monospace; background: transparent; border: none;"
            )
            layout.addWidget(self.shortcut_label)

    def set_selected(self, selected: bool):
        self._selected = selected
        if selected:
            self.setStyleSheet(
                f"background: {_C.GHOST}; border: 1px solid {_C.BORDER_B}; border-radius: 8px;"
            )
            self.label.setStyleSheet(f"color: {_C.PRI}; font-size: 14px; font-weight: 600; background: transparent; border: none;")
        else:
            self.setStyleSheet("background: transparent; border: none;")
            self.label.setStyleSheet(f"color: {_C.TEXT}; font-size: 14px; font-weight: 600; background: transparent; border: none;")

    def mousePressEvent(self, ev):
        self.clicked.emit(self.cmd.id)


# ── Command Palette ─────────────────────────────────────────────────────────
class CommandPalette(QWidget):
    """
    Floating command palette overlay (Ctrl+K).
    Filters commands by fuzzy search, supports keyboard navigation.
    """
    command_selected = Signal(str)  # emits the command text to execute

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(620)
        self.setFixedHeight(480)

        self._all_commands = get_all_commands()
        self._filtered: List[PaletteCommand] = list(self._all_commands)
        self._selected_index = 0
        self._item_widgets: List[CommandItemWidget] = []

        self._build_ui()
        self._apply_filter("")

    def _build_ui(self):
        """Build the palette UI."""
        # Opacity effect for fade animation
        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)

        # Fade in animation
        self._fade_in = QPropertyAnimation(self._opacity, b"opacity")
        self._fade_in.setDuration(150)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Fade out animation
        self._fade_out = QPropertyAnimation(self._opacity, b"opacity")
        self._fade_out.setDuration(120)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_out.finished.connect(self.hide)

        # Main container
        self._container = QFrame(self)
        self._container.setStyleSheet(
            f"QFrame {{ background: {_C.BG}; border: 2px solid {_C.BORDER_B}; border-radius: 16px; }}"
        )

        main_layout = QVBoxLayout(self._container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Header with search ──
        header = QFrame()
        header.setStyleSheet(f"background: {_C.PANEL}; border-top-left-radius: 16px; border-top-right-radius: 16px; border-bottom: 1px solid {_C.BORDER};")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 14, 20, 14)
        header_layout.setSpacing(12)

        # Search icon
        search_icon = QLabel("🔍")
        search_icon.setStyleSheet(f"color: {_C.PRI}; font-size: 18px; background: transparent; border: none;")
        header_layout.addWidget(search_icon)

        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Digite um comando… (Ctrl+K)")
        self.search_input.setStyleSheet(
            f"QLineEdit {{ color: {_C.TEXT}; font-size: 16px; font-weight: 500; "
            f"background: transparent; border: none; padding: 4px 0; "
            f"selection-background-color: {_C.BORDER_B}; }}"
        )
        self.search_input.textChanged.connect(self._apply_filter)
        self.search_input.keyPressEvent = self._on_input_key
        header_layout.addWidget(self.search_input, 1)

        # Close button
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(
            f"QPushButton {{ color: {_C.TEXT_DIM}; font-size: 14px; background: transparent; "
            f"border: 1px solid {_C.BORDER}; border-radius: 14px; }}"
            f"QPushButton:hover {{ color: {_C.RED}; border-color: {_C.RED}; }}"
        )
        close_btn.clicked.connect(self.close_palette)
        header_layout.addWidget(close_btn)

        main_layout.addWidget(header)

        # ── Category filter row ──
        self._category_frame = QFrame()
        self._category_frame.setStyleSheet(f"background: {_C.PANEL2}; border: none;")
        cat_layout = QHBoxLayout(self._category_frame)
        cat_layout.setContentsMargins(16, 8, 16, 8)
        cat_layout.setSpacing(6)

        self._cat_buttons: dict[str, QPushButton] = {}
        for cat in ["All", "System", "Deep Dev", "Code", "Memory", "Web", "Config", "Fun"]:
            btn = QPushButton(cat)
            btn.setCheckable(True)
            if cat == "All":
                btn.setChecked(True)
            btn.setStyleSheet(self._cat_btn_style(cat == "All"))
            btn.clicked.connect(lambda checked, c=cat: self._filter_by_category(c))
            cat_layout.addWidget(btn)
            self._cat_buttons[cat] = btn

        cat_layout.addStretch()
        main_layout.addWidget(self._category_frame)

        # ── Results list ──
        self._results_area = QScrollArea()
        self._results_area.setWidgetResizable(True)
        self._results_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._results_area.setStyleSheet(
            f"QScrollArea {{ background: {_C.BG}; border: none; }}"
            f"QScrollBar:vertical {{ background: transparent; width: 6px; margin: 0; }}"
            f"QScrollBar::handle:vertical {{ background: {_C.BORDER}; border-radius: 3px; min-height: 30px; }}"
            f"QScrollBar::handle:vertical:hover {{ background: {_C.BORDER_B}; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
        )

        self._results_widget = QWidget()
        self._results_layout = QVBoxLayout(self._results_widget)
        self._results_layout.setContentsMargins(8, 8, 8, 8)
        self._results_layout.setSpacing(2)
        self._results_layout.addStretch()

        self._results_area.setWidget(self._results_widget)
        main_layout.addWidget(self._results_area, 1)

        # ── Footer ──
        footer = QFrame()
        footer.setStyleSheet(f"background: {_C.PANEL}; border-top: 1px solid {_C.BORDER}; border-bottom-left-radius: 16px; border-bottom-right-radius: 16px;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 8, 20, 8)

        hints = QLabel("↑↓ navegar  ·  Enter selecionar  ·  Esc fechar")
        hints.setStyleSheet(f"color: {_C.TEXT_DIM}; font-size: 11px; background: transparent; border: none;")
        footer_layout.addWidget(hints)

        footer_layout.addStretch()

        count_label = QLabel(f"{len(self._all_commands)} comandos")
        count_label.setStyleSheet(f"color: {_C.TEXT_DIM}; font-size: 11px; background: transparent; border: none;")
        self._count_label = count_label
        footer_layout.addWidget(count_label)

        main_layout.addWidget(footer)

        # Layout for the palette itself
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._container)

    def _cat_btn_style(self, active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ color: {_C.BG}; font-size: 11px; font-weight: 700; "
                f"background: {_C.PRI}; border: none; border-radius: 10px; padding: 4px 12px; }}"
            )
        return (
            f"QPushButton {{ color: {_C.TEXT_DIM}; font-size: 11px; "
            f"background: {_C.GHOST}; border: 1px solid {_C.BORDER}; border-radius: 10px; padding: 4px 12px; }}"
            f"QPushButton:hover {{ color: {_C.TEXT}; border-color: {_C.BORDER_B}; }}"
        )

    # ── Filtering ───────────────────────────────────────────────────────────

    def _apply_filter(self, text: str):
        """Filter commands by search text."""
        query = text.lower().strip()
        self._filtered = []

        for cmd in self._all_commands:
            if not query:
                self._filtered.append(cmd)
                continue
            # Fuzzy match: all query words must appear in label, description, or category
            words = query.split()
            searchable = f"{cmd.label} {cmd.description} {cmd.category} {cmd.id}".lower()
            if all(w in searchable for w in words):
                self._filtered.append(cmd)

        self._selected_index = 0
        self._rebuild_results()

    def _filter_by_category(self, category: str):
        """Filter by category button."""
        for cat, btn in self._cat_buttons.items():
            btn.setChecked(cat == category)
            btn.setStyleSheet(self._cat_btn_style(cat == category))

        if category == "All":
            self._apply_filter(self.search_input.text())
        else:
            query = self.search_input.text().lower().strip()
            self._filtered = []
            for cmd in self._all_commands:
                if cmd.category != category:
                    continue
                if query:
                    searchable = f"{cmd.label} {cmd.description} {cmd.id}".lower()
                    if not all(w in searchable for w in query.split()):
                        continue
                self._filtered.append(cmd)
            self._selected_index = 0
            self._rebuild_results()

    def _rebuild_results(self):
        """Rebuild the results list."""
        # Clear old items
        for w in self._item_widgets:
            w.setParent(None)
            w.deleteLater()
        self._item_widgets.clear()

        # Remove the stretch (will re-add)
        count = self._results_layout.count()
        if count > 0:
            item = self._results_layout.itemAt(count - 1)
            if item and item.widget() is None and item.spacerItem():
                self._results_layout.removeItem(item)

        # Add filtered items
        for i, cmd in enumerate(self._filtered):
            widget = CommandItemWidget(cmd)
            widget.set_selected(i == self._selected_index)
            widget.clicked.connect(self._on_item_clicked)
            self._results_layout.addWidget(widget)
            self._item_widgets.append(widget)

        # Re-add stretch
        self._results_layout.addStretch()

        # Update count
        self._count_label.setText(f"{len(self._filtered)} de {len(self._all_commands)}")

    def _update_selection(self):
        """Update visual selection state."""
        for i, w in enumerate(self._item_widgets):
            w.set_selected(i == self._selected_index)

        # Scroll selected item into view
        if 0 <= self._selected_index < len(self._item_widgets):
            self._item_widgets[self._selected_index].scrollIntoView(
                self._results_area, self._results_area.verticalScrollBar()
            )

    # ── Keyboard navigation ─────────────────────────────────────────────────

    def _on_input_key(self, ev):
        """Handle key events in the search input."""
        key = ev.key()

        if key == Qt.Key.Key_Down:
            self._select_next()
        elif key == Qt.Key.Key_Up:
            self._select_prev()
        elif key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            self._execute_selected()
        elif key == Qt.Key.Key_Escape:
            self.close_palette()
        else:
            # Default behavior (type character)
            QLineEdit.keyPressEvent(self.search_input, ev)

    def _select_next(self):
        if self._filtered:
            self._selected_index = (self._selected_index + 1) % len(self._filtered)
            self._update_selection()

    def _select_prev(self):
        if self._filtered:
            self._selected_index = (self._selected_index - 1) % len(self._filtered)
            self._update_selection()

    def _execute_selected(self):
        if 0 <= self._selected_index < len(self._filtered):
            cmd = self._filtered[self._selected_index]
            self.command_selected.emit(cmd.id)
            self.close_palette()

    def _on_item_clicked(self, cmd_id: str):
        self.command_selected.emit(cmd_id)
        self.close_palette()

    # ── Show / Hide ─────────────────────────────────────────────────────────

    def show_palette(self):
        """Show the palette with fade-in animation."""
        if not self.parent():
            return

        # Center on parent
        parent = self.parent()
        px = parent.x() + (parent.width() - self.width()) // 2
        py = parent.y() + (parent.height() - self.height()) // 2
        # Offset slightly toward top
        py -= 40
        self.move(px, py)

        self.show()
        self.raise_()
        self.search_input.clear()
        self.search_input.setFocus()
        self._selected_index = 0
        self._apply_filter("")
        self._fade_in.start()

    def close_palette(self):
        """Close the palette with fade-out animation."""
        self._fade_out.start()

    def paintEvent(self, ev):
        """Custom paint for rounded corners and glow border."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self._container.geometry())

        # Glow effect
        for i in range(3):
            alpha = 30 - i * 8
            pen = QPen(QColor(168, 128, 28, alpha))
            pen.setWidth(2 + i * 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(-i, -i, i, i), 16 + i, 16 + i)

        painter.end()

    # Override to capture clicks outside
    def mousePressEvent(self, ev):
        if not self._container.geometry().contains(ev.pos()):
            self.close_palette()

    def focusOutEvent(self, ev):
        """Don't auto-close on focus out — user might click inside."""
        pass
