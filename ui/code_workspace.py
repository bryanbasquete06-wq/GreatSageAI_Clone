"""
Great Sage AI — CODE WORKSPACE (Ala de Programação — estilo ZCode / Cursor)
============================================================================
Janela IDE completa do Grande Sábio:

  • Explorador de projetos (com filtro de ruído: .git, __pycache__ etc.)
  • Editor de código com syntax highlight multi-linguagem e números de linha
  • Painel do Agente de Código ao vivo (passos visíveis, como no Cursor)
  • Terminal de execução embutido (rodar Python/Node/batch e ver a saída)
  • Tokens por passo configuráveis: 4k / 8k / 16k

Abre por voz/texto ("programar ...", "abrir a ala de programação", "modo
programador"), pelo botão ⌨ Programar ou por Ctrl+P na janela principal.
"""

from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

from PySide6.QtCore import (
    QDir, QProcess, QSortFilterProxyModel, Qt, Signal,
)
from PySide6.QtGui import (
    QColor, QFont, QFileSystemModel, QTextCharFormat, QTextCursor,
)
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
    QPushButton, QSplitter, QTextBrowser, QToolBar, QTreeView, QVBoxLayout,
    QWidget,
)

from GreatSageAI_Clone.ui.qt_ui import C, font_mono, font_ui
from GreatSageAI_Clone.ui.code_syntax import CodeHighlighter, LANG_NAMES, detect_language

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "config" / "code_dock.json"

SKIP_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".venv", "venv", "env",
    "node_modules", ".idea", ".vscode", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".next", ".nuxt", "site-packages", "dist", "build",
}
SKIP_EXTS = {
    ".pyc", ".pyo", ".so", ".dll", ".exe", ".msi", ".png", ".jpg", ".jpeg",
    ".gif", ".ico", ".webp", ".mp3", ".mp4", ".wav", ".ogg", ".zip", ".rar",
    ".7z", ".gz", ".ttf", ".otf", ".woff", ".woff2", ".o", ".a", ".lib",
    ".obj", ".pyd", ".node",
}

#: máximas de entrada/saída do subprocesso de execução (proteção)
MAX_OUTPUT_LINES = 2000


def _esc(text: str) -> str:
    """Escape para HTML seguro."""
    return html.escape(str(text), quote=False).replace("\n", "<br>")


# ---------------------------------------------------------------------------
# Árvore de arquivos com filtro de ruído
# ---------------------------------------------------------------------------

class ProjectTreeModel(QSortFilterProxyModel):
    """QSortFilterProxyModel que esconde diretórios/arquivos de ruído."""

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        model: QFileSystemModel = self.sourceModel()
        index = model.index(source_row, 0, source_parent)
        if not index.isValid():
            return False
        info = model.fileInfo(index)
        if not info.isDir() and not info.isFile():
            return False
        name = info.fileName()
        if name in SKIP_DIRS:
            return False
        if not info.isDir():
            ext = Path(name).suffix.lower()
            if ext in SKIP_EXTS:
                return False
        return True


# ---------------------------------------------------------------------------
# Editor com números de linha
# ---------------------------------------------------------------------------

class _LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        return self._editor._line_area_size_hint()

    def paintEvent(self, ev):
        self._editor._paint_line_numbers(ev)


class CodeEditor(QPlainTextEdit):
    """Editor de texto com números de linha e realce da linha atual."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._line_area = _LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_area_width)
        self.updateRequest.connect(self._update_line_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(" "))
        self._update_line_area_width()
        self._highlight_current_line()

    # ------------------------------------------------------------- área

    def _line_area_size_hint(self):
        digits = max(2, len(str(max(1, self.blockCount()))))
        width = 10 + self.fontMetrics().horizontalAdvance("9") * digits
        from PySide6.QtCore import QSize
        return QSize(width, 0)

    def _update_line_area_width(self, *_):
        self.setViewportMargins(self._line_area_size_hint().width(), 0, 0, 0)

    def _update_line_area(self, rect, dy):
        if dy:
            self._line_area.scroll(0, dy)
        else:
            self._line_area.update(rect)
        if rect.contains(self.viewport().rect()):
            self._update_line_area_width()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        cr = self.contentsRect()
        self._line_area.setGeometry(cr.left(), cr.top(),
                                    self._line_area_size_hint().width(), cr.height())

    def _paint_line_numbers(self, ev):
        from PySide6.QtGui import QPainter
        painter = QPainter(self._line_area)
        try:
            painter.fillRect(ev.rect(), QColor(C.PANEL))
            block = self.firstVisibleBlock()
            block_number = block.blockNumber()
            top = round(self.blockBoundingGeometry(block).translated(
                self.contentOffset()).top())
            bottom = top + round(self.blockBoundingRect(block).height())
            while block.isValid() and top <= ev.rect().bottom():
                if block.isVisible() and bottom >= ev.rect().top():
                    painter.setPen(QColor(C.TEXT_DIM))
                    painter.drawText(
                        0, top, self._line_area.width() - 6,
                        self.fontMetrics().height(),
                        Qt.AlignmentFlag.AlignRight, str(block_number + 1))
                block = block.next()
                top = bottom
                bottom = top + round(self.blockBoundingRect(block).height())
                block_number += 1
        finally:
            painter.end()

    def _highlight_current_line(self):
        from PySide6.QtGui import QTextFormat
        from PySide6.QtWidgets import QTextEdit
        if self.isReadOnly():
            return
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(QColor(C.GHOST))
        sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        sel.cursor = self.textCursor()
        sel.cursor.clearSelection()
        self.setExtraSelections([sel])


# ---------------------------------------------------------------------------
# CodeDock — Ala de Programação
# ---------------------------------------------------------------------------

class CodeWorkspaceWindow(QMainWindow):
    """Janela IDE completa: explorador + editor + agente + terminal."""

    sig_agent_chunk = Signal(str) # passo do agente (thread-safe)
    sig_agent_finished = Signal(str, str) # (relatório, resumo)
    report_signal = Signal(str) # relatório final → chat principal

    def __init__(self, llm=None, workspace: str | Path | None = None, parent=None):
        super().__init__(parent)
        self.llm = llm
        self.current_file: str | None = None
        self.current_lang = "python"
        self._dirty = False
        self._suppress_modified = False

        # estado do agente
        self._agent = None
        self._agent_thread: threading.Thread | None = None
        self._agent_stop = threading.Event()
        self._agent_entries: list[str] = []

        # toggles da IA super (auto-programação / reasoning / provider)
        self.auto_program = False
        self.reasoning_enabled = True


        # execução
        self._proc: QProcess | None = None

        # modelos / widgets
        self._fs_model = QFileSystemModel(self)
        self._fs_model.setFilter(QDir.Filter.AllDirs | QDir.Filter.Files
                                 | QDir.Filter.NoDotAndDotDot)

        # workspace
        saved = self._load_config()
        ws = workspace or saved.get("workspace")
        self.workspace = Path(ws).expanduser().resolve() if ws else PROJECT_ROOT
        self.workspace.mkdir(parents=True, exist_ok=True)

        self.setWindowTitle("⌨ ALA DE PROGRAMAÇÃO — CodeDock ＜大賢者＞")
        self.resize(1300, 800)
        self.setMinimumSize(1020, 640)

        self._build_ui()
        self._apply_palette()
        self._restore_geometry(saved)

        # sinais do agente → GUI
        self.sig_agent_chunk.connect(self._append_agent_chunk)
        self.sig_agent_finished.connect(self._on_agent_finished)

        self._refresh_tree()
        self.set_workspace_status(self.workspace)

    # -------------------------------------------------------------- utils

    @staticmethod
    def _load_config() -> dict:
        try:
            if CONFIG_FILE.exists():
                return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save_config(self):
        try:
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {"workspace": str(self.workspace)}
            if self.isMaximized():
                data["maximized"] = True
            else:
                data["geometry"] = [self.x(), self.y(), self.width(), self.height()]
            CONFIG_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _restore_geometry(self, cfg: dict):
        if cfg.get("maximized"):
            self.showMaximized()
        else:
            g = cfg.get("geometry")
            if isinstance(g, list) and len(g) == 4:
                try:
                    self.move(int(g[0]), int(g[1]))
                    self.resize(int(g[2]), int(g[3]))
                except Exception:
                    pass

    def refresh_theme(self):
        """Recolore widgets e rehighlight após troca de tema do Grande Sábio."""
        from GreatSageAI_Clone.ui.code_syntax import CodeHighlighter
        self._apply_palette()
        try:
            if self.highlighter:
                self.highlighter.refresh_theme()
        except Exception:
            pass

    # ------------------------------------------------------------- UI

    def _make_btn(self, text: str, tip: str, action, enabled: bool = True) -> QPushButton:
        b = QPushButton(text)
        b.setToolTip(tip)
        b.setFont(font_mono(9))
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setEnabled(enabled)
        b.clicked.connect(action)
        return b

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(6)

        # ================= TOOLBAR =================
        tb = QHBoxLayout()
        self.btn_workspace = self._make_btn("Pasta", "Trocar pasta do projeto",
                                            self.choose_workspace)
        self.btn_new_file = self._make_btn("Arquivo", "Criar novo arquivo",
                                           self.new_file)
        self.btn_new_dir = self._make_btn("Nova pasta", "Criar nova pasta",
                                          self.new_folder)
        self.btn_save = self._make_btn("Salvar", "Salvar arquivo (Ctrl+S)",
                                       self.save_current)
        self.btn_external = self._make_btn("Explorer", "Abrir pasta no Windows Explorer",
                                           self.open_in_explorer)
        self.btn_run = self._make_btn("Executar", "Rodar o arquivo atual",
                                      self.run_current)
        self.btn_stop = self._make_btn("Parar", "Interromper execução ou agente",
                                       self.stop_run)
        self.btn_stop.setStyleSheet("color: #ff4d6d;")

        self.cmb_tokens = QComboBox()
        # "0" == tokens ILIMITADOS (usa janela completa do provider)
        self.cmb_tokens.addItems(["0", "4096", "8192", "16384"])
        self.cmb_tokens.setCurrentText("16384")
        self.cmb_tokens.setToolTip("Tokens máximos por passo (0 = ilimitado)")
        self.cmb_tokens.setFont(font_mono(9))

        tok_lbl = QLabel("Tokens (0=inf)")
        tok_lbl.setFont(font_mono(8))
        tok_lbl.setStyleSheet("color: #9d8a5a;")

        for w in (self.btn_workspace, self.btn_new_file, self.btn_new_dir,
                  self.btn_save, self.btn_external, self.btn_run):
            tb.addWidget(w)
        tb.addWidget(self.btn_stop)
        tb.addSpacing(12)
        tb.addWidget(tok_lbl)
        tb.addWidget(self.cmb_tokens)
        # --- toggles da IA super (reasoning / auto-programação) ---
        self.btn_reasoning = self._make_btn("Rac", "Raciocínio profundo (high effort)", self._toggle_reasoning)
        self.btn_reasoning.setCheckable(True)
        self.btn_reasoning.setChecked(True)
        tb.addWidget(self.btn_reasoning)
        self.btn_auto_program = self._make_btn("Self", "Auto-programação (modifica arquivos fora do workspace)", self._toggle_self_program)
        self.btn_auto_program.setCheckable(True)
        self.btn_auto_program.setChecked(False)
        tb.addWidget(self.btn_auto_program)
        tb.addStretch()
        root.addLayout(tb)

        # ================= CENTRAL =================
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # -- painel esquerdo: árvore de arquivos
        self.tree = QTreeView()
        self.tree.setModel(ProjectTreeModel(self))
        self.tree.setHeaderHidden(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(14)
        self.tree.doubleClicked.connect(self._on_tree_double_clicked)
        self.splitter.addWidget(self.tree)

        # -- centro: editor + terminal
        center = QSplitter(Qt.Orientation.Vertical)

        editor_wrap = QWidget()
        ev = QVBoxLayout(editor_wrap)
        ev.setContentsMargins(0, 0, 0, 0)
        ev.setSpacing(0)

        self.editor = CodeEditor()
        self.editor.setFont(QFont("Consolas", 10))
        self.editor.textChanged.connect(self._on_editor_changed)
        self.editor.cursorPositionChanged.connect(self._on_cursor_moved)
        ev.addWidget(self.editor)

        self.highlighter = CodeHighlighter(self.editor.document(), "python")

        # barrinha do arquivo aberto (pseudo-aba)
        bar = QHBoxLayout()
        self.lbl_file = QLabel("novo arquivo sem nome")
        self.lbl_file.setFont(font_mono(9))
        bar.addWidget(self.lbl_file)
        bar.addStretch()
        self.lbl_lang = QLabel("PYTHON")
        self.lbl_lang.setFont(font_mono(8))
        bar.addWidget(self.lbl_lang)
        ev.addLayout(bar)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(MAX_OUTPUT_LINES)
        self.output.setFont(QFont("Consolas", 9))
        center.addWidget(editor_wrap)
        center.addWidget(self.output)
        center.setStretchFactor(0, 4)
        center.setStretchFactor(1, 1)
        center.setSizes([560, 180])
        self.splitter.addWidget(center)

        # -- painel direito: agente
        agent_panel = QWidget()
        av = QVBoxLayout(agent_panel)
        av.setContentsMargins(6, 6, 6, 6)
        av.setSpacing(6)
        head = QHBoxLayout()
        lbl_agent = QLabel("ARIA AGENTE DE CÓDIGO")
        lbl_agent.setFont(font_mono(9))
        head.addWidget(lbl_agent)
        head.addStretch()
        self.btn_clear_agent = self._make_btn("", "Limpar conversa do agente",
                                              self._clear_agent)
        self.btn_clear_agent.setFixedWidth(30)
        head.addWidget(self.btn_clear_agent)
        av.addLayout(head)

        self.transcript = QTextBrowser()
        self.transcript.setOpenExternalLinks(False)
        av.addWidget(self.transcript, 1)

        self.agent_input = QLineEdit()
        self.agent_input.setPlaceholderText(
            "Descreva a tarefa de programação… (Enter executa)")
        self.agent_input.setFont(font_ui(10))
        self.agent_input.returnPressed.connect(self.submit_agent_task)
        av.addWidget(self.agent_input)

        self.btn_agent = self._make_btn("⟳ EXECUTAR TAREFA", "Iniciar o agente de código",
                                        self.submit_agent_task)
        self.btn_agent.setStyleSheet(
            f"QPushButton {{ background: {C.PRI}; color: {C.BG}; border: none; "
            f"border-radius: 6px; padding: 8px 12px; font-weight: bold; }}")
        av.addWidget(self.btn_agent)
        self.splitter.addWidget(agent_panel)

        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([260, 700, 360])
        root.addWidget(self.splitter, 1)

        # status bar
        self.status_label = QLabel("")
        self.ln_col_label = QLabel("Lin 1, Col 1")
        self.status = self.statusBar()
        self.status.addWidget(self.status_label, 1)
        self.status.addPermanentWidget(self.ln_col_label)

        # atalhos locais
        from PySide6.QtGui import QShortcut, QKeySequence
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self.new_file)

    # ------------------------------------------------------------ estilo

    def _apply_palette(self):
        self.setStyleSheet(f"background-color: {C.BG}; color: {C.TEXT};")
        self.tree.setStyleSheet(f"""
            QTreeView {{
                background: {C.PANEL}; color: {C.TEXT};
                border: 1px solid {C.BORDER}; border-radius: 6px;
                font-family: Consolas; font-size: 12px;
            }}
            QTreeView::item {{ padding: 2px 4px; }}
            QTreeView::item:selected {{ background: {C.GHOST}; color: {C.ACC}; }}
            QTreeView::item:hover {{ background: {C.PANEL2}; }}
        """)
        self.editor.setStyleSheet(f"""
            QPlainTextEdit {{
                background: {C.BG}; color: {C.TEXT};
                border: 1px solid {C.BORDER}; border-radius: 6px;
                selection-background-color: {C.GHOST};
                selection-color: {C.ACC};
            }}
        """)
        self.output.setStyleSheet(f"""
            QPlainTextEdit {{
                background: {C.PANEL}; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 6px;
                font-family: Consolas; font-size: 10pt;
            }}
        """)
        self.transcript.setStyleSheet(f"""
            QTextBrowser {{
                background: {C.PANEL}; color: {C.TEXT};
                border: 1px solid {C.BORDER}; border-radius: 6px;
                font-family: Consolas; font-size: 10pt;
            }}
        """)
        self.agent_input.setStyleSheet(f"""
            QLineEdit {{
                background: {C.PANEL2}; color: {C.WHITE};
                border: 1px solid {C.BORDER_B}; border-radius: 6px;
                padding: 7px 10px; font-size: 11px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        self.statusBar().setStyleSheet(
            f"QStatusBar {{ background: {C.PANEL}; color: {C.TEXT_DIM};"
            f"border-top: 1px solid {C.BORDER}; }}")
        for b in (self.btn_workspace, self.btn_new_file, self.btn_new_dir,
                  self.btn_save, self.btn_external, self.btn_run, self.btn_stop,
                  self.btn_clear_agent):
            b.setStyleSheet(f"""
                QPushButton {{ background: {C.PANEL2}; color: {C.PRI};
                    border: 1px solid {C.BORDER_B}; border-radius: 5px;
                    padding: 5px 9px; font-weight: bold; }}
                QPushButton:hover {{ background: {C.GHOST}; border: 1px solid {C.PRI}; }}
                QPushButton:disabled {{ color: {C.TEXT_DIM}; border-color: {C.BORDER}; }}
            """)
        self.cmb_tokens.setStyleSheet(f"""
            QComboBox {{ background: {C.PANEL2}; color: {C.ACC};
                border: 1px solid {C.BORDER_B}; border-radius: 5px; padding: 4px 6px; }}
            QComboBox QAbstractItemView {{
                background: {C.PANEL2}; color: {C.TEXT};
                selection-background-color: {C.GHOST};
            }}
        """)
        self.lbl_file.setStyleSheet(f"color: {C.ACC}; background: {C.PANEL2};"
                                    f"padding: 3px 8px; border-radius: 4px;")
        self.lbl_lang.setStyleSheet(f"color: {C.GOLD}; background: {C.PANEL2};"
                                    f"padding: 3px 8px; border-radius: 4px;")

    # ------------------------------------------------------------ árvore

    def _refresh_tree(self):
        proxy = self.tree.model()
        proxy.setSourceModel(self._fs_model)
        root_idx = self._fs_model.setRootPath(str(self.workspace))
        proxy_root = proxy.mapFromSource(root_idx)
        self.tree.setRootIndex(proxy_root)
        self.tree.expand(proxy_root)

    def set_workspace_status(self, path: Path):
        self.status_label.setText(f" Workspace: {path}")

    def _on_tree_double_clicked(self, index):
        path = self._path_from_tree(index)
        if path and path.is_file():
            self.open_file(path)

    def _path_from_tree(self, index):
        src = self.tree.model().mapToSource(index)
        if not src.isValid():
            return None
        return Path(self._fs_model.filePath(src))

    # ------------------------------------------------------------ editor

    def _on_editor_changed(self):
        if self._suppress_modified:
            return
        if not self._dirty:
            self._dirty = True
            self._update_file_label()

    def _on_cursor_moved(self):
        c = self.editor.textCursor()
        self.ln_col_label.setText(f"Lin {c.blockNumber() + 1}, Col {c.columnNumber() + 1}")

    def _update_file_label(self):
        if not self.current_file:
            name = "novo arquivo sem nome"
        else:
            name = Path(self.current_file).name
        star = " " if self._dirty else ""
        self.lbl_file.setText(f" {name}{star}")

    # --------------------------------------------------------- arquivos

    def open_file(self, path: Path | str):
        p = Path(path)
        if not p.is_file():
            return
        try:
            data = p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            self._append_output(f" Não consegui ler '{p.name}': {e}\n")
            return
        self._suppress_modified = True
        self.editor.setPlainText(data)
        self._suppress_modified = False
        self.current_file = str(p)
        self._dirty = False
        self.current_lang = detect_language(p.name)
        self.highlighter.set_language(self.current_lang)
        self.lbl_lang.setText(LANG_NAMES.get(self.current_lang, "TEXTO").upper())
        self._update_file_label()
        self._append_output(f" Abri {p.name} ({len(data):,} chars)\n")

    def choose_workspace(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Escolher pasta do projeto", str(self.workspace))
        if not folder:
            return
        self.workspace = Path(folder).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self._refresh_tree()
        self.set_workspace_status(self.workspace)
        self._save_config()

    def new_file(self):
        name, ok = QInputDialog.getText(self, "Novo arquivo",
                                        "Nome do arquivo (ex.: script.py):")
        if not (ok and name.strip()):
            return
        target = self.workspace / name.strip()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_text("", encoding="utf-8")
        except Exception as e:
            QMessageBox.warning(self, "Erro", f"Não consegui criar: {e}")
            return
        self.open_file(target)

    def new_folder(self):
        name, ok = QInputDialog.getText(self, "Nova pasta", "Nome da pasta:")
        if not (ok and name.strip()):
            return
        target = self.workspace / name.strip()
        try:
            target.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            QMessageBox.warning(self, "Erro", f"Não consegui criar: {e}")
            return
        self._refresh_tree()

    def save_current(self):
        if not self.current_file:
            path, _ = QFileDialog.getSaveFileName(self, "Salvar como",
                                                  str(self.workspace))
            if not path:
                return
            self.current_file = path
        try:
            with open(self.current_file, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())
        except Exception as e:
            QMessageBox.warning(self, "Erro", f"Não consegui salvar: {e}")
            return
        self._dirty = False
        self.current_lang = detect_language(Path(self.current_file).name)
        self.highlighter.set_language(self.current_lang)
        self.lbl_lang.setText(LANG_NAMES.get(self.current_lang, "TEXTO").upper())
        self._update_file_label()
        self._append_output(f" Arquivo salvo: {self.current_file}\n")

    def open_in_explorer(self):
        os.startfile(str(self.workspace)) # noqa: S606 — uso local intencional

    # ------------------------------------------------------------ execução

    def run_current(self):
        if not self.current_file:
            self._append_output("Nenhum arquivo aberto para executar.\n")
            return
        path = Path(self.current_file)
        ext = path.suffix.lower()
        if ext in (".py", ".pyw"):
            program = sys.executable
            args = ["-u", str(path)]
        elif ext in (".js", ".mjs", ".jsx", ".cjs"):
            program = "node"
            args = [str(path)]
        elif ext == ".html":
            os.startfile(str(path)) # noqa: S606
            self._append_output(f" Abrindo {path.name} no navegador.\n")
            return
        elif ext in (".bat", ".cmd"):
            program = "cmd"
            args = ["/c", str(path)]
        elif ext in (".json", ".md", ".txt"):
            os.startfile(str(path)) # noqa: S606
            self._append_output(f" Abrindo {path.name}.\n")
            return
        else:
            os.startfile(str(path)) # noqa: S606
            self._append_output(f" Abrindo {path.name} com o app associado.\n")
            return

        self._append_output(f"\n$ {program} {' '.join(args)}\n")
        self._stop_proc()
        self._proc = QProcess(self)
        self._proc.setProgram(program)
        self._proc.setArguments(args)
        self._proc.setWorkingDirectory(str(self.workspace))
        self._proc.readyReadStandardOutput.connect(self._on_proc_stdout)
        self._proc.readyReadStandardError.connect(self._on_proc_stderr)
        self._proc.finished.connect(self._on_proc_finished)
        self._proc.start()
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)

    def stop_run(self):
        self._stop_proc()
        if self._agent and self._agent_thread and self._agent_thread.is_alive():
            self._agent_stop.set()
            self._append_agent_html(
                "<i style='color:#ff9d6a'>Interrupção solicitada pelo Mestre…</i>")

    def stop_run_btn_state(self):
        pass

    def _stop_proc(self):
        if self._proc and self._proc.state() != QProcess.ProcessState.NotRunning:
            try:
                self._proc.kill()
            except Exception:
                pass
            self._append_output("Processo encerrado.\n")
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def _on_proc_stdout(self):
        ba = self._proc.readAllStandardOutput()
        self._append_output(bytes(ba).decode("utf-8", errors="replace"))

    def _on_proc_stderr(self):
        ba = self._proc.readAllStandardError()
        self._append_output(bytes(ba).decode("utf-8", errors="replace"),
                            as_error=True)

    def _on_proc_finished(self, code, status):
        self._append_output(f"\n[processo encerrado — código {code}]\n")
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def _append_output(self, text: str, as_error: bool = False):
        self.output.moveCursor(QTextCursor.MoveOperation.End)
        label = text
        if as_error:
            label = f" {text}"
        if text.startswith("\n$"):
            label = "$ " + text[2:]
        self.output.insertPlainText(label)
        bar = self.output.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _toggle_reasoning(self):
        self.reasoning_enabled = self.btn_reasoning.isChecked()
        self.btn_reasoning.setStyleSheet(
            "" if self.reasoning_enabled else
            "background:#3a2e18;color:#ff9d6a;border:1px solid #ff9d6a;")
        self._append_agent_html(
            f"<div style='color:{C.ACC}'>raciocínio {' ON' if self.reasoning_enabled else ' OFF'}</div>")

    def _toggle_self_program(self):
        self.auto_program = self.btn_auto_program.isChecked()
        self.btn_auto_program.setStyleSheet(
            "" if not self.auto_program else
            "background:#1a2a1a;color:#4ff;border:1px solid #4ff;")
        self._append_agent_html(
            f"<div style='color:{C.ACC}'>auto-programação {' ON' if self.auto_program else ' OFF'}</div>")

    # ------------------------------------------------------------ agente

    def _append_agent_html(self, html_frag: str):
        self._agent_entries.append(html_frag)
        if len(self._agent_entries) > 400:
            self._agent_entries = self._agent_entries[-300:]
        body = "".join(self._agent_entries)
        self.transcript.setHtml(
            f"<body style='margin:6px; color:{C.TEXT}'>"
            f"<b style='color:{C.ACC2}'>ARIA AGENTE DE CÓDIGO</b><hr>{body}</body>")
        sb = self.transcript.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _append_agent_chunk(self, text: str):
        """Converte um passo de texto do agente em HTML colorido."""
        out = []
        for line in str(text).splitlines():
            if not line.strip():
                continue
            if line.startswith("== "):
                out.append(f"<div style='color:{C.PRI};font-weight:bold'>{_esc(line)}</div>")
            elif line.startswith("! "):
                out.append(f"<div style='color:{C.GOLD}'>{_esc(line)}</div>")
            elif line.startswith("- "):
                out.append(
                    f"<div style='color:{C.TEXT_MED};margin-left:10px'>"
                    f"{_esc(line).strip()}</div>")
            else:
                out.append(f"<div style='color:{C.TEXT}'>{_esc(line)}</div>")
        if out:
            self._append_agent_html("<br>" + "".join(out))

    def _agent_busy(self) -> bool:
        return (self._agent_thread is not None and self._agent_thread.is_alive())

    def _set_agent_running(self, busy: bool):
        self.btn_agent.setEnabled(not busy)
        self.agent_input.setEnabled(not busy)
        self.btn_agent.setText("AGENTE TRABALHANDO…" if busy
                               else "EXECUTAR TAREFA")
        running_proc = bool(self._proc and self._proc.state()
                            != QProcess.ProcessState.NotRunning)
        self.btn_stop.setEnabled(busy or running_proc)

    def submit_agent_task(self):
        task = self.agent_input.text().strip()
        if task:
            self.agent_input.clear()
            self.run_task(task)
        else:
            self._append_agent_html(
                "<div style='color:#ff9d6a'> Descreva a tarefa primeiro, Mestre.</div>")

    def run_task(self, task: str):
        """Dispara o agente de código em thread própria (vem do chat/voz também)."""
        if self._agent_busy():
            self._append_agent_html(
                "<div style='color:#ff9d6a'> O agente ainda está trabalhando — "
                "pressione Parar ou aguarde.</div>")
            return
        if self.llm is None:
            self._append_agent_html(
                "<div style='color:#ff9d6a'> Sem núcleo neural conectado "
                "(LLM não fornecido). Abra a Ala de Programação pela janela "
                "principal do Grande Sábio.</div>")
            return

        from GreatSageAI_Clone.modules.smart_agent import SmartCodeAgent
        from GreatSageAI_Clone.modules.code_index import CodeIndex

        self._agent = None
        self._agent_stop = threading.Event()
        try:
            max_tokens = int(self.cmb_tokens.currentText())
        except Exception:
            max_tokens = 16384

        self._append_agent_html(
            f"<div style='color:{C.ACC};font-weight:bold'>Mestre {_esc(task)}</div>")
        # index semântico: recupera trechos relevantes (contexto ilimitado)
        index = None
        try:
            index = CodeIndex(self.workspace, chunk_size=480, overlap=160, max_files=4000)
            index.build()
        except Exception:
            pass
        if index:
            self._append_agent_html(
                f"<div style='color:{C.TEXT_DIM}'>CodeIndex ativo · tokens/passo: {max_tokens or '∞'}</div>")
        agent = SmartCodeAgent(llm=self.llm, workspace=self.workspace,
                             on_step=self._on_agent_step, max_tokens=max_tokens,
                             self_program=self.auto_program,
                             reasoning=self.reasoning_enabled, index=index)
        self._agent = agent
        self._set_agent_running(True)

        def _worker():
            try:
                report, answer = agent.run(task, stop_event=self._agent_stop)
            except Exception as e:
                report = f"ERRO interno no agente: {e}"
                answer = "O agente falhou durante a execução, Mestre."
            self.sig_agent_finished.emit(report, answer)

        self._agent_thread = threading.Thread(target=_worker, daemon=True)
        self._agent_thread.start()

    def _on_agent_step(self, text: str):
        """Callback chamado na thread do agente → sinal thread-safe até a GUI."""
        try:
            self.sig_agent_chunk.emit(text)
        except Exception:
            pass

    def _on_agent_finished(self, report: str, answer: str):
        self._set_agent_running(False)
        self._append_agent_html(
            f"<br><div style='border-top:1px dashed {C.BORDER_B};padding-top:4px'>"
            f"<b style='color:{C.GREEN}'> {_esc(answer)}</b></div>")
        self.report_signal.emit(report)

    def _clear_agent(self):
        self._agent_entries.clear()
        self.transcript.clear()
        self._append_agent_html(
            f"<div style='color:{C.TEXT_DIM}'>Conversa do agente limpa.</div>")

    # ------------------------------------------------------------ encerrar

    def closeEvent(self, ev):
        try:
            self._save_config()
        except Exception:
            pass
        super().closeEvent(ev)


if __name__ == "__main__":
    # Modo standalone: python -m GreatSageAI_Clone.ui.code_workspace
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    llm = None
    try:
        from GreatSageAI_Clone.core.llm import GreatSageLLM
        llm = GreatSageLLM()
    except Exception as e:
        print(f"[CodeDock] LLM não carregado: {e}")
    win = CodeWorkspaceWindow(llm=llm)
    win.show()
    sys.exit(app.exec())