"""
Elívea — Chat Panel (Premium Tensura Theme)
====================================================
Rewritten using proper Qt widgets for reliable input handling.
Custom-painted message bubbles with gold/white/black Tensura theme.
"""
from __future__ import annotations

import time

try:
    from PySide6.QtCore import Qt, QTimer, QPointF, QRectF
    from PySide6.QtGui import (QPainter, QPen, QBrush, QColor, QFont, QFontMetrics,
                                QLinearGradient, QRadialGradient)
    from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
                                    QFrame, QLabel, QLineEdit, QPushButton, QSizePolicy)
except ImportError:
    from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
    from PyQt6.QtGui import (QPainter, QPen, QBrush, QColor, QFont, QFontMetrics,
                              QLinearGradient, QRadialGradient)
    from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
                                  QFrame, QLabel, QLineEdit, QPushButton, QSizePolicy)

# ── Tensura Theme ──
BG = "#000000"
PANEL = "#0a0a0a"
PANEL2 = "#111111"
GOLD = "#FFD700"
GOLD_DIM = "#b8960f"
TEXT = "#ffffff"
TEXT_DIM = "#666666"
TEXT_MED = "#999999"


def _font(size: int, bold: bool = True) -> QFont:
    return QFont("Consolas", size, QFont.Weight.Bold if bold else QFont.Weight.Normal)


def _font_ui(size: int, bold: bool = False) -> QFont:
    return QFont("Segoe UI", size, QFont.Weight.Bold if bold else QFont.Weight.Normal)


def _alpha(color: str, a: int) -> QColor:
    c = QColor(color)
    c.setAlpha(a)
    return c


class ChatBubbleWidget(QWidget):
    """Premium Tensura chat bubble with fade-in animation."""

    def __init__(self, role: str, text: str, parent=None):
        super().__init__(parent)
        self._role = role
        self._text = text
        self._timestamp = time.time()
        self._is_user = (role == "user")
        self._computed_h = 40
        self._wrap_lines: list[str] = []
        self._opacity = 0.0  # fade-in
        self._slide_x = 30.0 if not self._is_user else -30.0  # slide-in offset
        self._compute_size()
        # Fade-in + slide animation
        self._fade_timer = QTimer(self)
        self._fade_timer.timeout.connect(self._fade_tick)
        self._fade_timer.start(16)  # 60fps

    def _fade_tick(self):
        self._opacity = min(1.0, self._opacity + 0.06)
        # Smooth ease-out slide
        self._slide_x *= 0.85
        if abs(self._slide_x) < 0.5:
            self._slide_x = 0.0
        self.update()
        if self._opacity >= 1.0 and self._slide_x == 0.0:
            self._fade_timer.stop()

    def _compute_size(self):
        """Pre-compute wrapped text lines and height."""
        fm = QFontMetrics(_font(9, bold=False))
        max_w = 280  # max bubble width
        words = self._text.split()
        lines = []
        line = ""
        for word in words:
            test = line + " " + word if line else word
            if fm.horizontalAdvance(test) > max_w - 20:
                lines.append(line)
                line = word
            else:
                line = test
        if line:
            lines.append(line)
        if not lines:
            lines = [""]
        self._wrap_lines = lines
        self._computed_h = 24 + len(lines) * 14 + 8  # label + lines + padding

    def heightNeeded(self) -> int:
        return self._computed_h + 6

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        bubble_max_w = min(W - 20, 300)
        a = int(255 * self._opacity)  # fade-in alpha

        # Measure actual text width for bubble sizing
        fm = QFontMetrics(_font(9, bold=False))
        max_text_w = 0
        for line in self._wrap_lines:
            w = fm.horizontalAdvance(line)
            if w > max_text_w:
                max_text_w = w
        bubble_w = min(bubble_max_w, max_text_w + 24)
        bubble_w = max(bubble_w, 50)
        bubble_h = self._computed_h

        # Position: user right-aligned, assistant left-aligned + slide offset
        if self._is_user:
            bx = W - bubble_w - 10 + self._slide_x
        else:
            bx = 10 + self._slide_x

        by = 4

        # ── Bubble background with texture ──
        if self._is_user:
            bg = QLinearGradient(bx, 0, bx + bubble_w, 0)
            bg.setColorAt(0, _alpha("#2a2000", int(200 * self._opacity)))
            bg.setColorAt(1, _alpha("#1c1600", int(180 * self._opacity)))
            p.setBrush(QBrush(bg))
            p.setPen(QPen(_alpha(GOLD, int(40 * self._opacity)), 1))
        else:
            bg = QLinearGradient(bx, 0, bx + bubble_w, 0)
            bg.setColorAt(0, _alpha("#101828", int(200 * self._opacity)))
            bg.setColorAt(1, _alpha("#0c1220", int(180 * self._opacity)))
            p.setBrush(QBrush(bg))
            p.setPen(QPen(_alpha("#5599dd", int(30 * self._opacity)), 1))
        p.drawRoundedRect(QRectF(bx, by, bubble_w, bubble_h), 10, 10)

        # ── Subtle texture overlay (noise effect) ──
        if self._opacity > 0.3:
            tex_a = int(6 * self._opacity)
            # Pre-computed noise pattern (sparse, fast)
            for ty_tex in range(int(by) + 2, int(by + bubble_h) - 2, 8):
                for tx_tex in range(int(bx) + 2, int(bx + bubble_w) - 2, 10):
                    # Simple deterministic pattern (no hash call per pixel)
                    if ((tx_tex * 7 + ty_tex * 13) & 63) < 8:  # ~12% density
                        p.setPen(Qt.PenStyle.NoPen)
                        p.setBrush(QBrush(_alpha("#ffffff", tex_a)))
                        p.drawRect(QRectF(tx_tex, ty_tex, 1, 1))

        # ── Avatar (golden RuneCore for assistant) ──
        if not self._is_user and bx > 24:
            avatar_r = 10
            avatar_x = bx - 14
            avatar_y = by + 10
            # Outer glow
            avatar_glow = QRadialGradient(avatar_x, avatar_y, avatar_r * 2.5)
            avatar_glow.setColorAt(0, _alpha(GOLD, int(30 * self._opacity)))
            avatar_glow.setColorAt(0.5, _alpha(GOLD, int(10 * self._opacity)))
            avatar_glow.setColorAt(1, _alpha(GOLD, 0))
            p.setBrush(QBrush(avatar_glow)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(avatar_x, avatar_y), avatar_r * 2.5, avatar_r * 2.5)
            # Ring
            p.setPen(QPen(_alpha(GOLD, int(120 * self._opacity)), 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(avatar_x, avatar_y), avatar_r, avatar_r)
            # Core
            core = QRadialGradient(avatar_x, avatar_y, avatar_r * 0.5)
            core.setColorAt(0, _alpha("#ffffff", int(220 * self._opacity)))
            core.setColorAt(0.5, _alpha(GOLD, int(180 * self._opacity)))
            core.setColorAt(1, _alpha(GOLD, 0))
            p.setBrush(QBrush(core)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(avatar_x, avatar_y), avatar_r * 0.5, avatar_r * 0.5)

        # ── Role label ──
        p.setFont(_font(7))
        label_x = bx + (24 if not self._is_user else 8)
        if self._is_user:
            p.setPen(QPen(QColor(GOLD), int(160 * self._opacity)))
            label = "Você"
        else:
            p.setPen(QPen(QColor("#77bbff"), int(160 * self._opacity)))
            label = "＜Elívea＞"
        p.drawText(QRectF(label_x, by + 4, bubble_w - 16, 12), Qt.AlignmentFlag.AlignLeft, label)

        # ── Message text ──
        p.setFont(_font(9, bold=False))
        p.setPen(QPen(QColor(TEXT if self._is_user else "#d0dce8"), int(220 * self._opacity)))
        ty = by + 20
        for line in self._wrap_lines:
            p.drawText(QRectF(bx + 8, ty, bubble_w - 16, 14), Qt.AlignmentFlag.AlignLeft, line)
            ty += 14

        # ── Timestamp ──
        ts = time.strftime("%H:%M", time.localtime(self._timestamp))
        p.setFont(_font(6, bold=False))
        p.setPen(QPen(QColor(TEXT_DIM), int(80 * self._opacity)))
        if self._is_user:
            p.drawText(QRectF(bx, by + bubble_h - 2, bubble_w - 8, 10),
                       Qt.AlignmentFlag.AlignRight, ts)
        else:
            p.drawText(QRectF(bx + 8, by + bubble_h - 2, bubble_w - 16, 10),
                       Qt.AlignmentFlag.AlignLeft, ts)


class TypingIndicator(QWidget):
    """Animated typing indicator with pulsing waves."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._t = 0.0
        self._last = time.time()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)  # 30fps smooth animation

    def _tick(self):
        now = time.time()
        self._t += now - self._last
        self._last = now
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Background with subtle gradient
        bg = QLinearGradient(0, 0, W, 0)
        bg.setColorAt(0, _alpha("#0a1020", 180))
        bg.setColorAt(1, _alpha("#0e1528", 180))
        p.fillRect(0, 0, W, H, QBrush(bg))
        p.setPen(QPen(_alpha("#5599dd", 25), 1))
        p.drawRoundedRect(QRectF(8, 3, W - 16, H - 6), 8, 8)

        # Avatar + Label
        p.setFont(_font(7))
        p.setPen(QPen(QColor("#77bbff"), 140))
        p.drawText(QRectF(16, 5, 120, 12), Qt.AlignmentFlag.AlignLeft, "＜Elívea＞")

        # Animated dots with pulse waves
        dot_y = 19
        base_x = 18
        for i in range(3):
            phase = (self._t * 3.0 + i * 0.4) % 1.0
            # Each dot pulses with offset timing
            pulse = math.sin(phase * math.pi * 2) * 0.5 + 0.5
            dot_x = base_x + i * 14
            dot_r = 2.5 + pulse * 1.5
            alpha = int(80 + pulse * 175)
            # Glow behind dot
            glow_r = dot_r * 3
            glow = QRadialGradient(dot_x, dot_y, glow_r)
            glow.setColorAt(0, _alpha(GOLD, int(alpha * 0.3)))
            glow.setColorAt(1, _alpha(GOLD, 0))
            p.setBrush(QBrush(glow)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(dot_x, dot_y), glow_r, glow_r)
            # Core dot
            p.setBrush(QBrush(_alpha(GOLD, alpha)))
            p.drawEllipse(QPointF(dot_x, dot_y), dot_r, dot_r)

        # "pensando" text
        p.setFont(_font(7, bold=False))
        p.setPen(QPen(QColor(TEXT_DIM), 100))
        p.drawText(QRectF(62, 5, 100, 12), Qt.AlignmentFlag.AlignLeft, "pensando")

        # Expanding pulse ring (emanates from dots)
        pulse_phase = (self._t * 1.2) % 1.0
        pulse_r = 5 + pulse_phase * 25
        pulse_alpha = int(40 * (1.0 - pulse_phase))
        if pulse_alpha > 2:
            p.setPen(QPen(_alpha(GOLD, pulse_alpha), 0.8))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(base_x + 14, dot_y), pulse_r, pulse_r)


class ChatSidebar(QWidget):
    """Premium Tensura-themed chat panel with proper Qt input handling."""

    # Time-based background colors
    _TIME_BG = {
        'dawn':    ('#1a1020', '#120a18'),   # 5-8: warm purple
        'morning':  ('#0c1420', '#0a1018'),   # 8-12: cool blue
        'afternoon':('#0a1018', '#080c14'),   # 12-17: neutral dark
        'evening':  ('#18100a', '#140c08'),   # 17-20: warm amber
        'night':    ('#06080e', '#04060a'),   # 20-5: deep night
    }

    def _get_time_bg(self) -> tuple[str, str]:
        hour = time.localtime().tm_hour
        if 5 <= hour < 8: return self._TIME_BG['dawn']
        if 8 <= hour < 12: return self._TIME_BG['morning']
        if 12 <= hour < 17: return self._TIME_BG['afternoon']
        if 17 <= hour < 20: return self._TIME_BG['evening']
        return self._TIME_BG['night']

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(360)
        self._on_send = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header (dynamic time-based background) ──
        header = QWidget()
        header.setFixedHeight(44)
        bg1, bg2 = self._get_time_bg()
        header.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {bg1}, stop:1 {bg2});
            border-bottom: 1px solid rgba(255,215,0,0.15);
        """)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(14, 0, 14, 0)
        h_layout.setSpacing(8)

        icon = QLabel("💬")
        icon.setFont(_font_ui(12))
        h_layout.addWidget(icon)

        title = QLabel("Elívea")
        title.setFont(_font_ui(10, bold=True))
        title.setStyleSheet(f"color: {TEXT}; background: transparent;")
        h_layout.addWidget(title)

        dot = QLabel("●")
        dot.setFont(_font_ui(8))
        dot.setStyleSheet(f"color: #4ade80; background: transparent; padding: 0 2px;")
        h_layout.addWidget(dot)

        status = QLabel("online")
        status.setFont(_font_ui(7))
        status.setStyleSheet(f"color: rgba(74,222,128,0.7); background: transparent;")
        h_layout.addWidget(status)

        h_layout.addStretch()

        # History button — triggers the map overlay
        self._history_btn = QPushButton("📜")
        self._history_btn.setFixedSize(28, 28)
        self._history_btn.setFont(_font_ui(11))
        self._history_btn.setToolTip("Ver histórico de conversas")
        self._history_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,215,0,0.08);
                border: 1px solid rgba(255,215,0,0.2);
                border-radius: 14px;
                color: #FFD700;
            }
            QPushButton:hover {
                background: rgba(255,215,0,0.2);
                border: 1px solid rgba(255,215,0,0.5);
            }
            QPushButton:pressed {
                background: rgba(255,215,0,0.12);
            }
        """)
        self._on_history_toggle = None
        self._history_btn.clicked.connect(lambda: self._on_history_toggle() if self._on_history_toggle else None)
        h_layout.addWidget(self._history_btn)

        layout.addWidget(header)

        # ── Messages scroll area ──
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                width: 4px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,215,0,0.15);
                border-radius: 2px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

        self._msg_container = QWidget()
        self._msg_container.setStyleSheet("background: transparent;")
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setContentsMargins(8, 8, 8, 8)
        self._msg_layout.setSpacing(4)
        self._msg_layout.addStretch()  # Push messages to top

        self._scroll.setWidget(self._msg_container)
        layout.addWidget(self._scroll, stretch=1)

        self._bubbles: list[ChatBubbleWidget] = []
        self._typing_indicator: TypingIndicator | None = None

        # ── Welcome message ──
        self.add_message("assistant",
            "Elívea online, Mestre. Todos os sistemas nominais.\n"
            "Pode falar comigo naturalmente — estou te ouvindo.")

        # ── Input area ──
        input_frame = QWidget()
        input_frame.setFixedHeight(54)
        input_frame.setStyleSheet(f"""
            background: rgba(8,8,14,240);
            border-top: 1px solid rgba(255,215,0,0.12);
        """)
        in_layout = QHBoxLayout(input_frame)
        in_layout.setContentsMargins(10, 6, 10, 6)
        in_layout.setSpacing(8)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Digite sua mensagem...")
        self._input.setFont(_font_ui(9))
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(16,16,24,220);
                color: {TEXT};
                border: 1px solid rgba(255,215,0,0.2);
                border-radius: 10px;
                padding: 6px 14px;
                selection-background-color: rgba(255,215,0,0.3);
            }}
            QLineEdit:focus {{
                border: 1px solid rgba(255,215,0,0.5);
            }}
            QLineEdit::placeholder {{
                color: rgba(255,255,255,0.25);
            }}
        """)
        self._input.returnPressed.connect(self._send)
        in_layout.addWidget(self._input, stretch=1)

        self._send_btn = QPushButton("▶")
        self._send_btn.setFixedSize(36, 36)
        self._send_btn.setFont(_font_ui(10))
        self._send_btn.setStyleSheet(f"""
            QPushButton {{
                background: qradialgradient(cx:0.5, cy:0.5, radius:0.6,
                    stop:0 rgba(255,215,0,200), stop:1 rgba(184,150,15,180));
                color: #000000;
                border: none;
                border-radius: 18px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: qradialgradient(cx:0.5, cy:0.5, radius:0.6,
                    stop:0 rgba(255,228,77,230), stop:1 rgba(255,215,0,200));
            }}
            QPushButton:pressed {{
                background: rgba(184,150,15,220);
            }}
        """)
        self._send_btn.clicked.connect(self._send)
        in_layout.addWidget(self._send_btn)

        layout.addWidget(input_frame)

    def _send(self):
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        # Play send sound
        try:
            import winsound
            winsound.Beep(880, 40)  # quick high ping
        except Exception:
            pass
        if self._on_send:
            self._on_send(text)

    def add_message(self, role: str, text: str):
        """Add a message bubble to the chat."""
        self._remove_typing()
        # Play receive sound for assistant messages
        if role == "assistant":
            try:
                import winsound
                import threading as _t
                def _rx_sound():
                    try:
                        winsound.Beep(660, 30)
                    except Exception:
                        pass
                _t.Thread(target=_rx_sound, daemon=True).start()
            except Exception:
                pass

        bubble = ChatBubbleWidget(role, text)
        self._bubbles.append(bubble)

        # Insert before the stretch
        count = self._msg_layout.count()
        self._msg_layout.insertWidget(count - 1, bubble)

        # Set fixed height for the bubble
        bubble.setFixedHeight(bubble.heightNeeded())

        # Auto-scroll to bottom
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def begin_stream(self):
        """Show typing indicator, then start streaming."""
        self._show_typing()

    def append_stream(self, delta: str):
        """Append delta to the last assistant bubble — throttled to avoid lag."""
        if self._bubbles and self._bubbles[-1]._role == "assistant" and hasattr(self._bubbles[-1], '_streaming') and self._bubbles[-1]._streaming:
            self._bubbles[-1]._text += delta
            # Throttle: only resize+repaint every 80ms (not every token)
            now = time.time()
            last = getattr(self._bubbles[-1], '_last_stream_update', 0)
            if now - last > 0.08:
                self._bubbles[-1]._last_stream_update = now
                self._bubbles[-1]._compute_size()
                self._bubbles[-1].setFixedHeight(self._bubbles[-1].heightNeeded())
                self._bubbles[-1].update()
        else:
            self._remove_typing()
            bubble = ChatBubbleWidget("assistant", delta)
            bubble._streaming = True
            bubble._last_stream_update = time.time()
            self._bubbles.append(bubble)
            count = self._msg_layout.count()
            self._msg_layout.insertWidget(count - 1, bubble)
            bubble.setFixedHeight(bubble.heightNeeded())
        QTimer.singleShot(50, self._scroll_to_bottom)

    def end_stream(self):
        """Finalize streaming bubble."""
        if self._bubbles and hasattr(self._bubbles[-1], '_streaming'):
            self._bubbles[-1]._streaming = False
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _show_typing(self):
        if self._typing_indicator:
            return
        self._typing_indicator = TypingIndicator()
        self._typing_indicator.setFixedHeight(36)
        count = self._msg_layout.count()
        self._msg_layout.insertWidget(count - 1, self._typing_indicator)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _remove_typing(self):
        if self._typing_indicator:
            self._msg_layout.removeWidget(self._typing_indicator)
            self._typing_indicator.deleteLater()
            self._typing_indicator = None

    def set_typing(self, val: bool):
        if val:
            self._show_typing()
        else:
            self._remove_typing()

    def set_on_send(self, cb):
        self._on_send = cb

    def set_on_history_toggle(self, cb):
        """Set callback for the history button in the header."""
        self._on_history_toggle = cb

    def clear_all(self):
        for b in self._bubbles:
            self._msg_layout.removeWidget(b)
            b.deleteLater()
        self._bubbles.clear()
        self._remove_typing()
