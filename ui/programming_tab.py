"""
Great Sage AI — Programming Tab
================================
Aba integrada na janela principal com:
  • Mini-editor com syntax highlighting
  • Input para tarefas do agente de código
  • Output/terminal integrado
  • Análise rápida de código (AST)
  • Ações rápidas: analisar, executar, refatorar, documentar
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QTextCharFormat, QColor, QSyntaxHighlighter
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QSplitter, QVBoxLayout, QWidget, QFileDialog,
    QTabWidget, QComboBox, QProgressBar,
)


# ---------------------------------------------------------------------------
# Syntax Highlighter (Python-focused)
# ---------------------------------------------------------------------------

_PY_RULES = [
    (r'\b(def|class|if|elif|else|for|while|try|except|finally|with|as|import|from|return|yield|raise|pass|break|continue|and|or|not|is|in|lambda|global|nonlocal|assert|del|async|await)\b', '#ff79c6'),
    (r'\b(True|False|None)\b', '#bd93f9'),
    (r'\b(print|len|range|int|str|float|list|dict|set|tuple|type|isinstance|hasattr|getattr|setattr|super|self|cls)\b', '#50fa7b'),
    (r'"""[\s\S]*?"""', '#f1fa8c'),
    (r"'''[\s\S]*?'''", '#f1fa8c'),
    (r'"[^"]*"', '#f1fa8c'),
    (r"'[^']*'", '#f1fa8c'),
    (r'#[^\n]*', '#6272a4'),
    (r'\b\d+\.?\d*\b', '#bd93f9'),
    (r'(@\w+)', '#ffb86c'),
    (r'(=>|->|\*\*|//|<<|>>|!=|==|<=|>=|\+=|-=|\*=|/=)', '#ff79c6'),
]


class _PyHighlighter(QSyntaxHighlighter):
    def __init__(self, parent):
        super().__init__(parent)
        self._rules = []
        import re
        for pat, color in _PY_RULES:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            self._rules.append((re.compile(pat), fmt))

    def highlightBlock(self, text: str):
        for regex, fmt in self._rules:
            for m in regex.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)


# ---------------------------------------------------------------------------
# Output Panel
# ---------------------------------------------------------------------------

class OutputPanel(QPlainTextEdit):
    """Terminal/read-only output panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(5000)
        self.setFont(QFont("Consolas", 9))
        self.setStyleSheet("""
            QPlainTextEdit {
                background: #0a0a0a; color: #b0b0b0;
                border: 1px solid #333; border-radius: 4px;
                padding: 6px; selection-background-color: #264f78;
            }
        """)

    def append_line(self, text: str, color: str = "#b0b0b0"):
        self.appendHtml(f'<span style="color:{color}">{text}</span>')
        sb = self.verticalScrollBar()
        sb.setValue(sb.maximum())

    def append_html(self, html_text: str):
        self.appendHtml(html_text)
        sb = self.verticalScrollBar()
        sb.setValue(sb.maximum())


# ---------------------------------------------------------------------------
# Mini Code Editor
# ---------------------------------------------------------------------------

class MiniEditor(QPlainTextEdit):
    """Lightweight code editor with syntax highlighting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Consolas", 10))
        self.setTabStopDistance(20)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setStyleSheet("""
            QPlainTextEdit {
                background: #0d1117; color: #c9d1d9;
                border: 1px solid #30363d; border-radius: 4px;
                padding: 8px; selection-background-color: #264f78;
            }
        """)
        self._highlighter = _PyHighlighter(self.document())

    def set_code(self, code: str):
        self.setPlainText(code)

    def get_code(self) -> str:
        return self.toPlainText()


# ---------------------------------------------------------------------------
# Programming Tab Widget
# ---------------------------------------------------------------------------

class ProgrammingTab(QWidget):
    """Aba de programação integrada na janela principal."""

    # Signals
    task_submitted = Signal(str) # agent task text
    code_executed = Signal(str, str) # (code, lang)
    request_analysis = Signal(str) # file path to analyze

    def __init__(self, parent=None):
        super().__init__(parent)
        self._agent_handler = None # set by GreatSageMainWindow
        self._execute_handler = None # set by GreatSageMainWindow
        self._current_file = None
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        # ---- Header with tabs ----
        hdr = QHBoxLayout()
        title = QLabel("PROGRAMAÇÃO")
        title.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        title.setStyleSheet("color: #4fd8ff; background: transparent;")
        hdr.addWidget(title)
        hdr.addStretch()

        self._btn_open = self._make_btn("Abrir", self._open_file)
        self._btn_analyze = self._make_btn("Analisar", self._analyze_current)
        self._btn_run = self._make_btn("Executar", self._run_current)
        self._btn_save = self._make_btn("Salvar", self._save_current)
        for b in [self._btn_open, self._btn_analyze, self._btn_run, self._btn_save]:
            hdr.addWidget(b)
        lay.addLayout(hdr)

        # ---- Splitter: editor top, output bottom ----
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Editor
        self.editor = MiniEditor()
        self.editor.setPlaceholderText(
            "# Cole ou escreva código aqui...\n"
            "# Use o campo abaixo para enviar tarefas ao agente.\n"
        )
        splitter.addWidget(self.editor)

        # Bottom: output + agent input
        bottom = QWidget()
        blay = QVBoxLayout(bottom)
        blay.setContentsMargins(0, 4, 0, 0)
        blay.setSpacing(4)

        self.output = OutputPanel()
        blay.addWidget(self.output, stretch=1)

        # Agent task input
        agent_row = QHBoxLayout()
        agent_lbl = QLabel("Agente:")
        agent_lbl.setStyleSheet("color: #ff79c6; font-weight: bold; font-size: 10px;")
        agent_lbl.setFixedWidth(70)
        agent_row.addWidget(agent_lbl)

        self.agent_input = QLineEdit()
        self.agent_input.setPlaceholderText("Descreva a tarefa para o agente de código...")
        self.agent_input.setFont(QFont("Consolas", 9))
        self.agent_input.setStyleSheet("""
            QLineEdit {
                background: #161b22; color: #c9d1d9; border: 1px solid #30363d;
                border-radius: 4px; padding: 6px;
            }
            QLineEdit:focus { border: 1px solid #58a6ff; }
        """)
        self.agent_input.returnPressed.connect(self._submit_agent_task)
        agent_row.addWidget(self.agent_input, stretch=1)

        self._btn_agent = self._make_btn("Enviar", self._submit_agent_task)
        agent_row.addWidget(self._btn_agent)
        blay.addLayout(agent_row)

        # Quick actions row
        qa = QHBoxLayout()
        for label, handler in [
            ("Debug", self._quick_debug),
            ("Docstring", self._quick_document),
            ("Refatorar", self._quick_refactor),
            ("Otimizar", self._quick_optimize),
            ("Testes", self._quick_test),
            ("Métricas", self._quick_metrics),
        ]:
            b = self._make_btn(label, handler, small=True)
            qa.addWidget(b)
        qa.addStretch()
        blay.addLayout(qa)

        splitter.addWidget(bottom)
        splitter.setSizes([350, 250])
        lay.addWidget(splitter, stretch=1)

    def _make_btn(self, text: str, handler, small: bool = False) -> QPushButton:
        b = QPushButton(text)
        sz = 8 if small else 9
        b.setFont(QFont("Consolas", sz, QFont.Weight.Bold))
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(f"""
            QPushButton {{
                background: #161b22; color: #4fd8ff; border: 1px solid #30363d;
                border-radius: 4px; padding: {'3px 6px' if small else '5px 10px'};
            }}
            QPushButton:hover {{ background: #1f2937; border-color: #58a6ff; color: #aef0ff; }}
            QPushButton:pressed {{ background: #0d1117; }}
        """)
        b.clicked.connect(handler)
        return b

    # ---- File operations ----

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir Arquivo", "",
            "Python (*.py);;JavaScript (*.js);;Todos (*.*)"
        )
        if path:
            try:
                content = Path(path).read_text(encoding="utf-8", errors="replace")
                self.editor.set_code(content)
                self._current_file = path
                self.output.append_line(f" Aberto: {path}", "#58a6ff")
            except Exception as e:
                self.output.append_line(f"Erro ao abrir: {e}", "#ff4d4d")

    def _save_current(self):
        if self._current_file:
            try:
                Path(self._current_file).write_text(self.editor.get_code(), encoding="utf-8")
                self.output.append_line(f" Salvo: {self._current_file}", "#50fa7b")
            except Exception as e:
                self.output.append_line(f"Erro ao salvar: {e}", "#ff4d4d")
        else:
            path, _ = QFileDialog.getSaveFileName(
                self, "Salvar Como", "novo_arquivo.py",
                "Python (*.py);;JavaScript (*.js);;Todos (*.*)"
            )
            if path:
                self._current_file = path
                self._save_current()

    def _run_current(self):
        code = self.editor.get_code().strip()
        if not code:
            self.output.append_line("Nenhum código para executar.", "#ffb86c")
            return
        if self._current_file and self._current_file.endswith(".py"):
            self.output.append_line(f" Executando {self._current_file}...", "#50fa7b")
            self._run_file(self._current_file)
        else:
            self.output.append_line("Executando código inline...", "#50fa7b")
            self._run_inline(code)

    def _run_file(self, filepath: str):
        def _worker():
            try:
                proc = subprocess.run(
                    ["py", "-3", filepath],
                    capture_output=True, text=True, timeout=30,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                if proc.stdout:
                    for line in proc.stdout.splitlines():
                        QTimer.singleShot(0, lambda l=line: self.output.append_line(l, "#c9d1d9"))
                if proc.stderr:
                    for line in proc.stderr.splitlines():
                        QTimer.singleShot(0, lambda l=line: self.output.append_line(l, "#ff4d4d"))
                if proc.returncode == 0:
                    QTimer.singleShot(0, lambda: self.output.append_line("Executado com sucesso", "#50fa7b"))
                else:
                    QTimer.singleShot(0, lambda: self.output.append_line(f" Exit code: {proc.returncode}", "#ff4d4d"))
            except subprocess.TimeoutExpired:
                QTimer.singleShot(0, lambda: self.output.append_line("Timeout (30s)", "#ff4d4d"))
            except Exception as e:
                QTimer.singleShot(0, lambda: self.output.append_line(f" Erro: {e}", "#ff4d4d"))
        threading.Thread(target=_worker, daemon=True).start()

    def _run_inline(self, code: str):
        def _worker():
            try:
                proc = subprocess.run(
                    ["py", "-3", "-c", code],
                    capture_output=True, text=True, timeout=30,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                if proc.stdout:
                    for line in proc.stdout.splitlines():
                        QTimer.singleShot(0, lambda l=line: self.output.append_line(l, "#c9d1d9"))
                if proc.stderr:
                    for line in proc.stderr.splitlines():
                        QTimer.singleShot(0, lambda l=line: self.output.append_line(l, "#ff4d4d"))
            except Exception as e:
                QTimer.singleShot(0, lambda: self.output.append_line(f" {e}", "#ff4d4d"))
        threading.Thread(target=_worker, daemon=True).start()

    # ---- Analysis ----

    def _analyze_current(self):
        code = self.editor.get_code().strip()
        if not code:
            self.output.append_line("Nenhum código para analisar.", "#ffb86c")
            return
        self.output.append_line("Analisando código...", "#bd93f9")

        def _worker():
            try:
                import tempfile
                with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
                    f.write(code)
                    tmp = f.name
                from GreatSageAI_Clone.core.code_analyzer import quick_analyze
                result = quick_analyze(tmp)
                QTimer.singleShot(0, lambda: self.output.append_line(result, "#c9d1d9"))
                os.unlink(tmp)
            except Exception as e:
                QTimer.singleShot(0, lambda: self.output.append_line(f" Erro na análise: {e}", "#ff4d4d"))
        threading.Thread(target=_worker, daemon=True).start()

    # ---- Agent tasks ----

    def _submit_agent_task(self):
        task = self.agent_input.text().strip()
        if not task:
            return
        self.agent_input.clear()
        self.output.append_line(f" Tarefa: {task}", "#ff79c6")
        self.task_submitted.emit(task)

    # ---- Quick actions ----

    def _quick_debug(self):
        code = self.editor.get_code().strip()
        if code:
            self.output.append_line("Analisando bugs...", "#ff4d4d")
            self.task_submitted.emit(f"Analise e encontre bugs neste código:\n\n{code[:2000]}")

    def _quick_document(self):
        code = self.editor.get_code().strip()
        if code:
            self.output.append_line("Gerando docstrings...", "#f1fa8c")
            self.task_submitted.emit(f"Adicione docstrings completas a todas as funções e classes:\n\n{code[:2000]}")

    def _quick_refactor(self):
        code = self.editor.get_code().strip()
        if code:
            self.output.append_line("Refatorando...", "#50fa7b")
            self.task_submitted.emit(f"Refatore este código para ser mais limpo e eficiente:\n\n{code[:2000]}")

    def _quick_optimize(self):
        code = self.editor.get_code().strip()
        if code:
            self.output.append_line("Otimizando...", "#ffb86c")
            self.task_submitted.emit(f"Otimize este código para melhor performance:\n\n{code[:2000]}")

    def _quick_test(self):
        code = self.editor.get_code().strip()
        if code:
            self.output.append_line("Gerando testes...", "#bd93f9")
            self.task_submitted.emit(f"Gere testes unitários completos para este código:\n\n{code[:2000]}")

    def _quick_metrics(self):
        code = self.editor.get_code().strip()
        if code:
            self.output.append_line("Calculando métricas...", "#4fd8ff")
            self._analyze_current()

    # ---- Public API ----

    def set_agent_handler(self, handler):
        """Set the function to call when agent tasks are submitted."""
        self._agent_handler = handler

    def set_execute_handler(self, handler):
        """Set the function to call for code execution."""
        self._execute_handler = handler

    def append_output(self, text: str, color: str = "#c9d1d9"):
        """Append text to the output panel (thread-safe)."""
        QTimer.singleShot(0, lambda: self.output.append_line(text, color))

    def set_code(self, code: str, filepath: str = None):
        """Set code in the editor."""
        self.editor.set_code(code)
        if filepath:
            self._current_file = filepath
