#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elívea — Setup Wizard (Installer GUI v2)
=================================================
Complete setup wizard for end users:
  1. Check system requirements (Python, pip, audio)
  2. Install all dependencies automatically
  3. Configure API keys (Groq, Gemini) with validation
  4. Select voice (Elivea, Natural, Jarvis)
  5. Configure wake word
  6. Create desktop shortcuts
  7. Test voice pipeline
  8. Launch the AI

Cyberpunk-themed with animated magic circle and step progress.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor, QFont, QIcon, QPainter, QRadialGradient, QBrush, QPen,
)
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QPushButton, QScrollArea, QSizePolicy,
    QTextEdit, QVBoxLayout, QWidget, QStackedWidget,
)


# ── Theme ────────────────────────────────────────────────────────────────────

BG = "#060913"
PANEL = "#131008"
PANEL2 = "#1d180c"
GHOST = "#332708"
BORDER = "#5c4708"
BORDER_B = "#a8801c"
PRI = "#ffd24a"
ACC = "#ffedb0"
GOLD = "#ffe27a"
GREEN = "#7dff9e"
RED = "#ff4d6d"
BLUE = "#4a9eff"
TEXT = "#fff3d6"
TEXT_DIM = "#9d8a5a"
TEXT_MED = "#e0c98a"
WHITE = "#ffffff"


def qcol(h, a=255):
    c = QColor(h)
    c.setAlpha(a)
    return c


RUNES = list("ᚠᚢᚦᚨᚱᚲᚷᚹᚺᚾᛁᛃᛇᛈᛉᛊᛏᛒᛖᛗᛚᛜᛞᛟ")


def font_mono(size, bold=True):
    return QFont("Consolas", size, QFont.Weight.Bold if bold else QFont.Weight.Normal)


def font_cjk(size, bold=True):
    return QFont("Microsoft YaHei UI", size,
                 QFont.Weight.Bold if bold else QFont.Weight.Normal)


# ═══════════════════════════════════════════════════════════════════════════════
# MAGIC CIRCLE
# ═══════════════════════════════════════════════════════════════════════════════

class MagicCircle(QWidget):
    """Animated magic circle with progress arc."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(160, 160)
        self.setMaximumSize(200, 200)
        self._t = 0.0
        self._rune_rot = 0.0
        self._arc_rot = [0.0, 0.0]
        self._progress = 0.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(33)

    def set_progress(self, p: float):
        self._progress = max(0.0, min(1.0, p))

    def paintEvent(self, event):
        w, h = self.width(), self.height()
        self._t += 0.03
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = w / 2, h / 2
        r = min(w, h) * 0.42

        # Glow
        glow_r = r * 1.3
        grad = QRadialGradient(cx, cy, glow_r)
        grad.setColorAt(0, qcol(PRI, 25))
        grad.setColorAt(1, qcol(PRI, 0))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2)

        # Outer ring
        p.setPen(QPen(qcol(GOLD, 180), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # Rune ring
        self._rune_rot += 0.003
        rune_font = font_cjk(int(r * 0.13))
        p.setFont(rune_font)
        p.setPen(qcol(GOLD, 200))
        for i, rune in enumerate(RUNES):
            angle = 2 * math.pi * i / len(RUNES) + self._rune_rot
            rx = cx + math.cos(angle) * r
            ry = cy + math.sin(angle) * r
            p.drawText(rx - r * 0.05, ry + r * 0.05, rune)

        # Progress arc
        if self._progress > 0:
            pen_prog = QPen(qcol(GREEN, 220), 3.0)
            p.setPen(pen_prog)
            p.setBrush(Qt.BrushStyle.NoBrush)
            prog_r = r * 0.8
            start = -90 * 16
            span = int(self._progress * 360 * 16)
            p.drawArc(cx - prog_r, cy - prog_r, prog_r * 2, prog_r * 2, start, span)

        # Rotating arcs
        for idx, speed in enumerate([0.004, -0.003]):
            self._arc_rot[idx] += speed
            arc_r = r * (0.7 - idx * 0.1)
            p.setPen(QPen(qcol(PRI, 100 - idx * 20), 0.8))
            p.setBrush(Qt.BrushStyle.NoBrush)
            start_a = int(self._arc_rot[idx] * 57.3)
            span_a = int(math.pi * 0.8 * 57.3)
            p.drawArc(cx - arc_r, cy - arc_r, arc_r * 2, arc_r * 2, start_a, span_a)

        # Core
        core_r = r * 0.15
        pulse = 0.7 + 0.3 * math.sin(self._t * 3)
        grad2 = QRadialGradient(cx, cy, core_r * 2)
        grad2.setColorAt(0, qcol(GOLD, int(200 * pulse)))
        grad2.setColorAt(1, qcol(PRI, 0))
        p.setBrush(QBrush(grad2))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(cx - core_r * 2, cy - core_r * 2, core_r * 4, core_r * 4)

        # Label
        p.setFont(font_cjk(int(r * 0.18)))
        p.setPen(qcol(GOLD, 200))
        p.drawText(cx - r, cy + r * 0.3, r * 2, r * 0.3,
                   Qt.AlignmentFlag.AlignCenter, "＜Elívea＞")

        p.end()


# ═══════════════════════════════════════════════════════════════════════════════
# GOLDEN PROGRESS BAR
# ═══════════════════════════════════════════════════════════════════════════════

class ProgressBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._progress = 0.0
        self._shimmer = 0.0
        self.setFixedHeight(18)

    def set_progress(self, p: float):
        self._progress = max(0.0, min(1.0, p))
        self.update()

    def paintEvent(self, event):
        w, h = self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        p.setPen(QPen(qcol(BORDER, 100), 1))
        p.setBrush(qcol(GHOST, 80))
        p.drawRoundedRect(1, 1, w - 2, h - 2, 6, 6)

        fill_w = int((w - 4) * self._progress)
        if fill_w > 0:
            grad = __import__("PySide6.QtGui", fromlist=["QLinearGradient"]).QLinearGradient(0, 0, fill_w, 0)
            grad.setColorAt(0, qcol("#b8860b", 200))
            grad.setColorAt(0.5, qcol(PRI, 220))
            grad.setColorAt(1, qcol("#b8860b", 200))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(2, 2, fill_w, h - 4, 5, 5)

            self._shimmer += 0.03
            shimmer_x = int(fill_w * ((math.sin(self._shimmer) + 1) / 2))
            if shimmer_x > 5:
                p.setBrush(qcol(WHITE, 40))
                p.drawRect(shimmer_x - 3, 2, 6, h - 4)

        pct = f"{int(self._progress * 100)}%"
        p.setFont(font_mono(7))
        p.setPen(qcol(WHITE, 220))
        p.drawText(0, 0, w, h, Qt.AlignmentFlag.AlignCenter, pct)
        p.end()


# ═══════════════════════════════════════════════════════════════════════════════
# STEP INDICATOR
# ═══════════════════════════════════════════════════════════════════════════════

class StepIndicator(QWidget):
    def __init__(self, steps: list[str], parent=None):
        super().__init__(parent)
        self.steps = steps
        self.current = 0
        self.statuses = ["pending"] * len(steps)
        self.setFixedHeight(len(steps) * 30 + 10)

    def set_step(self, idx: int, status: str):
        if 0 <= idx < len(self.statuses):
            self.statuses[idx] = status
            self.update()

    def paintEvent(self, event):
        w, h = self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        y = 5
        for i, label in enumerate(self.steps):
            status = self.statuses[i]
            if status == "done":
                icon, color = "✓", GREEN
            elif status == "active":
                icon, color = "◎", GOLD
            elif status == "error":
                icon, color = "✗", RED
            else:
                icon, color = "○", TEXT_DIM

            p.setFont(font_mono(10))
            p.setPen(qcol(color, 200))
            p.drawText(4, y, 20, 24, Qt.AlignmentFlag.AlignCenter, icon)

            p.setFont(font_mono(8, bold=False))
            alpha = 180 if status != "pending" else 100
            p.setPen(qcol(TEXT, alpha))
            p.drawText(28, y, w - 32, 24,
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       label)
            y += 30

        p.end()


# ═══════════════════════════════════════════════════════════════════════════════
# SETUP WIZARD PAGE
# ═══════════════════════════════════════════════════════════════════════════════

class WizardPage(QWidget):
    """Base class for wizard pages."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(8)

        self.title_label = QLabel(title)
        self.title_label.setFont(font_mono(11))
        self.title_label.setStyleSheet(f"color: {GOLD}; background: transparent;")
        self.layout.addWidget(self.title_label)

        self.desc_label = QLabel()
        self.desc_label.setFont(font_mono(8, bold=False))
        self.desc_label.setStyleSheet(f"color: {TEXT_DIM}; background: transparent;")
        self.desc_label.setWordWrap(True)
        self.layout.addWidget(self.desc_label)

    def add_widget(self, w):
        self.layout.addWidget(w)

    def add_stretch(self):
        self.layout.addStretch()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN INSTALLER WINDOW
# ═══════════════════════════════════════════════════════════════════════════════

class InstallerWindow(QMainWindow):
    """Complete setup wizard for Elivea."""

    log_signal = Signal(str, str)  # msg, color
    step_signal = Signal(int, str)  # step_idx, status
    progress_signal = Signal(float)  # 0.0 - 1.0
    next_page_signal = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Elívea — Setup Wizard")
        self.setMinimumSize(780, 620)
        self.resize(820, 660)
        self.setStyleSheet(f"background: {BG}; color: {TEXT};")

        self._project_dir = self._find_project_dir()
        self._installing = False
        self._current_page = 0

        # Connect signals
        self.log_signal.connect(self._do_log)
        self.step_signal.connect(lambda i, s: self.steps.set_step(i, s))
        self.progress_signal.connect(self.progress.set_progress)
        self.next_page_signal.connect(self._next_page)

        self._build_ui()

    def _find_project_dir(self) -> Path:
        p = Path(__file__).resolve().parent.parent
        if (p / "main.py").exists():
            return p
        return Path(os.getcwd())

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 12, 20, 12)
        root.setSpacing(8)

        # ── Header ──
        hdr = QHBoxLayout()
        self.circle = MagicCircle()
        hdr.addWidget(self.circle)

        title_col = QVBoxLayout()
        title = QLabel("Elívea")
        title.setFont(font_mono(16))
        title.setStyleSheet(f"color: {GOLD}; background: transparent;")
        title_col.addWidget(title)

        sub = QLabel("＜Elívea＞ — Setup Wizard")
        sub.setFont(font_mono(9, bold=False))
        sub.setStyleSheet(f"color: {TEXT_DIM}; background: transparent;")
        title_col.addWidget(sub)

        self.page_title = QLabel("Bem-vindo ao assistente de instalação")
        self.page_title.setFont(font_mono(10))
        self.page_title.setStyleSheet(f"color: {TEXT}; background: transparent;")
        title_col.addWidget(self.page_title)
        title_col.addStretch()

        hdr.addLayout(title_col, stretch=1)
        root.addLayout(hdr)

        # ── Steps ──
        self.steps = StepIndicator([
            "Verificar sistema",
            "Instalar dependências",
            "Configurar API keys",
            "Selecionar voz",
            "Criar atalhos",
            "Testar e iniciar",
        ])
        root.addWidget(self.steps)

        # ── Progress ──
        self.progress = ProgressBar()
        root.addWidget(self.progress)

        # ── Page stack ──
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background: {PANEL}; border: 1px solid {BORDER}; border-radius: 6px;")
        self._build_pages()
        root.addWidget(self.stack, stretch=1)

        # ── Log ──
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(font_mono(7, bold=False))
        self.log.setMaximumHeight(100)
        self.log.setStyleSheet(f"""
            QTextEdit {{
                background: {PANEL2}; color: {TEXT_DIM};
                border: 1px solid {BORDER}; border-radius: 4px;
                padding: 4px;
            }}
        """)
        root.addWidget(self.log)

        # ── Buttons ──
        btn_row = QHBoxLayout()

        self.btn_back = QPushButton("← Voltar")
        self.btn_back.setFont(font_mono(9))
        self.btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {TEXT_DIM};
                           border: 1px solid {BORDER}; border-radius: 6px;
                           padding: 8px 16px; }}
            QPushButton:hover {{ background: {GHOST}; color: {TEXT}; }}
        """)
        self.btn_back.clicked.connect(self._prev_page)
        self.btn_back.setEnabled(False)
        btn_row.addWidget(self.btn_back)

        btn_row.addStretch()

        self.btn_next = QPushButton("Próximo →")
        self.btn_next.setFont(font_mono(9))
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.setStyleSheet(f"""
            QPushButton {{ background: {PRI}; color: {BG};
                           border: none; border-radius: 6px;
                           padding: 8px 24px; font-weight: bold; }}
            QPushButton:hover {{ background: {ACC}; }}
            QPushButton:disabled {{ background: {GHOST}; color: {TEXT_DIM}; }}
        """)
        self.btn_next.clicked.connect(self._next_page)
        btn_row.addWidget(self.btn_next)

        root.addLayout(btn_row)

    def _build_pages(self):
        # Page 0: Welcome
        p0 = WizardPage("Passo 1/6 — Verificar Sistema")
        p0.desc_label.setText(
            "O assistente vai verificar se seu computador tem tudo necessário para rodar o Elívea."
        )

        self.sys_info = QLabel("Clique 'Próximo' para começar a verificação...")
        self.sys_info.setFont(font_mono(8, bold=False))
        self.sys_info.setStyleSheet(f"color: {TEXT_MED}; background: transparent;")
        self.sys_info.setWordWrap(True)
        p0.add_widget(self.sys_info)
        p0.add_stretch()
        self.stack.addWidget(p0)

        # Page 1: Install dependencies
        p1 = WizardPage("Passo 2/6 — Instalar Dependências")
        p1.desc_label.setText(
            "O assistente vai instalar automaticamente todos os componentes necessários."
        )

        self.dep_info = QLabel("Aguardando verificação do sistema...")
        self.dep_info.setFont(font_mono(8, bold=False))
        self.dep_info.setStyleSheet(f"color: {TEXT_MED}; background: transparent;")
        self.dep_info.setWordWrap(True)
        p1.add_widget(self.dep_info)
        p1.add_stretch()
        self.stack.addWidget(p1)

        # Page 2: API Keys
        p2 = WizardPage("Passo 3/6 — Configurar Chaves de API")
        p2.desc_label.setText(
            "Para a IA funcionar, você precisa de uma chave de API gratuita. "
            "A mais fácil é do Groq (gratuita, sem cartão de crédito)."
        )

        # Groq key
        groq_label = QLabel("GROQ API KEY (obrigatória — gratuita):")
        groq_label.setFont(font_mono(8))
        groq_label.setStyleSheet(f"color: {GREEN}; background: transparent;")
        p2.add_widget(groq_label)

        groq_row = QHBoxLayout()
        self.groq_input = QLineEdit()
        self.groq_input.setPlaceholderText("gsk_... (cole sua chave aqui)")
        self.groq_input.setFont(font_mono(8, bold=False))
        self.groq_input.setStyleSheet(f"""
            QLineEdit {{ background: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER};
                         border-radius: 4px; padding: 6px; }}
        """)
        groq_row.addWidget(self.groq_input)

        groq_help = QPushButton("🔗 Obter-grátis")
        groq_help.setFont(font_mono(7))
        groq_help.setCursor(Qt.CursorShape.PointingHandCursor)
        groq_help.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {BLUE};
                           border: 1px solid {BLUE}; border-radius: 4px; padding: 6px 10px; }}
            QPushButton:hover {{ background: {BLUE}; color: {WHITE}; }}
        """)
        groq_help.clicked.connect(lambda: self._open_url("https://console.groq.com/keys"))
        groq_row.addWidget(groq_help)
        p2.add_layout(groq_row)

        self.groq_status = QLabel("")
        self.groq_status.setFont(font_mono(7, bold=False))
        self.groq_status.setStyleSheet(f"color: {TEXT_DIM}; background: transparent;")
        p2.add_widget(self.groq_status)

        # Gemini key (optional)
        gemini_label = QLabel("GEMINI API KEY (opcional — gratuita):")
        gemini_label.setFont(font_mono(8))
        gemini_label.setStyleSheet(f"color: {BLUE}; background: transparent;")
        p2.add_widget(gemini_label)

        gemini_row = QHBoxLayout()
        self.gemini_input = QLineEdit()
        self.gemini_input.setPlaceholderText("AIza... (opcional, para backup)")
        self.gemini_input.setFont(font_mono(8, bold=False))
        self.gemini_input.setStyleSheet(f"""
            QLineEdit {{ background: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER};
                         border-radius: 4px; padding: 6px; }}
        """)
        gemini_row.addWidget(self.gemini_input)

        gemini_help = QPushButton("🔗 Obter-grátis")
        gemini_help.setFont(font_mono(7))
        gemini_help.setCursor(Qt.CursorShape.PointingHandCursor)
        gemini_help.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {BLUE};
                           border: 1px solid {BLUE}; border-radius: 4px; padding: 6px 10px; }}
            QPushButton:hover {{ background: {BLUE}; color: {WHITE}; }}
        """)
        gemini_help.clicked.connect(lambda: self._open_url("https://aistudio.google.com/apikey"))
        gemini_row.addWidget(gemini_help)
        p2.add_layout(gemini_row)

        p2.add_stretch()
        self.stack.addWidget(p2)

        # Page 3: Voice selection
        p3 = WizardPage("Passo 4/6 — Selecionar Voz")
        p3.desc_label.setText(
            "Escolha a voz do Elívea. Você pode mudar depois nas configurações."
        )

        voices = [
            ("raphael", "Elívea — Voz Feminina Calma (Recomendado)", "pt-BR-FranciscaNeural"),
            ("raphael_natural", "Natural — Voz Feminina Natural", "pt-BR-ThalitaMultilingualNeural"),
            ("jarvis", "Jarvis — Voz Masculina Formal", "pt-BR-AntonioNeural"),
        ]

        for key, label, voice_id in voices:
            btn = QPushButton(f"  {label}")
            btn.setFont(font_mono(8))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER};
                    border-radius: 6px; padding: 10px; text-align: left;
                }}
                QPushButton:hover {{ background: {GHOST}; border-color: {PRI}; }}
                QPushButton:checked {{ background: {GHOST}; border-color: {PRI}; color: {GOLD}; }}
            """)
            btn.clicked.connect(lambda checked, k=key: self._select_voice(k))
            p3.add_widget(btn)

        self._selected_voice = "raphael"

        # Wake word
        wake_label = QLabel("\nPalavra de ativação:")
        wake_label.setFont(font_mono(8))
        wake_label.setStyleSheet(f"color: {TEXT_MED}; background: transparent;")
        p3.add_widget(wake_label)

        self.wake_input = QLineEdit("Ok Elívea")
        self.wake_input.setFont(font_mono(8, bold=False))
        self.wake_input.setStyleSheet(f"""
            QLineEdit {{ background: {PANEL2}; color: {TEXT}; border: 1px solid {BORDER};
                         border-radius: 4px; padding: 6px; }}
        """)
        p3.add_widget(self.wake_input)

        p3.add_stretch()
        self.stack.addWidget(p3)

        # Page 4: Shortcuts
        p4 = WizardPage("Passo 5/6 — Criar Atalhos")
        p4.desc_label.setText(
            "O assistente vai criar atalhos na Área de Trabalho para facilitar o acesso."
        )

        self.shortcut_info = QLabel("Clique 'Próximo' para criar os atalhos...")
        self.shortcut_info.setFont(font_mono(8, bold=False))
        self.shortcut_info.setStyleSheet(f"color: {TEXT_MED}; background: transparent;")
        self.shortcut_info.setWordWrap(True)
        p4.add_widget(self.shortcut_info)
        p4.add_stretch()
        self.stack.addWidget(p4)

        # Page 5: Test & Launch
        p5 = WizardPage("Passo 6/6 — Testar e Iniciar")
        p5.desc_label.setText(
            "Tudo pronto! O assistente vai testar o sistema de voz e iniciar o Elívea."
        )

        self.test_info = QLabel("Clique 'Instalar e Iniciar' para finalizar...")
        self.test_info.setFont(font_mono(8, bold=False))
        self.test_info.setStyleSheet(f"color: {TEXT_MED}; background: transparent;")
        self.test_info.setWordWrap(True)
        p5.add_widget(self.test_info)
        p5.add_stretch()
        self.stack.addWidget(p5)

    # ── Navigation ───────────────────────────────────────────────────────────

    def _next_page(self):
        page = self._current_page

        # Execute page actions
        if page == 0:
            self._run_check_system()
        elif page == 1:
            self._run_install_deps()
        elif page == 2:
            self._run_save_keys()
        elif page == 3:
            self._run_save_voice()
        elif page == 4:
            self._run_create_shortcuts()
        elif page == 5:
            self._run_final_launch()
            return

        self.btn_back.setEnabled(True)

    def _prev_page(self):
        if self._current_page > 0:
            self._current_page -= 1
            self.stack.setCurrentIndex(self._current_page)
            self.circle.set_progress(self._current_page / 5.0)
            self.btn_back.setEnabled(self._current_page > 0)
            self._update_page_title()

    def _go_to_page(self, idx: int):
        self._current_page = idx
        self.stack.setCurrentIndex(idx)
        self.circle.set_progress(idx / 5.0)
        self._update_page_title()

    def _update_page_title(self):
        titles = [
            "Verificando seu sistema...",
            "Instalando componentes...",
            "Configurando chaves de API...",
            "Escolhendo a voz...",
            "Criando atalhos...",
            "Teste final e inicialização...",
        ]
        if self._current_page < len(titles):
            self.page_title.setText(titles[self._current_page])

    # ── Page Actions ─────────────────────────────────────────────────────────

    def _run_check_system(self):
        self.steps.set_step(0, "active")
        self.progress.set_progress(0.05)
        self.btn_next.setEnabled(False)

        def worker():
            info = []

            # Python
            py_ver = sys.version.split()[0]
            py_ok = sys.version_info >= (3, 10)
            info.append(f"{'✓' if py_ok else '✗'} Python {py_ver} {'(OK)' if py_ok else '(requer 3.10+)'}")

            # pip
            try:
                import pip
                info.append("✓ pip disponível")
            except ImportError:
                info.append("✗ pip não encontrado")

            # Audio device
            try:
                import sounddevice as sd
                devices = sd.query_devices()
                inputs = [d for d in devices if d.get('max_input_channels', 0) > 0]
                info.append(f"✓ {len(inputs)} microfone(s) detectado(s)")
            except Exception:
                info.append("⚠ sounddevice não instalado (será instalado)")

            # Check .env
            env_path = self._project_dir / ".env"
            if env_path.exists():
                content = env_path.read_text(encoding="utf-8", errors="replace")
                has_groq = any("GROQ_API_KEY" in l and "=" in l and l.split("=", 1)[1].strip()
                               for l in content.splitlines() if l.strip() and not l.startswith("#"))
                info.append(f"{'✓' if has_groq else '⚠'} .env {'com chaves' if has_groq else 'sem chaves de API'}")
            else:
                info.append("⚠ .env não será criado agora")

            # main.py
            info.append(f"{'✓' if (self._project_dir / 'main.py').exists() else '✗'} Arquivos do projeto")

            self.sys_info.setText("\n".join(info))
            self.steps.set_step(0, "done")
            self.progress.set_progress(0.2)
            self.btn_next.setEnabled(True)
            self._log(f"Sistema verificado: Python {py_ver}", GREEN if py_ok else RED)

        threading.Thread(target=worker, daemon=True).start()

    def _run_install_deps(self):
        self.steps.set_step(1, "active")
        self.progress.set_progress(0.25)
        self.btn_next.setEnabled(False)

        def worker():
            self._log("Verificando dependências...", GOLD)

            # All required packages
            packages = {
                "PySide6": "PySide6",
                "requests": "requests",
                "numpy": "numpy",
                "sounddevice": "sounddevice",
                "pydub": "pydub",
                "scipy": "scipy",
                "edge_tts": "edge-tts",
                "groq": "groq",
                "google.genai": "google-genai",
                "dotenv": "python-dotenv",
                "imageio_ffmpeg": "imageio-ffmpeg",
                "psutil": "psutil",
                "pyautogui": "pyautogui",
                "keyboard": "keyboard",
                "pydantic": "pydantic",
                "ddgs": "duckduckgo-search",
                "speech_recognition": "SpeechRecognition",
            }

            # Check which are missing
            missing = []
            installed = []
            for mod, pkg in packages.items():
                try:
                    __import__(mod)
                    installed.append(pkg)
                except ImportError:
                    missing.append(pkg)

            self.dep_info.setText(
                f"✓ {len(installed)} pacotes já instalados\n"
                f"{'⚠ ' + str(len(missing)) + ' pacotes faltando' if missing else '✓ Todas as dependências OK'}"
            )
            self._log(f"{len(installed)} pacotes OK, {len(missing)} faltando", GREEN if not missing else GOLD)

            if missing:
                self._log(f"Instalando {len(missing)} pacotes...", GOLD)
                self.progress.set_progress(0.3)

                cmd = [sys.executable, "-m", "pip", "install", "--quiet",
                       "--disable-pip-version-check"] + missing
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    if result.returncode == 0:
                        self._log(f"✓ {len(missing)} pacotes instalados com sucesso", GREEN)
                        self.dep_info.setText(f"✓ Todas as {len(packages)} dependências instaladas!")
                    else:
                        # Retry with --break-system-packages
                        if "externally-managed" in (result.stderr or ""):
                            cmd.append("--break-system-packages")
                            result2 = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                            if result2.returncode == 0:
                                self._log("✓ Instalado (break-system-packages)", GREEN)
                            else:
                                self._log(f"⚠ Alguns pacotes podem ter falhado", RED)
                        else:
                            self._log(f"⚠ pip retornou erro (código {result.returncode})", RED)
                except subprocess.TimeoutExpired:
                    self._log("⚠ Timeout na instalação (10min)", RED)
                except Exception as e:
                    self._log(f"✗ Erro: {e}", RED)

            self.steps.set_step(1, "done")
            self.progress.set_progress(0.5)
            self.btn_next.setEnabled(True)

        threading.Thread(target=worker, daemon=True).start()

    def _run_save_keys(self):
        groq_key = self.groq_input.text().strip()
        gemini_key = self.gemini_input.text().strip()

        if not groq_key:
            self.groq_status.setText("⚠ Groq API Key é obrigatória! Obtenha gratuitamente em console.groq.com")
            self.groq_status.setStyleSheet(f"color: {RED}; background: transparent;")
            return

        if not groq_key.startswith("gsk_"):
            self.groq_status.setText("⚠ Chave inválida. Deve começar com 'gsk_'")
            self.groq_status.setStyleSheet(f"color: {RED}; background: transparent;")
            return

        self.groq_status.setText("✓ Chave válida!")
        self.groq_status.setStyleSheet(f"color: {GREEN}; background: transparent;")

        # Save to .env
        env_path = self._project_dir / ".env"
        env_content = f"# Elívea — Environment Variables\n"
        env_content += f"# Generated by Setup Wizard\n\n"
        env_content += f"GROQ_API_KEY={groq_key}\n"
        if gemini_key:
            env_content += f"GEMINI_API_KEY={gemini_key}\n"
        env_content += f"\n# Voice settings\n"
        env_content += f"VOICE_KEY={self._selected_voice}\n"
        env_content += f"WAKE_WORD={self.wake_input.text().strip()}\n"

        env_path.write_text(env_content, encoding="utf-8")
        self._log(f"✓ .env salvo com chaves de API", GREEN)
        self._go_to_page(3)

    def _run_save_voice(self):
        # Update .env with voice selection
        env_path = self._project_dir / ".env"
        if env_path.exists():
            content = env_path.read_text(encoding="utf-8")
            # Update VOICE_KEY
            if "VOICE_KEY=" in content:
                lines = content.splitlines()
                for i, line in enumerate(lines):
                    if line.startswith("VOICE_KEY="):
                        lines[i] = f"VOICE_KEY={self._selected_voice}"
                content = "\n".join(lines)
            else:
                content += f"\nVOICE_KEY={self._selected_voice}\n"

            # Update WAKE_WORD
            wake = self.wake_input.text().strip()
            if "WAKE_WORD=" in content:
                lines = content.splitlines()
                for i, line in enumerate(lines):
                    if line.startswith("WAKE_WORD="):
                        lines[i] = f"WAKE_WORD={wake}"
                content = "\n".join(lines)
            else:
                content += f"WAKE_WORD={wake}\n"

            env_path.write_text(content, encoding="utf-8")

        self._log(f"✓ Voz selecionada: {self._selected_voice}", GREEN)
        self._log(f"✓ Palavra de ativação: {self.wake_input.text().strip()}", GREEN)
        self._go_to_page(4)

    def _run_create_shortcuts(self):
        self.steps.set_step(4, "active")
        self.progress.set_progress(0.7)
        self.btn_next.setEnabled(False)

        def worker():
            created = []

            # Find desktop
            desktop = Path.home() / "Desktop"
            if not desktop.exists():
                desktop = Path.home() / "OneDrive" / "Desktop"

            if not desktop.exists():
                self.shortcut_info.setText("⚠ Área de Trabalho não encontrada")
                self.steps.set_step(4, "error")
                self.btn_next.setEnabled(True)
                return

            # Find correct Python
            python_exe = sys.executable
            # Prefer uv python if available
            uv_python = Path.home() / "AppData/Roaming/uv/python/cpython-3.11-windows-x86_64-none/python.exe"
            if uv_python.exists():
                python_exe = str(uv_python)

            # AI shortcut
            ai_bat = desktop / "Elívea AI.bat"
            ai_bat.write_text(
                f'@echo off\r\ntitle Elívea AI\r\ncd /d "{self._project_dir}"\r\n'
                f'"{python_exe}" main.py\r\nif errorlevel 1 pause\r\n',
                encoding="ascii", errors="replace"
            )
            created.append(str(ai_bat))

            # Installer shortcut
            inst_bat = desktop / "Instalador Elívea.bat"
            inst_bat.write_text(
                f'@echo off\r\ntitle Instalador Elívea\r\ncd /d "{self._project_dir}"\r\n'
                f'"{python_exe}" installer.py\r\nif errorlevel 1 pause\r\n',
                encoding="ascii", errors="replace"
            )
            created.append(str(inst_bat))

            self.shortcut_info.setText(
                f"✓ Atalhos criados na Área de Trabalho:\n"
                f"  • Elívea AI.bat\n"
                f"  • Instalador Elívea.bat"
            )
            self._log(f"✓ Atalhos criados: {len(created)}", GREEN)
            self.steps.set_step(4, "done")
            self.progress.set_progress(0.9)
            self.btn_next.setEnabled(True)

        threading.Thread(target=worker, daemon=True).start()

    def _run_final_launch(self):
        self.steps.set_step(5, "active")
        self.progress.set_progress(0.95)
        self.btn_next.setEnabled(False)
        self.btn_next.setText("🚀 Instalar e Iniciar")

        def worker():
            self._log("Testando sistema de voz...", GOLD)
            self.test_info.setText("Testando síntese de voz...")

            # Test TTS
            try:
                import asyncio
                import edge_tts

                async def test_tts():
                    comm = edge_tts.Communicate("Teste", "pt-BR-FranciscaNeural")
                    test_path = self._project_dir / "temp" / "test_tts.mp3"
                    test_path.parent.mkdir(exist_ok=True)
                    await comm.save(str(test_path))
                    return test_path.exists()

                tts_ok = asyncio.run(test_tts())
                if tts_ok:
                    self._log("✓ Síntese de voz OK", GREEN)
                    self.test_info.setText("✓ Voz funcionando!")
                else:
                    self._log("⚠ Síntese de voz falhou", RED)
            except Exception as e:
                self._log(f"⚠ Teste de voz: {e}", RED)

            # Test mic
            try:
                import sounddevice as sd
                devices = sd.query_devices()
                inputs = [d for d in devices if d.get('max_input_channels', 0) > 0]
                if inputs:
                    self._log(f"✓ Microfone detectado: {inputs[0]['name']}", GREEN)
                else:
                    self._log("⚠ Nenhum microfone detectado", RED)
            except Exception as e:
                self._log(f"⚠ Teste de mic: {e}", RED)

            self.steps.set_step(5, "done")
            self.progress.set_progress(1.0)

            # Launch AI
            self._log("Iniciando Elívea...", GOLD)
            self.test_info.setText("🚀 Iniciando Elívea...")

            try:
                main_py = self._project_dir / "main.py"
                if main_py.exists():
                    creationflags = 0
                    if os.name == "nt":
                        creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | \
                                        getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                    subprocess.Popen(
                        [sys.executable, str(main_py)],
                        cwd=str(self._project_dir),
                        creationflags=creationflags,
                        close_fds=True,
                    )
                    self._log("✓ Elivea iniciado!", GREEN)
                    self.test_info.setText(
                        "🎉 Instalação concluída!\n\n"
                        "O Elívea foi iniciado.\n"
                        "Use 'Ok Elívea' para ativar por voz.\n"
                        "Ou digite diretamente na caixa de texto."
                    )
                else:
                    self._log("✗ main.py não encontrado", RED)
            except Exception as e:
                self._log(f"✗ Erro ao iniciar: {e}", RED)

        threading.Thread(target=worker, daemon=True).start()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _select_voice(self, key: str):
        self._selected_voice = key

    def _open_url(self, url: str):
        import webbrowser
        webbrowser.open(url)

    def _log(self, msg: str, color: str = TEXT_DIM):
        self.log_signal.emit(msg, color)

    def _do_log(self, msg: str, color: str):
        self.log.append(f'<span style="color:{color}">{msg}</span>')
        sb = self.log.verticalScrollBar()
        sb.setValue(sb.maximum())


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Instalador Elívea")
    app.setStyleSheet(f"background: {BG}; color: {TEXT};")

    icon_path = Path(__file__).resolve().parent.parent / "elvea.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = InstallerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
