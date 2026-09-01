"""
Elívea — Professional Native Widgets
============================================
100% PySide6/Qt widgets — no web, no QWebEngine, no browser.
Matches the concept design with glassmorphism, gold theme, animations.

by: bryan
"""
from __future__ import annotations
import math
import random
import time
from collections import deque

import psutil

try:
    from PySide6.QtCore import (Qt, QTimer, QPointF, QRectF, QSize, QEasingCurve,
                                 QPropertyAnimation, QAbstractAnimation, Signal as pyqtSignal)
    from PySide6.QtGui import (QPainter, QPen, QBrush, QColor, QFont, QRadialGradient,
                                QLinearGradient, QPainterPath, QFontMetrics)
    from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                                    QScrollArea, QFrame, QLineEdit, QSizePolicy, QGraphicsOpacityEffect)
    _qt = "PySide6"
except ImportError:
    from PyQt6.QtCore import (Qt, QTimer, QPointF, QRectF, QSize, QEasingCurve,
                               QPropertyAnimation, QAbstractAnimation, pyqtSignal)
    from PyQt6.QtGui import (QPainter, QPen, QBrush, QColor, QFont, QRadialGradient,
                              QLinearGradient, QPainterPath, QFontMetrics)
    from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                                  QScrollArea, QFrame, QLineEdit, QSizePolicy, QGraphicsOpacityEffect)
    _qt = "PyQt6"

# ═══════════════════════════════════════════════════════════════════════════
# Theme Constants
# ═══════════════════════════════════════════════════════════════════════════
BG = "#000000"
PANEL = "#0a0a0a"
PANEL2 = "#111111"
BORDER = "#1a1a1a"
BORDER_GOLD = "#3d3200"
GOLD = "#FFD700"
GOLD_DIM = "#b8960f"
GOLD_BRIGHT = "#ffe44d"
TEXT = "#ffffff"
TEXT_DIM = "#666666"
TEXT_MED = "#999999"
GREEN = "#4ade80"
RED = "#f87171"

RUNES = list("ᚠᚢᚦᚨᚱᚲᚷᚹᚺᚾᛁᛃᛇᛈᛉᛊᛏᛒᛖᛗᛚᛜᛞᛟ")


def _font(size: int, bold: bool = True, mono: bool = True) -> QFont:
    name = "Consolas" if mono else "Segoe UI"
    return QFont(name, size, QFont.Weight.Bold if bold else QFont.Weight.Normal)


def _font_serif(size: int) -> QFont:
    return QFont("Georgia", size, QFont.Weight.Bold)


def _alpha(color: str, a: int) -> QColor:
    c = QColor(color)
    c.setAlpha(a)
    return c


# ═══════════════════════════════════════════════════════════════════════════
# Glass Panel Base
# ═══════════════════════════════════════════════════════════════════════════
class GlassPanel(QFrame):
    """Base panel with optional dynamic glow border that reacts to activity."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._activity_level = 0.0  # 0=idle, 1=high activity
        self._glow_color = "rgba(255,215,0,0.08)"
        self._update_style()

    def set_activity(self, level: float, color: str = None):
        """Set activity level 0-1 and optional glow color."""
        self._activity_level = max(0.0, min(1.0, level))
        if color:
            self._glow_color = color
        self._update_style()

    def _update_style(self):
        a = self._activity_level
        # Glow intensity scales with activity
        border_a = int(8 + a * 40)  # 8-48 alpha
        glow_a = int(0 + a * 25)   # 0-25 alpha for box-shadow effect
        self.setStyleSheet(f"""
            QFrame {{
                background: rgba(15,15,15,200);
                border: 1px solid rgba(255,215,0,{border_a});
                border-radius: 12px;
            }}
        """)



# ═══════════════════════════════════════════════════════════════════════════
# RuneCore Widget — Mystical Compass (Tensura-style magic circle)
# ═══════════════════════════════════════════════════════════════════════════
class RuneCoreWidget(QWidget):
    """Mystical compass — cyan runic outer ring + golden hexagram star.
    Faithful to the user's concept image: concentric circles with tick marks,
    runic inscriptions between rings, cross lines, 6-pointed star core glow.
    Color changes by state: idle=cyan+gold, thinking=orange, success=green,
    error=red, speaking=bright gold, listening=blue."""

    # Labels per state (static)
    STATE_LABELS = {
        "idle": "○ EM ESPERA", "thinking": "◐ PROCESSANDO",
        "speaking": "● FALANDO", "success": "✓ CONCLUÍDO",
        "error": "✗ ERRO", "listening": "◉ ESCUTANDO",
    }

    def _get_state_colors(self) -> dict:
        """Dynamic colors — reads live from theme palette C."""
        try:
            import sys
            _qt_mod = sys.modules.get('EliveaAI_Clone.ui.qt_ui') or sys.modules.get('ui.qt_ui')
            C = _qt_mod.C
            pri = C.PRI; gold = C.GOLD; green = C.GREEN; red = C.RED; acc = C.ACC
        except Exception:
            pri = "#00e5ff"; gold = "#FFD700"; green = "#4ade80"; red = "#f87171"; acc = "#ffedb0"
        return {
            "idle":      {"ring": pri,  "star": gold, "glow": gold},
            "thinking":  {"ring": acc,  "star": gold, "glow": pri},
            "speaking":  {"ring": gold, "star": gold, "glow": gold},
            "success":   {"ring": green,"star": green,"glow": green},
            "error":     {"ring": red,  "star": red,  "glow": red},
            "listening": {"ring": pri,  "star": pri,  "glow": pri},
        }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._t = 0.0
        self._last = time.time()
        self._rings = [0.0, 0.0, 0.0]  # outer_text, inner_text, star
        self._glow = 0.85
        self._glow_tgt = 0.85
        self._core_scale = 1.0
        self._state = "idle"
        self._particles: list[list[float]] = []
        self._shockwaves: list[float] = []
        self._breath = 0.0
        self._color_r = 0.0
        self._color_g = 0.898
        self._color_b = 1.0  # start cyan
        self._show_center = True
        self._transition_t = 1.0
        self._onboarding_phase = 0
        self._onboarding_t = 0.0
        self._onboarding_start_time = 0.0
        self._mouse_x = 0.5
        self._mouse_y = 0.5
        self._audio_level = 0.0
        self._rune_text = "ᚠᚢᚦᚨᚱᚲᚷᚹᚺᚾᛁᛃᛈᛇᛉᛊᛏᛒᛖᛗᛚᛜᛞᛟᚠᚢᚦᚨᚱᚲᚷᚹᚺᚾᛁᛃᛈᛇᛉᛊᛏᛒᛖᛗᛚᛜᛞᛟᚠᚢᚦᚨᚱᚲᚷᚹᚺᚾᛁᛃᛈᛇᛉᛊᛏᛒᛖᛗᛚᛜᛞᛟ"
        self.setMouseTracking(True)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)

    def set_center_detail(self, show: bool):
        self._show_center = show
        self.update()

    def set_audio_level(self, level: float):
        target = max(0.0, min(1.0, level))
        self._audio_level += (target - self._audio_level) * 0.3
        if level > 0.3:
            self._glow_tgt = min(1.3, self._glow_tgt + level * 0.15)

    def set_state(self, s: str):
        old = self._state
        self._state = s
        if s != old:
            self._shockwaves.append(0.0)
            self._transition_t = 0.0
        targets = {"speaking": 1.15, "thinking": 0.95, "success": 1.0,
                   "error": 1.0, "listening": 0.85, "idle": 0.55}
        self._glow_tgt = targets.get(s, 0.55)

    def _lerp_color(self, target_hex: str, speed: float = 0.03):
        tc = QColor(target_hex)
        tr, tg, tb = tc.red() / 255, tc.green() / 255, tc.blue() / 255
        dx = abs(tr - self._color_r) + abs(tg - self._color_g) + abs(tb - self._color_b)
        sp = speed * (1.0 + dx * 2.0)
        self._color_r += (tr - self._color_r) * min(sp, 0.15)
        self._color_g += (tg - self._color_g) * min(sp, 0.15)
        self._color_b += (tb - self._color_b) * min(sp, 0.15)

    def _tick(self):
        now = time.time()
        dt = now - self._last
        self._t += dt
        self._last = now
        if self._transition_t < 1.0:
            self._transition_t = min(1.0, self._transition_t + dt * 1.6)
        base = {"speaking": 0.55, "thinking": 0.35, "listening": 0.2,
                "success": 0.8, "error": 0.6}.get(self._state, 0.12)
        ease = 1.0 - (1.0 - self._transition_t) ** 3
        ring_base = base * (0.3 + 0.7 * ease)
        speeds = [0.3, -0.2, 0.15]
        for i in range(3):
            self._rings[i] = (self._rings[i] + ring_base * speeds[i]) % 360
        glow_diff = self._glow_tgt - self._glow
        self._glow += glow_diff * (0.02 + 0.06 * ease)
        sp = 0.1 if self._state in ("speaking", "success", "error") else 0.04
        self._core_scale += ((1.08 if self._state == "speaking" else 1.0) - self._core_scale) * sp
        self._breath = (self._breath + 0.02) % (2 * math.pi)
        sc = self._get_state_colors().get(self._state, self._get_state_colors()["idle"])
        self._lerp_color(sc["ring"])
        self._shockwaves = [s + 0.02 for s in self._shockwaves if s + 0.02 < 1.0]
        if self._onboarding_phase > 0:
            self._onboarding_t += dt
            if time.time() - getattr(self, '_onboarding_start_time', 0) > 7.0:
                self._onboarding_phase = 0
                self._glow_tgt = 0.85
        audio_boost = 1.0 + self._audio_level * 2.0
        max_p = {"speaking": 45, "thinking": 30, "success": 40, "error": 25,
                 "listening": 35}.get(self._state, 12)
        max_p = int(max_p * audio_boost)
        prob = 0.8 if self._state != "idle" else 0.25
        prob = min(1.0, prob * audio_boost)
        if len(self._particles) < max_p and random.random() < prob:
            ang = random.uniform(0, 2 * math.pi)
            dist = random.uniform(0.1, 0.45)
            spd = random.uniform(0.002, 0.006) * audio_boost
            size = random.uniform(0.6, 1.2) * audio_boost
            self._particles.append([ang, dist, spd, random.uniform(0.6, 1.0), size])
        new_p = []
        for p_data in self._particles:
            a, d, s, life = p_data[0], p_data[1], p_data[2], p_data[3]
            sz = p_data[4] if len(p_data) > 4 else 1.0
            nd = d + s
            nl = life - 0.004
            if nl > 0 and nd < 1.4:
                new_p.append([a, nd, s, nl, sz])
        self._particles = new_p
        self.update()

    def start_onboarding(self):
        self._onboarding_phase = 1
        self._onboarding_t = 0.0
        self._onboarding_start_time = time.time()
        self.update()
        QTimer.singleShot(9000, self._force_end_onboarding)

    def _force_end_onboarding(self):
        if self._onboarding_phase > 0:
            self._onboarding_phase = 0
            self._glow_tgt = 0.85
            self.update()

    def _draw_onboarding(self, p, W, H, cx, cy, R):
        t = self._onboarding_t
        if t < 2.0:
            overlay_a = int(80 * (t / 0.6)) if t < 0.6 else int(80 * (1.0 - (t - 0.6) / 1.4))
            p.fillRect(0, 0, W, H, _alpha("#000000", max(0, overlay_a)))
        if 1.5 < t < 3.5:
            flash_t = (t - 1.5) / 2.0
            flash_r = R * flash_t * 2.8
            flash_a = int(90 * (1.0 - flash_t))
            if flash_a > 0:
                flash = QRadialGradient(cx, cy, flash_r)
                flash.setColorAt(0, _alpha("#ffffff", flash_a))
                flash.setColorAt(0.2, _alpha(GOLD, int(flash_a * 0.7)))
                flash.setColorAt(0.6, _alpha(GOLD, int(flash_a * 0.3)))
                flash.setColorAt(1, _alpha(GOLD, 0))
                p.setBrush(QBrush(flash)); p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QRectF(cx - flash_r, cy - flash_r, flash_r * 2, flash_r * 2))
        if 2.5 < t < 6.0:
            text_t = min(1.0, (t - 2.5) / 3.0)
            text_t = 1.0 - (1.0 - text_t) ** 3
            full_text = "\uff1cElivea\uff1e"
            chars_to_show = int(len(full_text) * text_t)
            shown = full_text[:chars_to_show]
            text_a = int(255 * text_t)
            p.setFont(_font(max(10, int(R * 0.08))))
            p.setPen(QPen(_alpha("#ffffff", text_a)))
            p.drawText(QRectF(0, cy - R * 0.15, W, R * 0.15),
                       Qt.AlignmentFlag.AlignCenter, shown)
        if 5.0 < t < 7.5:
            sub_t = min(1.0, (t - 5.0) / 2.0)
            sub_t = 1.0 - (1.0 - sub_t) ** 2
            sub_a = int(200 * sub_t)
            p.setFont(_font(8, bold=False))
            p.setPen(QPen(_alpha(TEXT_DIM, sub_a)))
            p.drawText(QRectF(0, cy + R * 1.3, W, 16),
                       Qt.AlignmentFlag.AlignCenter, "Todos os sistemas nominais, Mestre.")
        if t >= 7.0:
            self._onboarding_phase = 0
            self._glow_tgt = 0.85

    def mouseMoveEvent(self, ev):
        W, H = self.width(), self.height()
        if W > 0 and H > 0:
            self._mouse_x = ev.position().x() / W
            self._mouse_y = ev.position().y() / H

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        px = (self._mouse_x - 0.5) * 6
        py = (self._mouse_y - 0.5) * 6
        cx, cy = W / 2 + px, H / 2 + py
        R = min(W, H) * 0.44

        sc = self._get_state_colors().get(self._state, self._get_state_colors()["idle"])
        rc = QColor(sc["ring"])
        star_c = QColor(sc["star"])
        glow_c = QColor(sc["glow"])
        g = max(0.0, min(1.2, self._glow))
        breath = 1.0 + 0.012 * math.sin(self._breath)

        # Interpolated ring color
        cr = max(0, min(255, int(self._color_r * 255)))
        cg = max(0, min(255, int(self._color_g * 255)))
        cb = max(0, min(255, int(self._color_b * 255)))
        mc = f"#{cr:02x}{cg:02x}{cb:02x}"
        mc_q = QColor(mc)

        # Audio boost
        audio_boost = 1.0 + self._audio_level * 2.5

        # ─── DEEP AMBIENT GLOW ───
        for rr, a in [(3.5, 5), (2.5, 12), (1.8, 20), (1.2, 35)]:
            boosted_a = int(a * g * audio_boost)
            bg = QRadialGradient(cx, cy, R * rr)
            bg.setColorAt(0, _alpha(mc, min(255, boosted_a)))
            bg.setColorAt(0.4, _alpha(mc, int(boosted_a * 0.3)))
            bg.setColorAt(1, _alpha(mc, 0))
            p.setBrush(QBrush(bg)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx - R * rr, cy - R * rr, R * rr * 2, R * rr * 2))

        # ─── OUTERMOST RING: tick marks (like compass bezel) ───
        outer_r = R * 1.0 * breath
        for i in range(120):
            a = math.radians(i * 3)
            big = i % 15 == 0
            mid = i % 5 == 0
            r1 = outer_r
            r2 = outer_r + (R * 0.04 if big else R * 0.025 if mid else R * 0.015)
            pw = 1.8 if big else 0.9 if mid else 0.4
            al = (220 if big else 130 if mid else 60) * g
            p.setPen(QPen(_alpha(mc, int(al)), pw))
            p.drawLine(QPointF(cx + r1 * math.cos(a), cy + r1 * math.sin(a)),
                       QPointF(cx + r2 * math.cos(a), cy + r2 * math.sin(a)))

        # ─── OUTER RING: two concentric lines with rune band between ───
        for rr, pw, al in [(outer_r, 1.8, 200), (outer_r * 0.93, 1.0, 140)]:
            p.setPen(QPen(_alpha(mc, int(al * g)), pw))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - rr, cy - rr, rr * 2, rr * 2))

        # ─── INSCRIBED RUNE TEXT RING (between outer rings) ───
        rune_ring_r = outer_r * 0.965
        p.save(); p.translate(cx, cy); p.rotate(self._rings[0])
        p.setFont(_font(max(5, int(R * 0.035))))
        n_chars = len(self._rune_text)
        for i, ch in enumerate(self._rune_text):
            a = math.radians(i * 360.0 / n_chars)
            p.save()
            p.rotate(math.degrees(a))
            p.translate(0, -rune_ring_r)
            p.rotate(180)
            ch_al = int(220 * g * (0.45 + 0.55 * math.sin(self._t * 1.2 + i * 0.25)))
            p.setPen(QPen(_alpha(mc, ch_al)))
            p.drawText(QRectF(-4, -4, 8, 8), Qt.AlignmentFlag.AlignCenter, ch)
            p.restore()
        p.restore()

        # ─── DOT BORDER between rune rings ───
        dot_r = (outer_r + outer_r * 0.93) / 2
        for i in range(120):
            a = math.radians(i * 3)
            dx = cx + dot_r * math.cos(a)
            dy = cy + dot_r * math.sin(a)
            dot_al = int(100 * g * (0.5 + 0.5 * math.sin(self._t * 0.8 + i * 0.3)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(_alpha(mc, dot_al)))
            p.drawEllipse(QPointF(dx, dy), 0.8, 0.8)

        # ─── CROSS LINES (subtle) ───
        beam_pulse = 0.75 + 0.25 * math.sin(self._t * 1.5)
        for ang_deg in [0, 90]:
            a = math.radians(ang_deg)
            p.setPen(QPen(_alpha(mc, int(25 * g * beam_pulse)), 0.6))
            p.drawLine(QPointF(cx + outer_r * 1.05 * math.cos(a), cy + outer_r * 1.05 * math.sin(a)),
                       QPointF(cx - outer_r * 1.05 * math.cos(a), cy - outer_r * 1.05 * math.sin(a)))

        # ─── INNER CONCENTRIC CIRCLES ───
        for rr, pw, al in [
            (R * 0.88 * breath, 1.2, 130),
            (R * 0.74 * breath, 0.8, 90),
            (R * 0.60 * breath, 0.6, 60),
            (R * 0.48, 0.4, 45),
            (R * 0.35, 0.3, 35),
        ]:
            p.setPen(QPen(_alpha(mc, int(al * g)), pw))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - rr, cy - rr, rr * 2, rr * 2))

        # ─── INNER RUNE TEXT RING (smaller, CCW) ───
        inner_text_r = R * 0.74
        p.save(); p.translate(cx, cy); p.rotate(self._rings[1])
        p.setFont(_font(max(4, int(R * 0.025))))
        for i, ch in enumerate(self._rune_text):
            a = math.radians(i * 360.0 / n_chars)
            p.save()
            p.rotate(math.degrees(a))
            p.translate(0, -inner_text_r)
            p.rotate(180)
            ch_al = int(160 * g * (0.35 + 0.35 * math.sin(self._t * 0.9 + i * 0.3)))
            p.setPen(QPen(_alpha(mc, ch_al)))
            p.drawText(QRectF(-3, -3, 6, 6), Qt.AlignmentFlag.AlignCenter, ch)
            p.restore()
        p.restore()

        # ─── 8 RUNE MARKERS on outer ring (cardinal + diagonal) ───
        marker_r = outer_r * 0.965 * breath
        marker_symbols = list("ᚠᚢᚦᚨᚱᚲᚷᚹ")
        for i in range(8):
            a = math.radians(i * 45 - 90)
            mx = cx + marker_r * math.cos(a)
            my = cy + marker_r * math.sin(a)
            # Glow halo
            glow_cr = R * 0.045
            glow_gr = QRadialGradient(mx, my, glow_cr)
            glow_gr.setColorAt(0, _alpha(mc, int(80 * g * beam_pulse)))
            glow_gr.setColorAt(0.5, _alpha(mc, int(20 * g * beam_pulse)))
            glow_gr.setColorAt(1, _alpha(mc, 0))
            p.setBrush(QBrush(glow_gr)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(mx - glow_cr, my - glow_cr, glow_cr * 2, glow_cr * 2))
            # Marker circle
            ring_r = R * 0.025
            p.setPen(QPen(_alpha(mc, int(180 * g)), 0.8))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(mx - ring_r, my - ring_r, ring_r * 2, ring_r * 2))
            # Rune symbol
            p.setFont(_font(max(5, int(R * 0.03))))
            al_sym = int(220 * g * (0.5 + 0.5 * math.sin(self._t * 2.0 + i * 0.8)))
            p.setPen(QPen(_alpha(mc, al_sym)))
            p.drawText(QRectF(mx - ring_r, my - ring_r, ring_r * 2, ring_r * 2),
                       Qt.AlignmentFlag.AlignCenter, marker_symbols[i])

        # ─── SCANNING LINE ───
        scan_angle = math.radians(self._rings[2] * 3)
        scan_gr = QLinearGradient(cx, cy,
            cx + R * 1.05 * math.cos(scan_angle),
            cy + R * 1.05 * math.sin(scan_angle))
        scan_gr.setColorAt(0, _alpha(mc, 0))
        scan_gr.setColorAt(0.3, _alpha(mc, int(20 * g)))
        scan_gr.setColorAt(1, _alpha(mc, int(8 * g)))
        p.setPen(QPen(QBrush(scan_gr), 0.8))
        p.drawLine(QPointF(cx, cy),
                   QPointF(cx + R * 1.05 * math.cos(scan_angle),
                           cy + R * 1.05 * math.sin(scan_angle)))

        # ─── SHOCKWAVES ───
        for s in self._shockwaves:
            sr = R * (0.3 + s * 1.2)
            sa = int(100 * (1.0 - s) * g)
            p.setPen(QPen(_alpha(mc, max(5, sa)), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - sr, cy - sr, sr * 2, sr * 2))

        # ─── FLOATING SPARK PARTICLES ───
        for p_data in self._particles:
            ang, dist, spd, life = p_data[0], p_data[1], p_data[2], p_data[3]
            p_size = p_data[4] if len(p_data) > 4 else 1.0
            pxp = cx + R * dist * math.cos(ang)
            pyp = cy + R * dist * math.sin(ang)
            al = int(255 * life * g * p_size)
            sz = (0.8 + life * 2.5) * p_size
            if al > 5:
                spark_g = QRadialGradient(pxp, pyp, sz * 4)
                spark_g.setColorAt(0, _alpha(mc, int(al * 0.6)))
                spark_g.setColorAt(0.4, _alpha(mc, int(al * 0.2)))
                spark_g.setColorAt(1, _alpha(mc, 0))
                p.setBrush(QBrush(spark_g)); p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(pxp, pyp), sz * 4, sz * 4)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(_alpha(mc, min(255, int(al * 1.2)))))
                p.drawEllipse(QPointF(pxp, pyp), sz * 0.8, sz * 0.8)
                p.setPen(QPen(_alpha(mc, al), sz))
                p.drawPoint(int(pxp), int(pyp))

        # ═══════════════════════════════════════════════════════════════
        #  CORE: GOLDEN HEXAGRAM STAR with intense glow (the key feature)
        # ═══════════════════════════════════════════════════════════════
        orb_r = R * 0.22 * self._core_scale * breath
        pulse = 0.65 + 0.35 * math.sin(self._t * 2.5)

        # Layer 1: Ultra-wide ambient radial glow
        glow_r = orb_r * 5.5
        gl = QRadialGradient(cx, cy, glow_r)
        gl.setColorAt(0, _alpha(sc["glow"], int(60 * pulse * g)))
        gl.setColorAt(0.12, _alpha(sc["glow"], int(30 * pulse * g)))
        gl.setColorAt(0.4, _alpha(sc["glow"], int(8 * pulse * g)))
        gl.setColorAt(1, _alpha(sc["glow"], 0))
        p.setBrush(QBrush(gl)); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2))

        # Layer 2: Horizontal + vertical lens flare streaks
        flare_len = orb_r * 7.0 * pulse * g
        flare_w = orb_r * 0.3
        for ang_deg in [0, 90]:
            a = math.radians(ang_deg)
            fg = QLinearGradient(
                cx - flare_len * math.cos(a), cy - flare_len * math.sin(a),
                cx + flare_len * math.cos(a), cy + flare_len * math.sin(a))
            fg.setColorAt(0, _alpha(mc, 0))
            fg.setColorAt(0.3, _alpha(mc, int(30 * pulse * g)))
            fg.setColorAt(0.5, _alpha(sc["star"], int(130 * pulse * g)))
            fg.setColorAt(0.7, _alpha(mc, int(30 * pulse * g)))
            fg.setColorAt(1, _alpha(mc, 0))
            p.setBrush(QBrush(fg)); p.setPen(Qt.PenStyle.NoPen)
            path = QPainterPath()
            perp_x = -math.sin(a) * flare_w
            perp_y = math.cos(a) * flare_w
            path.moveTo(cx - flare_len * math.cos(a) + perp_x,
                        cy - flare_len * math.sin(a) + perp_y)
            path.lineTo(cx + flare_len * math.cos(a) + perp_x,
                        cy + flare_len * math.sin(a) + perp_y)
            path.lineTo(cx + flare_len * math.cos(a) - perp_x,
                        cy + flare_len * math.sin(a) - perp_y)
            path.lineTo(cx - flare_len * math.cos(a) - perp_x,
                        cy - flare_len * math.sin(a) - perp_y)
            path.closeSubpath()
            p.drawPath(path)

        # Layer 3: Main orb gradient (warm golden radial)
        og = QRadialGradient(cx, cy, orb_r * 3.0)
        og.setColorAt(0, _alpha(sc["star"], int(255 * pulse * g)))
        og.setColorAt(0.08, _alpha(sc["star"], int(230 * pulse * g)))
        og.setColorAt(0.3, _alpha(sc["glow"], int(80 * g)))
        og.setColorAt(0.6, _alpha(sc["glow"], int(20 * g)))
        og.setColorAt(1, _alpha(sc["glow"], 0))
        p.setBrush(QBrush(og)); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - orb_r * 3.0, cy - orb_r * 3.0, orb_r * 6.0, orb_r * 6.0))

        # Layer 4: Bright golden core
        inner_r = orb_r * 0.5
        p.setBrush(QBrush(_alpha(sc["star"], int(250 * pulse * g))))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2))

        # Layer 5: Hot white center point
        hot_r = orb_r * 0.18
        p.setBrush(QBrush(_alpha("#ffffff", int(230 * pulse * g))))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - hot_r, cy - hot_r, hot_r * 2, hot_r * 2))

        # Layer 6: Subtle chromatic ring
        chrom_r = orb_r * 1.8
        p.setPen(QPen(_alpha(sc["star"], int(25 * pulse * g)), 0.6))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(cx - chrom_r, cy - chrom_r, chrom_r * 2, chrom_r * 2))

        # ═══ THE STAR: 6-pointed hexagram (like the image) ═══
        if self._show_center:
            star_r = orb_r * 1.6
            p.save(); p.translate(cx, cy); p.rotate(self._rings[2] * 0.5)

            # Glow behind the star
            star_glow = QRadialGradient(0, 0, star_r * 1.5)
            star_glow.setColorAt(0, _alpha(sc["star"], int(50 * pulse * g)))
            star_glow.setColorAt(0.5, _alpha(sc["star"], int(15 * pulse * g)))
            star_glow.setColorAt(1, _alpha(sc["star"], 0))
            p.setBrush(QBrush(star_glow)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(-star_r * 1.5, -star_r * 1.5, star_r * 3, star_r * 3))

            # Draw two overlapping triangles for 6-pointed star
            star_alpha = int(220 * pulse * g)
            for offset in (0, 60):
                pts = []
                for k in range(3):
                    a = math.radians(k * 120 + offset - 90)
                    pts.append(QPointF(star_r * math.cos(a), star_r * math.sin(a)))
                path = QPainterPath()
                path.moveTo(pts[0])
                path.lineTo(pts[1])
                path.lineTo(pts[2])
                path.closeSubpath()
                # Filled star with golden color
                star_fill = QRadialGradient(0, 0, star_r)
                star_fill.setColorAt(0, _alpha(sc["star"], int(star_alpha * 0.9)))
                star_fill.setColorAt(0.7, _alpha(sc["star"], int(star_alpha * 0.4)))
                star_fill.setColorAt(1, _alpha(sc["star"], int(star_alpha * 0.1)))
                p.setBrush(QBrush(star_fill))
                p.setPen(QPen(_alpha(sc["star"], star_alpha), 1.5))
                p.drawPath(path)

            # Center dot on star
            dot_r = orb_r * 0.25
            p.setBrush(QBrush(_alpha(sc["star"], int(255 * pulse * g))))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(0, 0), dot_r, dot_r)

            # Pulsing energy rings expanding from center
            for ring_idx in range(3):
                phase = (self._t * 0.8 + ring_idx * 0.33) % 1.0
                rr = orb_r * (0.5 + phase * 1.5)
                ring_al = int(35 * (1.0 - phase) * pulse * g)
                if ring_al > 1:
                    p.setPen(QPen(_alpha(sc["star"], ring_al), 0.5))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawEllipse(QRectF(-rr, -rr, rr * 2, rr * 2))

            p.restore()

        # ─── LABELS ───
        p.setFont(_font(9))
        p.setPen(QPen(_alpha(mc, 220), 1))
        p.drawText(QRectF(0, cy + R * 1.12, W, 16), Qt.AlignmentFlag.AlignCenter, self.STATE_LABELS.get(self._state, "○ EM ESPERA"))
        p.setFont(_font(8, bold=False))
        p.setPen(QPen(_alpha(TEXT_DIM, 140), 1))
        p.drawText(QRectF(cx - R * 0.7, cy + R * 1.12 + 16, R * 1.4, 12),
                   Qt.AlignmentFlag.AlignCenter, "＜Elívea＞ Elívea CORE")

        # ─── ONBOARDING AWAKENING OVERLAY ───
        if self._onboarding_phase > 0:
            try:
                self._draw_onboarding(p, W, H, cx, cy, R)
            except Exception:
                self._onboarding_phase = 0
                self._glow_tgt = 0.85


class ConversationHistoryMap(QWidget):
    """Interactive network graph where each node = a conversation.
    Hover shows preview, click loads it into chat.
    Shows 10-15 recent conversations; older ones accessible via HistoryDrawer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.setMouseTracking(True)
        self._t = 0.0
        self._last = time.time()
        self._conversations: list[dict] = []  # loaded from memory
        self._nodes: list[dict] = []  # {x, y, vx, vy, r, conv_idx, label, time_label}
        self._edges: list[tuple[int, int]] = []
        self._hover_idx = -1
        self._on_node_click = None  # callback(conv)
        self._on_history_click = None  # callback() — open full history
        self._history_btn_rect = QRectF()
        self._pulse_t = 0.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)

    def set_conversations(self, convs: list[dict]):
        """Set conversation list (from MemoryManager). Each dict has
        'user_speech', 'assistant_response', 'timestamp', 'id'."""
        self._conversations = convs[-15:]  # last 15
        self._rebuild_graph()

    def set_on_node_click(self, cb):
        self._on_node_click = cb

    def set_on_history_click(self, cb):
        self._on_history_click = cb

    def _rebuild_graph(self):
        """Create nodes from conversations with organic layout."""
        self._nodes = []
        self._edges = []
        n = len(self._conversations)
        if n == 0:
            return
        # Place nodes in a force-directed-ish layout: ring + center
        for i, conv in enumerate(self._conversations):
            if n == 1:
                nx_pos, ny_pos = 0.5, 0.5
            else:
                # Distribute in a spiral-like pattern
                angle = (i / n) * 2 * math.pi + (i % 3) * 0.3
                radius = 0.15 + 0.25 * (i / n)
                nx_pos = 0.5 + radius * math.cos(angle)
                ny_pos = 0.5 + radius * math.sin(angle)
            # Node radius: larger for more recent
            r = 5.0 + 4.0 * ((n - i) / n)
            # Time label
            ts = conv.get('timestamp', '')
            time_label = ts.split(' ')[-1][:5] if ' ' in ts else ''
            # Short preview
            speech = conv.get('user_speech', '')[:20]
            self._nodes.append({
                'x': nx_pos, 'y': ny_pos,
                'vx': random.uniform(-0.0008, 0.0008),
                'vy': random.uniform(-0.0008, 0.0008),
                'r': r, 'conv_idx': i,
                'label': speech, 'time_label': time_label,
            })
        # Connect adjacent + some random
        for i in range(n - 1):
            self._edges.append((i, i + 1))
        for i in range(n):
            for j in range(i + 2, min(i + 4, n)):
                if random.random() < 0.4:
                    self._edges.append((i, j))

    def _tick(self):
        now = time.time()
        self._t += now - self._last
        self._last = now
        self._pulse_t += 0.04
        # Gentle drift
        for nd in self._nodes:
            nx_pos = nd['x'] + nd['vx']
            ny_pos = nd['y'] + nd['vy']
            if nx_pos < 0.1 or nx_pos > 0.9: nd['vx'] *= -1
            if ny_pos < 0.1 or ny_pos > 0.9: nd['vy'] *= -1
            nd['x'] = max(0.08, min(0.92, nx_pos))
            nd['y'] = max(0.08, min(0.92, ny_pos))
        self.update()

    def mouseMoveEvent(self, ev):
        mx, my = ev.position().x(), ev.position().y()
        W, H = self.width(), self.height()
        self._hover_idx = -1
        for i, nd in enumerate(self._nodes):
            px, py = nd['x'] * W, nd['y'] * H
            if math.hypot(mx - px, my - py) < nd['r'] + 6:
                self._hover_idx = i
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                return
        # Check history button
        if self._history_btn_rect.contains(ev.position()):
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            return
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, ev):
        mx, my = ev.position().x(), ev.position().y()
        W, H = self.width(), self.height()
        # History button click
        if self._history_btn_rect.contains(ev.position()):
            if self._on_history_click:
                self._on_history_click()
            return
        # Node click
        for i, nd in enumerate(self._nodes):
            px, py = nd['x'] * W, nd['y'] * H
            if math.hypot(mx - px, my - py) < nd['r'] + 6:
                if self._on_node_click and i < len(self._conversations):
                    self._on_node_click(self._conversations[nd['conv_idx']])
                return

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Title
        p.setFont(_font(9))
        p.setPen(QPen(QColor(GOLD), 160))
        p.drawText(QRectF(8, 4, W - 80, 16), Qt.AlignmentFlag.AlignLeft, "💬 Histórico de Conversas")
        p.setFont(_font(7, bold=False))
        p.setPen(QPen(QColor(TEXT_DIM), 120))
        count = len(self._conversations)
        p.drawText(QRectF(8, 20, W - 80, 12), Qt.AlignmentFlag.AlignLeft,
                   f"{count} conversa{'s' if count != 1 else ''} recente{'s' if count != 1 else ''}")

        # History button (top-right)
        btn_w, btn_h = 56, 18
        btn_x = W - btn_w - 8
        btn_y = 4
        self._history_btn_rect = QRectF(btn_x, btn_y, btn_w, btn_h)
        p.setBrush(QBrush(_alpha(GOLD, 30)))
        p.setPen(QPen(_alpha(GOLD, 80), 1))
        p.drawRoundedRect(self._history_btn_rect, 8, 8)
        p.setFont(_font(7))
        p.setPen(QPen(QColor(GOLD), 180))
        p.drawText(self._history_btn_rect, Qt.AlignmentFlag.AlignCenter, "📋 Ver Tudo")

        if not self._nodes:
            # Empty state
            p.setFont(_font(8, bold=False))
            p.setPen(QPen(QColor(TEXT_DIM), 100))
            p.drawText(QRectF(0, H / 2 - 10, W, 20),
                       Qt.AlignmentFlag.AlignCenter, "Nenhuma conversa ainda")
            return

        # ── Edges ──
        for i, j in self._edges:
            if i >= len(self._nodes) or j >= len(self._nodes):
                continue
            nd_i, nd_j = self._nodes[i], self._nodes[j]
            x1, y1 = nd_i['x'] * W, nd_i['y'] * H
            x2, y2 = nd_j['x'] * W, nd_j['y'] * H
            dist = math.hypot(x2 - x1, y2 - y1)
            is_hovered = (i == self._hover_idx or j == self._hover_idx)
            if dist < W * 0.6:
                alpha = int(60 * (1 - dist / (W * 0.6)))
                if is_hovered:
                    alpha = min(255, alpha + 80)
                pw = 1.5 if is_hovered else 0.8
                p.setPen(QPen(_alpha(GOLD, max(10, alpha)), pw))
                p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # ── Nodes ──
        for i, nd in enumerate(self._nodes):
            px, py = nd['x'] * W, nd['y'] * H
            r = nd['r']
            is_hovered = (i == self._hover_idx)
            pulse = 0.7 + 0.3 * math.sin(self._pulse_t * 2 + nd['x'] * 10)

            # Outer glow
            if is_hovered:
                glow_r = r * 3.0
                glow_g = QRadialGradient(px, py, glow_r)
                glow_g.setColorAt(0, _alpha(GOLD, int(40 * pulse)))
                glow_g.setColorAt(0.5, _alpha(GOLD, int(12 * pulse)))
                glow_g.setColorAt(1, _alpha(GOLD, 0))
                p.setBrush(QBrush(glow_g)); p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QRectF(px - glow_r, py - glow_r, glow_r * 2, glow_r * 2))

            # Node outer ring
            p.setPen(QPen(_alpha(GOLD, int((200 if is_hovered else 120) * pulse)), 1.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(px, py), r * 1.8, r * 1.8)

            # Node filled
            fill_a = int((220 if is_hovered else 150) * pulse)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(_alpha(GOLD if i == len(self._nodes) - 1 else TEXT, fill_a)))
            p.drawEllipse(QPointF(px, py), r, r)

            # Inner bright dot
            p.setBrush(QBrush(_alpha(TEXT if is_hovered else GOLD, int(200 * pulse))))
            p.drawEllipse(QPointF(px, py), r * 0.35, r * 0.35)

            # Time label below node (always visible)
            if nd['time_label']:
                p.setFont(_font(6, bold=False))
                p.setPen(QPen(_alpha(TEXT_DIM, 120), 1))
                p.drawText(QRectF(px - 20, py + r + 4, 40, 10),
                           Qt.AlignmentFlag.AlignCenter, nd['time_label'])

        # ── Hover: show title label under the hovered node ──
        if self._hover_idx >= 0 and self._hover_idx < len(self._conversations):
            nd = self._nodes[self._hover_idx]
            conv = self._conversations[nd['conv_idx']]
            px, py = nd['x'] * W, nd['y'] * H
            r = nd['r']

            # Title label: just the user's speech as the "title"
            title = conv.get('user_speech', '')[:40]
            if not title:
                title = "(sem título)"

            # Measure text width for pill background
            p.setFont(_font(7))
            fm = QFontMetrics(p.font())
            text_w = fm.horizontalAdvance(title) + 16
            text_h = 18
            label_x = max(4, min(px - text_w / 2, W - text_w - 4))
            label_y = py + r + 14

            # Pill background
            pill_bg = QLinearGradient(label_x, label_y, label_x + text_w, label_y)
            pill_bg.setColorAt(0, _alpha("#1a1608", 230))
            pill_bg.setColorAt(1, _alpha("#120e04", 230))
            p.setBrush(QBrush(pill_bg))
            p.setPen(QPen(_alpha(GOLD, 80), 1))
            p.drawRoundedRect(QRectF(label_x, label_y, text_w, text_h), 8, 8)

            # Title text
            p.setFont(_font(7))
            p.setPen(QPen(QColor(GOLD), 220))
            p.drawText(QRectF(label_x + 8, label_y, text_w - 16, text_h),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)

            # Timestamp on second line
            ts = conv.get('timestamp', '')
            if ts:
                p.setFont(_font(6, bold=False))
                p.setPen(QPen(QColor(TEXT_DIM), 110))
                p.drawText(QRectF(label_x + 8, label_y + text_h, text_w - 16, 12),
                           Qt.AlignmentFlag.AlignLeft, ts)

        # ── Decorative: scan line ──
        scan_y = (self._t * 0.15) % 1.0 * H
        p.setPen(QPen(_alpha(GOLD, int(8 * (0.5 + 0.5 * math.sin(self._t)))), 0.5))
        p.drawLine(0, int(scan_y), W, int(scan_y))


class _OldNetworkGraphRemoved:
    pass

# (old NetworkGraphWidget removed — replaced by ConversationHistoryMap)


# ═══════════════════════════════════════════════════════════════════════════
# History Drawer — full conversation history panel
# ═══════════════════════════════════════════════════════════════════════════
class HistoryDrawer(QWidget):
    """Full conversation history panel. Slides in/out.
    Shows all stored conversations with search."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)
        self._conversations: list[dict] = []
        self._filtered: list[dict] = []
        self._scroll_offset = 0
        self._hover_idx = -1
        self._on_close = None
        self._on_select = None
        self._search_text = ""
        self._search_focused = False
        self._search_rect = QRectF()
        self._close_rect = QRectF()
        self._item_height = 64
        self.setMouseTracking(True)

    def set_conversations(self, convs: list[dict]):
        self._conversations = list(reversed(convs))  # newest first
        self._filtered = self._conversations[:]
        self._scroll_offset = 0
        self.update()

    def set_on_close(self, cb):
        self._on_close = cb

    def set_on_select(self, cb):
        self._on_select = cb

    def _apply_filter(self):
        if not self._search_text.strip():
            self._filtered = self._conversations[:]
        else:
            q = self._search_text.lower()
            self._filtered = [c for c in self._conversations
                              if q in c.get('user_speech', '').lower()
                              or q in c.get('assistant_response', '').lower()]
        self._scroll_offset = 0

    def wheelEvent(self, ev):
        delta = ev.angleDelta().y()
        max_scroll = max(0, len(self._filtered) * self._item_height - self.height() + 80)
        self._scroll_offset = max(0, min(max_scroll, self._scroll_offset - delta))
        self.update()

    def mouseMoveEvent(self, ev):
        mx, my = ev.position().x(), ev.position().y()
        self._hover_idx = -1
        # Check close button
        if self._close_rect.contains(ev.position()):
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            return
        # Check search
        if self._search_rect.contains(ev.position()):
            self.setCursor(Qt.CursorShape.IBeamCursor)
            return
        # Check items
        y_start = 60 - self._scroll_offset
        for i, conv in enumerate(self._filtered):
            iy = y_start + i * self._item_height
            if iy < -self._item_height or iy > self.height():
                continue
            item_rect = QRectF(12, iy, self.width() - 24, self._item_height - 4)
            if item_rect.contains(ev.position()):
                self._hover_idx = i
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                return
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, ev):
        mx, my = ev.position().x(), ev.position().y()
        # Close button
        if self._close_rect.contains(ev.position()):
            if self._on_close:
                self._on_close()
            self.setVisible(False)
            return
        # Search area
        if self._search_rect.contains(ev.position()):
            self._search_focused = True
            self.update()
            return
        # Items
        y_start = 60 - self._scroll_offset
        for i, conv in enumerate(self._filtered):
            iy = y_start + i * self._item_height
            item_rect = QRectF(12, iy, self.width() - 24, self._item_height - 4)
            if item_rect.contains(ev.position()):
                if self._on_select and i < len(self._filtered):
                    self._on_select(self._filtered[i])
                return
        self._search_focused = False
        self.update()

    def keyPressEvent(self, ev):
        if not self._search_focused:
            return
        key = ev.key()
        text = ev.text()
        if key == Qt.Key.Key_Backspace:
            self._search_text = self._search_text[:-1]
        elif key == Qt.Key.Key_Escape:
            self._search_focused = False
        elif text and text.isprintable():
            self._search_text += text
        self._apply_filter()
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Full background
        p.fillRect(0, 0, W, H, _alpha("#060608", 250))

        # Gold border left
        p.setPen(QPen(_alpha(GOLD, 40), 2))
        p.drawLine(0, 0, 0, H)

        # ── Header ──
        p.setFont(_font(11))
        p.setPen(QPen(QColor(GOLD), 200))
        p.drawText(QRectF(14, 8, W - 80, 20), Qt.AlignmentFlag.AlignLeft, "📋 Histórico Completo")

        # Close button
        close_x = W - 34
        self._close_rect = QRectF(close_x, 6, 26, 26)
        p.setBrush(QBrush(_alpha(RED, 30)))
        p.setPen(QPen(_alpha(RED, 80), 1))
        p.drawRoundedRect(self._close_rect, 6, 6)
        p.setFont(_font(9))
        p.setPen(QPen(QColor(RED), 160))
        p.drawText(self._close_rect, Qt.AlignmentFlag.AlignCenter, "✕")

        # ── Search bar ──
        self._search_rect = QRectF(14, 34, W - 28, 22)
        p.setBrush(QBrush(_alpha("#0e0e16", 200)))
        search_border = 60 if self._search_focused else 25
        p.setPen(QPen(_alpha(GOLD, search_border), 1))
        p.drawRoundedRect(self._search_rect, 8, 8)
        p.setFont(_font(7, bold=False))
        display = self._search_text if self._search_text else "🔍 Buscar conversas..."
        p.setPen(QPen(QColor(TEXT if self._search_text else TEXT_DIM), 160))
        p.drawText(QRectF(self._search_rect.x() + 8, self._search_rect.y(),
                          self._search_rect.width() - 16, self._search_rect.height()),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, display)

        # Count
        p.setFont(_font(7, bold=False))
        p.setPen(QPen(QColor(TEXT_DIM), 100))
        p.drawText(QRectF(14, 58, W - 28, 10), Qt.AlignmentFlag.AlignLeft,
                   f"{len(self._filtered)} conversa{'s' if len(self._filtered) != 1 else ''}")

        # ── Conversation items ──
        y_start = 60 - self._scroll_offset
        for i, conv in enumerate(self._filtered):
            iy = y_start + i * self._item_height
            if iy < -self._item_height or iy > self.height():
                continue

            is_hovered = (i == self._hover_idx)
            item_rect = QRectF(12, iy, W - 24, self._item_height - 4)

            # Item background
            if is_hovered:
                item_bg = QLinearGradient(item_rect.x(), 0, item_rect.x() + item_rect.width(), 0)
                item_bg.setColorAt(0, _alpha("#1a1608", 180))
                item_bg.setColorAt(1, _alpha("#120e04", 140))
                p.setBrush(QBrush(item_bg))
                p.setPen(QPen(_alpha(GOLD, 40), 1))
            else:
                p.setBrush(QBrush(_alpha("#0c0c12", 80)))
                p.setPen(QPen(_alpha(BORDER, 30), 0.5))
            p.drawRoundedRect(item_rect, 8, 8)

            # User speech
            speech = conv.get('user_speech', '')[:60]
            p.setFont(_font(8))
            p.setPen(QPen(QColor(GOLD if is_hovered else TEXT), 200))
            p.drawText(QRectF(item_rect.x() + 10, iy + 6, item_rect.width() - 20, 14),
                       Qt.AlignmentFlag.AlignLeft, f"🗣 {speech}")

            # Response preview
            resp = conv.get('assistant_response', '')[:50]
            p.setFont(_font(7, bold=False))
            p.setPen(QPen(QColor(TEXT_MED), 120))
            p.drawText(QRectF(item_rect.x() + 10, iy + 22, item_rect.width() - 20, 14),
                       Qt.AlignmentFlag.AlignLeft, f"＜Elívea＞ {resp}")

            # Timestamp + source
            ts = conv.get('timestamp', '')
            src = conv.get('source', '')
            src_icon = "🎙" if src == "voice" else "⌨"
            p.setFont(_font(6, bold=False))
            p.setPen(QPen(QColor(TEXT_DIM), 100))
            p.drawText(QRectF(item_rect.x() + 10, iy + 40, item_rect.width() - 20, 10),
                       Qt.AlignmentFlag.AlignLeft, f"{ts}  {src_icon} {src}")

        # ── Scroll indicator ──
        total_h = len(self._filtered) * self._item_height
        if total_h > H - 80:
            track_h = H - 80
            thumb_h = max(20, track_h * (H - 80) / total_h)
            thumb_y = 60 + (self._scroll_offset / max(1, total_h - (H - 80))) * (track_h - thumb_h)
            p.setBrush(QBrush(_alpha(GOLD, 40)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(W - 5, thumb_y, 3, thumb_h), 1, 1)


# ═══════════════════════════════════════════════════════════════════════════
# Waveform Widget
# ═══════════════════════════════════════════════════════════════════════════
class WaveformWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(70)
        self._t = 0.0
        self._last = time.time()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def _tick(self):
        self._t += time.time() - self._last
        self._last = time.time()
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        mid = H / 2

        # Gradient fill
        grad = QLinearGradient(0, 0, 0, H)
        grad.setColorAt(0, _alpha(GOLD, 30))
        grad.setColorAt(1, _alpha(GOLD, 0))

        path = QPainterPath()
        path.moveTo(0, mid)
        for x in range(0, W, 2):
            y = mid + math.sin(x * 0.02 + self._t * 1.5) * H * 0.3 * (0.6 + 0.4 * math.sin(self._t * 0.5))
            path.lineTo(x, y)
        path.lineTo(W, mid + H)
        path.lineTo(0, mid + H)
        path.closeSubpath()
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(path)

        # Line
        p.setPen(QPen(_alpha(GOLD, 150), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        path2 = QPainterPath()
        first = True
        for x in range(0, W, 2):
            y = mid + math.sin(x * 0.02 + self._t * 1.5) * H * 0.3 * (0.6 + 0.4 * math.sin(self._t * 0.5))
            if first:
                path2.moveTo(x, y); first = False
            else:
                path2.lineTo(x, y)
        p.drawPath(path2)


# ═══════════════════════════════════════════════════════════════════════════
# Stats Table Widget
# ═══════════════════════════════════════════════════════════════════════════
class StatsTableWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._metrics = [
            ("CACHE", "0.89%", "+0.02%", True),
            ("CARDS", "10.93%", "+1.4%", True),
            ("REFLECTION", "6.79K", "+312", True),
            ("VECTORS", "4.13K", "+89", True),
            ("CONTROLE", "0.014068", "-0.001", False),
            ("ADJUNTAS", "3.756", "+0.12", True),
            ("AUTONOM", "7,721", "+156", True),
            ("GOALS", "182,322", "+2,841", True),
        ]

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Title
        p.setFont(_font(10))
        p.setPen(QPen(QColor(TEXT), 200))
        p.drawText(QRectF(8, 4, W, 16), Qt.AlignmentFlag.AlignLeft, "Advanced Statistics")
        p.setFont(_font(8, bold=False))
        p.setPen(QPen(QColor(TEXT_DIM), 150))
        p.drawText(QRectF(8, 20, W, 12), Qt.AlignmentFlag.AlignLeft, "System performance metrics")

        # Metrics
        y = 38
        col_w = W / 2
        for i, (label, value, delta, up) in enumerate(self._metrics):
            col = 0 if i % 2 == 0 else 1
            row = i // 2
            x = 8 + col * col_w
            ry = y + row * 22

            p.setFont(_font(7, bold=False))
            p.setPen(QPen(QColor(TEXT_DIM), 120))
            p.drawText(QRectF(x, ry, col_w - 4, 10), Qt.AlignmentFlag.AlignLeft, label)

            p.setFont(_font(9))
            p.setPen(QPen(QColor(TEXT), 220))
            p.drawText(QRectF(x, ry + 10, col_w * 0.6, 10), Qt.AlignmentFlag.AlignLeft, value)

            p.setFont(_font(7))
            p.setPen(QPen(QColor(GREEN if up else RED), 180))
            p.drawText(QRectF(x + col_w * 0.6, ry + 10, col_w * 0.4, 10), Qt.AlignmentFlag.AlignLeft, delta)


# ═══════════════════════════════════════════════════════════════════════════
# Code Block Widget
# ═══════════════════════════════════════════════════════════════════════════
class CodeBlockWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lines = [
            ("import ", "{ ", "State", ", ", "Perception", " } from ", "'sage-core'", ";"),
            ("",),
            ("export ", "async ", "function ", "processInput", "(", "query", ": ", "string", ") {"),
            ("  ", "const ", "state", " = ", "State", ".acquire({"),
            ("    mode", ": ", "'rune-analysis'", ","),
            ("    depth", ": ", "12", ","),
            ("  });"),
            ("",),
            ("  ", "for", " (", "const ", "token ", "of ", "state.tokens) {"),
            ("    ", "const ", "decoded", " = ", "rune", ".decode(token);"),
            ("    ", "if", " (decoded.", "isSignificant", ") {"),
            ("      ", "return", " { ", "data", ": ", "decoded", " };"),
            ("    }"),
            ("  }"),
            ("",),
            ("  ", "return", " { ", "status", ": ", "'complete'", " };"),
            ("}",),
        ]

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Title
        p.setFont(_font(10))
        p.setPen(QPen(QColor(TEXT), 200))
        p.drawText(QRectF(8, 4, W, 16), Qt.AlignmentFlag.AlignLeft, "Code Execution Block")
        p.setFont(_font(8, bold=False))
        p.setPen(QPen(QColor(TEXT_DIM), 150))
        p.drawText(QRectF(8, 20, W, 12), Qt.AlignmentFlag.AlignLeft, "sage-core/process.ts")

        # Code background
        p.setBrush(QBrush(_alpha("#000000", 100)))
        p.setPen(QPen(_alpha(BORDER, 80), 1))
        p.drawRoundedRect(QRectF(4, 34, W - 8, H - 44), 6, 6)

        # Code lines
        y = 42
        p.setFont(_font(8))
        for i, segments in enumerate(self._lines[:16]):
            # Line number
            p.setPen(QPen(QColor(TEXT_DIM), 80))
            p.drawText(QRectF(8, y, 18, 10), Qt.AlignmentFlag.AlignRight, str(i + 1))

            # Tokens
            x = 30
            colors = {"import": GOLD, "export": GOLD, "async": GOLD, "function": GOLD,
                       "const": GOLD, "return": GOLD, "for": GOLD, "if": GOLD,
                       "'sage-core'": "#e8b84d", "'rune-analysis'": "#e8b84d", "'complete'": "#e8b84d",
                       "State": TEXT, "Perception": TEXT, "processInput": TEXT, "query": TEXT,
                       "state": TEXT, "decoded": TEXT, "rune": TEXT, "token": TEXT}
            for tok in segments:
                if not tok:
                    x += 4; continue
                col = colors.get(tok, TEXT_MED)
                p.setPen(QPen(QColor(col), 180))
                p.drawText(QRectF(x, y, W - x, 10), Qt.AlignmentFlag.AlignLeft, tok)
                fm = QFontMetrics(p.font())
                x += fm.horizontalAdvance(tok)
            y += 12


# ═══════════════════════════════════════════════════════════════════════════
# Chat Sidebar Widget — imported from chat_panel.py (proper Qt widgets)
# ═══════════════════════════════════════════════════════════════════════════
try:
    from ui.chat_panel import ChatSidebar, ChatBubbleWidget, TypingIndicator
except ImportError:
    from ui.chat_panel import ChatSidebar, ChatBubbleWidget, TypingIndicator


class _OldChatSidebarRemoved:
    pass


# (old ChatSidebar removed — now imported from chat_panel.py)

    def _blink_cursor(self):
        self._cursor_blink = not self._cursor_blink
        if self._typing or self._streaming:
            self.update()

    def add_message(self, role: str, text: str):
        self._messages.append(ChatMessage(role, text))
        self._typing = False
        self._streaming = False
        self._stream_text = ""
        self.update()

    def begin_stream(self):
        self._streaming = True
        self._stream_text = ""
        self.update()

    def append_stream(self, delta: str):
        self._stream_text += delta
        self.update()

    def end_stream(self):
        if self._stream_text:
            self.add_message("assistant", self._stream_text)
        self._streaming = False
        self.update()

    def set_input(self, text: str):
        self._input_text = text
        self.update()

    def get_input(self) -> str:
        return self._input_text

    def clear_input(self):
        self._input_text = ""
        self.update()

    def set_typing(self, val: bool):
        """Show/hide typing indicator."""
        self._typing = val
        self.update()

    def clear_all(self):
        """Clear all messages."""
        self._messages.clear()
        self.update()

    def set_on_send(self, cb):
        """Set callback for send button."""
        self._on_send = cb

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # ── Background with subtle gradient ──
        bg_grad = QLinearGradient(0, 0, 0, H)
        bg_grad.setColorAt(0, _alpha("#080810", 245))
        bg_grad.setColorAt(0.5, _alpha("#0a0a14", 250))
        bg_grad.setColorAt(1, _alpha("#06060c", 245))
        p.fillRect(0, 0, W, H, bg_grad)

        # Right border with gold glow
        glow_pen = QPen(_alpha(GOLD, 25), 3)
        p.setPen(glow_pen)
        p.drawLine(W - 1, 0, W - 1, H)
        p.setPen(QPen(_alpha(GOLD, 60), 1))
        p.drawLine(W - 2, 0, W - 2, H)

        # ── Header with icon and status ──
        hdr_h = 42
        hdr_grad = QLinearGradient(0, 0, 0, hdr_h)
        hdr_grad.setColorAt(0, _alpha("#12101a", 200))
        hdr_grad.setColorAt(1, _alpha("#0a0a14", 220))
        p.fillRect(0, 0, W, hdr_h, hdr_grad)

        # Gold accent line below header
        p.setPen(QPen(_alpha(GOLD, 50), 1))
        p.drawLine(0, hdr_h, W, hdr_h)

        # Header: chat icon + title + online dot
        p.setFont(_font(9))
        p.setPen(QPen(QColor(GOLD), 200))
        p.drawText(QRectF(12, 8, 20, 20), Qt.AlignmentFlag.AlignCenter, "💬")
        p.setFont(_font(9))
        p.setPen(QPen(QColor(TEXT), 220))
        p.drawText(QRectF(34, 8, 120, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "Elívea")
        # Online dot
        p.setBrush(QBrush(_alpha(GREEN, 180)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(130, 18), 3, 3)
        p.setFont(_font(7, bold=False))
        p.setPen(QPen(QColor(GREEN), 140))
        p.drawText(QRectF(138, 8, 50, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "online")

        # ── Messages area ──
        y = hdr_h + 8
        msg_area_h = H - 110
        bubble_pad = 8
        max_bubble_w = W - 56

        # Show last N messages that fit
        visible_msgs = self._messages[-25:]
        # Calculate total height needed and scroll offset
        total_h = 0
        msg_heights = []
        fm_calc = QFontMetrics(_font(8, bold=False))
        for msg in visible_msgs:
            # Estimate bubble height
            words = msg.text.split()
            lines = 1
            line = ""
            for word in words:
                test = line + " " + word if line else word
                if fm_calc.horizontalAdvance(test) > max_bubble_w:
                    lines += 1
                    line = word
                else:
                    line = test
            h = 20 + lines * 13 + bubble_pad  # label + lines + padding
            msg_heights.append(h)
            total_h += h

        # Auto-scroll to bottom
        scroll = max(0, total_h - msg_area_h)

        drawn_h = 0
        for idx, msg in enumerate(visible_msgs):
            h = msg_heights[idx] if idx < len(msg_heights) else 40
            if drawn_h - scroll + h < 0:
                drawn_h += h
                continue
            if drawn_h - scroll > msg_area_h:
                break

            msg_y = y + drawn_h - scroll
            is_user = msg.role == "user"

            # ── Chat bubble background ──
            bubble_x = 10 if not is_user else W - max_bubble_w - 10
            bubble_w = min(max_bubble_w, fm_calc.horizontalAdvance(msg.text) + 20)
            bubble_w = max(bubble_w, 60)
            bubble_rect = QRectF(bubble_x, msg_y, bubble_w, h - bubble_pad)

            if is_user:
                bubble_bg = QLinearGradient(bubble_x, 0, bubble_x + bubble_w, 0)
                bubble_bg.setColorAt(0, _alpha("#2a1f00", 180))
                bubble_bg.setColorAt(1, _alpha("#1a1500", 160))
                p.setBrush(QBrush(bubble_bg))
                p.setPen(QPen(_alpha(GOLD, 30), 1))
            else:
                bubble_bg = QLinearGradient(bubble_x, 0, bubble_x + bubble_w, 0)
                bubble_bg.setColorAt(0, _alpha("#0d1a2a", 180))
                bubble_bg.setColorAt(1, _alpha("#0a1420", 160))
                p.setBrush(QBrush(bubble_bg))
                p.setPen(QPen(_alpha("#4488cc", 25), 1))
            p.drawRoundedRect(bubble_rect, 10, 10)

            # ── Role label ──
            p.setFont(_font(7))
            if is_user:
                p.setPen(QPen(QColor(GOLD), 150))
            else:
                p.setPen(QPen(QColor("#66aaff"), 150))
            label = "Você" if is_user else "＜Elívea＞"
            p.drawText(QRectF(bubble_x + 8, msg_y + 4, bubble_w - 16, 12),
                       Qt.AlignmentFlag.AlignLeft, label)

            # ── Message text with word wrap ──
            p.setFont(_font(8, bold=False))
            p.setPen(QPen(QColor(TEXT if is_user else "#c8d8e8"), 210))
            fm = QFontMetrics(p.font())
            words = msg.text.split()
            line = ""
            ty = msg_y + 18
            for word in words:
                test = line + " " + word if line else word
                if fm.horizontalAdvance(test) > bubble_w - 16:
                    p.drawText(QRectF(bubble_x + 8, ty, bubble_w - 16, 13),
                               Qt.AlignmentFlag.AlignLeft, line)
                    ty += 13
                    line = word
                else:
                    line = test
            if line:
                p.drawText(QRectF(bubble_x + 8, ty, bubble_w - 16, 13),
                           Qt.AlignmentFlag.AlignLeft, line)

            drawn_h += h

        # ── Typing indicator ──
        if self._typing and not self._streaming:
            ty = y + drawn_h - scroll
            if ty < msg_area_h:
                dots = "●" * ((int(time.time() * 3) % 3) + 1)
                p.setFont(_font(8))
                p.setPen(QPen(QColor("#66aaff"), 120))
                p.drawText(QRectF(10, ty, W - 20, 14), Qt.AlignmentFlag.AlignLeft, f"＜Elívea＞ pensando {dots}")
                drawn_h += 18

        # ── Streaming text ──
        if self._streaming and self._stream_text:
            ty = y + drawn_h - scroll
            if ty < msg_area_h:
                bubble_x = 10
                bubble_w = min(max_bubble_w, 200)
                p.setBrush(QBrush(_alpha("#0d1a2a", 160)))
                p.setPen(QPen(_alpha("#4488cc", 20), 1))
                p.drawRoundedRect(QRectF(bubble_x, ty, bubble_w, 20), 8, 8)
                p.setFont(_font(8, bold=False))
                p.setPen(QPen(QColor("#c8d8e8"), 200))
                text_display = self._stream_text[-60:] if len(self._stream_text) > 60 else self._stream_text
                p.drawText(QRectF(bubble_x + 8, ty, bubble_w - 16, 20),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text_display)
                if self._cursor_blink:
                    fm = QFontMetrics(p.font())
                    cx = bubble_x + 8 + fm.horizontalAdvance(text_display) + 2
                    if cx < bubble_x + bubble_w - 10:
                        p.setPen(QPen(QColor(GOLD), 1))
                        p.drawLine(cx, ty + 4, cx, ty + 16)

        # ── Input area with send button ──
        iy = H - 54
        # Separator glow line
        sep_grad = QLinearGradient(8, 0, W - 8, 0)
        sep_grad.setColorAt(0, _alpha(GOLD, 0))
        sep_grad.setColorAt(0.5, _alpha(GOLD, 40))
        sep_grad.setColorAt(1, _alpha(GOLD, 0))
        p.setPen(QPen(sep_grad, 1))
        p.drawLine(8, iy, W - 8, iy)

        # Input box
        input_rect = QRectF(8, iy + 6, W - 58, 36)
        input_bg = QLinearGradient(input_rect.x(), 0, input_rect.x() + input_rect.width(), 0)
        input_bg.setColorAt(0, _alpha("#0e0e16", 220))
        input_bg.setColorAt(1, _alpha("#12121c", 220))
        p.setBrush(QBrush(input_bg))
        border_a = 60 if self._input_focused else 30
        p.setPen(QPen(_alpha(GOLD, border_a), 1))
        p.drawRoundedRect(input_rect, 12, 12)

        # Input text
        p.setFont(_font(9, bold=False))
        display = self._input_text if self._input_text else "Digite sua mensagem..."
        p.setPen(QPen(QColor(TEXT if self._input_text else TEXT_DIM), 180))
        p.drawText(QRectF(input_rect.x() + 12, input_rect.y(), input_rect.width() - 20, input_rect.height()),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, display)

        # Cursor
        if self._input_focused and self._cursor_blink and self._input_text:
            fm = QFontMetrics(p.font())
            cx = input_rect.x() + 12 + fm.horizontalAdvance(display)
            p.setPen(QPen(QColor(GOLD), 1))
            p.drawLine(cx, input_rect.y() + 8, cx, input_rect.y() + input_rect.height() - 8)

        # Send button
        send_rect = QRectF(W - 46, iy + 6, 38, 36)
        if self._input_text.strip():
            send_bg = QRadialGradient(send_rect.center().x(), send_rect.center().y(), 25)
            send_bg.setColorAt(0, QColor(GOLD))
            send_bg.setColorAt(1, _alpha(GOLD_DIM, 200))
            p.setBrush(QBrush(send_bg))
        else:
            p.setBrush(QBrush(_alpha(PANEL2, 150)))
        p.setPen(QPen(_alpha(GOLD, 40 if not self._input_text.strip() else 100), 1))
        p.drawRoundedRect(send_rect, 10, 10)
        p.setFont(_font(9))
        p.setPen(QPen(QColor(BG if self._input_text.strip() else TEXT_DIM), 220))
        p.drawText(send_rect, Qt.AlignmentFlag.AlignCenter, "▶")

    def mousePressEvent(self, ev):
        iy = self.height() - 54
        x, y = ev.position().x(), ev.position().y()
        send_rect = QRectF(self.width() - 46, iy + 6, 38, 36)
        # Send button click
        if send_rect.contains(ev.position()):
            if self._input_text.strip():
                cmd = self._input_text.strip()
                self.add_message("user", cmd)
                self._input_text = ""
                if hasattr(self, '_on_send') and self._on_send:
                    self._on_send(cmd)
            self.update()
            return
        # Input area click
        input_rect = QRectF(8, iy + 6, self.width() - 58, 36)
        if input_rect.contains(ev.position()):
            self._input_focused = True
        else:
            self._input_focused = False
        self.update()

    def keyPressEvent(self, ev):
        if not self._input_focused:
            return
        key = ev.key()
        text = ev.text()
        if key == Qt.Key.Key_Backspace:
            self._input_text = self._input_text[:-1]
        elif key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            if self._input_text.strip():
                cmd = self._input_text.strip()
                self.add_message("user", cmd)
                self._input_text = ""
                # Emit signal via parent
                if hasattr(self, '_on_send') and self._on_send:
                    self._on_send(cmd)
        elif text and text.isprintable():
            self._input_text += text
        self.update()

# ═══════════════════════════════════════════════════════════════════════════
# TopBar Widget
# ═══════════════════════════════════════════════════════════════════════════
class TopBarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self._connected = True

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Background
        p.fillRect(0, 0, W, H, _alpha(BG, 220))

        # Bottom border
        p.setPen(QPen(_alpha(BORDER, 100), 1))
        p.drawLine(0, H - 1, W, H - 1)

        # Left: back arrow + "BENTO DASHBOARD"
        p.setFont(_font(9))
        p.setPen(QPen(QColor(TEXT_DIM), 150))
        p.drawText(QRectF(12, 4, 20, H - 8), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "<")
        p.setFont(_font(8, bold=False))
        p.setPen(QPen(QColor(TEXT_DIM), 120))
        p.drawText(QRectF(36, 4, 120, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "SESSION")
        p.setFont(_font(9))
        p.setPen(QPen(QColor(TEXT_MED), 180))
        p.drawText(QRectF(36, 18, 120, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "BENTO DASHBOARD")

        # Center: Logo + Elivea
        cx = W / 2
        # Logo circle
        p.setPen(QPen(_alpha(GOLD, 100), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(cx - 50, 6, 28, 28))
        p.setFont(_font(10))
        p.setPen(QPen(QColor(GOLD), 200))
        p.drawText(QRectF(cx - 50, 6, 28, 28), Qt.AlignmentFlag.AlignCenter, "G")

        p.setFont(_font(10))
        p.setPen(QPen(QColor(TEXT), 230))
        p.drawText(QRectF(cx - 18, 4, 140, 16), Qt.AlignmentFlag.AlignLeft, "Elívea")
        p.setFont(_font(7, bold=False))
        p.setPen(QPen(QColor(GOLD_DIM), 120))
        p.drawText(QRectF(cx - 18, 22, 140, 12), Qt.AlignmentFlag.AlignLeft, "AI COMMAND CENTER")

        # Right: status + buttons
        rx = W - 200
        # Online dot
        p.setBrush(QBrush(_alpha(GOLD, 180)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(rx, H / 2), 3, 3)
        p.setFont(_font(8, bold=False))
        p.setPen(QPen(QColor(TEXT_DIM), 150))
        p.drawText(QRectF(rx + 8, 4, 50, H - 8), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "ONLINE")

        # User pill
        p.setPen(QPen(_alpha(BORDER, 80), 1))
        p.setBrush(QBrush(_alpha(PANEL2, 150)))
        p.drawRoundedRect(QRectF(W - 150, 10, 100, 28), 14, 14)
        p.setFont(_font(8, bold=False))
        p.setPen(QPen(QColor(TEXT_MED), 180))
        p.drawText(QRectF(W - 145, 10, 90, 28), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "User: sage-owner")

        # Power button
        p.setPen(QPen(_alpha(RED, 80), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(W - 40, 10, 28, 28), 6, 6)
        p.setFont(_font(9))
        p.setPen(QPen(QColor(RED), 150))
        p.drawText(QRectF(W - 40, 10, 28, 28), Qt.AlignmentFlag.AlignCenter, "⏻")


# ═══════════════════════════════════════════════════════════════════════════
# Input Bar Widget (bottom)
# ═══════════════════════════════════════════════════════════════════════════
class InputBarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(56)
        self._input = ""
        self._focused = False
        self._cursor = True
        self._on_submit = None

        self._timer = QTimer(self)
        self._timer.timeout.connect(lambda: (setattr(self, '_cursor', not self._cursor), self.update()))
        self._timer.start(500)

    def set_on_submit(self, cb):
        self._on_submit = cb

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Container
        cw = min(W - 40, 700)
        cx = (W - cw) / 2
        p.setBrush(QBrush(_alpha("#111111", 200)))
        p.setPen(QPen(_alpha(BORDER, 60), 1))
        p.drawRoundedRect(QRectF(cx, 4, cw, H - 8), 16, 16)

        # Mic icon
        p.setFont(_font(12))
        p.setPen(QPen(QColor(TEXT_DIM), 150))
        p.drawText(QRectF(cx + 12, 4, 30, H - 8), Qt.AlignmentFlag.AlignCenter, "🎙")

        # Input text
        p.setFont(_font(10, bold=False))
        display = self._input if self._input else "Pergunte ao Elívea ou insira um comando..."
        p.setPen(QPen(QColor(TEXT if self._input else TEXT_DIM), 180))
        p.drawText(QRectF(cx + 48, 4, cw - 140, H - 8),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, display)

        # Cursor
        if self._focused and self._cursor and self._input:
            fm = QFontMetrics(p.font())
            cx2 = cx + 48 + fm.horizontalAdvance(display)
            p.setPen(QPen(QColor(GOLD), 1))
            p.drawLine(cx2, 12, cx2, H - 12)

        # RUN button
        btn_x = cx + cw - 70
        p.setBrush(QBrush(QColor(GOLD)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(btn_x, 10, 56, H - 20), (H - 20) / 2, (H - 20) / 2)
        p.setFont(_font(9))
        p.setPen(QPen(QColor(BG), 220))
        p.drawText(QRectF(btn_x, 10, 56, H - 20), Qt.AlignmentFlag.AlignCenter, "RUN")

    def mousePressEvent(self, ev):
        self._focused = True
        self.update()

    def keyPressEvent(self, ev):
        if not self._focused:
            return
        key = ev.key()
        text = ev.text()
        if key == Qt.Key.Key_Backspace:
            self._input = self._input[:-1]
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._input.strip() and self._on_submit:
                self._on_submit(self._input.strip())
                self._input = ""
        elif text and text.isprintable():
            self._input += text
        self.update()

    def focusOutEvent(self, ev):
        self._focused = False
        self.update()


# ═══════════════════════════════════════════════════════════════════════════
# Command Center Drawer
# ═══════════════════════════════════════════════════════════════════════════
class CommandCenterDrawer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._open = False
        self._opacity = 0.0
        self._actions = [
            ("abrir chrome", "Chrome"), ("abrir firefox", "Firefox"), ("abrir edge", "Edge"),
            ("abrir terminal", "Terminal"), ("abrir spotify", "Spotify"), ("abrir discord", "Discord"),
            ("abrir code", "VS Code"), ("abrir explorer", "Explorer"), ("abrir powershell", "PowerShell"),
            ("abrir steam", "Steam"), ("abrir epic", "Epic Games"), ("abrir valorant", "Valorant"),
            ("abrir minecraft", "Minecraft"), ("abrir cs2", "CS2"),
            ("play pause", "Play/Pause"), ("próxima música", "Próxima"), ("aumentar volume", "Vol +"),
            ("diminuir volume", "Vol -"), ("mudo", "Mudo"), ("volume 50", "Volume 50%"),
            ("maximizar janela", "Maximizar"), ("minimizar janela", "Minimizar"),
            ("travar pc", "Lock"), ("capturar tela", "Screenshot"), ("dormir", "Sleep"),
            ("meu ip", "Meu IP"), ("wifi", "WiFi"), ("bateria", "Bateria"),
            ("google", "Google"), ("youtube", "YouTube"), ("abrir github", "GitHub"),
            ("clima", "Clima"), ("abrir chatgpt", "ChatGPT"),
            ("ctrl c", "Ctrl+C"), ("ctrl v", "Ctrl+V"), ("ctrl z", "Ctrl+Z"),
            ("alt tab", "Alt+Tab"), ("win d", "Win+D"), ("win l", "Win+L"),
            ("reiniciar", "⚠ Reiniciar"), ("desligar", "⚠ Desligar"),
        ]
        self._filter = ""
        self._on_execute = None

    def set_on_execute(self, cb):
        self._on_execute = cb

    def open(self):
        self._open = True
        self._opacity = 1.0
        self.show()
        self.raise_()
        self.setFocus()
        self.update()

    def close_drawer(self):
        self._open = False
        self.hide()

    def paintEvent(self, _):
        if not self._open:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Overlay
        p.fillRect(0, 0, W, H, _alpha("#000000", int(150 * self._opacity)))

        # Drawer panel
        dw = 320
        dx = W - dw
        p.fillRect(dx, 0, dw, H, _alpha("#0a0a0a", int(245 * self._opacity)))
        p.setPen(QPen(_alpha(BORDER, 80), 1))
        p.drawLine(dx, 0, dx, H)

        # Title
        p.setFont(_font(10))
        p.setPen(QPen(QColor(GOLD), 200))
        p.drawText(QRectF(dx + 12, 10, dw - 24, 20), Qt.AlignmentFlag.AlignLeft, "Command Center")

        # Search box
        p.setBrush(QBrush(_alpha(PANEL2, 200)))
        p.setPen(QPen(_alpha(BORDER, 60), 1))
        p.drawRoundedRect(QRectF(dx + 12, 38, dw - 24, 28), 6, 6)
        p.setFont(_font(8, bold=False))
        p.setPen(QPen(QColor(TEXT_DIM), 150))
        search_display = self._filter if self._filter else "Buscar comando..."
        p.drawText(QRectF(dx + 20, 38, dw - 40, 28),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, search_display)

        # Actions list
        y = 78
        filtered = [(cmd, name) for cmd, name in self._actions if not self._filter or self._filter.lower() in name.lower() or self._filter.lower() in cmd.lower()]
        for cmd, name in filtered[:20]:
            if y > H - 20:
                break
            danger = name.startswith("⚠")
            col = RED if danger else TEXT_MED
            p.setFont(_font(9, bold=False))
            p.setPen(QPen(QColor(col), 180))
            p.drawText(QRectF(dx + 16, y, dw - 32, 16), Qt.AlignmentFlag.AlignLeft, name)
            p.setFont(_font(7, bold=False))
            p.setPen(QPen(QColor(TEXT_DIM), 100))
            p.drawText(QRectF(dx + 16, y + 14, dw - 32, 10), Qt.AlignmentFlag.AlignLeft, cmd)
            y += 30

    def mousePressEvent(self, ev):
        if not self._open:
            return
        W, H = self.width(), self.height()
        dw = 320
        dx = W - dw
        x, y = ev.position().x(), ev.position().y()

        if x < dx:
            self.close_drawer()
            return

        # Check action clicks
        ay = 78
        filtered = [(cmd, name) for cmd, name in self._actions if not self._filter or self._filter.lower() in name.lower()]
        for cmd, name in filtered[:20]:
            if ay > H - 20:
                break
            if dx + 12 <= x <= W - 12 and ay - 4 <= y <= ay + 28:
                if self._on_execute:
                    self._on_execute(cmd)
                self.close_drawer()
                return
            ay += 30

    def keyPressEvent(self, ev):
        if not self._open:
            return
        key = ev.key()
        text = ev.text()
        if key == Qt.Key.Key_Escape:
            self.close_drawer()
        elif key == Qt.Key.Key_Backspace:
            self._filter = self._filter[:-1]
            self.update()
        elif text and text.isprintable():
            self._filter += text
            self.update()


# ═══════════════════════════════════════════════════════════════════════════
# System Monitor — Real-time CPU, RAM, Disk
# ═══════════════════════════════════════════════════════════════════════════
class SystemMonitorWidget(GlassPanel):
    """Animated system monitor with circular gauges and smooth transitions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cpu = 0.0
        self._cpu_smooth = 0.0
        self._ram = 0.0
        self._ram_smooth = 0.0
        self._ram_used = "0 GB"
        self._ram_total = "0 GB"
        self._disk = 0.0
        self._disk_smooth = 0.0
        self._disk_used = "0 GB"
        self._net_up = "0 KB/s"
        self._net_down = "0 KB/s"
        self._t = 0.0
        self._last = time.time()
        # Sparkline history (last 30 readings)
        self._cpu_history: list[float] = []
        self._ram_history: list[float] = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update)
        self._timer.start(2000)
        self._update()

    def _update(self):
        try:
            self._cpu = psutil.cpu_percent(interval=None)
            vm = psutil.virtual_memory()
            self._ram = vm.percent
            self._ram_used = f"{vm.used / (1024**3):.1f} GB"
            self._ram_total = f"{vm.total / (1024**3):.1f} GB"
            du = psutil.disk_usage('\\')
            self._disk = du.percent
            self._disk_used = f"{du.used / (1024**3):.0f} GB"
            net = psutil.net_io_counters()
            self._net_up = f"{net.bytes_sent / 1024:.0f} KB"
            self._net_down = f"{net.bytes_recv / 1024:.0f} KB"
            # Record sparkline history
            self._cpu_history.append(self._cpu)
            self._ram_history.append(self._ram)
            if len(self._cpu_history) > 30:
                self._cpu_history.pop(0)
            if len(self._ram_history) > 30:
                self._ram_history.pop(0)
            # Dynamic glow: CPU high = orange/red border, low = subtle gold
            activity = max(self._cpu, self._ram) / 100.0
            if activity > 0.8:
                self.set_activity(activity, "rgba(248,113,113,0.3)")  # red
            elif activity > 0.5:
                self.set_activity(activity, "rgba(251,191,36,0.2)")  # amber
            else:
                self.set_activity(activity * 0.3, "rgba(255,215,0,0.08)")  # gold
        except Exception:
            pass
        self.update()

    def _draw_gauge(self, p, cx, cy, r, value, color, label, sublabel=""):
        """Draw an animated circular gauge."""
        # Smooth transition
        attr = f"_{label.lower()}_smooth"
        current = getattr(self, attr, value)
        current += (value - current) * 0.15
        setattr(self, attr, current)

        # Background arc
        p.setPen(QPen(_alpha(BORDER, 80), 4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # Value arc
        span = int(360 * current / 100 * 16)
        if span > 0:
            # Gradient arc
            p.setPen(QPen(QColor(color), 4))
            rect = QRectF(cx - r, cy - r, r * 2, r * 2)
            p.drawArc(rect, 90 * 16, -span)

        # Glow effect
        glow_r = r * 0.85
        glow = QRadialGradient(cx, cy, glow_r)
        glow_a = int(15 * (current / 100))
        glow.setColorAt(0, _alpha(color, glow_a))
        glow.setColorAt(1, _alpha(color, 0))
        p.setBrush(QBrush(glow)); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2))

        # Center text
        p.setFont(_font(8))
        p.setPen(QPen(QColor(TEXT), 220))
        p.drawText(QRectF(cx - r, cy - 6, r * 2, 12),
                   Qt.AlignmentFlag.AlignCenter, f"{current:.0f}%")

        # Label below
        p.setFont(_font(6, bold=False))
        p.setPen(QPen(QColor(TEXT_DIM), 140))
        p.drawText(QRectF(cx - r, cy + r + 2, r * 2, 10),
                   Qt.AlignmentFlag.AlignCenter, label)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Title
        p.setFont(_font(9))
        p.setPen(QPen(QColor(GOLD), 200))
        p.drawText(QRectF(10, 6, W - 20, 14), Qt.AlignmentFlag.AlignLeft, "⚡ System Monitor")

        # Circular gauges
        gauge_r = min(30, (W - 20) // 3 - 10)
        y_center = 55
        spacing = W // 3
        self._draw_gauge(p, spacing * 0 + spacing // 2, y_center, gauge_r,
                        self._cpu, GOLD, "CPU")
        self._draw_gauge(p, spacing * 1 + spacing // 2, y_center, gauge_r,
                        self._ram, GREEN if self._ram < 70 else GOLD if self._ram < 85 else RED, "RAM")
        self._draw_gauge(p, spacing * 2 + spacing // 2, y_center, gauge_r,
                        self._disk, GREEN if self._disk < 70 else GOLD if self._disk < 85 else RED, "DISK")

        # Details
        y = 98
        p.setFont(_font(7, bold=False))
        p.setPen(QPen(QColor(TEXT_DIM), 130))
        p.drawText(QRectF(10, y, W - 20, 10),
                   Qt.AlignmentFlag.AlignLeft, f"RAM: {self._ram_used} / {self._ram_total}")
        y += 12
        p.drawText(QRectF(10, y, W - 20, 10),
                   Qt.AlignmentFlag.AlignLeft, f"DISK: {self._disk_used} used")
        y += 12
        p.drawText(QRectF(10, y, W // 2 - 10, 10),
                   Qt.AlignmentFlag.AlignLeft, f"↑ {self._net_up}")
        p.drawText(QRectF(W // 2, y, W // 2 - 10, 10),
                   Qt.AlignmentFlag.AlignRight, f"↓ {self._net_down}")

        # ── Sparklines (CPU & RAM history) ──
        y += 16
        spark_w = W - 20
        spark_h = 20
        if len(self._cpu_history) > 1:
            # CPU sparkline
            p.setFont(_font(6, bold=False))
            p.setPen(QPen(QColor(GOLD), 100))
            p.drawText(QRectF(10, y, 30, 8), Qt.AlignmentFlag.AlignLeft, "CPU")
            self._draw_sparkline(p, 38, y, spark_w - 38, spark_h, self._cpu_history, GOLD)
            y += spark_h + 4
            # RAM sparkline
            p.setPen(QPen(QColor(GREEN), 100))
            p.drawText(QRectF(10, y, 30, 8), Qt.AlignmentFlag.AlignLeft, "RAM")
            self._draw_sparkline(p, 38, y, spark_w - 38, spark_h, self._ram_history, GREEN)

    def _draw_sparkline(self, p, x, y, w, h, data: list[float], color: str):
        """Draw an animated sparkline chart."""
        if len(data) < 2:
            return
        n = len(data)
        step = w / max(n - 1, 1)

        # Fill gradient under the line
        path = QPainterPath()
        path.moveTo(x, y + h)
        for i, val in enumerate(data):
            px = x + i * step
            py = y + h - (val / 100.0) * h
            if i == 0:
                path.lineTo(px, py)
            else:
                path.lineTo(px, py)
        path.lineTo(x + (n - 1) * step, y + h)
        path.closeSubpath()
        fill = QLinearGradient(x, y, x, y + h)
        fill.setColorAt(0, _alpha(color, 25))
        fill.setColorAt(1, _alpha(color, 0))
        p.setBrush(QBrush(fill)); p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(path)

        # Line
        p.setPen(QPen(QColor(color), 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        line_path = QPainterPath()
        for i, val in enumerate(data):
            px = x + i * step
            py = y + h - (val / 100.0) * h
            if i == 0:
                line_path.moveTo(px, py)
            else:
                line_path.lineTo(px, py)
        p.drawPath(line_path)

        # Current value dot
        last_x = x + (n - 1) * step
        last_y = y + h - (data[-1] / 100.0) * h
        p.setBrush(QBrush(QColor(color)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(last_x, last_y), 2.5, 2.5)


# ═══════════════════════════════════════════════════════════════════════════
# Quick Actions — Frequently used commands
# ═══════════════════════════════════════════════════════════════════════════
class QuickActionsWidget(GlassPanel):
    """Premium quick-action buttons with icon, color accent, and hover glow."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._on_action = None
        self._actions = [
            ("🔍", "Google", "google", "#4285f4"),
            ("📁", "Files", "abrir explorer", "#f5a623"),
            ("💻", "Terminal", "abrir terminal", GREEN),
            ("🎮", "Steam", "abrir steam", "#1b2838"),
            ("🎵", "Spotify", "abrir spotify", "#1db954"),
            ("💬", "Discord", "abrir discord", "#5865f2"),
            ("📝", "VS Code", "abrir code", "#007acc"),
            ("📸", "Screenshot", "capturar tela", GOLD),
            ("🌐", "IP Info", "meu ip", "#60a5fa"),
            ("🧹", "Lixeira", "limpar lixeira", RED),
            ("🚀", "Boost RAM", "otimizar ram", GREEN),
            ("⚙️", "Programar", "programar", GOLD),
        ]
        self._hovered = -1
        self._pressed = -1

    def set_on_action(self, cb):
        self._on_action = cb

    def _cell_rect(self, idx: int):
        W = self.width()
        cols = 4
        cell_w = (W - 16) / cols
        cell_h = 28
        y0 = 24
        col = idx % cols
        row = idx // cols
        x = 8 + col * cell_w
        y = y0 + row * (cell_h + 4)
        return QRectF(x, y, cell_w - 4, cell_h)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Title
        p.setFont(_font(9))
        p.setPen(QPen(QColor(TEXT), 200))
        p.drawText(QRectF(10, 6, W - 20, 14), Qt.AlignmentFlag.AlignLeft, "⚡ Quick Actions")

        for i, (icon, name, cmd, color) in enumerate(self._actions):
            rect = self._cell_rect(i)
            if rect.y() + rect.height() > H - 4:
                break

            is_hov = (i == self._hovered)
            is_press = (i == self._pressed)

            # Hover glow effect (expands beyond button bounds)
            if is_hov and not is_press:
                glow_r = max(rect.width(), rect.height()) * 0.8
                glow_c = rect.center()
                glow = QRadialGradient(glow_c.x(), glow_c.y(), glow_r)
                glow.setColorAt(0, _alpha(color, 20))
                glow.setColorAt(0.5, _alpha(color, 8))
                glow.setColorAt(1, _alpha(color, 0))
                p.setBrush(QBrush(glow)); p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QRectF(glow_c.x() - glow_r, glow_c.y() - glow_r,
                                     glow_r * 2, glow_r * 2))

            # Button background
            if is_press:
                p.setBrush(QBrush(_alpha(color, 30)))
                p.setPen(QPen(_alpha(color, 70), 1.5))
            elif is_hov:
                p.setBrush(QBrush(_alpha(color, 15)))
                p.setPen(QPen(_alpha(color, 45), 1))
            else:
                p.setBrush(QBrush(_alpha(PANEL2, 120)))
                p.setPen(QPen(_alpha(BORDER, 50), 1))
            p.drawRoundedRect(rect, 6, 6)

            # Color accent dot (pulsing on hover)
            dot_x = rect.x() + 8
            dot_y = rect.center().y()
            dot_r = 3.0 if is_hov else 2.5
            p.setBrush(QBrush(QColor(color)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(dot_x, dot_y), dot_r, dot_r)

            # Icon
            p.setFont(_font(10))
            p.setPen(QPen(QColor(TEXT), 220 if is_hov else 200))
            p.drawText(QRectF(rect.x() + 16, rect.y(), 20, rect.height()),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, icon)

            # Name
            p.setFont(_font(8, bold=not is_hov))
            col_txt = TEXT if is_hov else TEXT_MED
            p.setPen(QPen(QColor(col_txt), 200 if is_hov else 180))
            p.drawText(QRectF(rect.x() + 34, rect.y(), rect.width() - 40, rect.height()),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

    def mouseMoveEvent(self, ev):
        for i in range(len(self._actions)):
            if self._cell_rect(i).contains(ev.position()):
                self._hovered = i
                self.setCursor(Qt.CursorShape.PointingHandCursor)
                self.update()
                return
        self._hovered = -1
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()

    def mousePressEvent(self, ev):
        for i in range(len(self._actions)):
            if self._cell_rect(i).contains(ev.position()):
                self._pressed = i
                self.update()
                return

    def mouseReleaseEvent(self, ev):
        if self._pressed >= 0 and self._cell_rect(self._pressed).contains(ev.position()):
            if self._on_action:
                self._on_action(self._actions[self._pressed][2])
        self._pressed = -1
        self.update()

    def leaveEvent(self, ev):
        self._hovered = -1
        self._pressed = -1
        self.update()


# ═══════════════════════════════════════════════════════════════════════════
# AI Status — Model info, tokens, session stats
# ═══════════════════════════════════════════════════════════════════════════
class AIStatusWidget(GlassPanel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = "GPT-OSS 120B"
        self._provider = "Groq"
        self._tokens_used = 0
        self._latency = 0
        self._commands_today = 0
        self._uptime = 0
        self._start_time = time.time()
        self._voice_active = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(5000)

    def set_model(self, model: str, provider: str = ""):
        self._model = model
        self._provider = provider
        self.update()

    def set_latency(self, ms: int):
        self._latency = ms
        self.update()

    def add_tokens(self, n: int):
        self._tokens_used += n
        self.update()

    def increment_commands(self):
        self._commands_today += 1
        self.update()

    def set_voice_active(self, active: bool):
        self._voice_active = active
        self.update()

    def _tick(self):
        self._uptime = int(time.time() - self._start_time)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        p.setFont(_font(9))
        p.setPen(QPen(QColor(TEXT), 200))
        p.drawText(QRectF(10, 6, W - 20, 14), Qt.AlignmentFlag.AlignLeft, "🧠 AI Status")

        y = 24
        items = [
            ("Model", self._model, GOLD),
            ("Provider", self._provider or "—", TEXT_MED),
            ("Tokens", f"{self._tokens_used:,}", GREEN),
            ("Latency", f"{self._latency}ms", GREEN if self._latency < 500 else GOLD if self._latency < 1500 else RED),
            ("Commands", str(self._commands_today), TEXT),
            ("Voice", "Active" if self._voice_active else "Idle", GREEN if self._voice_active else TEXT_DIM),
            ("Uptime", f"{self._uptime // 60}m {self._uptime % 60}s", TEXT_MED),
        ]
        for label, value, color in items:
            p.setFont(_font(7, bold=False))
            p.setPen(QPen(QColor(TEXT_DIM), 130))
            p.drawText(QRectF(10, y, 70, 10), Qt.AlignmentFlag.AlignLeft, label)
            p.setFont(_font(8))
            p.setPen(QPen(QColor(color), 200))
            p.drawText(QRectF(80, y, W - 100, 10), Qt.AlignmentFlag.AlignLeft, value)
            y += 14


# ═══════════════════════════════════════════════════════════════════════════
# Recent Commands — Scrollable history
# ═══════════════════════════════════════════════════════════════════════════
class RecentCommandsWidget(GlassPanel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._commands: list[tuple[str, str, float]] = []  # (cmd, result_preview, timestamp)
        self._max = 15

    def add_command(self, cmd: str, result: str = ""):
        self._commands.insert(0, (cmd, result[:60], time.time()))
        if len(self._commands) > self._max:
            self._commands = self._commands[:self._max]
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        p.setFont(_font(9))
        p.setPen(QPen(QColor(TEXT), 200))
        p.drawText(QRectF(10, 6, W - 20, 14), Qt.AlignmentFlag.AlignLeft, "📋 Recent Commands")

        if not self._commands:
            p.setFont(_font(8, bold=False))
            p.setPen(QPen(QColor(TEXT_DIM), 120))
            p.drawText(QRectF(10, 28, W - 20, 20),
                       Qt.AlignmentFlag.AlignCenter, "No commands yet")
            return

        y = 24
        for cmd, result, ts in self._commands[:8]:
            if y > H - 16:
                break
            elapsed = int(time.time() - ts)
            if elapsed < 60:
                time_str = f"{elapsed}s ago"
            elif elapsed < 3600:
                time_str = f"{elapsed // 60}m ago"
            else:
                time_str = f"{elapsed // 3600}h ago"

            # Time
            p.setFont(_font(6, bold=False))
            p.setPen(QPen(QColor(TEXT_DIM), 100))
            p.drawText(QRectF(10, y, 40, 8), Qt.AlignmentFlag.AlignLeft, time_str)

            # Command
            p.setFont(_font(8, bold=False))
            p.setPen(QPen(QColor(TEXT_MED), 180))
            display = cmd[:35] + "…" if len(cmd) > 35 else cmd
            p.drawText(QRectF(50, y, W - 60, 10), Qt.AlignmentFlag.AlignLeft, display)

            # Result preview
            if result:
                p.setFont(_font(7, bold=False))
                p.setPen(QPen(QColor(TEXT_DIM), 100))
                p.drawText(QRectF(50, y + 10, W - 60, 8), Qt.AlignmentFlag.AlignLeft, result[:40])
            y += 22


# ═══════════════════════════════════════════════════════════════════════════
# Notification Widget — Real-time activity feed
# ═══════════════════════════════════════════════════════════════════════════
class NotificationWidget(GlassPanel):
    """Live notification feed showing AI activity and system events."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._notifications: list[tuple[str, str, float]] = []  # (icon, text, timestamp)
        self._max = 8

    def add(self, icon: str, text: str):
        self._notifications.insert(0, (icon, text, time.time()))
        if len(self._notifications) > self._max:
            self._notifications = self._notifications[:self._max]
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Title
        p.setFont(_font(9))
        p.setPen(QPen(QColor(GOLD), 200))
        p.drawText(QRectF(10, 6, W - 20, 14), Qt.AlignmentFlag.AlignLeft, "🔔 Activity")

        y = 26
        for icon, text, ts in self._notifications:
            if y + 16 > H:
                break
            # Time ago
            ago = time.time() - ts
            if ago < 60:
                time_str = f"{int(ago)}s"
            elif ago < 3600:
                time_str = f"{int(ago/60)}m"
            else:
                time_str = f"{int(ago/3600)}h"

            # Icon
            p.setFont(_font(8))
            p.setPen(QPen(QColor(TEXT), 180))
            p.drawText(QRectF(10, y, 18, 14), Qt.AlignmentFlag.AlignLeft, icon)

            # Text
            p.setFont(_font(7, bold=False))
            p.setPen(QPen(QColor(TEXT_MED), 170))
            p.drawText(QRectF(28, y, W - 70, 14), Qt.AlignmentFlag.AlignLeft, text[:40])

            # Time
            p.setFont(_font(6, bold=False))
            p.setPen(QPen(QColor(TEXT_DIM), 100))
            p.drawText(QRectF(W - 35, y, 28, 14), Qt.AlignmentFlag.AlignRight, time_str)

            y += 16

        if not self._notifications:
            p.setFont(_font(7, bold=False))
            p.setPen(QPen(QColor(TEXT_DIM), 80))
            p.drawText(QRectF(10, y, W - 20, 14), Qt.AlignmentFlag.AlignLeft, "Nenhuma atividade ainda...")


# ═══════════════════════════════════════════════════════════════════════════
# Code Scratchpad — AI output, snippets, command results
# ═══════════════════════════════════════════════════════════════════════════
class CodeScratchpadWidget(GlassPanel):
    """A living scratchpad where the AI drops code, results, and notes.
    The user can see outputs, copy snippets, and the AI updates it live."""

    # Syntax colors
    COL_KW = GOLD          # keywords
    COL_STR = "#e8b84d"    # strings
    COL_FN = "#ffffff"     # functions
    COL_CM = TEXT_DIM      # comments
    COL_NUM = GREEN        # numbers
    COL_VAR = TEXT_MED     # variables
    COL_DEFAULT = TEXT_DIM # plain text

    KEYWORDS = {'import', 'export', 'from', 'const', 'let', 'var', 'function',
                'async', 'await', 'return', 'if', 'else', 'for', 'while',
                'class', 'new', 'this', 'try', 'catch', 'def', 'self',
                'print', 'True', 'False', 'None', 'python', 'pip', 'npm',
                'def', 'class', 'return', 'if', 'else', 'elif', 'for', 'while',
                'import', 'from', 'as', 'with', 'try', 'except', 'finally'}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lines: list[tuple[str, str]] = []  # (text, type) type: code/text/output/error
        self._scroll = 0
        self._max_lines = 50
        self._cursor = True
        self._filename = "scratchpad"
        self._modified = False

        # Initial content
        self.add_line("// Elívea Code Scratchpad", "comment")
        self.add_line("// AI outputs, code snippets, and results appear here", "comment")
        self.add_line("", "text")

        self._timer = QTimer(self)
        self._timer.timeout.connect(lambda: (setattr(self, '_cursor', not self._cursor), self.update()))
        self._timer.start(530)

    def add_line(self, text: str, line_type: str = "text"):
        """Add a line. line_type: code, text, output, error, comment"""
        self._lines.append((text, line_type))
        if len(self._lines) > self._max_lines:
            self._lines = self._lines[-self._max_lines:]
        self._modified = True
        self.update()

    def clear(self):
        self._lines.clear()
        self.add_line("// Scratchpad cleared", "comment")
        self.update()

    def set_code(self, code: str, language: str = "python"):
        """Set multi-line code with syntax highlighting."""
        self._lines.clear()
        self.add_line(f"// {language.upper()} — {self._filename}", "comment")
        self.add_line("", "text")
        for line in code.split("\n"):
            self.add_line(line, "code")
        self._modified = True
        self.update()

    def add_output(self, text: str):
        """Add command/output line (green-tinted)."""
        for line in text.split("\n"):
            self.add_line(f"> {line}", "output")

    def add_error(self, text: str):
        """Add error line (red-tinted)."""
        for line in text.split("\n"):
            self.add_line(f"✗ {line}", "error")

    def set_filename(self, name: str):
        self._filename = name
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Header
        p.setFont(_font(9))
        p.setPen(QPen(QColor(TEXT), 200))
        mod = " ●" if self._modified else ""
        p.drawText(QRectF(10, 6, W - 80, 14), Qt.AlignmentFlag.AlignLeft,
                   f"📝 Code Scratchpad{mod}")
        p.setFont(_font(7, bold=False))
        p.setPen(QPen(QColor(TEXT_DIM), 120))
        p.drawText(QRectF(W - 70, 6, 60, 14), Qt.AlignmentFlag.AlignRight, self._filename)

        # Separator
        p.setPen(QPen(_alpha(BORDER, 60), 1))
        p.drawLine(8, 22, W - 8, 22)

        # Content area background
        p.setBrush(QBrush(_alpha("#000000", 80)))
        p.setPen(QPen(_alpha(BORDER, 40), 1))
        p.drawRoundedRect(QRectF(4, 26, W - 8, H - 36), 4, 4)

        # Code lines
        y = 32
        line_h = 13
        max_visible = (H - 40) // line_h
        start = max(0, len(self._lines) - max_visible)

        for i in range(start, len(self._lines)):
            text, ltype = self._lines[i]
            if y > H - 8:
                break

            # Line number
            p.setFont(_font(7, bold=False))
            p.setPen(QPen(QColor(TEXT_DIM), 60))
            p.drawText(QRectF(8, y, 20, line_h), Qt.AlignmentFlag.AlignRight, str(i + 1))

            # Choose color by type
            if ltype == "code":
                col = self._highlight_syntax(text)
            elif ltype == "output":
                col = GREEN
            elif ltype == "error":
                col = RED
            elif ltype == "comment":
                col = TEXT_DIM
            else:
                col = TEXT_MED

            p.setFont(_font(8, bold=False))
            p.setPen(QPen(QColor(col), 170))
            # Truncate long lines
            display = text[:60] + "…" if len(text) > 60 else text
            p.drawText(QRectF(32, y, W - 40, line_h), Qt.AlignmentFlag.AlignLeft, display)
            y += line_h

        # Empty state
        if len(self._lines) <= 2:
            p.setFont(_font(8, bold=False))
            p.setPen(QPen(QColor(TEXT_DIM), 80))
            p.drawText(QRectF(0, H / 2 - 10, W, 20),
                       Qt.AlignmentFlag.AlignCenter, "Ask me to write code or run a command")

        # Scrollbar
        if len(self._lines) > max_visible:
            bar_h = max(20, int(H * max_visible / len(self._lines)))
            bar_y = 26 + int((H - 36 - bar_h) * start / max(1, len(self._lines) - max_visible))
            p.setBrush(QBrush(_alpha(GOLD, 30)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(W - 6, bar_y, 3, bar_h), 1, 1)

    def _highlight_syntax(self, line: str) -> str:
        """Simple keyword-based syntax highlighting."""
        stripped = line.strip()
        if not stripped:
            return TEXT_DIM
        if stripped.startswith("//") or stripped.startswith("#"):
            return self.COL_CM
        if stripped.startswith(("\"", "'", "`")):
            return self.COL_STR
        # Check first word
        first_word = stripped.split("(")[0].split(" ")[0].split(".")[0]
        if first_word in self.KEYWORDS:
            return self.COL_KW
        # Check for numbers
        first_token = stripped.split(" ")[0]
        if first_token.replace(".", "").replace("-", "").isdigit():
            return self.COL_NUM
        return self.COL_DEFAULT


# ═══════════════════════════════════════════════════════════════════════════
# Code Workspace — Full code editor panel
# ═══════════════════════════════════════════════════════════════════════════
class CodeWorkspaceWidget(QWidget):
    """Premium code generation workspace — prompt → AI code → run.
    Tensura-themed with gold accents, enhanced syntax highlighting,
    more visible lines, and keyboard shortcuts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._prompt = ""
        self._code = "# Descreva o que quer criar acima e clique ✨ Generate"
        self._output = ""
        self._running = False
        self._generating = False
        self._on_generate = None
        self._on_run = None
        self._on_close = None
        self._prompt_focused = False
        self._cursor = True
        self._scroll_offset = 0  # code scroll
        self._out_scroll = 0     # output scroll
        self._t = 0.0
        self._last_t = time.time()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)  # 30fps for smooth animation

    def _tick(self):
        import time as _time
        now = _time.time()
        self._t += now - self._last_t
        self._last_t = now
        self._cursor = not self._cursor
        self.update()

    def set_on_generate(self, cb): self._on_generate = cb
    def set_on_run(self, cb): self._on_run = cb
    def set_on_close(self, cb): self._on_close = cb

    def set_code(self, code: str):
        self._code = code
        self._generating = False
        self._scroll_offset = 0
        self.update()

    def set_output(self, text: str):
        self._output = text
        self._running = False
        self._out_scroll = 0
        self.update()

    def set_generating(self, val: bool):
        self._generating = val
        self.update()

    # ── Layout rects ──
    def _hdr_rect(self): return QRectF(0, 0, self.width(), 44)
    def _prompt_rect(self): return QRectF(46, 7, self.width() - 230, 30)
    def _gen_btn_rect(self): return QRectF(self.width() - 175, 7, 95, 30)
    def _run_btn_rect(self): return QRectF(self.width() - 75, 7, 58, 30)
    def _close_btn_rect(self): return QRectF(self.width() - 24, 0, 24, 24)
    def _code_rect(self): return QRectF(0, 44, self.width(), int(self.height() * 0.60))
    def _out_rect(self): return QRectF(0, 44 + int(self.height() * 0.60) + 2, self.width(), self.height())

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # ── Background: deep dark with subtle gradient ──
        bg = QLinearGradient(0, 0, 0, H)
        bg.setColorAt(0, _alpha("#0c0c14", 250))
        bg.setColorAt(1, _alpha("#06060a", 250))
        p.fillRect(0, 0, W, H, QBrush(bg))

        # ── Header bar ──
        hdr = self._hdr_rect()
        hdr_bg = QLinearGradient(0, 0, W, 0)
        hdr_bg.setColorAt(0, _alpha("#141420", 220))
        hdr_bg.setColorAt(0.5, _alpha("#1a1a28", 220))
        hdr_bg.setColorAt(1, _alpha("#141420", 220))
        p.fillRect(hdr, QBrush(hdr_bg))
        p.setPen(QPen(_alpha(GOLD, 30), 1))
        p.drawLine(0, 44, W, 44)

        # Title + icon
        p.setFont(_font(9))
        p.setPen(QPen(QColor(GOLD), 200))
        p.drawText(QRectF(10, 8, 28, 20), Qt.AlignmentFlag.AlignLeft, "⚡")
        p.setPen(QPen(QColor(TEXT), 200))
        p.drawText(QRectF(32, 8, 100, 20), Qt.AlignmentFlag.AlignLeft, "Code Studio")
        # Keyboard shortcut hint
        p.setFont(_font(7, bold=False))
        p.setPen(QPen(QColor(TEXT_DIM), 80))
        p.drawText(QRectF(120, 10, 100, 16), Qt.AlignmentFlag.AlignLeft, "Ctrl+Enter para gerar")

        # ── Prompt input ──
        pr = self._prompt_rect()
        input_bg = QLinearGradient(pr.x(), pr.y(), pr.x() + pr.width(), pr.y())
        input_bg.setColorAt(0, _alpha("#0a0a12", 220))
        input_bg.setColorAt(1, _alpha("#0e0e18", 220))
        p.setBrush(QBrush(input_bg))
        p.setPen(QPen(_alpha(GOLD, 70 if self._prompt_focused else 30), 1))
        p.drawRoundedRect(pr, 8, 8)
        # Prompt text
        p.setFont(_font(9, bold=False))
        display = self._prompt if self._prompt else "Descreva o que quer criar..."
        p.setPen(QPen(QColor(TEXT if self._prompt else TEXT_DIM), 180))
        p.drawText(QRectF(pr.x() + 12, pr.y(), pr.width() - 24, pr.height()),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, display)
        # Cursor
        if self._prompt_focused and self._cursor:
            fm = QFontMetrics(p.font())
            cur_x = pr.x() + 12 + fm.horizontalAdvance(display)
            p.setPen(QPen(QColor(GOLD), 1))
            p.drawLine(cur_x, pr.y() + 7, cur_x, pr.y() + pr.height() - 7)

        # ── Generate button ──
        gr = self._gen_btn_rect()
        if self._generating:
            # Pulsing animation
            pulse = 0.5 + 0.5 * math.sin(time.time() * 4)
            p.setBrush(QBrush(_alpha(GOLD, int(30 * pulse))))
            p.setPen(QPen(_alpha(GOLD, int(60 * pulse)), 1))
        elif self._prompt.strip():
            g = QLinearGradient(gr.x(), gr.y(), gr.x() + gr.width(), gr.y() + gr.height())
            g.setColorAt(0, QColor(GOLD))
            g.setColorAt(1, QColor("#b8960f"))
            p.setBrush(QBrush(g)); p.setPen(Qt.PenStyle.NoPen)
        else:
            p.setBrush(QBrush(_alpha(PANEL2, 120)))
            p.setPen(QPen(_alpha(BORDER, 40), 1))
        p.drawRoundedRect(gr, 8, 8)
        p.setFont(_font(8))
        btn_c = BG if self._prompt.strip() and not self._generating else GOLD if self._generating else TEXT_DIM
        p.setPen(QPen(QColor(btn_c), 220))
        btn_t = "⏳ Gerando..." if self._generating else "✨ Generate"
        p.drawText(gr, Qt.AlignmentFlag.AlignCenter, btn_t)

        # ── Run button ──
        rr = self._run_btn_rect()
        if self._running:
            p.setBrush(QBrush(_alpha(GREEN, 20)))
            p.setPen(QPen(_alpha(GREEN, 60), 1))
        else:
            run_g = QLinearGradient(rr.x(), rr.y(), rr.x() + rr.width(), rr.y() + rr.height())
            run_g.setColorAt(0, QColor(GREEN))
            run_g.setColorAt(1, QColor("#16a34a"))
            p.setBrush(QBrush(run_g)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rr, 8, 8)
        p.setFont(_font(8))
        p.setPen(QPen(QColor(BG if not self._running else GREEN), 220))
        p.drawText(rr, Qt.AlignmentFlag.AlignCenter, "▶ Run" if not self._running else "⏳")

        # ── Close button ──
        cr = self._close_btn_rect()
        p.setFont(_font(10))
        p.setPen(QPen(QColor(TEXT_DIM), 140))
        p.drawText(cr, Qt.AlignmentFlag.AlignCenter, "✕")

        # ═══ CODE AREA ═══
        code_r = self._code_rect()
        code_y = int(code_r.y())
        code_h = int(code_r.height())

        # Code background
        code_bg = QRectF(0, code_y, W, code_h)
        p.fillRect(code_bg, _alpha("#08080e", 240))

        # Line numbers gutter
        gutter_w = 40
        p.fillRect(QRectF(0, code_y, gutter_w, code_h), _alpha("#0a0a12", 240))
        p.setPen(QPen(_alpha(BORDER, 30), 0.5))
        p.drawLine(gutter_w, code_y, gutter_w, code_y + code_h)

        # Code lines
        lines = self._code.split("\n")
        line_h = 15
        max_lines = code_h // line_h
        y = code_y + 4
        start_idx = self._scroll_offset
        for i in range(start_idx, min(len(lines), start_idx + max_lines)):
            if y > code_y + code_h - 4:
                break
            line = lines[i]
            # Line number
            p.setFont(_font(7, bold=False, mono=True))
            p.setPen(QPen(QColor("#4a4a5a"), 80))
            p.drawText(QRectF(2, y, gutter_w - 6, line_h),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(i + 1))
            # Syntax highlighted tokens
            p.setFont(_font(8, bold=False, mono=True))
            tokens = self._tokenize(line)
            tx = gutter_w + 6
            for tok, col in tokens:
                p.setPen(QPen(QColor(col), 190))
                p.drawText(QRectF(tx, y, W - tx, line_h), Qt.AlignmentFlag.AlignLeft, tok)
                tx += QFontMetrics(p.font()).horizontalAdvance(tok)
            y += line_h

        # Generating animation
        if self._generating:
            p.setFont(_font(8, bold=False))
            p.setPen(QPen(QColor(GOLD), 140))
            dots = "." * ((int(self._t * 3) % 4) if hasattr(self, '_t') else int(self._cursor) * 3)
            p.drawText(QRectF(gutter_w + 6, y + 2, W - gutter_w - 12, 14),
                       Qt.AlignmentFlag.AlignLeft, f"AI está escrevendo o código{dots}")

        # ── Code area border ──
        p.setPen(QPen(_alpha(BORDER, 40), 0.5))
        p.drawLine(0, code_y + code_h, W, code_y + code_h)

        # ═══ OUTPUT CONSOLE ═══
        out_r = self._out_rect()
        out_y = int(out_r.y()) + 4
        out_h = int(out_r.height()) - out_r.y() - 4

        # Output header
        p.setFont(_font(7, bold=False))
        p.setPen(QPen(QColor(GOLD), 100))
        p.drawText(QRectF(8, out_y, 60, 12), Qt.AlignmentFlag.AlignLeft, "▎ OUTPUT")
        out_y += 16

        # Output lines
        if self._output:
            p.setFont(_font(8, bold=False, mono=True))
            out_lines = self._output.split("\n")
            for line in out_lines:
                if out_y > code_y + code_h + out_h - 4:
                    break
                is_err = line.startswith("✗") or "Error" in line or "error" in line
                is_ok = line.startswith(">") or line.startswith("✓")
                col = RED if is_err else GREEN if is_ok else TEXT_MED
                p.setPen(QPen(QColor(col), 150))
                p.drawText(QRectF(12, out_y, W - 20, 13),
                           Qt.AlignmentFlag.AlignLeft, line[:100])
                out_y += 13
        else:
            p.setFont(_font(8, bold=False))
            p.setPen(QPen(QColor(TEXT_DIM), 60))
            p.drawText(QRectF(12, out_y, W - 20, 13),
                       Qt.AlignmentFlag.AlignLeft, "Clique ▶ Run para executar o código...")

    def _tokenize(self, line: str) -> list[tuple[str, str]]:
        """Enhanced tokenizer with more color categories."""
        KEYWORDS = {'def', 'class', 'import', 'from', 'return', 'if', 'else', 'elif',
                    'for', 'while', 'try', 'except', 'with', 'as', 'async', 'await',
                    'yield', 'pass', 'break', 'continue', 'raise', 'del', 'global',
                    'nonlocal', 'assert', 'in', 'not', 'and', 'or', 'is'}
        BUILTINS = {'print', 'True', 'False', 'None', 'self', 'len', 'range', 'int',
                    'str', 'float', 'list', 'dict', 'set', 'tuple', 'type', 'isinstance',
                    'input', 'open', 'super', 'enumerate', 'zip', 'map', 'filter', 'sorted',
                    'lambda'}
        DECORATORS = {'@property', '@staticmethod', '@classmethod'}
        tokens: list[tuple[str, str]] = []
        i = 0
        while i < len(line):
            c = line[i]
            if c in (' ', '\t'):
                j = i
                while j < len(line) and line[j] in (' ', '\t'): j += 1
                tokens.append((line[i:j], TEXT_DIM)); i = j
            elif c == '#':
                tokens.append((line[i:], "#5a5a6a")); break
            elif c in ('"', "'"):
                # Check triple-quote
                q3 = line[i:i+3] in ('""\"', "'''")
                j = i + 3 if q3 else i + 1
                end = line.find(q3 and line[i:i+3] or c, j)
                j = (end + 3) if q3 and end >= 0 else (end + 1 if end >= 0 else len(line))
                tokens.append((line[i:j], "#e8b84d")); i = j
            elif c == '@':
                j = i + 1
                while j < len(line) and (line[j].isalnum() or line[j] == '_'): j += 1
                tokens.append((line[i:j], "#c084fc")); i = j  # purple for decorators
            elif c.isalpha() or c == '_':
                j = i
                while j < len(line) and (line[j].isalnum() or line[j] == '_'): j += 1
                word = line[i:j]
                if word in KEYWORDS:
                    tokens.append((word, "#ff79c6"))  # pink keywords
                elif word in BUILTINS:
                    tokens.append((word, "#8be9fd"))  # cyan builtins
                elif word.startswith('__') and word.endswith('__'):
                    tokens.append((word, "#bd93f9"))  # purple dunder
                else:
                    tokens.append((word, TEXT_MED))
                i = j
            elif c.isdigit():
                j = i
                while j < len(line) and (line[j].isdigit() or line[j] in '.xXoObBeE'): j += 1
                tokens.append((line[i:j], GREEN)); i = j
            elif c in ('(', ')', '[', ']', '{', '}'):
                tokens.append((c, "#f8f8f2")); i += 1
            elif c in ('=', '+', '-', '*', '/', '%', '!', '<', '>', '|', '&', '^', '~'):
                # Check for compound operators
                j = i + 1
                if j < len(line) and line[j] in ('=', '+', '-', '>', '<'):
                    j += 1
                tokens.append((line[i:j], "#ff6e6e")); i = j  # red operators
            elif c in (':', ',', ';', '.'):
                tokens.append((c, "#6272a4")); i += 1  # comment-color for punctuation
            else:
                tokens.append((c, TEXT_DIM)); i += 1
        return tokens

    def wheelEvent(self, ev):
        delta = ev.angleDelta().y()
        lines = self._code.split("\n")
        max_scroll = max(0, len(lines) - 10)
        if delta > 0:
            self._scroll_offset = max(0, self._scroll_offset - 3)
        else:
            self._scroll_offset = min(max_scroll, self._scroll_offset + 3)
        self.update()

    def mousePressEvent(self, ev):
        if self._close_btn_rect().contains(ev.position()):
            if self._on_close: self._on_close()
            return
        if self._gen_btn_rect().contains(ev.position()):
            if self._prompt.strip() and not self._generating:
                self._generating = True; self.update()
                if self._on_generate: self._on_generate(self._prompt.strip())
            return
        if self._run_btn_rect().contains(ev.position()):
            if not self._running and self._on_run:
                self._running = True; self._output = "Executando..."; self.update()
                self._on_run(self._code)
            return
        if self._prompt_rect().contains(ev.position()):
            self._prompt_focused = True; self.update(); return
        self._prompt_focused = False; self.update()

    def keyPressEvent(self, ev):
        key = ev.key()
        mods = ev.modifiers()
        # Ctrl+Enter = generate
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and mods & Qt.KeyboardModifier.ControlModifier:
            if self._prompt.strip() and not self._generating:
                self._generating = True; self.update()
                if self._on_generate: self._on_generate(self._prompt.strip())
            return
        if not self._prompt_focused:
            return
        text = ev.text()
        if key == Qt.Key.Key_Backspace:
            self._prompt = self._prompt[:-1]
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._prompt.strip() and not self._generating:
                self._generating = True; self.update()
                if self._on_generate: self._on_generate(self._prompt.strip())
        elif text and text.isprintable():
            self._prompt += text
        self.update()


# ═══════════════════════════════════════════════════════════════════════════
# Ambient Particles — floating golden particles for background depth
# ═══════════════════════════════════════════════════════════════════════════
class AmbientParticles(QWidget):
    """Transparent overlay with floating particles, parallax, fog, scan lines, vignette.
    Phase 4: Multi-layer depth, ambient fog, dust, glassmorphism, CRT, vignette."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._particles: list[list[float]] = []
        self._dust: list[list[float]] = []  # micro dust particles
        self._fog_layers: list[list[float]] = []  # ambient fog
        self._t = 0.0
        self._last = time.time()
        self._mouse_x = 0.5
        self._mouse_y = 0.5
        self.setMouseTracking(True)
        # Create particles (3 layers for parallax depth)
        for _ in range(20):  # far layer (slow, small)
            self._particles.append(self._make_particle(True, 0.3))
        for _ in range(15):  # mid layer
            self._particles.append(self._make_particle(True, 0.6))
        for _ in range(10):  # near layer (fast, large)
            self._particles.append(self._make_particle(True, 1.0))
        # Dust particles
        for _ in range(30):
            self._dust.append([
                random.uniform(0, 1), random.uniform(0, 1),
                random.uniform(-0.0001, 0.0001),
                random.uniform(-0.0003, -0.0001),
                random.uniform(0.3, 0.8),
                random.uniform(15, 40),
            ])
        # Fog layers
        for _ in range(4):
            self._fog_layers.append([
                random.uniform(0, 1),  # x
                random.uniform(0.3, 0.7),  # y
                random.uniform(0.0002, 0.0008),  # speed
                random.uniform(80, 200),  # radius
                random.uniform(3, 8),  # alpha
            ])
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)

    def _make_particle(self, random_y=False, depth=0.5):
        speed = 0.0005 + depth * 0.0015
        return [
            random.uniform(0, 1),
            random.uniform(0, 1) if random_y else random.uniform(0.8, 1.2),
            random.uniform(-speed, speed),
            random.uniform(-speed * 2, -speed * 0.5),
            random.uniform(0.5 + depth, 2.0 + depth * 2),
            random.uniform(20 + depth * 30, 60 + depth * 60),
            random.uniform(0, 2 * math.pi),
            depth,  # layer depth for parallax
        ]

    def _tick(self):
        now = time.time()
        self._t += now - self._last
        self._last = now
        for p in self._particles:
            depth = p[7] if len(p) > 7 else 0.5
            # Parallax: mouse influence scales with depth
            parallax_x = (self._mouse_x - 0.5) * depth * 0.01
            parallax_y = (self._mouse_y - 0.5) * depth * 0.01
            p[0] += p[2] + parallax_x
            p[1] += p[3] + parallax_y
            if p[1] < -0.05:
                p[1] = 1.05
                p[0] = random.uniform(0, 1)
            if p[0] < -0.05: p[0] = 1.05
            if p[0] > 1.05: p[0] = -0.05
        # Dust
        for d in self._dust:
            d[0] += d[2]
            d[1] += d[3]
            if d[1] < -0.05:
                d[1] = 1.05
                d[0] = random.uniform(0, 1)
        # Fog
        for f in self._fog_layers:
            f[0] += f[2]
            if f[0] > 1.3:
                f[0] = -0.3
                f[1] = random.uniform(0.3, 0.7)  # randomize Y on reset
        self.update()

    def mouseMoveEvent(self, ev):
        W, H = self.width(), self.height()
        if W > 0 and H > 0:
            self._mouse_x = ev.position().x() / W
            self._mouse_y = ev.position().y() / H

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # ── Ambient Fog Layers ──
        for fx_norm, fy_norm, speed, radius, base_a in self._fog_layers:
            fx = fx_norm * W
            fy = fy_norm * H
            fog = QRadialGradient(fx, fy, radius)
            pulse = 0.6 + 0.4 * math.sin(self._t * 0.3 + fx_norm * 10)
            a = int(base_a * pulse)
            fog.setColorAt(0, _alpha(GOLD, a))
            fog.setColorAt(0.5, _alpha(GOLD, int(a * 0.3)))
            fog.setColorAt(1, _alpha(GOLD, 0))
            p.setBrush(QBrush(fog)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(fx - radius, fy - radius, radius * 2, radius * 2))

        # ── Particles with parallax depth ──
        for x, y, _, _, sz, base_a, phase, *_ in self._particles:
            pulse = 0.5 + 0.5 * math.sin(self._t * 1.5 + phase)
            a = int(base_a * pulse)
            if a < 3:
                continue
            px, py = x * W, y * H
            glow_r = sz * 3
            glow = QRadialGradient(px, py, glow_r)
            glow.setColorAt(0, _alpha(GOLD, int(a * 0.4)))
            glow.setColorAt(0.5, _alpha(GOLD, int(a * 0.1)))
            glow.setColorAt(1, _alpha(GOLD, 0))
            p.setBrush(QBrush(glow)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(px - glow_r, py - glow_r, glow_r * 2, glow_r * 2))
            p.setBrush(QBrush(_alpha(GOLD, a)))
            p.drawEllipse(QPointF(px, py), sz * 0.5, sz * 0.5)

        # ── Dust Particles (micro, subtle) ──
        for dx, dy, _, _, sz, base_a in self._dust:
            px, py = dx * W, dy * H
            a = int(base_a * (0.5 + 0.5 * math.sin(self._t * 0.8 + dx * 20)))
            if a > 2:
                p.setPen(QPen(_alpha(GOLD, a), sz))
                p.drawPoint(int(px), int(py))

        # ── Subtle CRT Scan Lines ──
        scan_a = 3  # very subtle
        p.setPen(QPen(_alpha("#000000", scan_a), 0.5))
        for sy in range(0, H, 3):
            p.drawLine(0, sy, W, sy)

        # ── Vignette (darken edges) ──
        vig = QRadialGradient(W / 2, H / 2, max(W, H) * 0.7)
        vig.setColorAt(0, _alpha("#000000", 0))
        vig.setColorAt(0.6, _alpha("#000000", 0))
        vig.setColorAt(1.0, _alpha("#000000", 60))
        p.setBrush(QBrush(vig)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(0, 0, W, H)


# ═══════════════════════════════════════════════════════════════════════════
# Status Bar — bottom bar with system info
# ═══════════════════════════════════════════════════════════════════════════
class StatusBar(QWidget):
    """Professional bottom status bar with system info, uptime, connection."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self._uptime = 0.0
        self._last = time.time()
        self._cpu = 0.0
        self._ram = 0.0
        self._model = "—"
        self._commands_today = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(3000)
        self._tick()

    def set_model(self, name: str):
        self._model = name

    def set_commands_today(self, n: int):
        self._commands_today = n

    def _tick(self):
        now = time.time()
        self._uptime += now - self._last
        self._last = now
        try:
            self._cpu = psutil.cpu_percent(interval=0)
            self._ram = psutil.virtual_memory().percent
        except Exception:
            pass
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Background
        bg = QLinearGradient(0, 0, 0, H)
        bg.setColorAt(0, _alpha("#080808", 240))
        bg.setColorAt(1, _alpha("#040404", 250))
        p.fillRect(0, 0, W, H, bg)

        # Top border
        p.setPen(QPen(_alpha(GOLD, 20), 1))
        p.drawLine(0, 0, W, 0)

        p.setFont(_font(7, bold=False))
        x = 12

        # Connection dot
        p.setBrush(QBrush(_alpha(GREEN, 180)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(x + 4, H / 2), 2.5, 2.5)
        p.setPen(QPen(QColor(TEXT_DIM), 140))
        p.drawText(QRectF(x + 12, 0, 60, H), Qt.AlignmentFlag.AlignVCenter, "ONLINE")
        x += 80

        # Separator
        p.setPen(QPen(_alpha(GOLD, 15), 1))
        p.drawLine(x, 6, x, H - 6)
        x += 10

        # Model
        p.setPen(QPen(QColor(TEXT_MED), 130))
        p.drawText(QRectF(x, 0, 120, H), Qt.AlignmentFlag.AlignVCenter, f"🧠 {self._model[:20]}")
        x += 140

        # Separator
        p.setPen(QPen(_alpha(GOLD, 15), 1))
        p.drawLine(x, 6, x, H - 6)
        x += 10

        # CPU
        cpu_color = GREEN if self._cpu < 60 else ("#fbbf24" if self._cpu < 85 else RED)
        p.setPen(QPen(QColor(cpu_color), 130))
        p.drawText(QRectF(x, 0, 80, H), Qt.AlignmentFlag.AlignVCenter, f"CPU {self._cpu:.0f}%")
        x += 80

        # RAM
        ram_color = GREEN if self._ram < 60 else ("#fbbf24" if self._ram < 85 else RED)
        p.setPen(QPen(QColor(ram_color), 130))
        p.drawText(QRectF(x, 0, 80, H), Qt.AlignmentFlag.AlignVCenter, f"RAM {self._ram:.0f}%")
        x += 80

        # Separator
        p.setPen(QPen(_alpha(GOLD, 15), 1))
        p.drawLine(x, 6, x, H - 6)
        x += 10

        # Commands today
        p.setPen(QPen(QColor(TEXT_DIM), 120))
        p.drawText(QRectF(x, 0, 100, H), Qt.AlignmentFlag.AlignVCenter,
                   f"⚡ {self._commands_today} cmds hoje")
        x += 110

        # Uptime (right side)
        hrs = int(self._uptime // 3600)
        mins = int((self._uptime % 3600) // 60)
        p.setPen(QPen(QColor(TEXT_DIM), 100))
        p.drawText(QRectF(W - 120, 0, 110, H),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   f"⏱ {hrs:02d}:{mins:02d}")

        # Version (far right)
        p.setPen(QPen(_alpha(GOLD, 50), 1))
        p.drawText(QRectF(W - 240, 0, 110, H),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                   "v2.0 — ＜Elívea＞")


# ═══════════════════════════════════════════════════════════════════════════
# Micro-Interactions — Ripple, Confetti, Shake, Mouse Trail
# ═══════════════════════════════════════════════════════════════════════════
class MicroInteractions(QWidget):
    """Overlay for click ripples, confetti, error shake, and mouse trail."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._ripples: list[list] = []  # [x, y, radius, max_radius, alpha, color]
        self._confetti: list[list] = []  # [x, y, vx, vy, color, life, size]
        self._trail: list[list] = []  # [x, y, alpha, size]
        self._shake_offset = 0.0
        self._shake_target = 0.0
        self._t = 0.0
        self._last = time.time()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)  # 60fps

    def add_ripple(self, x, y, color=GOLD):
        """Add a click ripple at position."""
        self._ripples.append([x, y, 0.0, 80.0, 1.0, color])

    def add_confetti(self, x, y, count=20):
        """Add confetti explosion at position."""
        if len(self._confetti) > 100:  # prevent memory leak
            return
        colors = [GOLD, "#FFD700", "#FFA500", "#FFFFFF", "#4ade80", "#60a5fa"]
        for _ in range(count):
            ang = random.uniform(0, 2 * math.pi)
            spd = random.uniform(2, 8)
            self._confetti.append([
                x, y,
                spd * math.cos(ang), spd * math.sin(ang),
                random.choice(colors),
                1.0,  # life
                random.uniform(2, 5),
            ])

    def add_trail_point(self, x, y):
        """Add a mouse trail point."""
        self._trail.append([x, y, 0.6, random.uniform(1, 2.5)])
        if len(self._trail) > 15:
            self._trail.pop(0)

    def trigger_shake(self, intensity=5.0):
        """Trigger screen shake."""
        self._shake_target = intensity

    def _tick(self):
        now = time.time()
        dt = now - self._last
        self._t += now - self._last
        self._last = now
        # Update ripples
        self._ripples = [[x, y, r + 3, mr, a - 0.02, c]
                         for x, y, r, mr, a, c in self._ripples
                         if a - 0.02 > 0]
        # Update confetti
        new_confetti = []
        for c in self._confetti:
            c[0] += c[2]  # x += vx
            c[1] += c[3]  # y += vy
            c[3] += 0.08  # gravity (gentler)
            c[2] *= 0.97  # drag
            c[5] -= 0.012  # life
            if c[5] > 0:
                new_confetti.append(c)
        self._confetti = new_confetti
        # Update trail
        self._trail = [[x, y, a - 0.04, s] for x, y, a, s in self._trail if a - 0.04 > 0]
        # Shake decay
        if self._shake_target > 0:
            self._shake_offset = self._shake_target * math.sin(self._t * 40)
            self._shake_target *= 0.9
            if self._shake_target < 0.1:
                self._shake_target = 0
                self._shake_offset = 0
        self.update()

    def get_shake_offset(self) -> float:
        return self._shake_offset

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # ── Ripples ──
        for x, y, radius, max_r, alpha, color in self._ripples:
            a = int(alpha * 60)
            if a > 1:
                p.setPen(QPen(_alpha(color, a), 1.5))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(x, y), radius, radius)

        # ── Confetti ──
        for cx, cy, vx, vy, color, life, size in self._confetti:
            a = int(life * 255)
            if a > 5:
                p.setBrush(QBrush(_alpha(color, a)))
                p.setPen(Qt.PenStyle.NoPen)
                # Rotated rectangle
                p.save()
                p.translate(cx, cy)
                p.rotate(self._t * 200 + cx)
                p.drawRect(QRectF(-size / 2, -size / 2, size, size))
                p.restore()

        # ── Mouse Trail ──
        for tx, ty, ta, ts in self._trail:
            a = int(ta * 80)
            if a > 2:
                glow = QRadialGradient(tx, ty, ts * 4)
                glow.setColorAt(0, _alpha(GOLD, int(a * 0.4)))
                glow.setColorAt(1, _alpha(GOLD, 0))
                p.setBrush(QBrush(glow)); p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(tx, ty), ts * 4, ts * 4)
                p.setBrush(QBrush(_alpha(GOLD, a)))
                p.drawEllipse(QPointF(tx, ty), ts, ts)


# ═══════════════════════════════════════════════════════════════════════════
# Notification Toast — beautiful popup notifications
# ═══════════════════════════════════════════════════════════════════════════
class NotificationToast(QWidget):
    """Slide-in toast notification from the top-right corner."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(52)
        self.setVisible(False)
        self._text = ""
        self._icon = "💬"
        self._type = "info"  # info, success, error, warning
        self._opacity = 0.0
        self._fade_timer = QTimer(self)
        self._fade_timer.timeout.connect(self._fade_tick)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)

    def show_toast(self, text: str, toast_type: str = "info", duration_ms: int = 3000):
        self._text = text
        self._type = toast_type
        icons = {"info": "💬", "success": "✅", "error": "❌", "warning": "⚠️"}
        self._icon = icons.get(toast_type, "💬")
        self._opacity = 0.0
        self._fade_timer.start(20)
        self._hide_timer.start(duration_ms)
        # Position at top-right of parent
        if self.parent():
            pw = self.parent().width()
            self.setGeometry(pw - 320, 56, 310, 52)
        self.raise_()
        self.setVisible(True)
        self.update()

    def _fade_tick(self):
        self._opacity = min(1.0, self._opacity + 0.08)
        self.update()
        if self._opacity >= 1.0:
            self._fade_timer.stop()

    def _fade_out(self):
        self._fade_timer.start(20)
        # Reverse: fade out
        def _dec():
            self._opacity -= 0.06
            if self._opacity <= 0:
                self.setVisible(False)
                self._fade_timer.stop()
                return
            self.update()
        self._fade_timer.timeout.disconnect()
        self._fade_timer.timeout.connect(_dec)
        self._fade_timer.start(20)

    def paintEvent(self, _):
        if self._opacity <= 0:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        p.setOpacity(self._opacity)

        # Background
        type_colors = {"info": GOLD, "success": GREEN, "error": RED, "warning": "#fbbf24"}
        accent = type_colors.get(self._type, GOLD)

        bg = QLinearGradient(0, 0, 0, H)
        bg.setColorAt(0, _alpha("#141208", 240))
        bg.setColorAt(1, _alpha("#0c0a04", 240))
        p.setBrush(QBrush(bg))
        p.setPen(QPen(_alpha(accent, 50), 1))
        p.drawRoundedRect(QRectF(0, 0, W, H), 10, 10)

        # Left accent bar
        p.setBrush(QBrush(_alpha(accent, 120)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(0, 4, 3, H - 8), 1, 1)

        # Icon
        p.setFont(_font(12))
        p.setPen(QPen(QColor(accent), 200))
        p.drawText(QRectF(12, 0, 30, H), Qt.AlignmentFlag.AlignCenter, self._icon)

        # Text
        p.setFont(_font(8, bold=False))
        p.setPen(QPen(QColor(TEXT), 200))
        p.drawText(QRectF(48, 6, W - 60, H - 12),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   self._text[:60])

        p.setOpacity(1.0)


# ═══════════════════════════════════════════════════════════════════════════
# Ability Awakening — Sage → Elivea (anime Tensura 5:33-5:43)
# ═══════════════════════════════════════════════════════════════════════════

class AwakeningSFX:
    """Programmatic sound effects mimicking the anime awakening sequence.
    Uses winsound + ctypes for layered synthesis. No external files needed."""

    @staticmethod
    def _play_tone(freq: float, duration_ms: int, volume: int = 200,
                   fade_in: bool = True, fade_out: bool = True):
        """Play a sine wave tone with optional fade in/out."""
        try:
            import ctypes
            import ctypes.wintypes
            import struct
            import wave
            import tempfile
            import os

            sample_rate = 22050
            n_samples = int(sample_rate * duration_ms / 1000)
            max_amp = min(32767, volume)

            samples = []
            for i in range(n_samples):
                t = i / sample_rate
                val = int(max_amp * math.sin(2 * math.pi * freq * t))
                # Fade in
                if fade_in and i < n_samples * 0.1:
                    val = int(val * (i / (n_samples * 0.1)))
                # Fade out
                if fade_out and i > n_samples * 0.7:
                    fade = 1.0 - ((i - n_samples * 0.7) / (n_samples * 0.3))
                    val = int(val * max(0, fade))
                samples.append(struct.pack('<h', max(-32767, min(32767, val))))

            # Write WAV to temp file (unique name per call)
            uid = int(time.time() * 1000000) % 999999
            tmp = Path(tempfile.gettempdir()) / f'gs_tone_{uid}.wav'
            with wave.open(str(tmp), 'w') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(b''.join(samples))

            # Play with MCI
            alias = f'tone_{uid}'
            ctypes.windll.winmm.mciSendStringW(
                f'open "{tmp}" type mpegvideo alias {alias}', None, 0, 0)
            ctypes.windll.winmm.mciSendStringW(f'play {alias}', None, 0, 0)
            time.sleep(duration_ms / 1000 + 0.1)
            try:
                ctypes.windll.winmm.mciSendStringW(f'close {alias}', None, 0, 0)
            except Exception:
                pass
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
        except Exception:
            pass

    @staticmethod
    def _play_noise(duration_ms: int, volume: int = 150):
        """Play filtered white noise (rumble/whoosh)."""
        try:
            import struct
            import wave
            import tempfile
            import ctypes

            sample_rate = 22050
            n_samples = int(sample_rate * duration_ms / 1000)
            samples = []
            prev = 0.0
            for i in range(n_samples):
                t = i / sample_rate
                # Brown noise (low-pass filtered white noise)
                raw = random.uniform(-1, 1)
                val = (prev + (0.02 * raw)) / 1.02
                prev = val
                amp = min(32767, volume)
                sample = int(val * amp * 3)
                # Envelope
                progress = i / n_samples
                if progress < 0.1:
                    sample = int(sample * (progress / 0.1))
                elif progress > 0.6:
                    sample = int(sample * (1.0 - (progress - 0.6) / 0.4))
                samples.append(struct.pack('<h', max(-32767, min(32767, sample))))

            uid = int(time.time() * 1000000) % 999999
            tmp = Path(tempfile.gettempdir()) / f'gs_noise_{uid}.wav'
            with wave.open(str(tmp), 'w') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(b''.join(samples))

            alias = f'noise_{uid}'
            ctypes.windll.winmm.mciSendStringW(
                f'open "{tmp}" type mpegvideo alias {alias}', None, 0, 0)
            ctypes.windll.winmm.mciSendStringW(f'play {alias}', None, 0, 0)
            time.sleep(duration_ms / 1000 + 0.1)
            try:
                ctypes.windll.winmm.mciSendStringW(f'close {alias}', None, 0, 0)
            except Exception:
                pass
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
        except Exception:
            pass

    @staticmethod
    def _play_sweep(start_freq: float, end_freq: float, duration_ms: int, volume: int = 250):
        """Frequency sweep — rising or falling pitch."""
        try:
            import struct
            import wave
            import tempfile
            import ctypes

            sample_rate = 22050
            n_samples = int(sample_rate * duration_ms / 1000)
            samples = []
            for i in range(n_samples):
                t = i / n_samples
                freq = start_freq + (end_freq - start_freq) * t
                val = int(volume * math.sin(2 * math.pi * freq * i / sample_rate))
                # Envelope
                if t < 0.05:
                    val = int(val * (t / 0.05))
                elif t > 0.85:
                    val = int(val * (1.0 - (t - 0.85) / 0.15))
                samples.append(struct.pack('<h', max(-32767, min(32767, val))))

            uid = int(time.time() * 1000000) % 999999
            tmp = Path(tempfile.gettempdir()) / f'gs_sweep_{uid}.wav'
            with wave.open(str(tmp), 'w') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(b''.join(samples))

            alias = f'sweep_{uid}'
            ctypes.windll.winmm.mciSendStringW(
                f'open "{tmp}" type mpegvideo alias {alias}', None, 0, 0)
            ctypes.windll.winmm.mciSendStringW(f'play {alias}', None, 0, 0)
            time.sleep(duration_ms / 1000 + 0.1)
            try:
                ctypes.windll.winmm.mciSendStringW(f'close {alias}', None, 0, 0)
            except Exception:
                pass
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
        except Exception:
            pass

    @classmethod
    def play_awakening_sequence(cls):
        """6-second awakening SFX — perfectly synced with visual animation.
        Timeline:
          0-1.0s   PHASE 1: Deep rumble + sub-bass build (dark void)
          1.0-2.2s PHASE 2: Rising sweep + crystalline arpeggio (explosion)
          2.2-3.2s PHASE 3: MASSIVE EXPLOSION (energy burst)
          3.2-4.2s PHASE 4: Rune ignition staccato + crystal shatter
          4.2-5.5s PHASE 5: Final chord + sub-bass (revelation)
          5.5-6.0s PHASE 6: After-shock rumble fade"""
        def _seq():
            try:
                import winsound

                # PHASE 1 (0-1.8s): Deep energy build — dark void (slower)
                threading.Thread(target=cls._play_noise, args=(1200, 180), daemon=True).start()
                threading.Thread(target=cls._play_tone, args=(38, 1400, 140), daemon=True).start()
                threading.Thread(target=cls._play_tone, args=(76, 1100, 110), daemon=True).start()
                threading.Thread(target=cls._play_tone, args=(114, 850, 80), daemon=True).start()
                try:
                    winsound.Beep(45, 700)
                    time.sleep(0.15)
                    winsound.Beep(65, 600)
                    time.sleep(0.15)
                    winsound.Beep(85, 500)
                except Exception:
                    pass

                # PHASE 2 (1.8-3.5s): Rising sweep + crystalline (explosion) — slower
                time.sleep(1.0)
                threading.Thread(target=cls._play_sweep, args=(50, 1400, 1500, 300), daemon=True).start()
                threading.Thread(target=cls._play_tone, args=(165, 950, 120), daemon=True).start()
                time.sleep(0.3)
                for freq in [440, 554, 659, 880, 1047]:
                    threading.Thread(target=cls._play_tone,
                                    args=(freq, 400, 150, True, True), daemon=True).start()
                    try:
                        winsound.Beep(freq, 180)
                    except Exception:
                        pass
                    time.sleep(0.18)

                # PHASE 3 (3.5-5.5s): MASSIVE EXPLOSION — more time
                time.sleep(0.3)
                threading.Thread(target=cls._play_noise, args=(1000, 350), daemon=True).start()
                threading.Thread(target=cls._play_tone, args=(32, 1100, 300), daemon=True).start()
                threading.Thread(target=cls._play_tone, args=(64, 850, 260), daemon=True).start()
                threading.Thread(target=cls._play_tone, args=(128, 700, 230), daemon=True).start()
                threading.Thread(target=cls._play_tone, args=(256, 580, 180), daemon=True).start()
                threading.Thread(target=cls._play_sweep, args=(300, 30, 700, 260), daemon=True).start()
                try:
                    winsound.Beep(48, 450)
                    winsound.Beep(96, 400)
                    winsound.Beep(64, 420)
                except Exception:
                    pass

                # PHASE 4 (5.5-7.0s): Rune ignition + crystal shatter
                time.sleep(0.6)
                rune_freqs = [880, 1047, 1175, 1319, 1397, 1568, 1760, 2093]
                for i, freq in enumerate(rune_freqs):
                    vol = 120 + i * 18
                    threading.Thread(target=cls._play_tone,
                                    args=(freq, 250, vol, False, True), daemon=True).start()
                    try:
                        winsound.Beep(freq, 120)
                    except Exception:
                        pass
                    time.sleep(0.12)
                threading.Thread(target=cls._play_tone, args=(2093, 600, 160), daemon=True).start()
                threading.Thread(target=cls._play_tone, args=(2637, 500, 140), daemon=True).start()

                # PHASE 5 (7.0-7.8s): Final chord + sub-bass
                time.sleep(0.4)
                for freq in [110, 131, 165, 196, 262, 330, 392, 523]:
                    threading.Thread(target=cls._play_tone,
                                    args=(freq, 2200, 130, True, True), daemon=True).start()
                threading.Thread(target=cls._play_noise, args=(1400, 120), daemon=True).start()
                threading.Thread(target=cls._play_tone, args=(28, 1700, 200), daemon=True).start()
                try:
                    for freq in [110, 220, 330, 440]:
                        winsound.Beep(freq, 350)
                except Exception:
                    pass

                # PHASE 6 (7.8-8.0s): After-shock fade
                time.sleep(0.3)
                threading.Thread(target=cls._play_noise, args=(600, 100), daemon=True).start()
                threading.Thread(target=cls._play_tone, args=(25, 600, 120), daemon=True).start()

            except Exception:
                pass
        threading.Thread(target=_seq, daemon=True).start()

    @classmethod
    def play_energy_pulse(cls):
        """Quick energy pulse — used for state transitions."""
        threading.Thread(target=cls._play_tone, args=(440, 200, 100), daemon=True).start()

    @classmethod
    def play_rune_activate(cls):
        """Crystalline ping — rune activation."""
        threading.Thread(target=cls._play_tone, args=(1200, 150, 80), daemon=True).start()

    @classmethod
    def play_shockwave(cls):
        """Deep bass impact."""
        threading.Thread(target=cls._play_tone, args=(50, 400, 200), daemon=True).start()
        threading.Thread(target=cls._play_noise, args=(300, 120), daemon=True).start()


import threading  # needed for SFX threads


class AbilityAwakeningOverlay(QWidget):
    """Cinematic ability awakening — Sage evolves into Elívea.
    Inspired by Tensura anime 5:33-5:43.

    Phases:
      0 (0-1.8s):   Dark void — a small golden orb (Sage) pulses, energy builds
      1 (1.8-3.5s):  EXPLOSION — energy burst, 「賢者」 shatters
      2 (3.5-5.5s):  Magic circle forms, runes ignite one by one
      3 (5.5-7.0s):  「Elivea」 materializes with massive glow + shockwaves
      4 (7.0-8.0s):  Everything fades to main UI
    """
    done = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        if parent:
            self.setGeometry(parent.rect())
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        self._start_time = time.time()
        self._done_emitted = False
        self._sfx_played = [False, False, False, False, False]

        # Particles
        self._particles: list[list[float]] = []
        self._runes_data: list[list[float]] = []  # [angle, radius, alpha, char_idx]
        self._explosion_rings: list[list[float]] = []  # [radius, alpha, speed]

        # State
        self._orb_scale = 0.3
        self._orb_glow = 0.0
        self._flash_alpha = 0.0
        self._sage_text_alpha = 0.0  # 「賢者」
        self._great_text_alpha = 0.0  # 「Elivea」
        self._circle_alpha = 0.0
        self._rune_rot = 0.0
        self._energy_intensity = 0.0
        self._shockwave_r = 0.0
        self._shockwave_alpha = 0.0

        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(1.0)
        self.setGraphicsEffect(self._effect)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)  # 60 fps

    def _tick(self):
        t = time.time() - self._start_time
        self._rune_rot = (self._rune_rot + 0.8) % 360

        # Play SFX at phase transitions
        if t > 0.0 and not self._sfx_played[0]:
            self._sfx_played[0] = True
            threading.Thread(target=AwakeningSFX.play_awakening_sequence, daemon=True).start()

        # Phase 0 (0-1.8s): Dark void — small Sage orb pulses, energy builds
        if t < 1.8:
            pulse = 1.0 + 0.15 * math.sin(t * 8)
            self._orb_scale = (0.3 + 0.5 * (t / 1.8)) * pulse
            self._orb_glow = 0.3 + 0.7 * (t / 1.8)
            # Spawn subtle particles as energy builds
            if len(self._particles) < 20 and random.random() < 0.3:
                ang = random.uniform(0, 2 * math.pi)
                self._particles.append([self.width() / 2, self.height() / 2,
                                        math.cos(ang) * 1.5, math.sin(ang) * 1.5, 1.0, 1.5])

        # Phase 1 (1.8-3.5s): EXPLOSION — energy burst
        elif t < 3.5:
            p = (t - 1.8) / 1.7
            self._flash_alpha = max(0.0, 1.0 - p * 1.5)
            self._orb_scale = 0.7 + 2.5 * min(1.0, p * 2.5)
            self._orb_glow = 1.0 + 0.5 * min(1.0, p * 2)
            self._energy_intensity = min(1.0, p * 2)
            self._sage_text_alpha = min(1.0, p * 1.5) * max(0.0, 1.0 - p * 1.6)
            # Spawn explosion rings
            if len(self._explosion_rings) < 12 and random.random() < 0.4:
                self._explosion_rings.append([10.0, 1.0, random.uniform(250, 600)])
            # Spawn burst particles
            if len(self._particles) < 80 and random.random() < 0.7:
                cx, cy = self.width() / 2, self.height() / 2
                ang = random.uniform(0, 2 * math.pi)
                spd = random.uniform(2, 10)
                self._particles.append([cx, cy,
                                        math.cos(ang) * spd, math.sin(ang) * spd,
                                        1.0, random.uniform(1.5, 4.0)])

        # Phase 2 (3.5-5.5s): Circle forms, runes ignite one by one
        elif t < 5.5:
            p = (t - 3.5) / 2.0
            self._circle_alpha = min(1.0, p * 2)
            self._sage_text_alpha = max(0.0, self._sage_text_alpha - 0.012)
            self._orb_scale = max(1.0, self._orb_scale - 0.012)
            self._energy_intensity = 0.5 + 0.5 * math.sin(t * 3)
            # Spawn runes progressively
            if len(self._runes_data) < 28 and random.random() < 0.2:
                ang = random.uniform(0, 360)
                r = random.uniform(0.6, 1.0)
                self._runes_data.append([ang, r, 0.0, random.randint(0, len(RUNES) - 1)])
            # Slow rings continue
            if len(self._explosion_rings) < 4 and random.random() < 0.1:
                self._explosion_rings.append([50.0, 0.6, random.uniform(80, 200)])
            # Particles orbiting the circle
            if len(self._particles) < 40 and random.random() < 0.3:
                cx, cy = self.width() / 2, self.height() / 2
                ang = random.uniform(0, 2 * math.pi)
                r_px = min(self.width(), self.height()) * 0.22
                px = cx + r_px * math.cos(ang)
                py = cy + r_px * math.sin(ang)
                self._particles.append([px, py,
                                        math.cos(ang + math.pi / 2) * 1.5,
                                        math.sin(ang + math.pi / 2) * 1.5,
                                        0.8, random.uniform(1.0, 2.5)])

        # Phase 3 (5.5-7.0s): 「Elivea」 materializes — dramatic reveal
        elif t < 7.0:
            p = (t - 5.5) / 1.5
            self._great_text_alpha = min(1.0, p * 1.5)
            self._circle_alpha = 1.0
            self._energy_intensity = 1.0
            self._orb_scale = 1.0 + 0.1 * math.sin(t * 6)
            self._orb_glow = 1.2 + 0.3 * math.sin(t * 4)
            # Final shockwave
            if not self._sfx_played[3]:
                self._sfx_played[3] = True
                self._shockwave_r = 0.0
                self._shockwave_alpha = 1.0
            # Energy burst particles
            if len(self._particles) < 60 and random.random() < 0.4:
                cx, cy = self.width() / 2, self.height() / 2
                ang = random.uniform(0, 2 * math.pi)
                spd = random.uniform(1, 5)
                self._particles.append([cx, cy,
                                        math.cos(ang) * spd, math.sin(ang) * spd,
                                        0.9, random.uniform(1.0, 3.0)])
            # Second shockwave
            if p > 0.5 and not self._sfx_played[4]:
                self._sfx_played[4] = True
                self._shockwave_r = 0.0
                self._shockwave_alpha = 0.7

        # Phase 4 (7.0-8.0s): Fade out + hide
        else:
            p = min(1.0, (t - 7.0) / 1.0)
            self._great_text_alpha = max(0.0, 1.0 - p)
            self._circle_alpha = max(0.0, 1.0 - p)
            self._energy_intensity = max(0.0, 1.0 - p)
            self._orb_glow = max(0.0, 1.2 - p * 1.5)
            self._flash_alpha = 0.0
            # Fade out the widget itself
            self._effect.setOpacity(max(0.0, 1.0 - p))
            if t > 7.8 and not self._done_emitted:
                self._done_emitted = True
                self._timer.stop()
                self.done.emit()
                self.hide()
                self.deleteLater()
                return

        # Update explosion rings
        new_rings = []
        for ring in self._explosion_rings:
            ring[0] += ring[2] * 0.016  # radius += speed * dt
            ring[1] -= 0.015
            if ring[1] > 0:
                new_rings.append(ring)
        self._explosion_rings = new_rings

        # Update runes
        for rune in self._runes_data:
            rune[2] = min(1.0, rune[2] + 0.03)

        # Update particles
        if len(self._particles) < 80 and random.random() < self._energy_intensity * 0.8:
            cx, cy = self.width() / 2, self.height() / 2
            ang = random.uniform(0, 2 * math.pi)
            dist = random.uniform(20, min(self.width(), self.height()) * 0.5)
            px = cx + dist * math.cos(ang)
            py = cy + dist * math.sin(ang)
            vx = math.cos(ang) * random.uniform(1, 4) * self._energy_intensity
            vy = math.sin(ang) * random.uniform(1, 4) * self._energy_intensity
            self._particles.append([px, py, vx, vy, 1.0, random.uniform(1.0, 3.0)])

        alive = []
        for part in self._particles:
            part[0] += part[2]
            part[1] += part[3]
            part[4] -= 0.015
            if part[4] > 0:
                alive.append(part)
        self._particles = alive

        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        cx, cy = W / 2, H / 2
        R = min(W, H) * 0.22
        t = time.time() - self._start_time

        # ── Background ──
        p.fillRect(self.rect(), QColor(0, 0, 0))

        # ── Starfield ──
        rng = random.Random(42)
        for _ in range(40):
            sx, sy = rng.randint(0, W), rng.randint(0, H)
            flicker = int(50 + 40 * math.sin(t * 3 + sx * 0.07))
            p.setPen(QPen(_alpha(GOLD_DIM, flicker), 1))
            p.drawPoint(sx, sy)

        # ── Explosion rings ──
        for ring in self._explosion_rings:
            r, alpha, _ = ring
            if r > 4:
                a = int(220 * alpha * self._energy_intensity)
                p.setPen(QPen(_alpha(GOLD, a), 2.0))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # ── Atmospheric halo ──
        if self._energy_intensity > 0.01:
            halo_r = R * 3.0 * self._energy_intensity
            halo = QRadialGradient(cx, cy, halo_r)
            a = int(40 * self._energy_intensity)
            halo.setColorAt(0.0, _alpha(GOLD, a))
            halo.setColorAt(0.4, _alpha(GOLD, int(a * 0.3)))
            halo.setColorAt(1.0, _alpha(GOLD, 0))
            p.setBrush(QBrush(halo))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx - halo_r, cy - halo_r, halo_r * 2, halo_r * 2))

        # ── Magic Circle (phase 2+) ──
        if self._circle_alpha > 0.01:
            ca = int(200 * self._circle_alpha)
            # Outer ring
            p.setPen(QPen(_alpha(GOLD, ca), 2.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - R, cy - R, R * 2, R * 2))
            # Inner ring
            p.setPen(QPen(_alpha(GOLD, int(ca * 0.5)), 1.0))
            p.drawEllipse(QRectF(cx - R * 0.88, cy - R * 0.88, R * 1.76, R * 1.76))
            # Tick marks
            p.setPen(QPen(_alpha(GOLD, int(ca * 0.6)), 1))
            for i in range(36):
                ang = math.radians(i * 10)
                big = i % 4 == 0
                r1 = R * 1.0
                r2 = R * (0.93 if big else 0.96)
                p.drawLine(
                    QPointF(cx + r1 * math.cos(ang), cy + r1 * math.sin(ang)),
                    QPointF(cx + r2 * math.cos(ang), cy + r2 * math.sin(ang)),
                )
            # Rotating runes
            rune_r = R * 0.80
            p.save()
            p.translate(cx, cy)
            p.rotate(self._rune_rot)
            rf = QFont("Microsoft YaHei UI", 9, QFont.Weight.Bold)
            for i, rune_char in enumerate(RUNES):
                ang = i * 360 / len(RUNES)
                p.save()
                p.rotate(ang)
                p.translate(0, -rune_r)
                p.rotate(180)
                rune_a = int(ca * (0.5 + 0.5 * math.sin(t * 2.0 + i * 0.5)))
                p.setPen(QPen(_alpha(GOLD_BRIGHT, rune_a)))
                p.setFont(rf)
                p.drawText(QRectF(-10, -8, 20, 16), Qt.AlignmentFlag.AlignCenter, rune_char)
                p.restore()
            p.restore()
            # Central cross
            cross_a = int(ca * 0.7)
            p.setPen(QPen(_alpha(GOLD, cross_a), 2.0))
            p.drawLine(QPointF(cx - R * 0.4, cy), QPointF(cx + R * 0.4, cy))
            p.drawLine(QPointF(cx, cy - R * 0.4), QPointF(cx, cy + R * 0.4))
            # Diagonal cross
            p.setPen(QPen(_alpha(GOLD, int(cross_a * 0.5)), 1.0))
            d = R * 0.28
            p.drawLine(QPointF(cx - d, cy - d), QPointF(cx + d, cy + d))
            p.drawLine(QPointF(cx - d, cy + d), QPointF(cx + d, cy - d))
            # Hexagram
            hex_r = R * 0.55
            p.save()
            p.translate(cx, cy)
            p.rotate(t * 15)
            p.setPen(QPen(_alpha(GOLD, int(ca * 0.4)), 1.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            for offset in (0, 180):
                pts = []
                for k in range(3):
                    a = math.radians(k * 120 + offset - 90)
                    pts.append(QPointF(hex_r * math.cos(a), hex_r * math.sin(a)))
                path = QPainterPath()
                path.moveTo(pts[0])
                path.lineTo(pts[1])
                path.lineTo(pts[2])
                path.closeSubpath()
                p.drawPath(path)
            p.restore()

        # ── Shockwave ──
        if self._shockwave_alpha > 0.01:
            sr = R * (1.0 + self._shockwave_r)
            sa = int(255 * self._shockwave_alpha)
            p.setPen(QPen(_alpha(GOLD_BRIGHT, sa), 3.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - sr, cy - sr, sr * 2, sr * 2))
            self._shockwave_r += 0.08
            self._shockwave_alpha -= 0.025

        # ── Sage orb (center) ──
        if self._orb_glow > 0.01:
            orb_r = R * 0.20 * self._orb_scale
            # Glow
            glow_r = orb_r * 2.0
            glow = QRadialGradient(cx, cy, glow_r)
            ga = int(120 * self._orb_glow)
            glow.setColorAt(0.0, _alpha(GOLD_BRIGHT, ga))
            glow.setColorAt(0.5, _alpha(GOLD, int(ga * 0.3)))
            glow.setColorAt(1.0, _alpha(GOLD, 0))
            p.setBrush(QBrush(glow))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2))
            # Core
            core = QRadialGradient(cx, cy, orb_r)
            core.setColorAt(0.0, _alpha(GOLD_BRIGHT, int(255 * self._orb_glow)))
            core.setColorAt(0.6, _alpha(GOLD, int(180 * self._orb_glow)))
            core.setColorAt(1.0, _alpha(GOLD, 0))
            p.setBrush(QBrush(core))
            p.drawEllipse(QRectF(cx - orb_r, cy - orb_r, orb_r * 2, orb_r * 2))
            # White hot center
            core_r = orb_r * 0.25
            p.setBrush(QBrush(_alpha(GOLD_BRIGHT, int(240 * min(1.0, self._orb_glow)))))
            p.drawEllipse(QRectF(cx - core_r, cy - core_r, core_r * 2, core_r * 2))

        # ── Particles ──
        for part in self._particles:
            px, py, _, _, life, size = part
            a = int(200 * life * self._energy_intensity)
            if a > 5:
                p.setPen(QPen(_alpha(GOLD, a), size))
                p.drawPoint(int(px), int(py))

        # ── 「賢者」 shattering text (phase 1) ──
        if self._sage_text_alpha > 0.01:
            ta = int(255 * self._sage_text_alpha)
            p.setPen(QPen(_alpha(GOLD_BRIGHT, ta), 1))
            p.setFont(QFont("Microsoft YaHei UI", 40, QFont.Weight.Bold))
            p.drawText(QRectF(0, cy - 80, W, 80), Qt.AlignmentFlag.AlignCenter, "賢者")

        # ── 「Elivea」 reveal text (phase 3) ──
        if self._great_text_alpha > 0.01:
            ga = int(255 * self._great_text_alpha)
            # Outer glow
            glow_size = int(10 * self._great_text_alpha)
            for offset_x in range(-glow_size, glow_size + 1, 2):
                for offset_y in range(-glow_size, glow_size + 1, 2):
                    dist = math.sqrt(offset_x**2 + offset_y**2)
                    if dist <= glow_size:
                        ga_dim = int(ga * 0.15 * (1 - dist / glow_size))
                        if ga_dim > 5:
                            p.setPen(QPen(_alpha(GOLD, ga_dim), 1))
                            p.setFont(QFont("Microsoft YaHei UI", 48, QFont.Weight.Bold))
                            p.drawText(QRectF(offset_x, cy - 60 + offset_y, W, 100),
                                       Qt.AlignmentFlag.AlignCenter, "＜Elívea＞")
            # Main text
            p.setPen(QPen(_alpha(GOLD_BRIGHT, ga), 1))
            p.setFont(QFont("Microsoft YaHei UI", 48, QFont.Weight.Bold))
            p.drawText(QRectF(0, cy - 60, W, 100), Qt.AlignmentFlag.AlignCenter, "＜Elívea＞")
            # Subtitle
            p.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
            p.setPen(QPen(_alpha(GOLD, int(ga * 0.8)), 1))
            p.drawText(QRectF(0, cy + 50, W, 24), Qt.AlignmentFlag.AlignCenter,
                       "G R E A T   S A G E   —   R A P H A E L   C L A S S")

        # ── Flash effect ──
        if self._flash_alpha > 0.01:
            flash_r = min(W, H) * 0.9 * self._flash_alpha
            flash = QRadialGradient(cx, cy, flash_r)
            fa = int(255 * self._flash_alpha)
            flash.setColorAt(0.0, _alpha(GOLD_BRIGHT, fa))
            flash.setColorAt(0.3, _alpha(GOLD, int(fa * 0.5)))
            flash.setColorAt(1.0, _alpha(GOLD, 0))
            p.setBrush(QBrush(flash))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx - flash_r, cy - flash_r, flash_r * 2, flash_r * 2))

    def mousePressEvent(self, _):
        # Click to skip
        if self._done_emitted:
            return
        self._done_emitted = True
        self._timer.stop()
        self.done.emit()
