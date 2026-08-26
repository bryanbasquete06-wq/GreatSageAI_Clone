"""
Great Sage AI — Installer GUI
===============================
Cyberpunk-themed installer with animated magic circle, step progress,
and real dependency download.
"""

from __future__ import annotations

import math
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor, QFont, QPainter, QPainterPath, QPen, QRadialGradient, QBrush,
)
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMainWindow, QPushButton, QTextEdit,
    QVBoxLayout, QWidget, QSizePolicy,
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
# INSTALLER MAGIC CIRCLE
# ═══════════════════════════════════════════════════════════════════════════════

class InstallerCircle(QWidget):
    """Animated magic circle for installer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(180, 180)
        self.setMaximumSize(220, 220)
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
        pen_rune = QPen(qcol(GOLD, 180), 1.0)
        p.setPen(pen_rune)
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
                   Qt.AlignmentFlag.AlignCenter, "＜大賢者＞")

        p.end()


# ═══════════════════════════════════════════════════════════════════════════════
# STEP ROW
# ═══════════════════════════════════════════════════════════════════════════════

class StepRow(QWidget):
    """Single installation step with icon, label, and status."""

    def __init__(self, icon: str, label: str, parent=None):
        super().__init__(parent)
        self.icon = icon
        self.label = label
        self.status = "pending"  # pending | active | done | error
        self.setFixedHeight(28)

    def set_status(self, status: str):
        self.status = status
        self.update()

    def paintEvent(self, event):
        w, h = self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Icon
        if self.status == "done":
            icon = "✓"
            color = GREEN
        elif self.status == "active":
            icon = "◎"
            color = GOLD
        elif self.status == "error":
            icon = "✗"
            color = RED
        else:
            icon = "○"
            color = TEXT_DIM

        p.setFont(font_mono(10))
        p.setPen(qcol(color, 200))
        p.drawText(4, 4, 20, 20, Qt.AlignmentFlag.AlignCenter, icon)

        # Label
        p.setFont(font_mono(8, bold=False))
        p.setPen(qcol(TEXT, 180 if self.status != "pending" else 100))
        p.drawText(28, 4, w - 32, 20, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   self.label)

        p.end()


# ═══════════════════════════════════════════════════════════════════════════════
# GOLDEN PROGRESS BAR
# ═══════════════════════════════════════════════════════════════════════════════

class GoldenProgressBar(QWidget):
    """Animated progress bar with gold gradient."""

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

        # Background
        p.setPen(QPen(qcol(BORDER, 100), 1))
        p.setBrush(qcol(GHOST, 80))
        p.drawRoundedRect(1, 1, w - 2, h - 2, 6, 6)

        # Fill
        fill_w = int((w - 4) * self._progress)
        if fill_w > 0:
            grad = QLinearGradient(0, 0, fill_w, 0)
            grad.setColorAt(0, qcol("#b8860b", 200))
            grad.setColorAt(0.5, qcol(PRI, 220))
            grad.setColorAt(1, qcol("#b8860b", 200))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(2, 2, fill_w, h - 4, 5, 5)

            # Shimmer
            self._shimmer += 0.03
            shimmer_x = int(fill_w * ((math.sin(self._shimmer) + 1) / 2))
            if shimmer_x > 5:
                p.setBrush(qcol(WHITE, 40))
                p.drawRect(shimmer_x - 3, 2, 6, h - 4)

        # Percentage text
        pct = f"{int(self._progress * 100)}%"
        p.setFont(font_mono(7))
        p.setPen(qcol(WHITE, 220))
        p.drawText(0, 0, w, h, Qt.AlignmentFlag.AlignCenter, pct)

        p.end()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN INSTALLER WINDOW
# ═══════════════════════════════════════════════════════════════════════════════

class InstallerWindow(QMainWindow):
    """Main installer window with cyberpunk theme."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Instalador Great Sage AI")
        self.setMinimumSize(700, 550)
        self.resize(750, 600)
        self.setStyleSheet(f"background: {BG}; color: {TEXT};")

        self._installing = False
        self._project_dir = self._find_project_dir()

        self._build_ui()

    def _find_project_dir(self) -> Path:
        """Find the project directory."""
        # From this file: ui/installer_gui.py -> project root
        p = Path(__file__).resolve().parent.parent
        if (p / "main.py").exists():
            return p
        # Fallback
        return Path("F:/programação/J.A.R.V.I.S/GreatSageAI_Clone")

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 15, 20, 15)
        root.setSpacing(10)

        # ── Header ──
        header = QLabel("INSTALADOR GREAT SAGE AI")
        header.setFont(font_mono(14))
        header.setStyleSheet(f"color: {GOLD}; background: transparent;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(header)

        subtitle = QLabel("＜大賢者＞ — Instalação Automática")
        subtitle.setFont(font_mono(9, bold=False))
        subtitle.setStyleSheet(f"color: {TEXT_DIM}; background: transparent;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(subtitle)

        # ── Directory display ──
        dir_label = QLabel(f"Diretório: {self._project_dir}")
        dir_label.setFont(font_mono(8, bold=False))
        dir_label.setStyleSheet(f"""
            color: {TEXT_MED}; background: {PANEL}; border: 1px solid {BORDER};
            border-radius: 4px; padding: 6px 12px;
        """)
        root.addWidget(dir_label)

        # ── Magic circle + Steps ──
        mid = QWidget()
        mid_layout = QVBoxLayout(mid)
        mid_layout.setContentsMargins(0, 0, 0, 0)

        # Circle
        self.circle = InstallerCircle()
        circle_row = QVBoxLayout()
        circle_row.addWidget(self.circle, alignment=Qt.AlignmentFlag.AlignCenter)
        mid_layout.addLayout(circle_row)

        # Steps
        self.steps = [
            StepRow("📁", "Preparar ambiente de execução"),
            StepRow("📦", "Instalar dependências (pip)"),
            StepRow("🔗", "Vincular ao sistema"),
            StepRow("🔒", "Configurar protocolos de segurança"),
            StepRow("✅", "Finalizar configuração"),
        ]
        for step in self.steps:
            mid_layout.addWidget(step)

        root.addWidget(mid, stretch=1)

        # ── Progress bar ──
        self.progress = GoldenProgressBar()
        root.addWidget(self.progress)

        # ── Log console ──
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(font_mono(8, bold=False))
        self.log.setMaximumHeight(120)
        self.log.setStyleSheet(f"""
            QTextEdit {{
                background: {PANEL}; color: {TEXT_DIM};
                border: 1px solid {BORDER}; border-radius: 4px;
                padding: 6px;
            }}
        """)
        root.addWidget(self.log)

        # ── Buttons ──
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_verify = QPushButton("🔍 Verificar")
        self.btn_verify.setFont(font_mono(10))
        self.btn_verify.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_verify.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {PRI};
                           border: 2px solid {PRI}; border-radius: 8px;
                           padding: 10px 24px; }}
            QPushButton:hover {{ background: {GHOST}; }}
        """)
        self.btn_verify.clicked.connect(self._on_verify)
        btn_layout.addWidget(self.btn_verify)

        self.btn_install = QPushButton("⚡ Instalar")
        self.btn_install.setFont(font_mono(10))
        self.btn_install.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_install.setStyleSheet(f"""
            QPushButton {{ background: {PRI}; color: {BG};
                           border: none; border-radius: 8px;
                           padding: 10px 30px; font-weight: bold; }}
            QPushButton:hover {{ background: {ACC}; }}
        """)
        self.btn_install.clicked.connect(self._on_install)
        btn_layout.addWidget(self.btn_install)

        self.btn_cancel = QPushButton("✕ Cancelar")
        self.btn_cancel.setFont(font_mono(10))
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {RED};
                           border: 2px solid {RED}; border-radius: 8px;
                           padding: 10px 24px; }}
            QPushButton:hover {{ background: {RED}; color: {WHITE}; }}
        """)
        self.btn_cancel.clicked.connect(self.close)
        btn_layout.addWidget(self.btn_cancel)

        root.addWidget(btn_row)

    # ── Logging ─────────────────────────────────────────────────────────────

    def _log(self, msg: str, color: str = TEXT_DIM):
        self.log.append(f'<span style="color:{color}">{msg}</span>')
        # Auto-scroll
        sb = self.log.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ── Verify ──────────────────────────────────────────────────────────────

    def _on_verify(self):
        self._log("🔍 Verificando sistema...", GOLD)
        self.steps[0].set_status("active")
        self.progress.set_progress(0.1)

        # Check Python
        self._log(f"  ✓ Python: {sys.version.split()[0]}", GREEN)
        self.steps[0].set_status("done")
        self.progress.set_progress(0.2)

        # Check PySide6
        self.steps[1].set_status("active")
        try:
            import PySide6
            self._log(f"  ✓ PySide6: {PySide6.__version__}", GREEN)
        except ImportError:
            self._log("  ✗ PySide6 não encontrado", RED)
        self.steps[1].set_status("done")
        self.progress.set_progress(0.4)

        # Check .env
        self.steps[3].set_status("active")
        env_path = self._project_dir / ".env"
        if env_path.exists():
            content = env_path.read_text()
            keys = [line.split("=")[0] for line in content.splitlines()
                    if line.strip() and not line.startswith("#") and "=" in line]
            self._log(f"  ✓ .env: {len(keys)} chaves configuradas", GREEN)
        else:
            self._log("  ✗ .env não encontrado", RED)
        self.steps[3].set_status("done")
        self.progress.set_progress(0.8)

        # Check main.py
        self.steps[4].set_status("active")
        if (self._project_dir / "main.py").exists():
            self._log(f"  ✓ main.py encontrado", GREEN)
        else:
            self._log(f"  ✗ main.py não encontrado", RED)
        self.steps[4].set_status("done")
        self.progress.set_progress(1.0)

        self._log("✅ Verificação concluída!", GREEN)

    # ── Install ─────────────────────────────────────────────────────────────

    def _on_install(self):
        if self._installing:
            return
        self._installing = True
        self.btn_install.setEnabled(False)
        self._log("⚡ Iniciando instalação...", GOLD)

        thread = threading.Thread(target=self._do_install, daemon=True)
        thread.start()

    def _do_install(self):
        base = self._project_dir

        try:
            # Step 1: Prepare environment
            self._step_set(0, "active")
            self._step_log("📁 Preparando ambiente...")
            for d in ["config", "memory", "logs", "modules"]:
                (base / d).mkdir(exist_ok=True)
            self._step_log("  ✓ Pastas criadas", GREEN)
            self._step_set(0, "done")
            self._progress_set(0.15)

            # Step 2: Install dependencies
            self._step_set(1, "active")
            self._step_log("📦 Instalando dependências...")

            packages = [
                "PySide6", "psutil", "requests", "numpy",
                "edge-tts", "groq", "google-genai", "python-dotenv",
                "duckduckgo-search",
            ]

            # Find which are missing
            missing = []
            for pkg in packages:
                mod_name = pkg.replace("-", "_").replace("python-", "")
                if pkg == "google-genai":
                    mod_name = "google.genai"
                elif pkg == "python-dotenv":
                    mod_name = "dotenv"
                elif pkg == "edge-tts":
                    mod_name = "edge_tts"
                elif pkg == "duckduckgo-search":
                    mod_name = "ddgs"
                try:
                    __import__(mod_name)
                except ImportError:
                    missing.append(pkg)

            if missing:
                self._step_log(f"  Instalando {len(missing)} pacote(s): {', '.join(missing)}")
                cmd = [sys.executable, "-m", "pip", "install", "--quiet",
                       "--disable-pip-version-check"] + missing
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode == 0:
                    self._step_log(f"  ✓ {len(missing)} pacotes instalados", GREEN)
                else:
                    self._step_log(f"  ⚠ Erro no pip: {result.stderr[-200:]}", RED)
            else:
                self._step_log("  ✓ Todas as dependências já instaladas", GREEN)

            self._step_set(1, "done")
            self._progress_set(0.45)

            # Step 3: Create desktop shortcuts
            self._step_set(2, "active")
            self._step_log("🔗 Criando atalhos na Área de Trabalho...")
            self._create_shortcuts()
            self._step_set(2, "done")
            self._progress_set(0.65)

            # Step 4: Configure security / settings
            self._step_set(3, "active")
            self._step_log("🔒 Configurando protocolos de segurança...")
            settings_path = base / "config" / "settings.json"
            if settings_path.exists():
                import json
                data = json.loads(settings_path.read_text(encoding="utf-8"))
                data["setup_complete"] = True
                settings_path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                                         encoding="utf-8")
                self._step_log("  ✓ settings.json atualizado", GREEN)
            self._step_set(3, "done")
            self._progress_set(0.85)

            # Step 5: Finalize
            self._step_set(4, "active")
            self._step_log("✅ Finalizando...")
            self._step_log("  ✓ Configuração concluída", GREEN)
            self._step_set(4, "done")
            self._progress_set(1.0)

            self._step_log("🎉 Instalação concluída com sucesso!", GREEN)
            self._step_log("   Clique em 'Grande Sabio AI' na Área de Trabalho para iniciar.", GOLD)

        except Exception as e:
            self._step_log(f"❌ Erro: {e}", RED)

        finally:
            self._installing = False
            # Enable button from main thread
            QTimer.singleShot(0, lambda: self.btn_install.setEnabled(True))

    def _create_shortcuts(self):
        """Create .bat shortcuts on desktop."""
        try:
            desktop = Path.home() / "Desktop"
            if not desktop.exists():
                desktop = Path.home() / "OneDrive" / "Desktop"

            base = self._project_dir

            # Find correct python
            python_exe = sys.executable

            # AI shortcut
            ai_bat = desktop / "Grande Sabio AI.bat"
            ai_content = (
                "@echo off\r\n"
                "title Grande Sabio AI\r\n"
                f'cd /d "{base}"\r\n'
                f'"{python_exe}" main.py\r\n'
                "if errorlevel 1 pause\r\n"
            )
            ai_bat.write_bytes(ai_content.encode("ascii", errors="replace"))
            self._step_log(f"  ✓ {ai_bat}", GREEN)

            # Installer shortcut
            inst_bat = desktop / "Instalador Great Sage.bat"
            inst_content = (
                "@echo off\r\n"
                "title Instalador Great Sage\r\n"
                f'cd /d "{base}"\r\n'
                f'"{python_exe}" installer.py\r\n'
                "if errorlevel 1 pause\r\n"
            )
            inst_bat.write_bytes(inst_content.encode("ascii", errors="replace"))
            self._step_log(f"  ✓ {inst_bat}", GREEN)

        except Exception as e:
            self._step_log(f"  ⚠ Erro ao criar atalhos: {e}", RED)

    # ── Thread-safe UI updates ──────────────────────────────────────────────

    def _step_set(self, idx: int, status: str):
        QTimer.singleShot(0, lambda: self.steps[idx].set_status(status))

    def _step_log(self, msg: str, color: str = TEXT_DIM):
        QTimer.singleShot(0, lambda m=msg, c=color: self._log(m, c))

    def _progress_set(self, p: float):
        QTimer.singleShot(0, lambda: self.progress.set_progress(p))


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Instalador Great Sage")
    app.setStyleSheet(f"background: {BG}; color: {TEXT};")

    icon_path = Path(__file__).resolve().parent.parent / "great_sage.ico"
    if icon_path.exists():
        from PySide6.QtGui import QIcon
        app.setWindowIcon(QIcon(str(icon_path)))

    window = InstallerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
