#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elívea — Programming Panel (Integrated IDE v3)
====================================================
Full-featured programming environment:
  • Multi-language syntax highlighting (Python, JS, HTML, CSS, JSON)
  • Auto-complete with keywords, snippets, and context-aware suggestions
  • Line number gutter with current-line highlight
  • Bracket matching (parentheses, brackets, braces)
  • Tab/Shift-Tab indentation
  • Find/Replace (Ctrl+F / Ctrl+H)
  • AI code generation from natural language
  • Live terminal/output panel
  • File explorer sidebar
  • Run/Debug/Save/Load actions
"""

import os
import sys
import re
import time
import threading
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, List, Tuple

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPlainTextEdit,
        QPushButton, QLabel, QSplitter, QFrame, QTreeWidget, QTreeWidgetItem,
        QTabWidget, QMenuBar, QMenu, QToolBar, QStatusBar, QFileDialog,
        QMessageBox, QScrollArea, QSizePolicy, QLineEdit, QComboBox,
        QListWidget, QListWidgetItem, QAbstractItemView, QGraphicsDropShadowEffect
    )
    from PySide6.QtCore import (
        Qt, Signal, QTimer, QSize, QThread, QRect, QPoint, QPropertyAnimation,
        QEasingCurve
    )
    from PySide6.QtGui import (
        QFont, QColor, QPainter, QPen, QBrush, QLinearGradient,
        QRadialGradient, QSyntaxHighlighter, QTextCharFormat, QTextCursor,
        QAction, QIcon, QKeySequence, QShortcut, QTextDocument,
        QTextFormat, QPalette, QPainterPath
    )
except ImportError:
    from PyQt6.QtWidgets import *
    from PyQt6.QtCore import *
    from PyQt6.QtGui import *
    Signal = pyqtSignal


# ═══════════════════════════════════════════════════════════════════════════
# Color Constants (Elivea dark-gold theme)
# ═══════════════════════════════════════════════════════════════════════════

BG_DARK = "#0a0a12"
BG_PANEL = "#0f0f1a"
BG_EDITOR = "#0c0c18"
BG_HEADER = "#12121f"
BG_SIDEBAR = "#0d0d18"
BG_HOVER = "#1a1a2a"
BG_INPUT = "#141425"
BG_LINE_NUM = "#0e0e1a"
BG_CURSOR_LINE = "#1a1a2a"

GOLD = "#d4a843"
GOLD_DIM = "#8a6d2b"
GOLD_BRIGHT = "#f0c040"
GOLD_BG = "#1a1508"

TEXT = "#e0e0e0"
TEXT_DIM = "#606070"
TEXT_BRIGHT = "#ffffff"
TEXT_CODE = "#c9d1d9"

GREEN = "#4ec9b0"
RED = "#f44747"
BLUE = "#569cd6"
CYAN = "#4fc1ff"
PURPLE = "#c586c0"
ORANGE = "#ce9178"
YELLOW = "#dcdcaa"
COMMENT = "#6a9955"
KEYWORD = "#569cd6"
STRING = "#ce9178"
NUMBER = "#b5cea8"
FUNCTION = "#dcdcaa"
CLASS_TYPE = "#4ec9b0"
DECORATOR = "#d7ba7d"
TAG_NAME = "#569cd6"
ATTR_NAME = "#9cdcfe"
ATTR_VALUE = "#ce9178"
CSS_PROP = "#9cdcfe"
CSS_VAL = "#ce9178"
JSON_KEY = "#9cdcfe"
BRACKET_MATCH = "#ffd700"


# ═══════════════════════════════════════════════════════════════════════════
# Multi-Language Syntax Highlighters
# ═══════════════════════════════════════════════════════════════════════════

class BaseHighlighter(QSyntaxHighlighter):
    """Base class with shared highlighting utilities."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rules: List[Tuple[re.Pattern, QTextCharFormat, int]] = []

    def highlightBlock(self, text: str):
        for pattern, fmt, group in self._rules:
            for match in pattern.finditer(text):
                if group >= 0 and match.lastindex and match.lastindex >= group:
                    start = match.start(group)
                    length = match.end(group) - start
                else:
                    start = match.start()
                    length = match.end() - start
                self.setFormat(start, length, fmt)

    def _fmt(self, color: str, bold=False, italic=False, underline=False):
        f = QTextCharFormat()
        f.setForeground(QColor(color))
        if bold:
            f.setFontWeight(QFont.Weight.Bold)
        if italic:
            f.setFontItalic(True)
        if underline:
            f.setFontUnderline(True)
        return f


class PythonHighlighter(BaseHighlighter):
    """VS Code-inspired Python syntax highlighting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        kw = self._fmt(KEYWORD, bold=True)
        bi = self._fmt(YELLOW)
        st = self._fmt(STRING)
        fs = self._fmt(ORANGE)
        cm = self._fmt(COMMENT, italic=True)
        nm = self._fmt(NUMBER)
        dc = self._fmt(DECORATOR)
        fn = self._fmt(FUNCTION, bold=True)
        sf = self._fmt(CLASS_TYPE, italic=True)
        op = self._fmt(PURPLE)

        keywords = (
            'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await',
            'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except',
            'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is',
            'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return',
            'try', 'while', 'with', 'yield'
        )
        builtins = (
            'print', 'len', 'range', 'int', 'str', 'float', 'list', 'dict',
            'set', 'tuple', 'type', 'super', 'self', 'cls', 'object',
            'isinstance', 'hasattr', 'getattr', 'setattr', 'enumerate',
            'zip', 'map', 'filter', 'sorted', 'reversed', 'input',
            'open', 'abs', 'max', 'min', 'sum', 'any', 'all',
            'Exception', 'ValueError', 'TypeError', 'KeyError', 'IndexError',
            'RuntimeError', 'StopIteration', 'FileNotFoundError',
            'os', 'sys', 'path', 'Path', 're', 'json', 'time', 'threading',
        )

        self._rules = [
            (re.compile(r'""".*?"""', re.DOTALL), st, 0),
            (re.compile(r"'''.*?'''", re.DOTALL), st, 0),
            (re.compile(r'f"[^"\\]*(\\.[^"\\]*)*"'), fs, 0),
            (re.compile(r"f'[^'\\]*(\\.[^'\\]*)*'"), fs, 0),
            (re.compile(r'"[^"\\]*(\\.[^"\\]*)*"'), st, 0),
            (re.compile(r"'[^'\\]*(\\.[^'\\]*)*'"), st, 0),
            (re.compile(r'#.*'), cm, 0),
            (re.compile(r'\b(' + '|'.join(keywords) + r')\b'), kw, 0),
            (re.compile(r'\b(' + '|'.join(builtins) + r')\b'), bi, 0),
            (re.compile(r'\b\d+\.?\d*\b'), nm, 0),
            (re.compile(r'\b0x[0-9a-fA-F]+\b'), nm, 0),
            (re.compile(r'@\w+'), dc, 0),
            (re.compile(r'\b(def|class)\s+(\w+)'), fn, 2),
            (re.compile(r'\bself\b'), sf, 0),
            (re.compile(r'[+\-*/%=<>!&|^~]+'), op, 0),
        ]


class JavaScriptHighlighter(BaseHighlighter):
    """VS Code-inspired JavaScript/TypeScript syntax highlighting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        kw = self._fmt(KEYWORD, bold=True)
        st = self._fmt(STRING)
        cm = self._fmt(COMMENT, italic=True)
        bc = self._fmt(COMMENT, italic=True)  # block comment
        nm = self._fmt(NUMBER)
        fn = self._fmt(FUNCTION, bold=True)
        tp = self._fmt(CLASS_TYPE)
        op = self._fmt(PURPLE)
        pr = self._fmt(CYAN)

        keywords = (
            'async', 'await', 'break', 'case', 'catch', 'class', 'const',
            'continue', 'debugger', 'default', 'delete', 'do', 'else',
            'export', 'extends', 'finally', 'for', 'from', 'function',
            'if', 'import', 'in', 'instanceof', 'let', 'new', 'of',
            'return', 'static', 'super', 'switch', 'this', 'throw',
            'try', 'typeof', 'var', 'void', 'while', 'with', 'yield',
        )
        builtins = (
            'console', 'document', 'window', 'Math', 'JSON', 'Promise',
            'Array', 'Object', 'String', 'Number', 'Boolean', 'Map', 'Set',
            'Date', 'RegExp', 'Error', 'parseInt', 'parseFloat', 'isNaN',
            'undefined', 'null', 'true', 'false', 'NaN', 'Infinity',
        )

        self._rules = [
            (re.compile(r'""".*?"""', re.DOTALL), st, 0),
            (re.compile(r"'''.*?'''", re.DOTALL), st, 0),
            (re.compile(r'`[^`]*`'), st, 0),
            (re.compile(r'"[^"\\]*(\\.[^"\\]*)*"'), st, 0),
            (re.compile(r"'[^'\\]*(\\.[^'\\]*)*'"), st, 0),
            (re.compile(r'//.*'), cm, 0),
            (re.compile(r'/\*.*?\*/', re.DOTALL), bc, 0),
            (re.compile(r'\b(' + '|'.join(keywords) + r')\b'), kw, 0),
            (re.compile(r'\b(' + '|'.join(builtins) + r')\b'), pr, 0),
            (re.compile(r'\b\d+\.?\d*([eE][+-]?\d+)?\b'), nm, 0),
            (re.compile(r'\b0x[0-9a-fA-F]+\b'), nm, 0),
            (re.compile(r'\b(const|let|var)\s+(\w+)'), tp, 2),
            (re.compile(r'\b(function)\s+(\w+)'), fn, 2),
            (re.compile(r'\b(\w+)\s*(?=\()'), fn, 1),
            (re.compile(r'[+\-*/%=<>!&|^~?:]+'), op, 0),
        ]


class HTMLHighlighter(BaseHighlighter):
    """HTML syntax highlighting with tag/attribute coloring."""

    def __init__(self, parent=None):
        super().__init__(parent)
        tg = self._fmt(TAG_NAME, bold=True)
        at = self._fmt(ATTR_NAME)
        av = self._fmt(STRING)
        cm = self._fmt(COMMENT, italic=True)
        st = self._fmt(STRING)

        self._rules = [
            (re.compile(r'<!--.*?-->', re.DOTALL), cm, 0),
            (re.compile(r'<(/?)(\w[\w-]*)'), tg, 2),
            (re.compile(r'\b(\w[\w-]*)(=)'), at, 1),
            (re.compile(r'"[^"]*"'), av, 0),
            (re.compile(r"'[^']*'"), av, 0),
            (re.compile(r'<style.*?>.*?</style>', re.DOTALL | re.IGNORECASE), st, 0),
            (re.compile(r'<script.*?>.*?</script>', re.DOTALL | re.IGNORECASE), st, 0),
        ]


class CSSHighlighter(BaseHighlighter):
    """CSS syntax highlighting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        pr = self._fmt(CSS_PROP)
        vl = self._fmt(CSS_VAL)
        nm = self._fmt(NUMBER)
        cm = self._fmt(COMMENT, italic=True)
        se = self._fmt(FUNCTION, bold=True)
        at = self._fmt(DECORATOR)

        self._rules = [
            (re.compile(r'/\*.*?\*/', re.DOTALL), cm, 0),
            (re.compile(r'@media|@keyframes|@import|@font-face|@supports'), at, 0),
            (re.compile(r'#[\w-]+'), se, 0),
            (re.compile(r'\.[\w-]+'), se, 0),
            (re.compile(r'[\w-]+(?=\s*:)'), pr, 0),
            (re.compile(r':\s*([^;{}]+)'), vl, 1),
            (re.compile(r'\b\d+\.?\d*(px|em|rem|%|vh|vw|s|ms|deg|fr)?\b'), nm, 0),
            (re.compile(r'#[0-9a-fA-F]{3,8}\b'), nm, 0),
        ]


class JSONHighlighter(BaseHighlighter):
    """JSON syntax highlighting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        ky = self._fmt(JSON_KEY, bold=True)
        st = self._fmt(STRING)
        nm = self._fmt(NUMBER)
        bl = self._fmt(PURPLE, bold=True)

        self._rules = [
            (re.compile(r'"([^"\\]|\\.)*"(?=\s*:)'), ky, 0),
            (re.compile(r'"([^"\\]|\\.)*"'), st, 0),
            (re.compile(r'\b\d+\.?\d*([eE][+-]?\d+)?\b'), nm, 0),
            (re.compile(r'\b(true|false|null)\b'), bl, 0),
        ]


# Language detection from file extension
_LANG_MAP = {
    '.py': PythonHighlighter,
    '.pyw': PythonHighlighter,
    '.js': JavaScriptHighlighter,
    '.jsx': JavaScriptHighlighter,
    '.ts': JavaScriptHighlighter,
    '.tsx': JavaScriptHighlighter,
    '.html': HTMLHighlighter,
    '.htm': HTMLHighlighter,
    '.css': CSSHighlighter,
    '.scss': CSSHighlighter,
    '.json': JSONHighlighter,
    '.jsonl': JSONHighlighter,
}


def get_highlighter_for_file(filepath: str, parent=None):
    """Return the appropriate highlighter class for a file extension."""
    ext = Path(filepath).suffix.lower()
    cls = _LANG_MAP.get(ext, PythonHighlighter)
    return cls(parent)


# ═══════════════════════════════════════════════════════════════════════════
# Auto-Complete Engine
# ═══════════════════════════════════════════════════════════════════════════

# Snippets per language
_SNIPPETS: Dict[str, Dict[str, str]] = {
    'python': {
        'def': 'def ${1:name}(${2:args}):\n    ${3:pass}',
        'class': 'class ${1:Name}:\n    def __init__(self${2:, args}):\n        ${3:pass}',
        'if': 'if ${1:condition}:\n    ${2:pass}',
        'elif': 'elif ${1:condition}:\n    ${2:pass}',
        'else': 'else:\n    ${1:pass}',
        'for': 'for ${1:item} in ${2:iterable}:\n    ${3:pass}',
        'while': 'while ${1:condition}:\n    ${2:pass}',
        'try': 'try:\n    ${1:pass}\nexcept ${2:Exception} as e:\n    ${3:print(e)}',
        'with': 'with ${1:expression} as ${2:var}:\n    ${3:pass}',
        'async def': 'async def ${1:name}(${2:args}):\n    ${3:await pass}',
        'import': 'import ${1:module}',
        'from': 'from ${1:module} import ${2:name}',
        'print': 'print(${1:value})',
        'lambda': 'lambda ${1:args}: ${2:expression}',
        'list comprehension': '[${1:expr} for ${2:x} in ${3:iterable}]',
        'dict comprehension': '{${1:k}: ${2:v} for ${3:k}, ${4:v} in ${5:items}}',
    },
    'javascript': {
        'function': 'function ${1:name}(${2:params}) {\n    ${3:// body}\n}',
        'const': 'const ${1:name} = ${2:value};',
        'let': 'let ${1:name} = ${2:value};',
        'var': 'var ${1:name} = ${2:value};',
        'if': 'if (${1:condition}) {\n    ${2:// body}\n}',
        'else': ' else {\n    ${1:// body}\n}',
        'for': 'for (let ${1:i} = 0; ${1:i} < ${2:length}; ${1:i}++) {\n    ${3:// body}\n}',
        'forof': 'for (const ${1:item} of ${2:iterable}) {\n    ${3:// body}\n}',
        'while': 'while (${1:condition}) {\n    ${2:// body}\n}',
        'try': 'try {\n    ${1:// body}\n} catch (${2:e}) {\n    ${3:console.error(e)}\n}',
        'async function': 'async function ${1:name}(${2:params}) {\n    ${3:// body}\n}',
        'arrow': '(${1:params}) => ${2:expression}',
        'arrow block': '(${1:params}) => {\n    ${2:// body}\n}',
        'class': 'class ${1:Name} {\n    constructor(${2:params}) {\n        ${3:// init}\n    }\n}',
        'import': 'import ${1:name} from \'${2:module}\';',
        'console.log': 'console.log(${1:value});',
        'promise': 'new Promise((${1:resolve}, ${2:reject}) => {\n    ${3:// body}\n})',
        'map': '.map((${1:item}) => ${2:item})',
        'filter': '.filter((${1:item}) => ${2:item})',
        'reduce': '.reduce((${1:acc}, ${2:item}) => ${3:acc}, ${4:init})',
    },
    'html': {
        'html5': '<!DOCTYPE html>\n<html lang="pt-BR">\n<head>\n    <meta charset="UTF-8">\n    <title>${1:Title}</title>\n</head>\n<body>\n    ${2:}\n</body>\n</html>',
        'div': '<div ${1:class}>${2:}</div>',
        'p': '<p>${1:text}</p>',
        'a': '<a href="${1:url}">${2:text}</a>',
        'img': '<img src="${1:src}" alt="${2:alt}">',
        'ul': '<ul>\n    <li>${1:item}</li>\n</ul>',
        'form': '<form action="${1:url}" method="${2:post}">\n    ${3:}\n</form>',
        'input': '<input type="${1:text}" name="${2:name}" placeholder="${3:}">',
        'button': '<button type="${1:button}">${2:text}</button>',
        'script': '<script>\n    ${1:// code}\n</script>',
        'style': '<style>\n    ${1:/* styles */}\n</style>',
    },
    'css': {
        'class': '.${1:name} {\n    ${2:property}: ${3:value};\n}',
        'id': '#${1:name} {\n    ${2:property}: ${3:value};\n}',
        'flex': 'display: flex;\njustify-content: ${1:center};\nalign-items: ${2:center};',
        'grid': 'display: grid;\ngrid-template-columns: ${1:1fr 1fr};\ngap: ${2:16px};',
        'position': 'position: ${1:absolute};\ntop: ${2:0};\nleft: ${3:0};',
        'transition': 'transition: ${1:all} ${2:0.3s} ${3:ease};',
        'media': '@media (max-width: ${1:768px}) {\n    ${2:}\n}',
    },
    'json': {
        'object': '{\n    "${1:key}": ${2:value}\n}',
        'array': '[\n    ${1:value}\n]',
    },
}

# Keywords per language (for auto-complete list)
_KEYWORDS: Dict[str, List[str]] = {
    'python': [
        'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await',
        'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except',
        'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is',
        'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return',
        'try', 'while', 'with', 'yield',
        'print', 'len', 'range', 'int', 'str', 'float', 'list', 'dict',
        'set', 'tuple', 'type', 'super', 'self', 'object', 'isinstance',
        'hasattr', 'getattr', 'setattr', 'enumerate', 'zip', 'map', 'filter',
        'sorted', 'reversed', 'input', 'open', 'abs', 'max', 'min', 'sum',
        'any', 'all', 'Exception', 'ValueError', 'TypeError',
    ],
    'javascript': [
        'async', 'await', 'break', 'case', 'catch', 'class', 'const',
        'continue', 'debugger', 'default', 'delete', 'do', 'else',
        'export', 'extends', 'finally', 'for', 'from', 'function',
        'if', 'import', 'in', 'instanceof', 'let', 'new', 'of',
        'return', 'static', 'super', 'switch', 'this', 'throw',
        'try', 'typeof', 'var', 'void', 'while', 'with', 'yield',
        'console', 'document', 'window', 'Math', 'JSON', 'Promise',
        'Array', 'Object', 'String', 'Number', 'Boolean', 'Map', 'Set',
        'Date', 'RegExp', 'Error', 'parseInt', 'parseFloat', 'undefined',
        'null', 'true', 'false',
    ],
    'html': [
        'DOCTYPE', 'html', 'head', 'body', 'div', 'span', 'p', 'a', 'h1',
        'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'table', 'tr',
        'td', 'th', 'form', 'input', 'button', 'select', 'option',
        'textarea', 'img', 'video', 'audio', 'canvas', 'script', 'style',
        'link', 'meta', 'title', 'header', 'footer', 'nav', 'main',
        'section', 'article', 'aside',
    ],
    'css': [
        'display', 'position', 'width', 'height', 'margin', 'padding',
        'border', 'background', 'color', 'font-size', 'font-weight',
        'text-align', 'justify-content', 'align-items', 'flex', 'grid',
        'gap', 'overflow', 'z-index', 'opacity', 'transition', 'transform',
        'animation', 'box-shadow', 'border-radius', 'top', 'left', 'right',
        'bottom', 'flex-direction', 'flex-wrap', 'grid-template-columns',
        'grid-template-rows',
    ],
    'json': [
        'true', 'false', 'null',
    ],
}


class AutoCompletePopup(QListWidget):
    """Floating auto-complete popup list."""

    item_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(320)
        self.setMaximumHeight(220)
        self.setUniformItemSizes(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(f"""
            QListWidget {{
                background-color: #141420;
                color: {TEXT};
                border: 1px solid {GOLD_DIM}60;
                border-radius: 8px;
                padding: 4px;
                font-family: 'Cascadia Code', 'Consolas', monospace;
                font-size: 12px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 5px 10px;
                border-radius: 4px;
            }}
            QListWidget::item:selected {{
                background-color: {GOLD_BG};
                color: {GOLD};
            }}
            QListWidget::item:hover {{
                background-color: #1a1a2a;
            }}
        """)
        self.itemClicked.connect(self._on_click)

    def _on_click(self, item):
        self.item_selected.emit(item.text())
        self.hide()

    def show_items(self, items: List[str], keyword_map: Dict[str, str] = None):
        """Show filtered items. keyword_map maps display text → snippet/type."""
        self.clear()
        for item_text in items[:20]:
            QListWidgetItem(item_text, self)
        if self.count() > 0:
            self.setCurrentRow(0)
            self.show()
            self.raise_()
            self.setFocus()
        else:
            self.hide()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            item = self.currentItem()
            if item:
                self.item_selected.emit(item.text())
                self.hide()
        elif event.key() == Qt.Key.Key_Escape:
            self.hide()
        elif event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)


# ═══════════════════════════════════════════════════════════════════════════
# Code Editor with Line Numbers + Bracket Matching
# ═══════════════════════════════════════════════════════════════════════════

class LineNumberArea(QWidget):
    """Gutter widget that renders line numbers."""

    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self._editor.line_number_area_paint_event(event)


class CodeEditorWidget(QPlainTextEdit):
    """Enhanced code editor with line numbers, bracket matching, auto-complete, and multi-language highlighting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Cascadia Code, Consolas, Fira Code, monospace", 11))
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ') * 4)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {BG_EDITOR};
                color: {TEXT_CODE};
                border: none;
                padding: 4px 8px 4px 8px;
                selection-background-color: #264f78;
            }}
        """)

        # Line number area
        self._line_area = LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_area_width)
        self.updateRequest.connect(self._update_line_area)
        self._update_line_area_width(0)

        # Current line highlight
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self._highlight_current_line()

        # Bracket matching
        self._bracket_positions = []
        self.cursorPositionChanged.connect(self._match_brackets)

        # Syntax highlighter (default Python)
        self._highlighter = PythonHighlighter(self.document())

        # Auto-complete
        self._autocomplete = AutoCompletePopup(self)
        self._autocomplete.item_selected.connect(self._insert_completion)
        self._ac_enabled = True
        self._ac_min_chars = 2
        self._current_word = ""
        self._language = "python"

        # Zoom
        self._zoom_level = 0

    def set_language(self, lang: str):
        """Change syntax highlighting language."""
        self._language = lang
        cls = {
            'python': PythonHighlighter,
            'javascript': JavaScriptHighlighter,
            'html': HTMLHighlighter,
            'css': CSSHighlighter,
            'json': JSONHighlighter,
        }.get(lang, PythonHighlighter)
        self._highlighter = cls(self.document())

    def set_file_language(self, filepath: str):
        """Auto-detect language from file extension."""
        ext = Path(filepath).suffix.lower()
        lang_map = {
            '.py': 'python', '.pyw': 'python',
            '.js': 'javascript', '.jsx': 'javascript',
            '.ts': 'javascript', '.tsx': 'javascript',
            '.html': 'html', '.htm': 'html',
            '.css': 'css', '.scss': 'css',
            '.json': 'json', '.jsonl': 'json',
        }
        self.set_language(lang_map.get(ext, 'python'))

    # ── Line Numbers ──

    def line_number_area_width(self):
        digits = max(1, len(str(self.blockCount())))
        space = 12 + self.fontMetrics().horizontalAdvance('9') * digits + 12
        return space

    def _update_line_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_area(self, rect, dy):
        if dy:
            self._line_area.scroll(0, dy)
        else:
            self._line_area.update(0, rect.y(), self._line_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def line_number_area_paint_event(self, event):
        painter = QPainter(self._line_area)
        painter.fillRect(event.rect(), QColor(BG_LINE_NUM))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        current_line = self.textCursor().blockNumber()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                if block_number == current_line:
                    painter.setPen(QColor(GOLD))
                    font = painter.font()
                    font.setBold(True)
                    painter.setFont(font)
                else:
                    painter.setPen(QColor(TEXT_DIM))
                    font = painter.font()
                    font.setBold(False)
                    painter.setFont(font)

                painter.drawText(
                    0, top, self._line_area.width() - 8,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    number
                )

            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1
        painter.end()

    # ── Current Line Highlight ──

    def _highlight_current_line(self):
        extra = []
        if not self.isReadOnly():
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(QColor(BG_CURSOR_LINE))
            sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            sel.cursor = self.textCursor()
            sel.cursor.clearSelection()
            extra.append(sel)
        self.setExtraSelections(extra)

    # ── Bracket Matching ──

    def _match_brackets(self):
        """Highlight matching brackets under cursor."""
        cursor = self.textCursor()
        pos = cursor.position()
        doc = self.document()
        text = doc.toPlainText()

        self._bracket_positions = []
        if pos >= len(text):
            self.viewport().update()
            return

        char = text[pos] if pos < len(text) else ''
        char_before = text[pos - 1] if pos > 0 else ''

        # Check char at cursor or before
        check_pos = pos if char in '()[]{}' else (pos - 1 if char_before in '()[]{}' else -1)
        if check_pos < 0:
            self.viewport().update()
            return

        open_bracket = text[check_pos]
        close_map = {'(': ')', '[': ']', '{': '}'}
        open_map = {')': '(', ']': '[', '}': '{'}

        if open_bracket in close_map:
            # Find matching close
            target = close_map[open_bracket]
            depth = 1
            for i in range(check_pos + 1, len(text)):
                if text[i] == open_bracket:
                    depth += 1
                elif text[i] == target:
                    depth -= 1
                    if depth == 0:
                        self._bracket_positions = [check_pos, i]
                        break
        elif open_bracket in open_map:
            # Find matching open
            target = open_map[open_bracket]
            depth = 1
            for i in range(check_pos - 1, -1, -1):
                if text[i] == open_bracket:
                    depth += 1
                elif text[i] == target:
                    depth -= 1
                    if depth == 0:
                        self._bracket_positions = [i, check_pos]
                        break

        self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._bracket_positions:
            return

        painter = QPainter(self.viewport())
        painter.setPen(QPen(QColor(BRACKET_MATCH), 2))

        doc = self.document()
        for pos in self._bracket_positions:
            cursor = QTextCursor(doc)
            cursor.setPosition(pos)
            cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 1)
            rect = self.cursorRect(cursor)
            # Draw underline highlight
            painter.fillRect(rect.adjusted(-1, rect.height() - 3, 1, 0), QColor(BRACKET_MATCH))
        painter.end()

    # ── Tab Indentation ──

    def keyPressEvent(self, event):
        # Auto-complete trigger
        if self._ac_enabled and event.text() and event.text().isalnum():
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor)
            word = cursor.selectedText()
            cursor.movePosition(QTextCursor.MoveOperation.Right)
            self._current_word = word + event.text()
            if len(self._current_word) >= self._ac_min_chars:
                QTimer.singleShot(50, self._show_autocomplete)
            super().keyPressEvent(event)
            return

        if event.key() == Qt.Key.Key_Tab:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._dedent_line()
            else:
                self._indent_line()
            return

        # Auto-close brackets
        if event.text() in '({[':
            close_map = {'(': ')', '[': ']', '{': '}'}
            cursor = self.textCursor()
            cursor.insertText(event.text() + close_map[event.text()])
            cursor.movePosition(QTextCursor.MoveOperation.Left)
            self.setTextCursor(cursor)
            return

        # Auto-close quotes
        if event.text() in ('"', "'"):
            cursor = self.textCursor()
            cursor.insertText(event.text() * 2)
            cursor.movePosition(QTextCursor.MoveOperation.Left)
            self.setTextCursor(cursor)
            return

        # Enter — auto-indent
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            cursor = self.textCursor()
            block_text = cursor.block().text()
            indent = ''
            for ch in block_text:
                if ch in (' ', '\t'):
                    indent += ch
                else:
                    break
            # Extra indent after : or {
            stripped = block_text.rstrip()
            if stripped and stripped[-1] in (':', '{', '('):
                indent += '    '
            cursor.insertText('\n' + indent)
            self.setTextCursor(cursor)
            return

        # Hide autocomplete on other keys
        if self._autocomplete.isVisible() and event.key() not in (
            Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Return, Qt.Key.Key_Enter
        ):
            self._autocomplete.hide()

        super().keyPressEvent(event)

    def _indent_line(self):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.insertText('    ')
        self.setTextCursor(cursor)

    def _dedent_line(self):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 4)
        text = cursor.selectedText()
        if text.startswith('    '):
            cursor.removeSelectedText()
        elif text.startswith('\t'):
            cursor.removeSelectedText()

    # ── Auto-Complete ──

    def _show_autocomplete(self):
        word = self._current_word.lower()
        if not word or len(word) < self._ac_min_chars:
            return

        keywords = _KEYWORDS.get(self._language, _KEYWORDS.get('python', []))
        snippets = _SNIPPETS.get(self._language, {})

        # Combine keywords + snippet names
        all_items = list(set(keywords + list(snippets.keys())))
        matches = [item for item in all_items if item.lower().startswith(word)]

        if matches:
            # Position popup near cursor
            cursor_rect = self.cursorRect()
            global_pos = self.mapToGlobal(cursor_rect.bottomLeft())
            self._autocomplete.move(global_pos)
            self._autocomplete.show_items(matches)
        else:
            self._autocomplete.hide()

    def _insert_completion(self, text: str):
        snippets = _SNIPPETS.get(self._language, {})
        if text in snippets:
            snippet = snippets[text]
            # Remove tab stops ${n:placeholder} → just the placeholder
            clean = re.sub(r'\$\{\d+:([^}]*)\}', r'\1', snippet)
            clean = re.sub(r'\$\d+', '', clean)
            cursor = self.textCursor()
            # Delete current word
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, len(self._current_word))
            cursor.removeSelectedText()
            cursor.insertText(clean)
        else:
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, len(self._current_word))
            cursor.removeSelectedText()
            cursor.insertText(text)
        self._current_word = ""

    # ── Zoom ──

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            font = self.font()
            size = font.pointSize() + (1 if delta > 0 else -1)
            size = max(8, min(28, size))
            font.setPointSize(size)
            self.setFont(font)
            self._zoom_level = size - 11
        else:
            super().wheelEvent(event)

    def get_language(self):
        return self._language


# ═══════════════════════════════════════════════════════════════════════════
# Find/Replace Bar
# ═══════════════════════════════════════════════════════════════════════════

class FindReplaceBar(QFrame):
    """Find and replace bar — toggled with Ctrl+F / Ctrl+H."""

    def __init__(self, editor: CodeEditorWidget, parent=None):
        super().__init__(parent)
        self._editor = editor
        self.setFixedHeight(38)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_PANEL};
                border-bottom: 1px solid #ffffff10;
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        # Find
        find_label = QLabel("🔍")
        find_label.setStyleSheet("background: transparent;")
        layout.addWidget(find_label)

        self._find_input = QLineEdit()
        self._find_input.setPlaceholderText("Buscar...")
        self._find_input.setFixedWidth(200)
        self._find_input.setFont(QFont("Consolas", 10))
        self._find_input.setStyleSheet(f"""
            QLineEdit {{
                background: {BG_INPUT}; color: {TEXT};
                border: 1px solid {GOLD_DIM}40; border-radius: 4px;
                padding: 3px 8px;
            }}
        """)
        self._find_input.returnPressed.connect(self._find_next)
        self._find_input.textChanged.connect(self._find_all_highlight)
        layout.addWidget(self._find_input)

        # Count
        self._count_label = QLabel("0/0")
        self._count_label.setFixedWidth(50)
        self._count_label.setStyleSheet(f"color: {TEXT_DIM}; background: transparent; font-size: 10px;")
        layout.addWidget(self._count_label)

        # Prev/Next
        for text, handler in [("▲", self._find_prev), ("▼", self._find_next)]:
            btn = QPushButton(text)
            btn.setFixedSize(24, 24)
            btn.setStyleSheet(f"""
                QPushButton {{ background: transparent; color: {TEXT_DIM}; border: 1px solid {TEXT_DIM}30; border-radius: 4px; font-size: 10px; }}
                QPushButton:hover {{ color: {GOLD}; border-color: {GOLD}60; }}
            """)
            btn.clicked.connect(handler)
            layout.addWidget(btn)

        # Replace (optional)
        self._replace_input = QLineEdit()
        self._replace_input.setPlaceholderText("Substituir...")
        self._replace_input.setFixedWidth(200)
        self._replace_input.setFont(QFont("Consolas", 10))
        self._replace_input.setStyleSheet(f"""
            QLineEdit {{
                background: {BG_INPUT}; color: {TEXT};
                border: 1px solid {GOLD_DIM}40; border-radius: 4px;
                padding: 3px 8px;
            }}
        """)
        layout.addWidget(self._replace_input)

        for text, handler in [("Substituir", self._replace_one), ("Todas", self._replace_all)]:
            btn = QPushButton(text)
            btn.setFixedHeight(24)
            btn.setStyleSheet(f"""
                QPushButton {{ background: transparent; color: {TEXT_DIM}; border: 1px solid {TEXT_DIM}30; border-radius: 4px; padding: 0 8px; font-size: 10px; }}
                QPushButton:hover {{ color: {GOLD}; border-color: {GOLD}60; }}
            """)
            btn.clicked.connect(handler)
            layout.addWidget(btn)

        layout.addStretch()

        # Close
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(22, 22)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {TEXT_DIM}; border: none; font-size: 11px; }}
            QPushButton:hover {{ color: {RED}; }}
        """)
        close_btn.clicked.connect(self.hide)
        layout.addWidget(close_btn)

        self.hide()

    def toggle_replace(self):
        self._replace_input.setVisible(not self._replace_input.isVisible())
        self.show()
        self._find_input.setFocus()

    def _find_next(self):
        text = self._find_input.text()
        if not text:
            return
        doc = self._editor.document()
        cursor = self._editor.textCursor()
        # Start searching from current position
        found = doc.find(text, cursor)
        if found.isNull():
            # Wrap around
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            found = doc.find(text, cursor)
        if not found.isNull():
            self._editor.setTextCursor(found)
            self._update_count()

    def _find_prev(self):
        text = self._find_input.text()
        if not text:
            return
        doc = self._editor.document()
        cursor = self._editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Left)
        found = doc.find(text, cursor, QTextDocument.FindFlag.FindBackward)
        if found.isNull():
            cursor.movePosition(QTextCursor.MoveOperation.End)
            found = doc.find(text, cursor, QTextDocument.FindFlag.FindBackward)
        if not found.isNull():
            self._editor.setTextCursor(found)
            self._update_count()

    def _find_all_highlight(self):
        """Highlight all occurrences."""
        text = self._find_input.text()
        # Remove old highlights
        self._editor.setExtraSelections([])
        if not text or len(text) < 2:
            self._count_label.setText("0/0")
            return
        # Find all
        extras = []
        doc = self._editor.document()
        cursor = QTextCursor(doc)
        count = 0
        first_pos = -1
        while True:
            found = doc.find(text, cursor)
            if found.isNull():
                break
            count += 1
            if first_pos < 0:
                first_pos = found.selectionStart()
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(QColor("#4a3d00"))
            sel.cursor = found
            extras.append(sel)
            cursor = found
        # Keep current line highlight + add find highlights
        current_sel = QTextEdit.ExtraSelection()
        current_sel.format.setBackground(QColor(BG_CURSOR_LINE))
        current_sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        current_sel.cursor = self._editor.textCursor()
        current_sel.cursor.clearSelection()
        extras.append(current_sel)
        self._editor.setExtraSelections(extras)
        self._count_label.setText(f"{count}")

    def _update_count(self):
        self._find_all_highlight()

    def _replace_one(self):
        text = self._find_input.text()
        repl = self._replace_input.text()
        if not text:
            return
        cursor = self._editor.textCursor()
        if cursor.hasSelection() and cursor.selectedText() == text:
            cursor.insertText(repl)
        self._find_next()

    def _replace_all(self):
        text = self._find_input.text()
        repl = self._replace_input.text()
        if not text:
            return
        cursor = self._editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self._editor.setTextCursor(cursor)
        count = 0
        doc = self._editor.document()
        while True:
            found = doc.find(text, self._editor.textCursor())
            if found.isNull():
                break
            found.insertText(repl)
            count += 1
        self._count_label.setText(f"0")


# ═══════════════════════════════════════════════════════════════════════════
# Output/Terminal Panel
# ═══════════════════════════════════════════════════════════════════════════

class OutputPanel(QPlainTextEdit):
    """Terminal-like output panel with colored output."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Cascadia Code, Consolas, monospace", 10))
        self.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: #050510;
                color: {TEXT_DIM};
                border: none;
                padding: 8px;
            }}
        """)

    def append_output(self, text: str, color: str = None):
        self.appendPlainText(text)
        if color:
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.MoveAnchor)
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            cursor.mergeCharFormat(fmt)
        sb = self.verticalScrollBar()
        sb.setValue(sb.maximum())

    def append_html(self, html: str):
        self.appendHtml(html)
        sb = self.verticalScrollBar()
        sb.setValue(sb.maximum())

    def clear_output(self):
        self.clear()


# ═══════════════════════════════════════════════════════════════════════════
# File Explorer Tree
# ═══════════════════════════════════════════════════════════════════════════

class FileExplorer(QTreeWidget):
    """File explorer with project tree."""

    file_clicked = Signal(str)

    def __init__(self, parent=None, root_path: str = None):
        super().__init__(parent)
        self.root_path = Path(root_path) if root_path else Path.cwd()
        self.setHeaderLabel("Project Files")
        self.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {BG_SIDEBAR};
                color: {TEXT_DIM};
                border: none;
                font-size: 11px;
            }}
            QTreeWidget::item {{ padding: 3px 8px; border: none; }}
            QTreeWidget::item:selected {{ background-color: {GOLD_BG}; color: {GOLD}; }}
            QTreeWidget::item:hover {{ background-color: {BG_HOVER}; }}
        """)
        self.itemClicked.connect(self._on_click)
        self._refresh()

    def _refresh(self):
        self.clear()
        self._add_path(self.root_path, self.invisibleRootItem())

    def _add_path(self, path: Path, parent_item):
        items = []
        try:
            for entry in sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
                if entry.name.startswith('.') or entry.name == '__pycache__' or entry.name == 'node_modules':
                    continue
                items.append(entry)
        except PermissionError:
            return
        for entry in items[:50]:
            tree_item = QTreeWidgetItem(parent_item)
            tree_item.setText(0, entry.name)
            tree_item.setData(0, Qt.ItemDataRole.UserRole, str(entry))
            if entry.is_dir():
                tree_item.setIcon(0, self.style().standardIcon(self.style().StandardPixmap.SP_DirIcon))
                self._add_path(entry, tree_item)
            else:
                tree_item.setIcon(0, self.style().standardIcon(self.style().StandardPixmap.SP_FileIcon))

    def _on_click(self, item, col):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path and os.path.isfile(path):
            self.file_clicked.emit(path)

    def set_root(self, path: str):
        self.root_path = Path(path)
        self._refresh()


# ═══════════════════════════════════════════════════════════════════════════
# Programming Panel — Complete IDE
# ═══════════════════════════════════════════════════════════════════════════

class ProgrammingPanel(QWidget):
    """Full programming panel — AI code gen + editor + terminal + files."""

    sig_code_request = Signal(str)
    sig_close = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_file = None
        self._generate_handler = None
        self._execute_handler = None
        self._is_generating = False
        self._is_running = False
        self._t = 0.0
        self._last_t = time.time()

        self.setStyleSheet(f"background-color: {BG_DARK};")
        self._build_ui()
        self._setup_shortcuts()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)

    def _tick(self):
        import time as _time
        now = _time.time()
        self._t += now - self._last_t
        self._last_t = now

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ═══ HEADER ═══
        header = QFrame()
        header.setFixedHeight(48)
        header.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #12121f, stop:0.5 #1a1a2e, stop:1 #12121f);
                border-bottom: 1px solid {GOLD_DIM}40;
            }}
        """)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 8, 16, 8)

        title = QLabel("Ala de Programacao")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {GOLD}; background: transparent;")
        h_layout.addWidget(title)

        h_layout.addStretch()

        # Language selector
        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["Python", "JavaScript", "HTML", "CSS", "JSON"])
        self._lang_combo.setFixedWidth(120)
        self._lang_combo.setStyleSheet(f"""
            QComboBox {{
                background: {BG_INPUT}; color: {TEXT};
                border: 1px solid {GOLD_DIM}40; border-radius: 4px;
                padding: 3px 8px; font-size: 11px;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background: {BG_PANEL}; color: {TEXT};
                selection-background-color: {GOLD_BG};
            }}
        """)
        self._lang_combo.currentTextChanged.connect(self._on_lang_change)
        h_layout.addWidget(self._lang_combo)

        # Status
        self._status_label = QLabel("Pronto")
        self._status_label.setFont(QFont("Segoe UI", 10))
        self._status_label.setStyleSheet(f"color: {GREEN}; background: transparent;")
        h_layout.addWidget(self._status_label)

        # Close
        close_btn = QPushButton("X")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_DIM};
                border: 1px solid {TEXT_DIM}40; border-radius: 14px; font-size: 12px;
            }}
            QPushButton:hover {{ background: {RED}40; color: {RED}; border-color: {RED}; }}
        """)
        close_btn.clicked.connect(self._on_close)
        h_layout.addWidget(close_btn)

        root.addWidget(header)

        # ═══ AI PROMPT BAR ═══
        prompt_bar = QFrame()
        prompt_bar.setFixedHeight(52)
        prompt_bar.setStyleSheet(f"QFrame {{ background-color: {BG_PANEL}; border-bottom: 1px solid #ffffff10; }}")
        p_layout = QHBoxLayout(prompt_bar)
        p_layout.setContentsMargins(12, 6, 12, 6)

        ai_icon = QLabel("AI")
        ai_icon.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        ai_icon.setStyleSheet(f"color: {GOLD}; background: transparent;")
        p_layout.addWidget(ai_icon)

        self._prompt_input = QLineEdit()
        self._prompt_input.setPlaceholderText("Descreva o que quer criar... (ex: 'crie um scraper com BeautifulSoup')")
        self._prompt_input.setFont(QFont("Segoe UI", 11))
        self._prompt_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {BG_INPUT}; color: {TEXT};
                border: 1px solid {GOLD_DIM}60; border-radius: 8px; padding: 8px 14px;
                selection-background-color: {GOLD_BG};
            }}
            QLineEdit:focus {{ border-color: {GOLD}80; }}
        """)
        self._prompt_input.returnPressed.connect(self._on_generate)
        p_layout.addWidget(self._prompt_input)

        self._gen_btn = QPushButton("Generate")
        self._gen_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._gen_btn.setFixedHeight(32)
        self._gen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._gen_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {GOLD}, stop:1 {GOLD_BRIGHT});
                color: #000000; border: none; border-radius: 8px;
                padding: 0 20px; font-weight: bold;
            }}
            QPushButton:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {GOLD_BRIGHT}, stop:1 #ffe066); }}
            QPushButton:pressed {{ background: {GOLD_DIM}; }}
            QPushButton:disabled {{ background: {BG_HOVER}; color: {TEXT_DIM}; }}
        """)
        self._gen_btn.clicked.connect(self._on_generate)
        p_layout.addWidget(self._gen_btn)

        root.addWidget(prompt_bar)

        # ═══ FIND/REPLACE BAR (hidden by default) ═══

        # ═══ MAIN CONTENT — splitter ═══
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{ background-color: {GOLD_DIM}30; width: 2px; }}
            QSplitter::handle:hover {{ background-color: {GOLD}60; }}
        """)

        # ── Left: File Explorer ──
        self._file_tree = FileExplorer()
        self._file_tree.setFixedWidth(220)
        self._file_tree.file_clicked.connect(self._on_file_open)
        splitter.addWidget(self._file_tree)

        # ── Center: Editor + Output ──
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        center_splitter = QSplitter(Qt.Orientation.Vertical)
        center_splitter.setStyleSheet(f"QSplitter::handle {{ background-color: {GOLD_DIM}30; height: 2px; }}")

        # Editor
        editor_frame = QFrame()
        editor_layout = QVBoxLayout(editor_frame)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)

        editor_header = QFrame()
        editor_header.setFixedHeight(26)
        editor_header.setStyleSheet(f"background-color: {BG_HEADER}; border-bottom: 1px solid #ffffff08;")
        eh_layout = QHBoxLayout(editor_header)
        eh_layout.setContentsMargins(12, 0, 8, 0)
        eh_label = QLabel("Editor")
        eh_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        eh_label.setStyleSheet(f"color: {TEXT_DIM}; background: transparent;")
        eh_layout.addWidget(eh_label)
        eh_layout.addStretch()

        # Find/Replace bar + button
        self._find_replace = None  # created after editor
        find_btn = QPushButton("Find")
        find_btn.setFixedSize(50, 20)
        find_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {TEXT_DIM}; border: 1px solid {TEXT_DIM}20; border-radius: 3px; font-size: 9px; }}
            QPushButton:hover {{ color: {GOLD}; border-color: {GOLD}60; }}
        """)
        find_btn.clicked.connect(self._toggle_find)
        eh_layout.addWidget(find_btn)

        editor_layout.addWidget(editor_header)

        self._editor = CodeEditorWidget()
        self._editor.setPlainText(
            "# Elivea Code Editor\n"
            "# Descreva o que quer criar no prompt acima e clique Generate\n"
            "# Ou escreva codigo diretamente aqui\n\n"
            "def hello():\n"
            "    print('Ola, Mestre! Estou pronto para programar.')\n\n"
            "if __name__ == '__main__':\n"
            "    hello()\n"
        )
        editor_layout.addWidget(self._editor)

        # Find/Replace bar (inside editor frame)
        self._find_replace = FindReplaceBar(self._editor)
        editor_layout.addWidget(self._find_replace)

        center_splitter.addWidget(editor_frame)

        # Output panel
        output_frame = QFrame()
        output_layout = QVBoxLayout(output_frame)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.setSpacing(0)

        out_header = QFrame()
        out_header.setFixedHeight(28)
        out_header.setStyleSheet(f"background-color: {BG_HEADER}; border: none;")
        oh_layout = QHBoxLayout(out_header)
        oh_layout.setContentsMargins(12, 0, 8, 0)

        out_label = QLabel("Output / Terminal")
        out_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        out_label.setStyleSheet(f"color: {TEXT_DIM}; background: transparent;")
        oh_layout.addWidget(out_label)
        oh_layout.addStretch()

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFont(QFont("Segoe UI", 8))
        self._clear_btn.setFixedHeight(20)
        self._clear_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {TEXT_DIM}; border: 1px solid {TEXT_DIM}30; border-radius: 4px; padding: 0 8px; }}
            QPushButton:hover {{ color: {RED}; border-color: {RED}; }}
        """)
        self._clear_btn.clicked.connect(lambda: self._output.clear_output())
        oh_layout.addWidget(self._clear_btn)

        output_layout.addWidget(out_header)

        self._output = OutputPanel()
        self._output.setPlainText("Elivea Programming Panel v3.0\nAguardando comandos...\n")
        output_layout.addWidget(self._output)

        center_splitter.addWidget(output_frame)
        center_splitter.setStretchFactor(0, 3)
        center_splitter.setStretchFactor(1, 2)

        center_layout.addWidget(center_splitter)
        splitter.addWidget(center)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter)

        # ═══ ACTION BAR ═══
        action_bar = QFrame()
        action_bar.setFixedHeight(44)
        action_bar.setStyleSheet(f"QFrame {{ background-color: {BG_PANEL}; border-top: 1px solid #ffffff10; }}")
        a_layout = QHBoxLayout(action_bar)
        a_layout.setContentsMargins(12, 6, 12, 6)

        actions = [
            ("Run", GREEN, self._on_run),
            ("Debug", CYAN, self._on_debug),
            ("Save", GOLD, self._on_save),
            ("Open", TEXT_DIM, self._on_open_file),
            ("Analyze", PURPLE, self._on_analyze),
            ("Refactor", ORANGE, self._on_refactor),
            ("Document", BLUE, self._on_document),
            ("Test", GREEN, self._on_test),
        ]

        for text, color, handler in actions:
            btn = QPushButton(text)
            btn.setFont(QFont("Segoe UI", 9))
            btn.setFixedHeight(28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {color}; border: 1px solid {color}40;
                    border-radius: 6px; padding: 0 12px;
                }}
                QPushButton:hover {{ background: {color}20; border-color: {color}80; }}
                QPushButton:pressed {{ background: {color}40; }}
            """)
            btn.clicked.connect(handler)
            a_layout.addWidget(btn)

        a_layout.addStretch()

        self._file_label = QLabel("Novo arquivo")
        self._file_label.setFont(QFont("Segoe UI", 9))
        self._file_label.setStyleSheet(f"color: {TEXT_DIM}; background: transparent;")
        a_layout.addWidget(self._file_label)

        root.addWidget(action_bar)

    # ═══════════════════════════════════════════════════════════════════════
    # Keyboard Shortcuts
    # ═══════════════════════════════════════════════════════════════════════

    def _setup_shortcuts(self):
        # Ctrl+F — Find
        find_sc = QShortcut(QKeySequence("Ctrl+F"), self)
        find_sc.activated.connect(self._toggle_find)

        # Ctrl+H — Find & Replace
        replace_sc = QShortcut(QKeySequence("Ctrl+H"), self)
        replace_sc.activated.connect(self._toggle_replace)

        # Ctrl+S — Save
        save_sc = QShortcut(QKeySequence("Ctrl+S"), self)
        save_sc.activated.connect(self._on_save)

        # Ctrl+O — Open
        open_sc = QShortcut(QKeySequence("Ctrl+O"), self)
        open_sc.activated.connect(self._on_open_file)

        # Ctrl+R — Run
        run_sc = QShortcut(QKeySequence("Ctrl+R"), self)
        run_sc.activated.connect(self._on_run)

        # Escape — close find bar
        esc = QShortcut(QKeySequence("Escape"), self)
        esc.activated.connect(self._hide_find)

    def _toggle_find(self):
        if self._find_replace:
            self._find_replace.show()
            self._find_replace._find_input.setFocus()

    def _toggle_replace(self):
        if self._find_replace:
            self._find_replace.toggle_replace()
            self._find_replace._find_input.setFocus()

    def _hide_find(self):
        if self._find_replace:
            self._find_replace.hide()

    # ═══════════════════════════════════════════════════════════════════════
    # Language
    # ═══════════════════════════════════════════════════════════════════════

    def _on_lang_change(self, text):
        lang_map = {
            "Python": "python", "JavaScript": "javascript",
            "HTML": "html", "CSS": "css", "JSON": "json"
        }
        self._editor.set_language(lang_map.get(text, "python"))

    # ═══════════════════════════════════════════════════════════════════════
    # Actions
    # ═══════════════════════════════════════════════════════════════════════

    def _on_generate(self):
        prompt = self._prompt_input.text().strip()
        if not prompt:
            return
        self._is_generating = True
        self._status_label.setText("Gerando...")
        self._status_label.setStyleSheet(f"color: {GOLD}; background: transparent;")
        self._output.append_output(f"\nGerando codigo para: {prompt}", GOLD)
        if self._generate_handler:
            threading.Thread(target=self._generate_handler, args=(prompt,), daemon=True).start()
        else:
            self._output.append_output("Handler de geracao nao conectado", RED)
            self._finish_generating()

    def _on_run(self):
        code = self._editor.toPlainText()
        if not code.strip():
            return
        self._is_running = True
        self._status_label.setText("Executando...")
        self._status_label.setStyleSheet(f"color: {GREEN}; background: transparent;")
        self._output.append_output("\n" + "=" * 50, TEXT_DIM)
        self._output.append_output("Executando codigo...", GREEN)

        def _worker():
            try:
                suffix = ".py"
                with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False, encoding='utf-8') as f:
                    f.write(code)
                    tmp_path = f.name
                result = subprocess.run(
                    [sys.executable, tmp_path], capture_output=True, text=True,
                    timeout=15, encoding='utf-8', errors='replace'
                )
                if result.stdout:
                    self._output.append_output(result.stdout, TEXT_CODE)
                if result.stderr:
                    self._output.append_output(result.stderr, RED)
                if result.returncode == 0:
                    self._output.append_output("Execucao concluida com sucesso!", GREEN)
                else:
                    self._output.append_output(f"Exit code: {result.returncode}", RED)
                os.unlink(tmp_path)
            except subprocess.TimeoutExpired:
                self._output.append_output("Timeout (15s) — execucao interrompida", RED)
            except Exception as e:
                self._output.append_output(f"Erro: {e}", RED)
            finally:
                self._is_running = False
                QTimer.singleShot(0, lambda: self._status_label.setText("Pronto"))
                QTimer.singleShot(0, lambda: self._status_label.setStyleSheet(
                    f"color: {GREEN}; background: transparent;"))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_debug(self):
        self._output.append_output("\nModo debug — verbose output ativado", CYAN)
        self._on_run()

    def _on_save(self):
        path, _ = QFileDialog.getSaveFileName(self, "Salvar Arquivo", "", "Python Files (*.py);;JavaScript (*.js);;HTML (*.html);;CSS (*.css);;JSON (*.json);;All Files (*)")
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self._editor.toPlainText())
            self._current_file = path
            self._file_label.setText(os.path.basename(path))
            self._editor.set_file_language(path)
            self._output.append_output(f"Salvo: {path}", GREEN)

    def _on_open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Abrir Arquivo", "", "All Files (*)")
        if path:
            self.load_file(path)

    def _on_file_open(self, path: str):
        self.load_file(path)

    def load_file(self, path: str):
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            self._editor.setPlainText(content)
            self._current_file = path
            self._file_label.setText(os.path.basename(path))
            self._editor.set_file_language(path)
            # Update language combo
            ext = Path(path).suffix.lower()
            lang_name = {'.py': 'Python', '.js': 'JavaScript', '.html': 'HTML',
                         '.htm': 'HTML', '.css': 'CSS', '.json': 'JSON'}.get(ext, 'Python')
            idx = self._lang_combo.findText(lang_name)
            if idx >= 0:
                self._lang_combo.setCurrentIndex(idx)
            self._output.append_output(f"Abrindo: {path}", TEXT_DIM)
        except Exception as e:
            self._output.append_output(f"Erro ao abrir: {e}", RED)

    def _on_analyze(self):
        code = self._editor.toPlainText()
        if not code.strip():
            return
        self._output.append_output("\nAnalisando codigo...", PURPLE)
        if self._generate_handler:
            threading.Thread(target=self._generate_handler,
                           args=(f"Analise este codigo e sugira melhorias:\n\n```python\n{code[:2000]}\n```",),
                           daemon=True).start()

    def _on_refactor(self):
        code = self._editor.toPlainText()
        if not code.strip():
            return
        self._output.append_output("\nRefatorando codigo...", ORANGE)
        if self._generate_handler:
            threading.Thread(target=self._generate_handler,
                           args=(f"Refatore este codigo seguindo SOLID, DRY, KISS:\n\n```python\n{code[:2000]}\n```",),
                           daemon=True).start()

    def _on_document(self):
        code = self._editor.toPlainText()
        if not code.strip():
            return
        self._output.append_output("\nGerando documentacao...", BLUE)
        if self._generate_handler:
            threading.Thread(target=self._generate_handler,
                           args=(f"Gere docstring completa para este codigo:\n\n```python\n{code[:2000]}\n```",),
                           daemon=True).start()

    def _on_test(self):
        code = self._editor.toPlainText()
        if not code.strip():
            return
        self._output.append_output("\nGerando testes...", GREEN)
        if self._generate_handler:
            threading.Thread(target=self._generate_handler,
                           args=(f"Crie testes unitarios pytest para este codigo:\n\n```python\n{code[:2000]}\n```",),
                           daemon=True).start()

    def _on_close(self):
        self.sig_close.emit()

    # ═══════════════════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════════════════

    def set_generate_handler(self, handler):
        self._generate_handler = handler

    def set_execute_handler(self, handler):
        self._execute_handler = handler

    def set_code(self, code: str, filepath: str = None):
        self._editor.setPlainText(code)
        if filepath:
            self._current_file = filepath
            self._file_label.setText(os.path.basename(filepath))
            self._editor.set_file_language(filepath)

    def append_output(self, text: str, color: str = None):
        self._output.append_output(text, color)

    def set_generating(self, val: bool):
        self._is_generating = val
        if val:
            self._status_label.setText("Gerando...")
            self._status_label.setStyleSheet(f"color: {GOLD}; background: transparent;")
        else:
            self._status_label.setText("Pronto")
            self._status_label.setStyleSheet(f"color: {GREEN}; background: transparent;")

    def _finish_generating(self):
        self.set_generating(False)

    def set_prompt(self, text: str):
        self._prompt_input.setText(text)

    def get_code(self) -> str:
        return self._editor.toPlainText()

    def set_root_path(self, path: str):
        self._file_tree.set_root(path)
