"""
Elívea — Visual Diff Viewer
=============================
Professional side-by-side code diff viewer with:
  • Line-by-line side-by-side comparison
  • Syntax-aware highlighting (keywords, strings, comments, numbers)
  • Line numbers on both sides
  • Unified/split view toggle
  • File header with path and change stats
  • Hunk headers (@@ ... @@) with context
  • Inline word-level diff highlighting
  • Smooth scroll sync between panels

100% PySide6/Qt custom paint — matches Direction B Rune Keeper theme.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

try:
    from PySide6.QtCore import Qt, QRectF, QPointF, Signal as pyqtSignal
    from PySide6.QtGui import (
        QPainter, QPen, QBrush, QColor, QFont, QLinearGradient,
        QPainterPath, QTextCursor, QTextCharFormat, QSyntaxHighlighter,
        QTextDocument,
    )
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
        QSizePolicy, QFrame, QSplitter, QTextEdit, QPushButton,
        QPlainTextEdit,
    )
except ImportError:
    from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
    from PyQt6.QtGui import (
        QPainter, QPen, QBrush, QColor, QFont, QLinearGradient,
        QPainterPath, QTextCursor, QTextCharFormat, QSyntaxHighlighter,
        QTextDocument,
    )
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
        QSizePolicy, QFrame, QSplitter, QTextEdit, QPushButton,
        QPlainTextEdit,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Theme
# ═══════════════════════════════════════════════════════════════════════════

BG = "#020204"
PANEL = "#060609"
PANEL2 = "#0d0d12"
BORDER = "#1a1a20"
GOLD = "#C9A84C"
GOLD_DIM = "#8B7A2E"
GOLD_BRIGHT = "#E8C55A"
TEXT = "#E8E0D0"
TEXT_DIM = "#6B6358"
TEXT_MED = "#9B9080"

# Diff colors
DIFF_ADD_BG = "#0a2e14"      # Dark green background
DIFF_ADD_TEXT = "#4ade80"     # Green text
DIFF_ADD_BORDER = "#1a5c30"   # Green border
DIFF_DEL_BG = "#2e0a0a"      # Dark red background
DIFF_DEL_TEXT = "#ff6b6b"     # Red text
DIFF_DEL_BORDER = "#5c1a1a"   # Red border
DIFF_CTX_BG = "transparent"   # No background
DIFF_CTX_TEXT = "#9B9080"     # Gray text
DIFF_HUNK_BG = "#1a1520"      # Purple-ish hunk header
DIFF_HUNK_TEXT = "#C9A84C"    # Gold text
DIFF_HEADER_BG = "#0a0a14"    # Dark blue-ish file header
DIFF_HEADER_TEXT = "#C9A84C"  # Gold text
LINE_NUM_BG = "#060610"
LINE_NUM_TEXT = "#3a3530"

def _hex_to_rgb(hex_color: str) -> str:
    """Convert #RRGGBB to 'R,G,B' for rgba() CSS."""
    h = hex_color.lstrip("#")
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"{r},{g},{b}"
    return "128,128,128"


# Syntax highlighting colors (dark theme)
SYNTAX_KEYWORD = "#E8C55A"    # Gold
SYNTAX_STRING = "#4ade80"     # Green
SYNTAX_COMMENT = "#5a5550"    # Dim gray
SYNTAX_NUMBER = "#ff9d6b"     # Orange
SYNTAX_FUNCTION = "#88b4ff"   # Blue
SYNTAX_CLASS = "#ff88aa"      # Pink
SYNTAX_DECORATOR = "#c084fc"  # Purple


# ═══════════════════════════════════════════════════════════════════════════
# Syntax Highlighter
# ═══════════════════════════════════════════════════════════════════════════

class _DiffSyntaxHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for diff code lines."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rules: List[Tuple[re.Pattern, str]] = []
        self._build_rules()

    def _build_rules(self):
        # Keywords
        kw = (r'\b(def|class|import|from|return|if|elif|else|for|while|try|except|'
              r'finally|with|as|yield|lambda|pass|break|continue|raise|assert|'
              r'true|false|none|self|and|or|not|in|is|async|await|print)\b')
        self._rules.append((re.compile(kw, re.IGNORECASE), SYNTAX_KEYWORD))

        # Strings (single/double/triple quotes)
        self._rules.append((re.compile(r'""".*?"""|\'\'\'.*?\'\'\''), SYNTAX_STRING))
        self._rules.append((re.compile(r'"[^"\\]*(\\.[^"\\]*)*"|\'[^\'\\]*(\\.[^\'\\]*)*\''), SYNTAX_STRING))

        # Comments
        self._rules.append((re.compile(r'#[^\n]*'), SYNTAX_COMMENT))

        # Decorators
        self._rules.append((re.compile(r'@\w+'), SYNTAX_DECORATOR))

        # Numbers
        self._rules.append((re.compile(r'\b\d+\.?\d*\b'), SYNTAX_NUMBER))

        # Function calls
        self._rules.append((re.compile(r'\b([a-zA-Z_]\w*)\s*\('), SYNTAX_FUNCTION))

        # Class names
        self._rules.append((re.compile(r'\bclass\s+([A-Z]\w*)'), SYNTAX_CLASS))

    def highlightBlock(self, text: str):
        for pattern, color in self._rules:
            for match in pattern.finditer(text):
                fmt = QTextCharFormat()
                fmt.setForeground(QColor(color))
                self.setFormat(match.start(), match.end() - match.start(), fmt)


# ═══════════════════════════════════════════════════════════════════════════
# Diff Line Model
# ═══════════════════════════════════════════════════════════════════════════

class DiffLine:
    """Single line in a diff."""
    __slots__ = ('kind', 'old_num', 'new_num', 'content', 'old_content', 'new_content')

    def __init__(self, kind: str, content: str = "",
                 old_num: int = 0, new_num: int = 0,
                 old_content: str = "", new_content: str = ""):
        self.kind = kind          # 'add', 'del', 'ctx', 'hunk', 'header'
        self.content = content    # For unified diffs
        self.old_num = old_num
        self.new_num = new_num
        self.old_content = old_content  # For side-by-side
        self.new_content = new_content


# ═══════════════════════════════════════════════════════════════════════════
# Diff Parser
# ═══════════════════════════════════════════════════════════════════════════

def parse_diff(diff_text: str) -> List[DiffLine]:
    """Parse unified diff text into DiffLine objects."""
    lines = diff_text.split('\n')
    result: List[DiffLine] = []
    old_line = 0
    new_line = 0

    for line in lines:
        if line.startswith('diff --git') or line.startswith('index '):
            result.append(DiffLine('header', content=line))
        elif line.startswith('---') and not line.startswith('----'):
            result.append(DiffLine('header', content=line))
        elif line.startswith('+++'):
            result.append(DiffLine('header', content=line))
        elif line.startswith('@@'):
            # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
            m = re.match(r'@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@(.*)', line)
            if m:
                old_line = int(m.group(1))
                new_line = int(m.group(2))
                result.append(DiffLine('hunk', content=line.strip(),
                                       old_num=old_line, new_num=new_line))
            else:
                result.append(DiffLine('hunk', content=line))
        elif line.startswith('+') and not line.startswith('+++'):
            result.append(DiffLine('add', content=line[1:],
                                   new_num=new_line))
            new_line += 1
        elif line.startswith('-') and not line.startswith('---'):
            result.append(DiffLine('del', content=line[1:],
                                   old_num=old_line))
            old_line += 1
        elif line.startswith(' '):
            result.append(DiffLine('ctx', content=line[1:],
                                   old_num=old_line, new_num=new_line))
            old_line += 1
            new_line += 1
        elif line == '':
            pass  # Skip empty lines
        else:
            # Treat as context
            result.append(DiffLine('ctx', content=line,
                                   old_num=old_line, new_num=new_line))
            old_line += 1
            new_line += 1

    return result


def to_side_by_side(lines: List[DiffLine]) -> List[Tuple[Optional[DiffLine], Optional[DiffLine]]]:
    """Convert unified diff lines to side-by-side pairs."""
    result: List[Tuple[Optional[DiffLine], Optional[DiffLine]]] = []
    pending_del: List[DiffLine] = []

    for line in lines:
        if line.kind == 'hunk' or line.kind == 'header':
            result.append((line, line))
        elif line.kind == 'del':
            pending_del.append(line)
        elif line.kind == 'add':
            if pending_del:
                old = pending_del.pop(0)
                result.append((old, line))
            else:
                result.append((None, line))
        elif line.kind == 'ctx':
            # Flush pending deletes
            while pending_del:
                result.append((pending_del.pop(0), None))
            result.append((line, line))

    # Flush remaining
    while pending_del:
        result.append((pending_del.pop(0), None))

    return result


# ═══════════════════════════════════════════════════════════════════════════
# Side-by-Side Diff Widget (custom paint)
# ═══════════════════════════════════════════════════════════════════════════

class SideBySideDiffWidget(QWidget):
    """Custom-painted side-by-side diff viewer with line numbers and syntax highlighting."""

    sig_scroll_changed = pyqtSignal(float)  # normalized scroll position (0-1)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pairs: List[Tuple[Optional[DiffLine], Optional[DiffLine]]] = []
        self._line_height = 20
        self._line_num_width = 45
        self._font = QFont("Consolas", 9)
        self._font_metrics = None
        self._scroll_offset = 0
        self._total_height = 0
        self._view_height = 0
        self._highlighter = _DiffSyntaxHighlighter()
        self._word_diffs: dict = {}  # Cache for word-level diffs

    def set_diff(self, diff_text: str):
        """Parse and display a unified diff as side-by-side."""
        lines = parse_diff(diff_text)
        self._pairs = to_side_by_side(lines)
        self._compute_total_height()
        self._scroll_offset = 0
        self.update()

    def _compute_total_height(self):
        total = 0
        for left, right in self._pairs:
            if left and left.kind == 'hunk':
                total += self._line_height + 4  # Extra spacing for hunk headers
            elif left and left.kind == 'header':
                total += self._line_height + 2
            else:
                total += self._line_height
        self._total_height = total

    def set_scroll_offset(self, offset: int):
        self._scroll_offset = max(0, offset)
        self.update()

    def resizeEvent(self, ev):
        self._view_height = self.height()
        super().resizeEvent(ev)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        W, H = self.width(), self.height()

        # Background
        p.fillRect(0, 0, W, H, QColor(BG))

        # Center divider
        mid_x = W // 2
        p.setPen(QPen(QColor(BORDER), 1))
        p.drawLine(mid_x, 0, mid_x, H)

        if not self._pairs:
            p.setPen(QPen(QColor(TEXT_DIM), 1))
            p.setFont(self._font)
            p.drawText(QRectF(0, 0, W, H), Qt.AlignmentFlag.AlignCenter, "No diff to display")
            p.end()
            return

        # Draw lines
        y = -self._scroll_offset
        lh = self._line_height
        half_w = W // 2
        code_x = self._line_num_width + 8

        for left, right in self._pairs:
            if y + lh < 0:
                y += lh + (4 if (left and left.kind in ('hunk', 'header')) else 0)
                continue
            if y > H:
                break

            # Extra spacing for headers/hunks
            extra = 0
            if left and left.kind == 'hunk':
                extra = 4
            elif left and left.kind == 'header':
                extra = 2

            # ── Draw left side ──
            self._draw_line_panel(p, left, 0, mid_x, y, lh, code_x, is_left=True)

            # ── Draw right side ──
            self._draw_line_panel(p, right, mid_x, W, y, lh, code_x, is_left=False)

            # ── Center divider accent for changed lines ──
            if left and left.kind in ('add', 'del'):
                accent_color = DIFF_ADD_BORDER if left.kind == 'add' else DIFF_DEL_BORDER
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(QColor(accent_color)))
                p.drawRect(mid_x - 1, y, 2, lh)

            y += lh + extra

        p.end()

    def _draw_line_panel(self, p: QPainter, line: Optional[DiffLine],
                         x_start: int, x_end: int, y: float, lh: int,
                         code_x: int, is_left: bool):
        """Draw a single panel (left or right) of a diff line."""
        w = x_end - x_start

        if line is None:
            # Empty panel (deletion on add side, or vice versa)
            p.fillRect(x_start, y, w, lh, QColor("#080810"))
            return

        if line.kind == 'hunk':
            # Hunk header
            p.fillRect(x_start, y, w, lh + 4, QColor(DIFF_HUNK_BG))
            p.setFont(self._font)
            p.setPen(QPen(QColor(DIFF_HUNK_TEXT), 180))
            text = line.content[:80] if line.content else "@@"
            p.drawText(QRectF(x_start + 8, y, w - 16, lh),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
            return

        if line.kind == 'header':
            # File header
            p.fillRect(x_start, y, w, lh + 2, QColor(DIFF_HEADER_BG))
            p.setFont(self._font)
            p.setPen(QPen(QColor(DIFF_HEADER_TEXT), 180))
            text = line.content[:80] if line.content else ""
            p.drawText(QRectF(x_start + 8, y, w - 16, lh),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
            return

        # Background based on type
        if line.kind == 'add':
            bg_color = DIFF_ADD_BG
        elif line.kind == 'del':
            bg_color = DIFF_DEL_BG
        else:
            bg_color = DIFF_CTX_BG

        if bg_color != "transparent":
            p.fillRect(x_start, y, w, lh, QColor(bg_color))

        # Line number
        if line.kind == 'ctx':
            num = line.old_num if is_left else line.new_num
        elif line.kind == 'del' and is_left:
            num = line.old_num
        elif line.kind == 'add' and not is_left:
            num = line.new_num
        else:
            num = 0

        if num > 0:
            p.setFont(QFont("Consolas", 8))
            num_color = LINE_NUM_TEXT
            if line.kind == 'add':
                num_color = DIFF_ADD_BORDER
            elif line.kind == 'del':
                num_color = DIFF_DEL_BORDER
            p.setPen(QPen(QColor(num_color), 140))
            p.drawText(QRectF(x_start + 2, y, self._line_num_width - 4, lh),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       str(num))

        # Code content
        content = line.content if line.content else ""
        if len(content) > 200:
            content = content[:200] + "..."

        if line.kind == 'add':
            text_color = DIFF_ADD_TEXT
        elif line.kind == 'del':
            text_color = DIFF_DEL_TEXT
        else:
            text_color = DIFF_CTX_TEXT

        # Simple syntax coloring
        p.setFont(self._font)
        self._draw_syntax_text(p, content, x_start + code_x, y, w - code_x - 8, lh, text_color)

        # Left border accent
        if line.kind == 'add':
            accent = DIFF_ADD_BORDER
        elif line.kind == 'del':
            accent = DIFF_DEL_BORDER
        else:
            accent = None

        if accent:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(accent)))
            p.drawRect(x_start, y, 2, lh)

    def _draw_syntax_text(self, p: QPainter, text: str, x: float, y: float,
                          max_w: float, lh: int, default_color: str):
        """Draw text with basic syntax highlighting."""
        if not text:
            return

        # Simple token-based highlighting
        tokens = self._tokenize(text)
        cx = x

        for token_text, token_type in tokens:
            if cx >= x + max_w:
                break

            if token_type == 'keyword':
                color = SYNTAX_KEYWORD
            elif token_type == 'string':
                color = SYNTAX_STRING
            elif token_type == 'comment':
                color = SYNTAX_COMMENT
            elif token_type == 'number':
                color = SYNTAX_NUMBER
            elif token_type == 'decorator':
                color = SYNTAX_DECORATOR
            else:
                color = default_color

            p.setPen(QPen(QColor(color), 180))
            # Truncate if would exceed max width
            display_text = token_text
            while cx + len(display_text) * 5.4 > x + max_w and len(display_text) > 1:
                display_text = display_text[:-1]

            p.drawText(QRectF(cx, y, max_w + x - cx, lh),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       display_text)
            cx += len(token_text) * 5.4  # Approximate character width

    def _tokenize(self, text: str) -> List[Tuple[str, str]]:
        """Simple tokenizer for syntax highlighting."""
        tokens = []
        i = 0
        n = len(text)

        while i < n:
            # Comments
            if text[i] == '#':
                tokens.append((text[i:], 'comment'))
                break

            # Strings
            if text[i] in ('"', "'"):
                quote = text[i]
                j = i + 1
                while j < n and text[j] != quote:
                    if text[j] == '\\':
                        j += 1
                    j += 1
                tokens.append((text[i:j + 1], 'string'))
                i = j + 1
                continue

            # Decorators
            if text[i] == '@':
                j = i + 1
                while j < n and text[j].isalnum():
                    j += 1
                tokens.append((text[i:j], 'decorator'))
                i = j
                continue

            # Numbers
            if text[i].isdigit():
                j = i + 1
                while j < n and (text[j].isdigit() or text[j] == '.'):
                    j += 1
                tokens.append((text[i:j], 'number'))
                i = j
                continue

            # Words (keywords or identifiers)
            if text[i].isalpha() or text[i] == '_':
                j = i + 1
                while j < n and (text[j].isalnum() or text[j] == '_'):
                    j += 1
                word = text[i:j]
                kw = {'def', 'class', 'import', 'from', 'return', 'if', 'elif',
                      'else', 'for', 'while', 'try', 'except', 'finally', 'with',
                      'as', 'yield', 'lambda', 'pass', 'break', 'continue', 'raise',
                      'assert', 'True', 'False', 'None', 'self', 'and', 'or', 'not',
                      'in', 'is', 'async', 'await', 'print'}
                if word in kw:
                    tokens.append((word, 'keyword'))
                elif j < n and text[j] == '(':
                    tokens.append((word, 'function'))
                else:
                    tokens.append((word, 'text'))
                i = j
                continue

            # Other characters
            tokens.append((text[i], 'text'))
            i += 1

        return tokens


# ═══════════════════════════════════════════════════════════════════════════
# Unified Diff Widget (alternative view)
# ═══════════════════════════════════════════════════════════════════════════

class UnifiedDiffWidget(QWidget):
    """Unified diff view (single column) with line numbers and syntax highlighting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lines: List[DiffLine] = []
        self._line_height = 20
        self._font = QFont("Consolas", 9)
        self._scroll_offset = 0
        self._total_height = 0

    def set_diff(self, diff_text: str):
        self._lines = parse_diff(diff_text)
        self._total_height = len(self._lines) * self._line_height
        self._scroll_offset = 0
        self.update()

    def set_scroll_offset(self, offset: int):
        self._scroll_offset = max(0, offset)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        W, H = self.width(), self.height()

        p.fillRect(0, 0, W, QColor(BG))

        if not self._lines:
            p.setPen(QPen(QColor(TEXT_DIM), 1))
            p.setFont(self._font)
            p.drawText(QRectF(0, 0, W, H), Qt.AlignmentFlag.AlignCenter, "No diff to display")
            p.end()
            return

        y = -self._scroll_offset
        lh = self._line_height
        num_w = 80
        code_x = num_w + 8

        for line in self._lines:
            if y + lh < 0:
                y += lh
                continue
            if y > H:
                break

            # Background
            if line.kind == 'add':
                p.fillRect(0, y, W, lh, QColor(DIFF_ADD_BG))
            elif line.kind == 'del':
                p.fillRect(0, y, W, lh, QColor(DIFF_DEL_BG))
            elif line.kind == 'hunk':
                p.fillRect(0, y, W, lh, QColor(DIFF_HUNK_BG))
            elif line.kind == 'header':
                p.fillRect(0, y, W, lh, QColor(DIFF_HEADER_BG))

            # Line numbers
            p.setFont(QFont("Consolas", 8))
            if line.kind in ('ctx', 'del') and line.old_num:
                p.setPen(QPen(QColor(LINE_NUM_TEXT), 130))
                p.drawText(QRectF(2, y, 36, lh),
                           Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                           str(line.old_num))
            if line.kind in ('ctx', 'add') and line.new_num:
                p.setPen(QPen(QColor(LINE_NUM_TEXT), 130))
                p.drawText(QRectF(40, y, 36, lh),
                           Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                           str(line.new_num))

            # Prefix
            if line.kind == 'add':
                prefix = '+'
                color = DIFF_ADD_TEXT
            elif line.kind == 'del':
                prefix = '-'
                color = DIFF_DEL_TEXT
            elif line.kind == 'hunk' or line.kind == 'header':
                prefix = ' '
                color = DIFF_HUNK_TEXT if line.kind == 'hunk' else DIFF_HEADER_TEXT
            else:
                prefix = ' '
                color = DIFF_CTX_TEXT

            p.setFont(self._font)
            p.setPen(QPen(QColor(color), 180))
            p.drawText(QRectF(num_w, y, 12, lh),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, prefix)

            # Content
            content = line.content
            if len(content) > 120:
                content = content[:120] + "..."
            p.drawText(QRectF(code_x, y, W - code_x - 8, lh),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, content)

            # Left accent bar
            if line.kind == 'add':
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(QColor(DIFF_ADD_BORDER)))
                p.drawRect(0, y, 3, lh)
            elif line.kind == 'del':
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(QColor(DIFF_DEL_BORDER)))
                p.drawRect(0, y, 3, lh)

            y += lh

        p.end()


# ═══════════════════════════════════════════════════════════════════════════
# Diff Viewer (main widget with controls)
# ═══════════════════════════════════════════════════════════════════════════

class VisualDiffViewer(QWidget):
    """Complete diff viewer with toggle between side-by-side and unified views."""

    sig_approve = pyqtSignal()
    sig_discard = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = "side_by_side"  # "side_by_side" or "unified"
        self._diff_text = ""
        self._file_path = ""
        self._added = 0
        self._removed = 0
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header bar ──
        header = QWidget()
        header.setFixedHeight(36)
        header.setStyleSheet(f"""
            background: {PANEL2};
            border-bottom: 1px solid {BORDER};
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 0, 12, 0)
        header_layout.setSpacing(8)

        # File path
        self._file_label = QLabel("📁 diff")
        self._file_label.setFont(QFont("Consolas", 9))
        self._file_label.setStyleSheet(f"color: {GOLD}; background: transparent;")
        header_layout.addWidget(self._file_label)

        # Stats
        self._stats_label = QLabel("")
        self._stats_label.setFont(QFont("Consolas", 9))
        self._stats_label.setStyleSheet(f"color: {TEXT_DIM}; background: transparent;")
        header_layout.addWidget(self._stats_label)

        header_layout.addStretch()

        # View toggle buttons
        self._btn_split = QPushButton("⊞ Split")
        self._btn_split.setFont(QFont("Consolas", 8))
        self._btn_split.setFixedHeight(24)
        self._btn_split.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_split.setStyleSheet(f"""
            QPushButton {{
                background: rgba({_hex_to_rgb(GOLD)}, 0.15);
                border: 1px solid rgba({_hex_to_rgb(GOLD)}, 0.3);
                border-radius: 4px;
                color: {GOLD};
                padding: 2px 8px;
            }}
            QPushButton:hover {{ background: rgba({_hex_to_rgb(GOLD)}, 0.25); }}
        """)
        self._btn_split.clicked.connect(lambda: self._set_mode("side_by_side"))
        header_layout.addWidget(self._btn_split)

        self._btn_unified = QPushButton("☰ Unified")
        self._btn_unified.setFont(QFont("Consolas", 8))
        self._btn_unified.setFixedHeight(24)
        self._btn_unified.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_unified.setStyleSheet(f"""
            QPushButton {{
                background: rgba({_hex_to_rgb(GOLD)}, 0.08);
                border: 1px solid rgba({_hex_to_rgb(GOLD)}, 0.15);
                border-radius: 4px;
                color: {TEXT_DIM};
                padding: 2px 8px;
            }}
            QPushButton:hover {{ background: rgba({_hex_to_rgb(GOLD)}, 0.15); }}
        """)
        self._btn_unified.clicked.connect(lambda: self._set_mode("unified"))
        header_layout.addWidget(self._btn_unified)

        layout.addWidget(header)

        # ── Diff views ──
        self._split_view = SideBySideDiffWidget()
        self._unified_view = UnifiedDiffWidget()
        self._unified_view.hide()

        layout.addWidget(self._split_view, stretch=1)
        layout.addWidget(self._unified_view, stretch=1)

        # ── Action buttons ──
        btn_row = QWidget()
        btn_row.setFixedHeight(36)
        btn_row.setStyleSheet(f"background: {PANEL2}; border-top: 1px solid {BORDER};")
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(12, 4, 12, 4)
        btn_layout.setSpacing(8)

        btn_layout.addStretch()

        self._btn_discard = QPushButton("✗ Descartar")
        self._btn_discard.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        self._btn_discard.setFixedHeight(28)
        self._btn_discard.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_discard.setStyleSheet(f"""
            QPushButton {{
                background: rgba({_hex_to_rgb('#ff4d6d')}, 0.12);
                border: 1px solid rgba({_hex_to_rgb('#ff4d6d')}, 0.3);
                border-radius: 5px;
                color: #ff4d6d;
                padding: 4px 14px;
            }}
            QPushButton:hover {{ background: rgba({_hex_to_rgb('#ff4d6d')}, 0.25); }}
        """)
        self._btn_discard.clicked.connect(self.sig_discard.emit)
        btn_layout.addWidget(self._btn_discard)

        self._btn_approve = QPushButton("✓ Aplicar Alterações")
        self._btn_approve.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        self._btn_approve.setFixedHeight(28)
        self._btn_approve.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_approve.setStyleSheet(f"""
            QPushButton {{
                background: rgba({_hex_to_rgb('#4ade80')}, 0.15);
                border: 1px solid rgba({_hex_to_rgb('#4ade80')}, 0.4);
                border-radius: 5px;
                color: #4ade80;
                padding: 4px 14px;
            }}
            QPushButton:hover {{ background: rgba({_hex_to_rgb('#4ade80')}, 0.3); }}
        """)
        self._btn_approve.clicked.connect(self.sig_approve.emit)
        btn_layout.addWidget(self._btn_approve)

        layout.addWidget(btn_row)

    def set_diff(self, diff_text: str, file_path: str = ""):
        """Set the diff to display."""
        self._diff_text = diff_text
        self._file_path = file_path

        # Parse stats
        self._added = sum(1 for l in diff_text.split('\n') if l.startswith('+') and not l.startswith('+++'))
        self._removed = sum(1 for l in diff_text.split('\n') if l.startswith('-') and not l.startswith('---'))

        # Update header
        display_path = file_path if file_path else "changes"
        if len(display_path) > 50:
            display_path = "..." + display_path[-47:]
        self._file_label.setText(f"📁 {display_path}")
        self._stats_label.setText(f"+{self._added} / -{self._removed}")

        # Set diff in both views
        self._split_view.set_diff(diff_text)
        self._unified_view.set_diff(diff_text)

        self.show()

    def clear(self):
        """Clear the diff viewer."""
        self._diff_text = ""
        self._file_path = ""
        self._split_view._pairs = []
        self._unified_view._lines = []
        self.hide()

    def _set_mode(self, mode: str):
        self._mode = mode
        if mode == "side_by_side":
            self._split_view.show()
            self._unified_view.hide()
            self._btn_split.setStyleSheet(f"""
                QPushButton {{
                    background: rgba({_hex_to_rgb(GOLD)}, 0.15);
                    border: 1px solid rgba({_hex_to_rgb(GOLD)}, 0.3);
                    border-radius: 4px;
                    color: {GOLD};
                    padding: 2px 8px;
                }}
            """)
            self._btn_unified.setStyleSheet(f"""
                QPushButton {{
                    background: rgba({_hex_to_rgb(GOLD)}, 0.08);
                    border: 1px solid rgba({_hex_to_rgb(GOLD)}, 0.15);
                    border-radius: 4px;
                    color: {TEXT_DIM};
                    padding: 2px 8px;
                }}
            """)
        else:
            self._split_view.hide()
            self._unified_view.show()
            self._btn_unified.setStyleSheet(f"""
                QPushButton {{
                    background: rgba({_hex_to_rgb(GOLD)}, 0.15);
                    border: 1px solid rgba({_hex_to_rgb(GOLD)}, 0.3);
                    border-radius: 4px;
                    color: {GOLD};
                    padding: 2px 8px;
                }}
            """)
            self._btn_split.setStyleSheet(f"""
                QPushButton {{
                    background: rgba({_hex_to_rgb(GOLD)}, 0.08);
                    border: 1px solid rgba({_hex_to_rgb(GOLD)}, 0.15);
                    border-radius: 4px;
                    color: {TEXT_DIM};
                    padding: 2px 8px;
                }}
            """)
