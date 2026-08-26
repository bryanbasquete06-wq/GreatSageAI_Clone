# -*- coding: utf-8 -*-
"""Command Palette — busca global estilo VS Code (Ctrl+K)."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QLabel, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QShortcut

from typing import List, Tuple, Callable, Optional
import logging

logger = logging.getLogger("greatsage.palette")

class CommandPalette(QFrame):
    command_executed = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(500, 400)
        self.setStyleSheet("""
            QFrame { background: #131008; border: 2px solid #5c4708; border-radius: 12px; }
            QLineEdit { background: #1d180c; color: #fff3d6; border: 1px solid #5c4708;
                         border-radius: 8px; padding: 10px 14px; font-size: 14px; }
            QLineEdit:focus { border: 1px solid #ffd24a; }
            QListWidget { background: transparent; color: #fff3d6; border: none; font-size: 13px; }
            QListWidget::item { padding: 8px 14px; border-radius: 6px; }
            QListWidget::item:selected { background: #332708; }
            QListWidget::item:hover { background: #1d180c; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar comando... (Ctrl+K)")
        self.search.textChanged.connect(self._filter)
        layout.addWidget(self.search)

        self.results = QListWidget()
        self.results.itemDoubleClicked.connect(self._on_execute)
        layout.addWidget(self.results)

        self.status = QLabel("0 comandos")
        self.status.setStyleSheet("color: #9d8a5a; font-size: 11px; padding: 2px;")
        layout.addWidget(self.status)

        self._commands: List[Tuple[str, str, str, Optional[Callable]]] = []
        self._filtered: List[Tuple[str, str, str, Optional[Callable]]] = []
        self.search.returnPressed.connect(self._on_execute_selected)

    def register(self, cmd_id: str, name: str, category: str, callback: Callable = None):
        self._commands.append((cmd_id, name, category, callback))

    def register_batch(self, commands: List[Tuple[str, str, str, Callable]]):
        for cmd in commands:
            self.register(*cmd)

    def show_palette(self):
        self.search.clear()
        self._filtered = list(self._commands)
        self._populate()
        self.show()
        self.raise_()
        self.activateWindow()
        self.search.setFocus()

    def _filter(self, text: str):
        text = text.lower()
        if not text:
            self._filtered = list(self._commands)
        else:
            self._filtered = [c for c in self._commands if text in c[1].lower() or text in c[2].lower() or text in c[0].lower()]
        self._populate()

    def _populate(self):
        self.results.clear()
        current_cat = None
        for cmd_id, name, category, _ in self._filtered:
            if category != current_cat:
                cat_item = QListWidgetItem(f"  [{category}]")
                cat_item.setForeground(QColor("#9d8a5a"))
                cat_item.setFlags(Qt.ItemFlag.NoItemFlags)
                self.results.addItem(cat_item)
                current_cat = category
            item = QListWidgetItem(f"    {name}")
            item.setData(Qt.ItemDataRole.UserRole, cmd_id)
            self.results.addItem(item)
        self.status.setText(f"{len(self._filtered)} comandos")

    def _on_execute(self, item: QListWidgetItem):
        cmd_id = item.data(Qt.ItemDataRole.UserRole)
        if cmd_id:
            self._execute(cmd_id)

    def _on_execute_selected(self):
        item = self.results.currentItem()
        if item:
            self._on_execute(item)

    def _execute(self, cmd_id: str):
        for cid, _, _, cb in self._commands:
            if cid == cmd_id:
                if cb:
                    try:
                        cb()
                    except Exception as e:
                        logger.error(f"Erro ao executar comando '{cmd_id}': {e}")
                self.command_executed.emit(cmd_id, cb)
                self.hide()
                return
