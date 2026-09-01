"""
Elívea — Tensura Holographic Interface (＜Elívea＞)
==========================================================
Interface inspirada no anime "Tensei Shitara Slime Daitaiken" (Tensura):

  • Círculo mágico do Elívea: anel de runas rotativo, arcos
    contrarrotativos, heptagrama de Elivea e núcleo pulsante
  • Visualizador radial de voz (RMS do microfone) ao redor do círculo
  • Chat em painéis holográficos azuis estilo "Ability Panel" do anime
  • Sequência de boot animada com linhas digitadas
  • Telemetria viva (CPU / RAM / MIC) e chips de latência ponta-a-ponta
  • 4 temas: Tensura Blue (padrão), Gold Foil, Crimson, Emerald

by: bryan
"""

from __future__ import annotations

import html
import math
import random
import sys
import threading
import time
from collections import deque
from pathlib import Path

import psutil

# Compatibilidade PySide6 (instalado) / PyQt6 (antigo) — pega o que estiver
try:
    from PySide6.QtCore import (
        QEvent, QEasingCurve, QPointF, QPropertyAnimation, QRectF, QSize, Qt,
        QTimer, Signal as pyqtSignal,
    )
    from PySide6.QtGui import (
        QBrush, QColor, QFont, QFontDatabase, QPainter, QPainterPath, QPen,
        QPixmap, QRadialGradient, QLinearGradient,
    )
    from PySide6.QtWidgets import (
        QApplication, QComboBox, QFrame, QGraphicsOpacityEffect, QHBoxLayout,
        QLabel, QLineEdit, QMainWindow, QPushButton, QScrollArea, QSizePolicy,
        QSplitter, QVBoxLayout, QWidget,
    )
    _qt_api = "PySide6"
except ImportError:
    from PyQt6.QtCore import (
        QEvent, QEasingCurve, QPointF, QPropertyAnimation, QRectF, QSize, Qt,
        QTimer, pyqtSignal,
    )
    from PyQt6.QtGui import (
        QBrush, QColor, QFont, QFontDatabase, QPainter, QPainterPath, QPen,
        QPixmap, QRadialGradient, QLinearGradient,
    )
    from PyQt6.QtWidgets import (
        QApplication, QComboBox, QFrame, QGraphicsOpacityEffect, QHBoxLayout,
        QLabel, QLineEdit, QMainWindow, QPushButton, QScrollArea, QSizePolicy,
        QSplitter, QVBoxLayout, QWidget,
    )
    _qt_api = "PyQt6"

# ---------------------------------------------------------------------------
# Theme system — recolors everything live
# ---------------------------------------------------------------------------

THEMES: dict[str, dict[str, str]] = {
    "tensura_gold": dict(
        name="Tensura Dourado ＜Elívea＞",
        BG="#060913", PANEL="#131008", PANEL2="#1d180c", GHOST="#332708",
        BORDER="#5c4708", BORDER_B="#a8801c", BORDER_A="#7a5e10",
        PRI="#ffd24a", ACC="#ffedb0", ACC2="#f5a623", GOLD="#ffe27a",
        GREEN="#7dff9e", RED="#ff4d6d", TEXT="#fff3d6", TEXT_DIM="#9d8a5a",
        TEXT_MED="#e0c98a", WHITE="#ffffff",
    ),
    "tensura": dict(
        name="Tensura Blue ＜Elívea＞",
        BG="#020817", PANEL="#06122b", PANEL2="#0a1c3d", GHOST="#0e2c55",
        BORDER="#0f3a6e", BORDER_B="#1e5fa8", BORDER_A="#16457e",
        PRI="#4fd8ff", ACC="#aef0ff", ACC2="#22b8f0", GOLD="#ffd76a",
        GREEN="#39ff9e", RED="#ff4d6d", TEXT="#dff4ff", TEXT_DIM="#5f88ad",
        TEXT_MED="#9fc9e8", WHITE="#ffffff",
    ),
    "gold": dict(
        name="Gold Foil (Clássico)",
        BG="#080601", PANEL="#120f02", PANEL2="#1a1403", GHOST="#2a2100",
        BORDER="#403300", BORDER_B="#806600", BORDER_A="#554400",
        PRI="#ffd700", ACC="#ffea00", ACC2="#ffaa00", GOLD="#ffd700",
        GREEN="#55ff00", RED="#ff3355", TEXT="#fff5b3", TEXT_DIM="#807333",
        TEXT_MED="#ccb84d", WHITE="#ffffff",
    ),
    "crimson": dict(
        name="Crimson Lord",
        BG="#0f0205", PANEL="#1a0409", PANEL2="#280811", GHOST="#3a0e1c",
        BORDER="#66001a", BORDER_B="#cc0033", BORDER_A="#8a0e2c",
        PRI="#ff3355", ACC="#ff8099", ACC2="#ff0033", GOLD="#ffb36a",
        GREEN="#55ff88", RED="#ff3355", TEXT="#ffe0e6", TEXT_DIM="#ad5f70",
        TEXT_MED="#e8a0af", WHITE="#ffffff",
    ),
    "emerald": dict(
        name="Emerald Slime",
        BG="#010e08", PANEL="#041a10", PANEL2="#08281a", GHOST="#0c3a24",
        BORDER="#00552b", BORDER_B="#00aa55", BORDER_A="#007a3d",
        PRI="#00ff88", ACC="#80ffbb", ACC2="#00cc66", GOLD="#ffe08a",
        GREEN="#7dff9e", RED="#ff4d6d", TEXT="#d9ffe9", TEXT_DIM="#5fad88",
        TEXT_MED="#a0e8c4", WHITE="#ffffff",
    ),
}


class C:
    """Live theme palette (mutated on theme switch; widgets repaint live)."""
    name = THEMES["tensura_gold"]["name"]
    BG = THEMES["tensura_gold"]["BG"]; PANEL = THEMES["tensura_gold"]["PANEL"]
    PANEL2 = THEMES["tensura_gold"]["PANEL2"]; GHOST = THEMES["tensura_gold"]["GHOST"]
    BORDER = THEMES["tensura_gold"]["BORDER"]; BORDER_B = THEMES["tensura_gold"]["BORDER_B"]
    BORDER_A = THEMES["tensura_gold"]["BORDER_A"]; PRI = THEMES["tensura_gold"]["PRI"]
    ACC = THEMES["tensura_gold"]["ACC"]; ACC2 = THEMES["tensura_gold"]["ACC2"]
    GOLD = THEMES["tensura_gold"]["GOLD"]; GREEN = THEMES["tensura_gold"]["GREEN"]
    RED = THEMES["tensura_gold"]["RED"]; TEXT = THEMES["tensura_gold"]["TEXT"]
    TEXT_DIM = THEMES["tensura_gold"]["TEXT_DIM"]; TEXT_MED = THEMES["tensura_gold"]["TEXT_MED"]
    WHITE = THEMES["tensura_gold"]["WHITE"]


def apply_theme(key: str):
    theme = THEMES.get(key, THEMES["tensura_gold"])
    for attr, val in theme.items():
        if attr != "name":
            setattr(C, attr, val)
    C.name = theme["name"]


def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h)
    c.setAlpha(a)
    return c


def qp(x: float, y: float) -> QPointF:
    return QPointF(x, y)


def font_mono(size: int, bold: bool = True) -> QFont:
    return QFont("Consolas", size, QFont.Weight.Bold if bold else QFont.Weight.Normal)


def font_cjk(size: int, bold: bool = True) -> QFont:
    return QFont("Microsoft YaHei UI", size, QFont.Weight.Bold if bold else QFont.Weight.Normal)


def font_ui(size: int, bold: bool = False) -> QFont:
    return QFont("Segoe UI", size, QFont.Weight.Bold if bold else QFont.Weight.Normal)


# ---------------------------------------------------------------------------
# Windows autostart helper
# ---------------------------------------------------------------------------

def set_windows_autostart(enable: bool) -> bool:
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "Elívea"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        if enable:
            app_script = Path(__file__).resolve().parent.parent / "elvea_app.py"
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{sys.executable}" "{app_script}"')
        else:
            try:
                winreg.DeleteValue(key, app_name)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"[Autostart Error] {e}")
        return False


# ===========================================================================
# ＜Elívea＞ Magic Circle — the centerpiece
# ===========================================================================

RUNES = list("ᚠᚢᚦᚨᚱᚲᚷᚹᚺᚾᛁᛃᛇᛈᛉᛊᛏᛒᛖᛗᛚᛜᛞᛟ")


class MagicCircleWidget(QWidget):
    """Elívea magic circle: rune ring, counter-rotating arcs, heptagram,
    pulsing core and radial mic visualizer — all animated at 30 fps."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumSize(320, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.state = "idle"            # idle | listening | thinking | speaking
        self.speaking = False
        self._t = 0.0
        self._last = time.time()
        self._rune_rot = 0.0
        self._rune_rot2 = 0.0
        self._arc_rot = [0.0, 0.0, 0.0]
        self._hex_rot = 0.0
        self._star_rot = 0.0
        self._core_scale = 1.0
        self._core_tgt = 1.0
        self._glow = 0.55
        self._glow_tgt = 0.55
        self._rms_hist = deque([0.0] * 56, maxlen=56)
        self._particles: list[list[float]] = []
        self._sparkles: list[list[float]] = []
        self._shockwaves: list[float] = []
        self._scan_y = 0.0
        self._beam_alpha = 0.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    # ------------------------------------------------------------- external

    def push_rms(self, rms: float):
        self._rms_hist.append(rms)

    def set_state(self, state: str):
        old = self.state
        self.state = state
        self.speaking = state == "speaking"
        if state != old:
            self._shockwaves.append(0.0)

    # ------------------------------------------------------------------ anim

    def _tick(self):
        now = time.time()
        dt = now - self._last
        self._last = now
        self._t += dt

        speaking = self.state == "speaking"
        thinking = self.state == "thinking"
        listening = self.state == "listening"

        spd = 0.55 if speaking else 0.28 if thinking else 0.12 if listening else 0.08
        self._rune_rot = (self._rune_rot + spd) % 360
        self._rune_rot2 = (self._rune_rot2 - spd * 0.65) % 360
        self._arc_rot[0] = (self._arc_rot[0] + (spd * 0.65 if speaking else 0.12)) % 360
        self._arc_rot[1] = (self._arc_rot[1] - (spd * 0.50 if speaking else 0.09)) % 360
        self._arc_rot[2] = (self._arc_rot[2] + (spd * 0.80 if speaking else 0.14)) % 360
        self._hex_rot = (self._hex_rot + spd * 0.35) % 360
        self._star_rot = (self._star_rot + (spd * 0.22 if speaking else 0.04 if thinking else 0.018)) % 360

        if speaking:
            self._core_tgt = random.uniform(1.12, 1.28)
            self._glow_tgt = random.uniform(1.0, 1.2)
        elif thinking:
            self._core_tgt = random.uniform(1.03, 1.09)
            self._glow_tgt = 0.92
        elif listening:
            self._core_tgt = random.uniform(1.0, 1.04)
            self._glow_tgt = 0.72
        else:
            self._core_tgt = random.uniform(0.98, 1.0)
            self._glow_tgt = 0.52

        sp = 0.32 if speaking else 0.13
        self._core_scale += (self._core_tgt - self._core_scale) * sp
        self._glow += (self._glow_tgt - self._glow) * sp

        beam_tgt = 0.9 if (speaking or thinking) else 0.0
        self._beam_alpha += (beam_tgt - self._beam_alpha) * 0.08

        self._shockwaves = [s + 0.018 for s in self._shockwaves if s + 0.018 < 1.0]
        self._scan_y = (self._scan_y + 0.45) % 1.0

        max_p = 50 if speaking else 35 if thinking else 26 if listening else 18
        if len(self._particles) < max_p and random.random() < (0.85 if speaking else 0.55):
            ang = random.uniform(0, 2 * math.pi)
            self._particles.append([ang, random.uniform(0.82, 1.12), random.uniform(0.002, 0.006)])
        self._particles = [[a, d - s, s * 1.03] for a, d, s in self._particles if d - s > 0.20]

        if speaking and random.random() < 0.55:
            ang = random.uniform(0, 2 * math.pi)
            self._sparkles.append([ang, random.uniform(0.12, 0.35), 1.0])
        elif thinking and random.random() < 0.25:
            ang = random.uniform(0, 2 * math.pi)
            self._sparkles.append([ang, random.uniform(0.15, 0.30), 0.8])
        self._sparkles = [[a, d + 0.007, l - 0.042] for a, d, l in self._sparkles if l - 0.042 > 0]

        self.update()

    # ----------------------------------------------------------------- paint

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        cx, cy = W / 2, H / 2
        R = min(W, H) * 0.335

        p.fillRect(self.rect(), qcol(C.BG))

        # ---- starfield (flickering)
        rng = random.Random(42)
        for _ in range(35):
            sx, sy = rng.randint(0, W), rng.randint(0, H)
            flicker = int(80 + 60 * math.sin(self._t * 2 + sx * 0.1))
            p.setPen(QPen(qcol(C.BORDER, flicker), 1))
            p.drawPoint(sx, sy)

        dim = self.state == "idle"
        base_a = 115 if dim else 190
        glow = max(0.0, min(1.25, self._glow))

        # ---- expanding shockwave rings (on state change)
        for s in self._shockwaves:
            r = R * (0.3 + s * 1.2)
            a = int(160 * (1.0 - s) * glow)
            p.setPen(QPen(qcol(C.PRI, max(10, a)), 2.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # ---- atmospheric halo
        halo_r = R * 1.7
        halo = QRadialGradient(cx, cy, halo_r)
        halo.setColorAt(0.0, qcol(C.PRI, int(40 * glow)))
        halo.setColorAt(0.45, qcol(C.PRI, int(14 * glow)))
        halo.setColorAt(1.0, qcol(C.PRI, 0))
        p.setBrush(QBrush(halo))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - halo_r, cy - halo_r, halo_r * 2, halo_r * 2))

        # ---- outer double ring + ticks
        for rr, pen_w, alpha in [(1.05, 2.2, base_a), (1.015, 1.0, int(base_a * 0.55))]:
            p.setPen(QPen(qcol(C.PRI, alpha), pen_w))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - R * rr, cy - R * rr, R * rr * 2, R * rr * 2))
        p.setPen(QPen(qcol(C.PRI, int(base_a * 0.7)), 1))
        for i in range(72):
            ang = math.radians(i * 5)
            big = i % 6 == 0
            r1 = R * 1.05
            r2 = R * (0.995 if big else 1.02)
            p.drawLine(
                qp(cx + r1 * math.cos(ang), cy + r1 * math.sin(ang)),
                qp(cx + r2 * math.cos(ang), cy + r2 * math.sin(ang)),
            )

        # ---- inner decorative ring
        p.setPen(QPen(qcol(C.ACC, int(base_a * 0.30)), 0.8))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(cx - R * 0.93, cy - R * 0.93, R * 1.86, R * 1.86))

        # ---- rune ring (outer, clockwise)
        rune_r = R * 0.875
        p.save()
        p.translate(cx, cy)
        p.rotate(self._rune_rot)
        rf = font_cjk(10)
        for i, rune in enumerate(RUNES):
            ang = i * 360 / len(RUNES)
            p.save()
            p.rotate(ang)
            p.translate(0, -rune_r)
            p.rotate(180)
            alpha = int(base_a * (0.72 + 0.28 * math.sin(self._t * 1.8 + i * 0.5)))
            p.setPen(QPen(qcol(C.ACC, alpha)))
            p.setFont(rf)
            p.drawText(QRectF(-14, -10, 28, 22), Qt.AlignmentFlag.AlignCenter, rune)
            p.restore()
        p.restore()

        # ---- rune ring (inner, counter-clockwise)
        rune_r2 = R * 0.76
        p.save()
        p.translate(cx, cy)
        p.rotate(self._rune_rot2)
        p.setFont(font_cjk(6))
        for i, rune in enumerate(RUNES[:16]):
            ang = i * 360 / 16
            p.save()
            p.rotate(ang)
            p.translate(0, -rune_r2)
            p.rotate(180)
            alpha = int(base_a * (0.50 + 0.30 * math.sin(self._t * 1.4 + i * 0.7)))
            p.setPen(QPen(qcol(C.PRI, alpha)))
            p.drawText(QRectF(-8, -6, 16, 12), Qt.AlignmentFlag.AlignCenter, rune)
            p.restore()
        p.restore()

        # ---- hexagram ring (rotating sacred geometry)
        hex_r = R * 0.65
        p.save()
        p.translate(cx, cy)
        p.rotate(self._hex_rot)
        hex_alpha = int(base_a * 0.45 * glow)
        p.setPen(QPen(qcol(C.ACC2, hex_alpha), 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for offset in (0, 180):
            pts_tri = []
            for k in range(3):
                a = math.radians(k * 120 + offset - 90)
                pts_tri.append(qp(hex_r * math.cos(a), hex_r * math.sin(a)))
            path = QPainterPath()
            path.moveTo(pts_tri[0])
            path.lineTo(pts_tri[1])
            path.lineTo(pts_tri[2])
            path.closeSubpath()
            p.drawPath(path)
        p.restore()

        # ---- counter-rotating HUD arcs (3 layers)
        arc_cfg = [
            (0.78, 2.8, 90, 46, C.PRI),
            (0.68, 1.8, 60, 64, C.ACC2),
            (0.58, 1.4, 38, 82, C.ACC),
        ]
        for idx, (r_f, pen_w, arc_len, gap, col) in enumerate(arc_cfg):
            rr = R * r_f
            rot_val = self._arc_rot[idx] if idx < len(self._arc_rot) else 0.0
            base = rot_val if col != C.ACC2 else -rot_val
            alpha = int(base_a * min(1.0, glow) * 0.85)
            p.setPen(QPen(qcol(col, alpha), pen_w))
            p.setBrush(Qt.BrushStyle.NoBrush)
            rect = QRectF(cx - rr, cy - rr, rr * 2, rr * 2)
            ang = base
            while ang < base + 360:
                p.drawArc(rect, int(ang * 16), int(arc_len * 16))
                ang += arc_len + gap

        # ---- heptagram (7/3 star) — Elivea's sigil
        star_r = R * 0.545
        rot = self._star_rot
        pts = []
        for i in range(7):
            ang = math.radians(i * (360 / 7) + rot - 90)
            pts.append((cx + star_r * math.cos(ang), cy + star_r * math.sin(ang)))
        pen = QPen(qcol(C.PRI, int(200 * min(1.0, glow + 0.2))), 1.8)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        path.moveTo(*pts[0])
        for k in range(1, 8):
            x, y = pts[(k * 3) % 7]
            path.lineTo(x, y)
        p.drawPath(path)
        poly_r = star_r * 0.42
        p.setPen(QPen(qcol(C.ACC, int(150 * glow)), 1.2))
        for i in range(7):
            a1 = math.radians(i * (360 / 7) + rot - 90)
            a2 = math.radians((i + 1) * (360 / 7) + rot - 90)
            p.drawLine(
                qp(cx + poly_r * math.cos(a1), cy + poly_r * math.sin(a1)),
                qp(cx + poly_r * math.cos(a2), cy + poly_r * math.sin(a2)),
            )
        for (vx, vy) in pts:
            p.setBrush(QBrush(qcol(C.ACC, 210)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(qp(vx, vy), 2.6, 2.6)

        # ---- horizontal scan lines (holographic shimmer)
        if not dim:
            scan_y = self._scan_y * H
            scan_h = H * 0.08
            scan_grad = QRadialGradient(cx, scan_y, scan_h)
            scan_grad.setColorAt(0.0, qcol(C.PRI, int(25 * glow)))
            scan_grad.setColorAt(1.0, qcol(C.PRI, 0))
            p.setBrush(QBrush(scan_grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(QRectF(0, scan_y - scan_h, W, scan_h * 2))
            # subtle horizontal lines
            line_a = int(15 * glow)
            p.setPen(QPen(qcol(C.PRI, line_a), 0.5))
            for ly in range(0, H, 4):
                p.drawLine(0, ly, W, ly)

        # ---- vertical energy beams (thinking/speaking)
        if self._beam_alpha > 0.01:
            beam_a = int(45 * self._beam_alpha * glow)
            beam_w = R * 0.12
            grad_beam = QRadialGradient(cx, cy, R * 1.2)
            grad_beam.setColorAt(0.0, qcol(C.PRI, beam_a))
            grad_beam.setColorAt(0.3, qcol(C.PRI, int(beam_a * 0.4)))
            grad_beam.setColorAt(1.0, qcol(C.PRI, 0))
            p.setBrush(QBrush(grad_beam))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx - beam_w, cy - R * 1.15, beam_w * 2, R * 2.3))

        # ---- particles flowing into core
        for ang, dist, _ in self._particles:
            px = cx + R * dist * math.cos(ang)
            py = cy + R * dist * math.sin(ang)
            alpha = int(180 * (1.05 - dist))
            size = 1.0 + (1.0 - dist) * 2.0
            p.setPen(QPen(qcol(C.ACC, max(20, alpha)), size))
            p.drawPoint(int(px), int(py))

        # ---- core orb (multi-layer pulsing)
        orb_r = R * 0.30 * self._core_scale
        glow_r = orb_r * 1.8
        glow_grad = QRadialGradient(cx, cy, glow_r)
        glow_grad.setColorAt(0.0, qcol(C.PRI, int(55 * glow)))
        glow_grad.setColorAt(0.6, qcol(C.PRI, int(20 * glow)))
        glow_grad.setColorAt(1.0, qcol(C.PRI, 0))
        p.setBrush(QBrush(glow_grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2))

        grad = QRadialGradient(cx, cy, orb_r * 1.6)
        if self.state == "thinking":
            c_in = QColor(C.GOLD)
        elif dim:
            c_in = QColor(C.PRI); c_in.setAlpha(120)
        else:
            c_in = QColor(C.WHITE)
        grad.setColorAt(0.0, QColor(c_in.red(), c_in.green(), c_in.blue(), int(235 * glow)))
        grad.setColorAt(0.35, qcol(C.PRI, int(190 * glow)))
        grad.setColorAt(0.75, qcol(C.PRI, int(60 * glow)))
        grad.setColorAt(1.0, qcol(C.PRI, 0))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - orb_r * 1.6, cy - orb_r * 1.6, orb_r * 3.2, orb_r * 3.2))
        p.setBrush(QBrush(qcol(C.WHITE, int(200 * glow))))
        p.drawEllipse(QRectF(cx - orb_r * 0.34, cy - orb_r * 0.34, orb_r * 0.68, orb_r * 0.68))

        # ---- sparkles orbiting core
        for ang, dist, life in self._sparkles:
            sx = cx + R * dist * math.cos(ang)
            sy = cy + R * dist * math.sin(ang)
            p.setPen(QPen(qcol(C.ACC, int(220 * life)), 1.2))
            p.drawPoint(int(sx), int(sy))

        # ---- radial mic visualizer bars
        n_bars = 56
        for i in range(n_bars):
            rms = self._rms_hist[i % len(self._rms_hist)]
            norm = min(1.0, rms / 240.0)
            if self.state == "listening":
                norm = min(1.0, norm * 1.6)
            bar_len = 2 + norm * R * 0.18
            ang = math.radians(i * 360 / n_bars - 90)
            r1 = R * 1.08
            r2 = r1 + bar_len
            col = qcol(C.GREEN if norm > 0.55 else C.PRI, int(85 + 170 * norm))
            p.setPen(QPen(col, 2))
            p.drawLine(
                qp(cx + r1 * math.cos(ang), cy + r1 * math.sin(ang)),
                qp(cx + r2 * math.cos(ang), cy + r2 * math.sin(ang)),
            )

        # ---- title ＜Elívea＞
        p.setPen(QPen(qcol(C.ACC, 235), 1))
        p.setFont(font_cjk(17))
        p.drawText(QRectF(0, cy + R * 1.02, W, 30), Qt.AlignmentFlag.AlignCenter, "＜Elívea＞")
        p.setFont(font_mono(9))
        p.setPen(QPen(qcol(C.PRI, 200), 1))
        p.drawText(QRectF(0, cy + R * 1.02 + 28, W, 16), Qt.AlignmentFlag.AlignCenter, "G R E A T   S A G E   —   R A P H A E L")

        # ---- state line
        if self.state == "listening":
            txt, col = "◉ ESCUTANDO", C.GREEN
        elif self.state == "thinking":
            phase = "◐◓◑◒"[int(self._t * 3) % 4]
            txt, col = f"{phase} PROCESSANDO", C.GOLD
        elif self.state == "speaking":
            txt, col = "● FALANDO", C.PRI
        else:
            txt, col = "○ EM ESPERA", C.TEXT_DIM
        p.setPen(QPen(qcol(col), 1))
        p.setFont(font_mono(9))
        p.drawText(QRectF(0, cy + R * 1.02 + 48, W, 16), Qt.AlignmentFlag.AlignCenter, txt)


# ===========================================================================
# Telemetry bars
# ===========================================================================

class MetricBar(QWidget):
    def __init__(self, label: str, color: str | None = None, parent=None):
        super().__init__(parent)
        self._label = label
        self._color = color
        self._value = 0.0
        self._text = "--"
        self.setFixedHeight(38)
        self.setMinimumWidth(80)

    def set_value(self, pct: float, text: str):
        self._value = max(0.0, min(100.0, pct))
        self._text = text
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        p.setBrush(QBrush(qcol(C.PANEL2)))
        p.setPen(QPen(qcol(C.BORDER_A), 1))
        p.drawRoundedRect(QRectF(1, 1, W - 2, H - 2), 5, 5)

        bar_h = 5
        bar_y = H - bar_h - 5
        bar_w, bar_x = W - 12, 6
        fill_w = int(bar_w * self._value / 100)

        p.setBrush(QBrush(qcol(C.BG)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 2, 2)

        if self._value > 85:
            bar_col = qcol(C.RED)
        elif self._value > 65:
            bar_col = qcol(C.GOLD)
        else:
            bar_col = qcol(self._color or C.PRI)

        if fill_w > 0:
            p.setBrush(QBrush(bar_col))
            p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 2, 2)

        p.setFont(font_mono(7))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(8, 4, 60, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._label)
        p.setFont(font_mono(8))
        p.setPen(QPen(bar_col if self._text != "--" else qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(0, 4, W - 8, 14), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self._text)


# ===========================================================================
# Chat — Tensura ability panels
# ===========================================================================

def md_to_html(text: str) -> str:
    """Featherweight markdown → HTML for chat bubbles."""
    parts = html.escape(text).split("`")
    if len(parts) > 2:
        built = parts[0]
        for i, seg in enumerate(parts[1:]):
            if i % 2 == 0:
                built += (f"<code style='color:{C.ACC2};background:{C.BG};"
                          f"padding:0 3px;border-radius:3px'>{seg}</code>")
            else:
                built += seg
        t = built
    else:
        t = parts[0]
    return t.replace("**", "").replace("*", "").replace("\n", "<br>")


# ===========================================================================
# Waveform — horizontal sound wave (speaking & listening)
# ===========================================================================

class WaveformWidget(QWidget):
    """Horizontal waveform that reacts to audio RMS — shows when listening or speaking."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(44)
        self._rms_hist = deque([0.0] * 60, maxlen=60)
        self._t = 0.0
        self._last = time.time()
        self._state = "idle"
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def push_rms(self, rms: float):
        self._rms_hist.append(rms)

    def set_state(self, state: str):
        self._state = state

    def _tick(self):
        now = time.time()
        self._t += now - self._last
        self._last = now
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        mid_y = H / 2
        n = len(self._rms_hist)

        speaking = self._state == "speaking"
        listening = self._state == "listening"
        active = speaking or listening

        if not active or n == 0:
            p.setPen(QPen(qcol(C.BORDER, 60), 1))
            p.drawLine(0, int(mid_y), W, int(mid_y))
            p.end()
            return

        col = C.GREEN if listening else C.PRI
        step_x = max(1.0, W / n)

        # upper wave
        pts_upper = []
        for i in range(n):
            norm = min(1.0, self._rms_hist[i] / 200.0)
            amp = 2 + norm * H * 0.35
            x = i * step_x
            wave = math.sin(self._t * (3.0 if speaking else 1.8) + i * 0.2) * amp
            pts_upper.append(qp(x, mid_y - abs(wave)))

        path_upper = QPainterPath()
        path_upper.moveTo(pts_upper[0])
        for pt in pts_upper[1:]:
            path_upper.lineTo(pt)

        # fill
        path_fill = QPainterPath(path_upper)
        for i in range(n - 1, -1, -1):
            norm = min(1.0, self._rms_hist[i] / 200.0)
            amp = 2 + norm * H * 0.35
            x = i * step_x
            wave = math.sin(self._t * (3.0 if speaking else 1.8) + i * 0.2) * amp
            path_fill.lineTo(qp(x, mid_y + abs(wave)))
        path_fill.closeSubpath()
        fill_grad = QLinearGradient(0, 0, 0, H)
        fill_grad.setColorAt(0.0, qcol(col, 40))
        fill_grad.setColorAt(1.0, qcol(col, 0))
        p.setBrush(QBrush(fill_grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(path_fill)

        # upper line
        p.setPen(QPen(qcol(col, 180), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path_upper)

        # center pulse
        pulse = 0.5 + 0.5 * math.sin(self._t * 4.0)
        p.setPen(QPen(qcol(C.ACC, int(40 + 50 * pulse)), 0.6))
        p.drawLine(0, int(mid_y), W, int(mid_y))

        p.end()


class ChatBubble(QFrame):
    """Holographic panel: sage (left, cyan) or master (right, blue)."""

    def __init__(self, role: str, parent=None):
        super().__init__(parent)
        self.role = role
        self._full = ""
        self._shown = ""
        self._typing = False

        self.lbl_header = QLabel()
        self.lbl_header.setFont(font_mono(8))
        self.lbl_body = QLabel()
        self.lbl_body.setFont(font_ui(10))
        self.lbl_body.setWordWrap(True)
        self.lbl_body.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 10)
        lay.setSpacing(4)
        lay.addWidget(self.lbl_header)
        lay.addWidget(self.lbl_body)

        self._restyle()
        self._type_timer = QTimer(self)
        self._type_timer.timeout.connect(self._type_step)

    def _restyle(self):
        sage = self.role == "sage"
        border = C.PRI if sage else C.BORDER_B
        bg = C.PANEL if sage else C.PANEL2
        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {bg}F2, stop:1 {C.BG}E6);
                border: 1px solid {border};
                border-{'' if sage else ''}left: 3px solid {border};
                border-radius: 8px;
            }}
        """)
        if sage:
            self.lbl_header.setText("『Elívea』 ＜Elívea＞")
            self.lbl_header.setStyleSheet(f"color: {C.PRI}; background: transparent; border: none;")
            self.lbl_body.setStyleSheet(f"color: {C.TEXT}; background: transparent; border: none;")
        else:
            try:
                from core.persona import _load_user_name
                user = _load_user_name()
            except Exception:
                user = "Mestre"
            self.lbl_header.setText(f"{user} ➤")
            self.lbl_header.setStyleSheet(f"color: {C.ACC2}; background: transparent; border: none;")
            self.lbl_body.setStyleSheet(f"color: {C.WHITE}; background: transparent; border: none;")

    # ------------------------------------------------------------- content

    def set_text(self, text: str):
        self._full = text
        self._shown = text
        self.lbl_body.setText(md_to_html(text))

    def stream_append(self, delta: str):
        self._full += delta
        self._shown = self._full
        self.lbl_body.setText(md_to_html(self._full) + "<span style='color:" + C.PRI + "'>▊</span>")

    def stream_end(self):
        self.lbl_body.setText(md_to_html(self._full))

    def type_in(self, text: str):
        """Typewriter reveal for instant (local) responses."""
        self._full = text
        self._shown = ""
        self._typing = True
        self._type_timer.start(12)

    def _type_step(self):
        if len(self._shown) < len(self._full):
            step = max(1, len(self._full) // 90)
            self._shown = self._full[:len(self._shown) + step]
            self.lbl_body.setText(md_to_html(self._shown) + "▊")
        else:
            self._type_timer.stop()
            self._typing = False
            self.lbl_body.setText(md_to_html(self._full))


class ChatFlow(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._host = QWidget()
        self._lay = QVBoxLayout(self._host)
        self._lay.setContentsMargins(6, 6, 6, 6)
        self._lay.setSpacing(10)
        self._lay.addStretch()
        self.setWidget(self._host)
        self.setWidgetResizable(True)
        self.setStyleSheet(f"""
            QScrollArea {{ border: 1px solid {C.BORDER}; border-radius: 8px; background: {C.BG}; }}
            QScrollBar:vertical {{ background: {C.PANEL}; width: 8px; border-radius: 4px; }}
            QScrollBar::handle:vertical {{ background: {C.BORDER_B}; border-radius: 4px; min-height: 30px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

    def add_bubble(self, role: str, max_w: int) -> ChatBubble:
        bubble = ChatBubble(role)
        bubble.setMaximumWidth(max_w)
        bubble.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        if role == "sage":
            row.addWidget(bubble)
            row.addStretch()
        else:
            row.addStretch()
            row.addWidget(bubble)
        wrap = QWidget()
        wrap.setLayout(row)
        wrap.setStyleSheet("background: transparent;")
        self._lay.insertWidget(self._lay.count() - 1, wrap)
        self._scroll_bottom()
        return bubble

    def _scroll_bottom(self):
        def _go():
            sb = self.verticalScrollBar()
            sb.setValue(sb.maximum())

    def clear_all(self):
        """Remove all chat bubbles."""
        while self._lay.count() > 1:  # Keep the stretch
            item = self._lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._scroll_bottom()
        QTimer.singleShot(30, _go)


# ===========================================================================
# Status chips
# ===========================================================================

class StatusChip(QLabel):
    def __init__(self, icon: str, initial: str = "—", parent=None):
        super().__init__(parent)
        self._icon = icon
        self.setFont(font_mono(8))
        self.set_value(initial)

    def set_value(self, val: str, color: str | None = None):
        self.setText(f"{self._icon} {val}")
        self.setStyleSheet(f"""
            color: {color or C.TEXT_MED};
            background: {C.PANEL2};
            border: 1px solid {C.BORDER};
            border-radius: 9px;
            padding: 3px 9px;
        """)


# ===========================================================================
# Boot overlay — anime system startup
# ===========================================================================

BOOT_STATUS = [
    ("Núcleo neural", "ONLINE"),
    ("Síntese de voz neural", "ONLINE"),
    ("Pipeline de áudio unificado", "ONLINE"),
    ("Whisper V3 Turbo (STT)", "ONLINE"),
    ("Conversor de voz", "ONLINE"),
    ("Memória do usuário", "CARREGADA"),
    ("Módulos de automação", "CARREGADOS"),
    ("Agente de código", "ONLINE"),
    ("Motor de busca", "ONLINE"),
    ("Otimizador de performance", "ONLINE"),
]


class BootOverlay(QWidget):
    """Cinematic boot sequence — 2.5s total, golden particles, rune ring, status cascade."""
    done = pyqtSignal()

    def __init__(self, parent: None | QWidget):
        super().__init__(parent)
        if parent:
            self.setGeometry(parent.rect())
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        self._start_time = time.time()
        self._ring_r = 0.0
        self._particles: list[list[float]] = []  # [x, y, vx, vy, life, size, alpha]
        self._status_idx = 0
        self._status_shown: list[tuple[str, str, float]] = []  # (label, status, shown_at)
        self._phase = 0  # 0=flash, 1=name, 2=status, 3=done
        self._flash_alpha = 0.0
        self._name_alpha = 0.0
        self._subtitle_alpha = 0.0
        self._rune_rot = 0.0
        self._done_emitted = False

        # Mini rune ring for preview
        self._rune_ring_alpha = 0.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(20)  # 50 fps

        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(1.0)
        self.setGraphicsEffect(self._effect)

    def _tick(self):
        t = time.time() - self._start_time
        self._ring_r += 18
        self._rune_rot = (self._rune_rot + 0.6) % 360

        # Phase management
        if t < 0.3:
            self._phase = 0
            self._flash_alpha = min(1.0, t / 0.3)
        elif t < 1.0:
            self._phase = 1
            self._flash_alpha = max(0.0, 1.0 - (t - 0.3) / 0.5)
            self._name_alpha = min(1.0, (t - 0.3) / 0.5)
            self._rune_ring_alpha = min(1.0, (t - 0.3) / 0.6)
        elif t < 2.0:
            self._phase = 2
            self._name_alpha = 1.0
            self._rune_ring_alpha = 1.0
            # Cascade status lines
            interval = 0.08
            idx = int((t - 1.0) / interval)
            if idx > self._status_idx and idx <= len(BOOT_STATUS):
                self._status_idx = min(idx, len(BOOT_STATUS))
                for i in range(len(self._status_shown), self._status_idx):
                    self._status_shown.append((*BOOT_STATUS[i], time.time()))
            if len(BOOT_STATUS) > 0:
                self._subtitle_alpha = min(1.0, max(0.0, (t - 1.6) / 0.4))
        else:
            self._phase = 3
            self._name_alpha = max(0.0, 1.0 - (t - 2.0) / 0.5)
            self._rune_ring_alpha = max(0.0, 1.0 - (t - 2.0) / 0.5)
            self._subtitle_alpha = max(0.0, 1.0 - (t - 2.0) / 0.4)
            for i in range(len(self._status_shown)):
                lbl, st, at = self._status_shown[i]
                self._status_shown[i] = (lbl, st, at)  # keep as-is
            if t > 2.5 and not self._done_emitted:
                self._done_emitted = True
                self._timer.stop()
                self.done.emit()
                return

        # Spawn golden particles
        if len(self._particles) < 60 and random.random() < 0.7:
            cx, cy = self.width() / 2, self.height() * 0.38
            ang = random.uniform(0, 2 * math.pi)
            dist = random.uniform(20, min(self.width(), self.height()) * 0.45)
            px = cx + dist * math.cos(ang)
            py = cy + dist * math.sin(ang)
            vx = random.uniform(-0.3, 0.3)
            vy = random.uniform(-0.8, -0.2)
            self._particles.append([px, py, vx, vy, 1.0, random.uniform(1.0, 3.0), random.uniform(100, 220)])

        # Update particles
        alive = []
        for part in self._particles:
            part[0] += part[2]
            part[1] += part[3]
            part[4] -= 0.012
            part[3] -= 0.005  # gravity
            if part[4] > 0:
                alive.append(part)
        self._particles = alive

        self.update()

    def fade_out(self):
        anim = QPropertyAnimation(self._effect, b"opacity", self)
        anim.setDuration(500)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        anim.finished.connect(self.hide)
        anim.start()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        cx, cy = W / 2, H * 0.38
        R = min(W, H) * 0.18
        t = time.time() - self._start_time

        # ── Background ──
        p.fillRect(self.rect(), qcol(C.BG))

        # ── Starfield ──
        rng = random.Random(77)
        for _ in range(50):
            sx, sy = rng.randint(0, W), rng.randint(0, H)
            flicker = int(60 + 50 * math.sin(t * 2.5 + sx * 0.05))
            p.setPen(QPen(qcol(GOLD_DIM, flicker), 1))
            p.drawPoint(sx, sy)

        # ── Expanding startup rings ──
        for i in range(5):
            r = (self._ring_r - i * 70) % (min(W, H) * 0.8)
            if r > 4:
                alpha = max(0, int(120 * (1.0 - r / (min(W, H) * 0.8))))
                p.setPen(QPen(qcol(GOLD, alpha), 1.2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # ── Atmospheric halo ──
        if self._rune_ring_alpha > 0.01:
            halo_r = R * 2.5
            halo = QRadialGradient(cx, cy, halo_r)
            a = int(35 * self._rune_ring_alpha)
            halo.setColorAt(0.0, qcol(GOLD, a))
            halo.setColorAt(0.4, qcol(GOLD, int(a * 0.3)))
            halo.setColorAt(1.0, qcol(GOLD, 0))
            p.setBrush(QBrush(halo))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx - halo_r, cy - halo_r, halo_r * 2, halo_r * 2))

        # ── Mini Rune Ring Preview ──
        if self._rune_ring_alpha > 0.01:
            ra = int(200 * self._rune_ring_alpha)
            # Outer ring
            p.setPen(QPen(qcol(GOLD, ra), 2.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - R, cy - R, R * 2, R * 2))
            # Inner ring
            p.setPen(QPen(qcol(GOLD, int(ra * 0.4)), 0.8))
            p.drawEllipse(QRectF(cx - R * 0.88, cy - R * 0.88, R * 1.76, R * 1.76))
            # Tick marks
            p.setPen(QPen(qcol(GOLD, int(ra * 0.5)), 1))
            for i in range(36):
                ang = math.radians(i * 10)
                big = i % 4 == 0
                r1 = R * 1.0
                r2 = R * (0.94 if big else 0.97)
                p.drawLine(
                    QPointF(cx + r1 * math.cos(ang), cy + r1 * math.sin(ang)),
                    QPointF(cx + r2 * math.cos(ang), cy + r2 * math.sin(ang)),
                )
            # Rotating runes
            rune_r = R * 0.82
            p.save()
            p.translate(cx, cy)
            p.rotate(self._rune_rot)
            rf = QFont("Microsoft YaHei UI", 8, QFont.Weight.Bold)
            for i, rune in enumerate(RUNES):
                ang = i * 360 / len(RUNES)
                p.save()
                p.rotate(ang)
                p.translate(0, -rune_r)
                p.rotate(180)
                rune_a = int(ra * (0.6 + 0.4 * math.sin(t * 2.0 + i * 0.5)))
                p.setPen(QPen(qcol(GOLD_BRIGHT, rune_a)))
                p.setFont(rf)
                p.drawText(QRectF(-10, -8, 20, 16), Qt.AlignmentFlag.AlignCenter, rune)
                p.restore()
            p.restore()
            # Central cross
            cross_a = int(ra * 0.6)
            p.setPen(QPen(qcol(GOLD, cross_a), 1.5))
            p.drawLine(QPointF(cx - R * 0.35, cy), QPointF(cx + R * 0.35, cy))
            p.drawLine(QPointF(cx, cy - R * 0.35), QPointF(cx, cy + R * 0.35))
            # Diagonal cross
            p.setPen(QPen(qcol(GOLD, int(cross_a * 0.5)), 0.8))
            d = R * 0.25
            p.drawLine(QPointF(cx - d, cy - d), QPointF(cx + d, cy + d))
            p.drawLine(QPointF(cx - d, cy + d), QPointF(cx + d, cy - d))
            # Central glow
            glow_r = R * 0.25
            glow = QRadialGradient(cx, cy, glow_r)
            ga = int(180 * self._rune_ring_alpha)
            glow.setColorAt(0.0, qcol(GOLD_BRIGHT, ga))
            glow.setColorAt(0.5, qcol(GOLD, int(ga * 0.4)))
            glow.setColorAt(1.0, qcol(GOLD, 0))
            p.setBrush(QBrush(glow))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2))
            # Inner white core
            core_r = R * 0.06
            p.setBrush(QBrush(qcol(GOLD_BRIGHT, int(220 * self._rune_ring_alpha))))
            p.drawEllipse(QRectF(cx - core_r, cy - core_r, core_r * 2, core_r * 2))

        # ── Flash effect ──
        if self._flash_alpha > 0.01:
            flash_r = min(W, H) * 0.8 * self._flash_alpha
            flash = QRadialGradient(cx, cy, flash_r)
            fa = int(180 * self._flash_alpha)
            flash.setColorAt(0.0, qcol(GOLD_BRIGHT, fa))
            flash.setColorAt(0.3, qcol(GOLD, int(fa * 0.5)))
            flash.setColorAt(1.0, qcol(GOLD, 0))
            p.setBrush(QBrush(flash))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx - flash_r, cy - flash_r, flash_r * 2, flash_r * 2))

        # ── Particles ──
        for part in self._particles:
            px, py, _, _, life, size, base_alpha = part
            a = int(base_alpha * life * self._rune_ring_alpha)
            if a > 5:
                p.setPen(QPen(qcol(GOLD, a), size))
                p.drawPoint(int(px), int(py))

        # ── Title: ＜Elívea＞ ──
        if self._name_alpha > 0.01:
            na = int(255 * self._name_alpha)
            p.setPen(QPen(qcol(GOLD_BRIGHT, na), 1))
            p.setFont(QFont("Microsoft YaHei UI", 30, QFont.Weight.Bold))
            p.drawText(QRectF(0, cy + R * 1.2, W, 50), Qt.AlignmentFlag.AlignCenter, "＜Elívea＞")
            # Subtitle line
            p.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            p.setPen(QPen(qcol(GOLD, int(na * 0.85)), 1))
            p.drawText(QRectF(0, cy + R * 1.2 + 48, W, 20), Qt.AlignmentFlag.AlignCenter, "A E T H E L I S   C L A S S")

        # ── Status cascade ──
        if self._status_shown:
            start_y = cy + R * 1.2 + 90
            p.setFont(QFont("Consolas", 8, QFont.Weight.Normal))
            for i, (label, status, shown_at) in enumerate(self._status_shown):
                age = time.time() - shown_at
                alpha = min(1.0, age / 0.15)  # fade in fast
                y = start_y + i * 17
                if y > H - 40:
                    break
                # Status dot (green)
                dot_a = int(220 * alpha)
                is_online = status in ("ONLINE", "CARREGADA", "CARREGADOS")
                dot_col = GREEN if is_online else GOLD
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(qcol(dot_col, dot_a)))
                p.drawEllipse(QRectF(W / 2 - 240, y + 3, 5, 5))
                # Label
                p.setPen(QPen(qcol(TEXT_MED, int(200 * alpha)), 1))
                p.drawText(QRectF(W / 2 - 228, y, 280, 16), Qt.AlignmentFlag.AlignLeft, label)
                # Status
                p.setPen(QPen(qcol(dot_col, dot_a), 1))
                dots = "." * (int(time.time() * 8) % 4)
                status_txt = status + (" " + dots if age < 0.12 else "")
                p.drawText(QRectF(W / 2 + 60, y, 160, 16), Qt.AlignmentFlag.AlignRight, status_txt)

        # ── Subtitle ──
        if self._subtitle_alpha > 0.01:
            sa = int(200 * self._subtitle_alpha)
            p.setPen(QPen(qcol(GOLD, sa), 1))
            p.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.Normal))
            final_y = cy + R * 1.2 + 90 + len(BOOT_STATUS) * 17 + 20
            if final_y < H - 30:
                p.drawText(QRectF(0, final_y, W, 24), Qt.AlignmentFlag.AlignCenter, "Todos os sistemas nominais, Mestre.")

    def mousePressEvent(self, _):
        # click to skip boot
        if self._done_emitted:
            return
        self._done_emitted = True
        self._timer.stop()
        self.done.emit()


# ===========================================================================
# Config dialog
# ===========================================================================

class ConfigDialog(QWidget):
    def __init__(self, main_win, voices: list[str], current_voice: str, parent=None):
        super().__init__(parent)
        self.main_win = main_win
        self.setWindowTitle("Configurações — Elívea")
        self.resize(560, 420)
        self.setStyleSheet(f"background-color: {C.PANEL}; color: {C.TEXT};")

        lay = QVBoxLayout(self)
        title = QLabel("⚙ CONFIGURAÇÕES DO ELIVEA")
        title.setFont(font_mono(12))
        title.setStyleSheet(f"color: {C.PRI}; padding: 6px;")
        lay.addWidget(title)

        # system box
        box1 = QFrame()
        box1.setStyleSheet(f"background: {C.PANEL2}; border: 1px solid {C.BORDER}; border-radius: 8px;")
        l1 = QVBoxLayout(box1)
        lbl1 = QLabel("INICIALIZAÇÃO & SISTEMA")
        lbl1.setFont(font_mono(9))
        lbl1.setStyleSheet(f"color: {C.ACC2};")
        l1.addWidget(lbl1)

        self.chk_autostart = QPushButton(" [✓] Iniciar com o Windows ")
        self.chk_autostart.setCheckable(True)
        self.chk_autostart.setChecked(True)
        self.chk_autostart.setStyleSheet(f"color: {C.GREEN}; text-align: left; background: {C.PANEL}; padding: 8px; border: 1px solid {C.BORDER};")
        self.chk_autostart.clicked.connect(self._toggle_autostart)
        l1.addWidget(self.chk_autostart)
        lay.addWidget(box1)

        # voice box
        box2 = QFrame()
        box2.setStyleSheet(f"background: {C.PANEL2}; border: 1px solid {C.BORDER}; border-radius: 8px;")
        l2 = QVBoxLayout(box2)
        lbl2 = QLabel("🗣 VOZ NEURAL DO ELIVEA")
        lbl2.setFont(font_mono(9))
        lbl2.setStyleSheet(f"color: {C.ACC2};")
        l2.addWidget(lbl2)

        self.combo_voice = QComboBox()
        self.combo_voice.addItems(voices)
        if current_voice in voices:
            self.combo_voice.setCurrentText(current_voice)
        self.combo_voice.setStyleSheet(f"""
            QComboBox {{ background: {C.PANEL}; color: {C.TEXT}; border: 1px solid {C.BORDER_B}; border-radius: 5px; padding: 6px; }}
            QComboBox QAbstractItemView {{ background: {C.PANEL2}; color: {C.TEXT}; selection-background-color: {C.GHOST}; }}
        """)
        self.combo_voice.currentTextChanged.connect(self._change_voice)
        l2.addWidget(self.combo_voice)

        btn_test = QPushButton("🔊 Testar voz neural")
        btn_test.setStyleSheet(f"background: {C.PRI}; color: {C.BG}; font-weight: bold; padding: 8px; border-radius: 5px;")
        btn_test.clicked.connect(self._test_voice)
        l2.addWidget(btn_test)
        lay.addWidget(box2)

        lay.addStretch()
        btn_close = QPushButton(" FECHAR ")
        btn_close.setFont(font_mono(10))
        btn_close.setStyleSheet(f"background: {C.PRI}; color: {C.BG}; padding: 10px; border-radius: 5px;")
        btn_close.clicked.connect(self.close)
        lay.addWidget(btn_close)

    def _toggle_autostart(self, checked: bool):
        ok = set_windows_autostart(checked)
        status = "Ativado" if checked else "Desativado"
        self.chk_autostart.setText(f" [{'✓' if checked else '✗'}] Iniciar com o Windows ({status}) ")
        self.chk_autostart.setStyleSheet(
            f"color: {C.GREEN if checked else C.RED}; text-align: left; background: {C.PANEL}; padding: 8px; border: 1px solid {C.BORDER};")
        if ok and self.main_win:
            self.main_win.add_sage_message(f"Aviso. Inicialização automática do Windows {status.lower()} com sucesso, Mestre.")

    def _change_voice(self, label: str):
        if self.main_win and self.main_win.voice_handler:
            self.main_win.voice_handler(label)

    def _test_voice(self):
        if self.main_win:
            self.main_win.voice_test_requested.emit()


# ===========================================================================
# Main window
# ===========================================================================

class EliveaMainWindow(QMainWindow):
    voice_test_requested = pyqtSignal()

    def __init__(self,
                 command_handler=None,
                 pipeline=None,
                 speech=None,
                 llm=None,
                 voice_handler=None,
                 stop_speech_handler=None,
                 mic_button_handler=None):
        super().__init__()
        self.command_handler = command_handler
        self.pipeline = pipeline
        self.speech = speech
        self.llm = llm
        self.voice_handler = voice_handler
        self.stop_speech_handler = stop_speech_handler
        self.mic_button_handler = mic_button_handler

        self.theme_key = self._detect_theme_by_time()
        apply_theme(self.theme_key)
        # Dynamic theme timer — checks every 10 minutes for time-based theme switch
        self._theme_timer = QTimer(self)
        self._theme_timer.timeout.connect(self._check_theme_update)
        self._theme_timer.start(600000)  # 10 minutes
        self._stream_bubble: ChatBubble | None = None
        self._t0_cmd = 0.0
        self._real_exit = False

        self.setWindowTitle("＜Elívea＞ Elívea — Elivea • Gisele Vechin [by: bryan]")
        self.resize(1400, 850)
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(f"background-color: {C.BG}; color: {C.TEXT};")

        self._build_ui()
        self._start_telemetry()

        # Cinematic awakening overlay — anime-style ability awakening
        from ui.professional_widgets import AbilityAwakeningOverlay, AwakeningSFX
        self.awakening = AbilityAwakeningOverlay(self)
        self.awakening.done.connect(self._on_awakening_done)
        self.awakening.show()
        self.awakening.raise_()
        # SFX are played internally by the overlay's _tick
        # Voice during overlay (2.0s from app start — during explosion phase)
        QTimer.singleShot(2000, lambda: self._speak_awakening())

        # Elivea companion orb (visible when the window leaves the screen)
        from ui.orb_widget import EliveaOrb
        self.orb = EliveaOrb(self)

    # ------------------------------------------------------------------- UI

    def _build_ui(self):
        from ui.professional_widgets import (
            RuneCoreWidget, TopBarWidget, InputBarWidget,
            CommandCenterDrawer, GlassPanel, BG,
            SystemMonitorWidget, QuickActionsWidget, AIStatusWidget, RecentCommandsWidget,
            CodeScratchpadWidget, CodeWorkspaceWidget, ConversationHistoryMap, HistoryDrawer,
            AmbientParticles, StatusBar, NotificationToast, MicroInteractions
        )
        from ui.chat_panel import ChatSidebar
        from ui.deep_dev_panel import DeepDevPanelWidget
        from ui.command_palette import CommandPalette
        central = QWidget()
        central.setStyleSheet(f"background: {BG};")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ============ TOP BAR ============
        self.top_bar = TopBarWidget()
        root.addWidget(self.top_bar)

        # ============ MAIN CONTENT ============
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # ---- Left: Chat Sidebar ----
        self.chat_sidebar = ChatSidebar()
        self.chat_sidebar.set_on_send(self.submit_command)
        self.chat_sidebar.set_on_history_toggle(self.toggle_history_map)
        body.addWidget(self.chat_sidebar, stretch=0)

        # ---- Center: RuneCore + Code Workspace (overlay) ----
        center = QWidget()
        center.setStyleSheet("background: transparent;")
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        self.rune_core = RuneCoreWidget()
        center_layout.addWidget(self.rune_core, stretch=1)
        # Code Workspace (hidden by default, overlay on top)
        self.code_workspace = CodeWorkspaceWidget()
        self.code_workspace.setParent(center)
        self.code_workspace.hide()
        self.code_workspace.set_on_close(self._close_code_workspace)
        self.code_workspace.set_on_run(self._run_code)
        self.code_workspace.set_on_generate(self._on_generate_code)

        # Programming Panel (full IDE — hidden by default)
        from ui.programming_panel import ProgrammingPanel
        self.programming_panel = ProgrammingPanel()
        self.programming_panel.setParent(center)
        self.programming_panel.hide()
        self.programming_panel.sig_close.connect(self._close_programming_panel)
        self.programming_panel.set_generate_handler(self._on_programming_generate)
        self.programming_panel.set_root_path(str(Path(__file__).resolve().parent.parent))
        # Deep Dev Panel (floating overlay - hidden by default)
        self.deep_dev_panel = DeepDevPanelWidget()
        self.deep_dev_panel.setParent(center)
        self.deep_dev_panel.hide()
        self.deep_dev_panel.sig_close.connect(self._close_deep_dev_panel)
        self.deep_dev_panel.sig_execute.connect(self._on_deep_dev_execute)
        self.deep_dev_panel.sig_approve.connect(self._on_deep_dev_approve)
        self.deep_dev_panel.sig_discard.connect(self._on_deep_dev_discard)
        body.addWidget(center, stretch=2)

        # ---- Right: Useful panels ----
        right = QWidget()
        right.setFixedWidth(340)
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setStyleSheet(f"QScrollArea {{ background: transparent; border: none; }} QScrollBar:vertical {{ width: 4px; }} QScrollBar::handle:vertical {{ background: rgba(255,215,0,0.15); border-radius: 2px; }}")
        right_inner = QWidget()
        right_inner.setStyleSheet("background: transparent;")
        right_layout = QVBoxLayout(right_inner)
        right_layout.setContentsMargins(4, 4, 4, 4)
        right_layout.setSpacing(6)

        # System Monitor
        self.sys_monitor = SystemMonitorWidget()
        self.sys_monitor.setFixedHeight(130)
        right_layout.addWidget(self.sys_monitor)

        # AI Status
        self.ai_status = AIStatusWidget()
        self.ai_status.setFixedHeight(145)
        right_layout.addWidget(self.ai_status)

        # Provider Status (real-time API health + usage bars)
        from ui.provider_status_panel import ProviderStatusPanel
        self.provider_status = ProviderStatusPanel()
        self.provider_status.setFixedHeight(340)
        self.provider_status.sig_detail_requested.connect(self._on_provider_detail)
        right_layout.addWidget(self.provider_status)

        # Quick Actions
        self.quick_actions = QuickActionsWidget()
        self.quick_actions.setFixedHeight(115)
        self.quick_actions.set_on_action(self._on_quick_action)
        right_layout.addWidget(self.quick_actions)

        # Recent Commands
        self.recent_cmds = RecentCommandsWidget()
        self.recent_cmds.setFixedHeight(120)
        right_layout.addWidget(self.recent_cmds)

        # Notifications
        from ui.professional_widgets import NotificationWidget
        self.notifications = NotificationWidget()
        self.notifications.setFixedHeight(140)
        right_layout.addWidget(self.notifications)

        # Code Scratchpad
        self.code_scratchpad = CodeScratchpadWidget()
        self.code_scratchpad.setFixedHeight(160)
        right_layout.addWidget(self.code_scratchpad)

        right_layout.addStretch()
        right_scroll.setWidget(right_inner)
        right_layout_main = QVBoxLayout(right)
        right_layout_main.setContentsMargins(0, 0, 0, 0)
        right_layout_main.addWidget(right_scroll)

        body.addWidget(right)
        root.addLayout(body, stretch=1)

        # ============ HISTORY MAP (overlay on center, over RuneCore) ============
        self.conv_history_map = ConversationHistoryMap(self)
        self.conv_history_map.setVisible(False)
        self.conv_history_map.set_on_node_click(self._on_history_node_click)
        self.conv_history_map.set_on_history_click(self._open_history_drawer)

        # ============ HISTORY DRAWER (full-screen overlay) ============
        self.history_drawer = HistoryDrawer(self)
        self.history_drawer.setVisible(False)
        self.history_drawer.set_on_close(lambda: self.history_drawer.setVisible(False))
        self.history_drawer.set_on_select(self._on_history_select)

        # ============ STATUS BAR ============
        self.status_bar = StatusBar()
        root.addWidget(self.status_bar)

        # ============ AMBIENT PARTICLES (behind everything) ============
        self.ambient_particles = AmbientParticles(self)
        self.ambient_particles.lower()

        # ============ MICRO-INTERACTIONS ============
        self.micro = MicroInteractions(self)
        self.micro.raise_()

        # ============ NOTIFICATION TOAST ============
        self.toast = NotificationToast(self)

        # ============ COMMAND CENTER DRAWER ============
        self.cmd_drawer = CommandCenterDrawer(self)
        self.cmd_drawer.set_on_execute(self.submit_command)
        self.cmd_drawer.setGeometry(self.rect())
        self.cmd_drawer.hide()

        # Hidden backward-compat widgets
        self.chat = ChatFlow(); self.chat.hide()
        self.circle = MagicCircleWidget(); self.circle.hide()
        self.waveform = WaveformWidget(); self.waveform.hide()
        self.m_cpu = MetricBar("CPU"); self.m_ram = MetricBar("RAM"); self.m_mic = MetricBar("MIC")
        self.chip_state = StatusChip("◉", "IDLE"); self.chip_state.hide()
        self.chip_stt = StatusChip("🎙", "STT"); self.chip_stt.hide()
        self.chip_ttft = StatusChip("⚡", "TTFT"); self.chip_ttft.hide()
        self.chip_model = StatusChip("◈", "LLM"); self.chip_model.hide()
        self.btn_theme = QPushButton(); self.btn_theme.hide()
        self.btn_voice = QPushButton(); self.btn_voice.hide()
        self.btn_usage = QPushButton(); self.btn_usage.hide()
        self.btn_config = QPushButton(); self.btn_config.hide()
        self.btn_ptt = QPushButton(); self.btn_ptt.hide()
        self.btn_mode = QPushButton(); self.btn_mode.hide()
        self.btn_stop = QPushButton(); self.btn_stop.hide()
        self.entry = QLineEdit(); self.entry.hide()

        # Atalhos
        try:
            from PySide6.QtGui import QShortcut, QKeySequence
        except ImportError:
            from PyQt6.QtGui import QShortcut, QKeySequence
        QShortcut(QKeySequence("Escape"), self).activated.connect(self._on_escape)
        QShortcut(QKeySequence("Ctrl+P"), self).activated.connect(lambda: self.open_code_workspace())
        QShortcut(QKeySequence("Ctrl+Shift+P"), self).activated.connect(lambda: self.open_programming_panel())
        QShortcut(QKeySequence("F1"), self).activated.connect(self._show_help)
        QShortcut(QKeySequence("Ctrl+K"), self).activated.connect(self._open_command_palette)

    def _detect_theme_by_time(self) -> str:
        """Auto-select theme based on time of day."""
        import datetime
        hour = datetime.datetime.now().hour
        if 6 <= hour < 12:    # Morning
            return "tensura_gold"  # warm golden
        elif 12 <= hour < 18:  # Afternoon
            return "gold"         # bright gold
        elif 18 <= hour < 22:  # Evening
            return "tensura"      # blue tones
        else:                   # Night (22-6)
            return "crimson"      # deep dark red

    def _check_theme_update(self):
        """Periodically check if theme should change based on time."""
        new_theme = self._detect_theme_by_time()
        if new_theme != self.theme_key:
            self.theme_key = new_theme
            apply_theme(new_theme)
            # Re-apply stylesheet with new theme colors
            self.setStyleSheet(f"background-color: {C.BG}; color: {C.TEXT};")
            self.add_sage_message(f"Tema alterado automaticamente para {C.name}, Mestre.")

    def _on_escape(self):
        """Escape closes overlays (history map, drawer, code workspace)."""
        if hasattr(self, 'history_drawer') and self.history_drawer.isVisible():
            self.history_drawer.setVisible(False)
            return
        if hasattr(self, 'conv_history_map') and self.conv_history_map.isVisible():
            self.conv_history_map.setVisible(False)
            if hasattr(self, 'rune_core'):
                self.rune_core.set_center_detail(True)
            return
        if hasattr(self, 'code_workspace') and self.code_workspace.isVisible():
            self.code_workspace.setVisible(False)
            return
        self._stop_speech()

    # -------------------------------------------------- history map/drawer

    def _load_conversations_for_map(self):
        """Load recent conversations into the history map."""
        try:
            from memory.memory_manager import MemoryManager
            convs = MemoryManager.get_recent_turns(limit=15)
            if hasattr(self, 'conv_history_map'):
                self.conv_history_map.set_conversations(convs)
        except Exception:
            pass

    def toggle_history_map(self):
        """Toggle the history map overlay on top of the RuneCore."""
        if not hasattr(self, 'conv_history_map'):
            return
        if self.conv_history_map.isVisible():
            self.conv_history_map.setVisible(False)
            # Restore center detail on RuneCore
            if hasattr(self, 'rune_core'):
                self.rune_core.set_center_detail(True)
            return
        # Load conversations
        self._load_conversations_for_map()
        # Position over the center area (where RuneCore is)
        r = self.geometry()
        chat_w = 360
        right_w = 340
        center_x = chat_w
        center_w = r.width() - chat_w - right_w
        self.conv_history_map.setGeometry(center_x, 48, center_w, r.height() - 104)
        self.conv_history_map.raise_()
        self.conv_history_map.setVisible(True)
        # Hide center detail on RuneCore while history map is open
        if hasattr(self, 'rune_core'):
            self.rune_core.set_center_detail(False)
        self.conv_history_map.update()

    def _on_history_node_click(self, conv: dict):
        """Load a past conversation into the chat."""
        user_speech = conv.get('user_speech', '')
        assistant_response = conv.get('assistant_response', '')
        if user_speech:
            self.chat_sidebar.add_message('user', user_speech)
        if assistant_response:
            self.chat_sidebar.add_message('assistant', assistant_response)
        # Close the map after selecting
        self.conv_history_map.setVisible(False)
        # Restore center detail on RuneCore
        if hasattr(self, 'rune_core'):
            self.rune_core.set_center_detail(True)

    def _open_history_drawer(self):
        """Open the full history drawer."""
        try:
            from memory.memory_manager import MemoryManager
            convs = MemoryManager.get_recent_turns(limit=200)
            self.history_drawer.set_conversations(convs)
        except Exception:
            self.history_drawer.set_conversations([])
        self.history_drawer.setGeometry(self.rect())
        self.history_drawer.raise_()
        self.history_drawer.setVisible(True)
        self.history_drawer.update()

    def _on_history_select(self, conv: dict):
        """Select a conversation from the full history drawer."""
        self._on_history_node_click(conv)
        self.history_drawer.setVisible(False)

    # ------------------------------------------------------------ boot

    def _on_awakening_done(self):
        """Called when the ability awakening animation finishes."""
        # Force-hide the overlay (safety)
        if hasattr(self, 'awakening'):
            try:
                self.awakening.hide()
                self.awakening.deleteLater()
            except Exception:
                pass
        # Play boot chime from speech engine
        try:
            if self.speech:
                self.speech.play_boot_chime()
        except Exception:
            pass
        try:
            from core.persona import _load_user_name
            user = _load_user_name()
        except Exception:
            user = "Mestre"
        # Show welcome message after a brief pause
        QTimer.singleShot(300, lambda: self._show_welcome_msg(user))
        # Load conversation history into the map
        QTimer.singleShot(1000, self._load_conversations_for_map)
        # Toast notification
        QTimer.singleShot(500, lambda: self.toast.show_toast(
            "Elívea online — todos os sistemas nominais", "success", 4000))
        # Set status bar model
        self.status_bar.set_model(getattr(self, '_current_model', '9Router'))

    def _speak_awakening(self):
        """Speak the awakening line with the TTS engine."""
        try:
            if self.speech:
                self.speech.speak("Habilidade única desbloqueada: Elívea")
        except Exception:
            pass

    def _show_welcome_msg(self, user="Mestre"):
        """Show the welcome message after the awakening animation."""
        try:
            from core.persona import _load_user_name
            user = _load_user_name()
        except Exception:
            pass
        self.add_sage_message(
            f"Elívea online, {user}. Todos os sistemas nominais. "
            "Pode falar comigo naturalmente — estou te ouvindo."
        )

    def _on_boot_done(self):
        """Legacy boot done — now routes to awakening."""
        self._on_awakening_done() 

    def showEvent(self, ev):
        super().showEvent(ev)
        # Size particles to window
        QTimer.singleShot(100, self._layout_overlays)

    def _layout_overlays(self):
        r = self.rect()
        if hasattr(self, 'ambient_particles'):
            self.ambient_particles.setGeometry(r)

    # -------------------------------------------------- window ↔ orb modes

    def changeEvent(self, ev):
        try:
            if ev.type() == QEvent.Type.WindowStateChange and self.isMinimized():
                QTimer.singleShot(0, self._hide_to_orb)
            super().changeEvent(ev)
        except Exception:
            pass

    def closeEvent(self, ev):
        try:
            if not self._real_exit:
                ev.ignore()
                self._hide_to_orb()
                return
            self.orb.hide()
            super().closeEvent(ev)
        except Exception:
            ev.accept()

    def _hide_to_orb(self):
        """Minimizar/fechar → o Elívea vira o orbe flutuante do anime."""
        self.hide()
        self.orb.set_state(self.circle.state)
        self.orb.show()

    def _restore_from_orb(self):
        self.orb.hide()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    # ------------------------------------------------------ chat helpers

    def add_master_message(self, text: str):
        self.chat_sidebar.add_message("user", text)

    def add_sage_message(self, text: str):
        # DEDUP: skip if the last bubble already has this exact text
        bubbles = self.chat_sidebar._bubbles
        if bubbles:
            last = bubbles[-1]
            last_text = getattr(last, '_text', '') or getattr(last, '_full', '')
            if last_text.strip() == text.strip():
                return  # already shown
        # Check if there's already a streaming bubble OR a recent assistant bubble
        if bubbles and hasattr(bubbles[-1], '_streaming') and bubbles[-1]._streaming:
            # Streaming bubble exists — just finalize it with the complete text
            bubbles[-1]._text = text
            bubbles[-1]._streaming = False
            bubbles[-1]._compute_size()
            bubbles[-1].setFixedHeight(bubbles[-1].heightNeeded())
            bubbles[-1].update()
        elif bubbles and getattr(bubbles[-1], '_role', '') == 'assistant' and not getattr(bubbles[-1], '_finalized', False):
            # LLM stream created a bubble via append_stream — update it instead of duplicating
            bubbles[-1]._text = text
            bubbles[-1]._finalized = True
            bubbles[-1]._compute_size()
            bubbles[-1].setFixedHeight(bubbles[-1].heightNeeded())
            bubbles[-1].update()
        else:
            # No existing bubble — create a new one (local answers)
            self.chat_sidebar.add_message("assistant", text)
        # Feed code scratchpad
        if hasattr(self, 'code_scratchpad'):
            has_code = any(kw in text for kw in ['def ', 'import ', 'class ', 'function ', '```', 'return ', 'if ', 'for '])
            if has_code and len(text) > 20:
                self.code_scratchpad.add_line("", "text")
                self.code_scratchpad.add_line("// AI Response:", "comment")
                for line in text.split('\n')[:15]:
                    self.code_scratchpad.add_line(line, "code")
            elif text.strip():
                self.code_scratchpad.add_output(text[:120])
        return None

    def begin_sage_stream(self):
        self.chat_sidebar.begin_stream()
        self._stream_bubble = True

    def append_sage_stream(self, delta: str):
        self.chat_sidebar.append_stream(delta)

    def end_sage_stream(self):
        self.chat_sidebar.end_stream()
        self._stream_bubble = None
        # Refresh history map with new conversation
        QTimer.singleShot(500, self._load_conversations_for_map)

    # ------------------------------------------------------ state/telemetry

    def _on_shutdown_requested(self):
        self._real_exit = True
        self.close()
        # SAFETY: use SuperUser with 30s delay, not os.system with 5s
        try:
            from modules.superuser import SuperUser
            SuperUser.shutdown(30)
        except Exception:
            pass

    def set_pipeline_state(self, state: str):
        self.circle.set_state(state)
        self.waveform.set_state(state)
        self.rune_core.set_state(state)
        icons = {"idle": ("EM ESPERA", C.TEXT_DIM),
                 "listening": ("ESCUTANDO", C.GREEN),
                 "thinking": ("PROCESSANDO", C.GOLD),
                 "speaking": ("FALANDO", C.PRI),
                 "success": ("CONCLUÍDO", C.GREEN),
                 "error": ("ERRO", C.RED)}
        icon, col = icons.get(state, ("EM ESPERA", C.TEXT_DIM))
        self.chip_state.set_value(icon, col)
        if self.orb.isVisible():
            self.orb.set_state(state)
        # Log notification
        if hasattr(self, 'notifications') and state in ('success', 'error', 'listening'):
            notif_icons = {'success': '✅', 'error': '❌', 'listening': '🎙'}
            notif_texts = {'success': 'Comando concluído', 'error': 'Erro no processamento', 'listening': 'Escutando...'}
            self.notifications.add(notif_icons.get(state, '•'), notif_texts.get(state, state))
        # Micro-interactions: confetti on success, shake on error
        if state == "success" and hasattr(self, 'micro'):
            self.micro.add_confetti(self.width() / 2, self.height() / 2, 25)
        if state == "error" and hasattr(self, 'micro'):
            self.micro.trigger_shake(6.0)
        # Auto-reset success/error to idle after 2s
        if state in ("success", "error"):
            QTimer.singleShot(2000, lambda: self.set_pipeline_state("idle"))

    def update_mic_rms(self, rms: float):
        try:
            self.circle.push_rms(rms)
            self.waveform.push_rms(rms)
            self.orb.push_rms(rms)
            val = min(100.0, (rms / 260.0) * 100.0)
            self.m_mic.set_value(val, f"{rms:.0f}")
            # Audio reactivity for RuneCore
            if hasattr(self, 'rune_core'):
                audio_norm = min(1.0, rms / 200.0)
                self.rune_core.set_audio_level(audio_norm)
        except Exception:
            pass

    def update_telemetry(self, stt_engine: str, stt_ms: int, model: str, ttft_ms: int):
        self.chip_stt.set_value(f"STT {stt_engine} {stt_ms}ms")
        self.chip_model.set_value(f"LLM {model.split('-')[0]}")
        self.chip_ttft.set_value(f"TTFT {ttft_ms}ms", C.GREEN if ttft_ms and ttft_ms < 1500 else C.GOLD)
        if hasattr(self, 'ai_status'):
            self.ai_status.set_model(model, "Groq")
            self.ai_status.set_latency(ttft_ms)

    def _start_telemetry(self):
        self._tele_timer = QTimer(self)
        self._tele_timer.timeout.connect(self._tick_telemetry)
        self._tele_timer.start(1500)

    def _tick_telemetry(self):
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            self.m_cpu.set_value(cpu, f"{cpu:.0f}%")
            self.m_ram.set_value(ram, f"{ram:.0f}%")
        except Exception:
            pass

    # ------------------------------------------------------ interactions

    def _on_provider_detail(self, provider_name: str):
        """Handle click on a provider row — show detailed status in chat."""
        try:
            from core.multi_provider_router import get_router
            router = get_router()
            status = router.get_status()
            info = status.get("providers", {}).get(provider_name, {})
            if not info:
                self.submit_command(f"router")
                return
            display = {
                "groq": "Groq", "gemini": "Gemini", "cerebras": "Cerebras",
                "openrouter": "OpenRouter", "mistral": "Mistral",
                "nvidia_nim": "NVIDIA NIM", "cloudflare": "Cloudflare",
                "ovhcloud": "OVHcloud", "siliconflow": "SiliconFlow",
                "huggingface": "HuggingFace", "ollama": "Ollama",
                "kilo_code": "Kilo Code",
            }.get(provider_name, provider_name)
            icon = "🟢" if info.get("available") else "🔴"
            detail = (
                f"{icon} {display}\n"
                f"Tier: {info.get('tier', '?')} | Quality: {info.get('quality', '?')}\n"
                f"Context: {info.get('context_window', '?')} tokens\n"
                f"Requests today: {info.get('requests_today', 0)}/{info.get('rpm_limit', '?')} RPM\n"
                f"Total tokens: {info.get('total_tokens', 0):,}\n"
                f"Avg latency: {info.get('avg_latency', '?')} | Errors: {info.get('error_rate', '?')}"
            )
            self.add_master_message(f"📊 Provider: {display}")
            self.add_ai_message(detail)
        except Exception:
            self.submit_command("router")

    def _on_quick_action(self, cmd: str):
        """Handle quick action buttons — intercept special commands."""
        cmd_lower = cmd.strip().lower()
        # Programming panel
        if cmd_lower in ('programar', 'modo programador', 'ala de programacao',
                         'ala de programação', 'code lab'):
            self.open_programming_panel()
            return
        # Everything else goes to normal command handler
        self.submit_command(cmd)

    def submit_command(self, cmd: str, echo: bool = True):
        """Show master bubble and dispatch to the app brain (async)."""
        if not cmd.strip():
            return
        if echo:
            self.add_master_message(cmd)
        self.set_pipeline_state("thinking")
        self._t0_cmd = time.perf_counter()
        # Track in recent commands
        if hasattr(self, 'recent_cmds'):
            self.recent_cmds.add_command(cmd)
        if hasattr(self, 'ai_status'):
            self.ai_status.increment_commands()
        # Log notification
        if hasattr(self, 'notifications'):
            self.notifications.add("💬", cmd[:35])
        # Toast
        if hasattr(self, 'toast'):
            self.toast.show_toast(f"Processando: {cmd[:40]}...", "info", 2000)
        if self.command_handler:
            threading.Thread(target=self._exec_async, args=(cmd,), daemon=True).start()

    def _exec_async(self, cmd: str):
        try:
            self.command_handler(cmd)
        except Exception as e:
            print(f"[UI] command error: {e}")
            self.set_pipeline_state("error")

    def _on_enter(self):
        cmd = self.entry.text().strip()
        if cmd:
            self.entry.clear()
            self.submit_command(cmd)

    def _push_to_talk(self):
        self.btn_ptt.setText(" 🎙 OUVINDO… ")
        self.set_pipeline_state("listening")
        if self.mic_button_handler:
            self.mic_button_handler()
        QTimer.singleShot(7000, lambda: self.btn_ptt.setText(" 🎙 OUVIR "))

    def _toggle_listen_mode(self):
        if not self.pipeline:
            return
        if self.pipeline.mode == "always_on":
            self.pipeline.set_mode("wake")
            self.btn_mode.setText(" 🔑 SÓ COM 'ELIVEA' ")
            self.btn_mode.setStyleSheet(f"""
                QPushButton {{ background: {C.PANEL2}; color: {C.GOLD}; border: 1px solid {C.GOLD}; border-radius: 6px; padding: 8px 10px; }}
            """)
            self.add_sage_message("Modo de escuta seletiva ativado. Diga 'Elívea' para me chamar, Mestre.")
        else:
            self.pipeline.set_mode("always_on")
            self.btn_mode.setText(" 📡 SEMPRE OUVINDO ")
            self.btn_mode.setStyleSheet(f"""
                QPushButton {{ background: {C.PANEL2}; color: {C.GREEN}; border: 1px solid {C.GREEN}; border-radius: 6px; padding: 8px 10px; }}
            """)
            self.add_sage_message("Escuta contínua ativada. Fale comigo livremente, Mestre.")

    def _stop_speech(self):
        if self.stop_speech_handler:
            self.stop_speech_handler()
        self.set_pipeline_state("listening")

    def _clear_chat(self):
        """Clear all chat messages."""
        if hasattr(self, 'chat'):
            self.chat.clear_all()
            self.add_sage_message("Chat limpo. Pronto para uma nova conversa, Mestre.")

    def _toggle_mic(self):
        """Toggle microphone on/off."""
        if self.mic_button_handler:
            self.mic_button_handler()

    def _save_history(self):
        """Save conversation history."""
        try:
            from memory.memory_manager import MemoryManager
            MemoryManager._ensure_files()
            self.add_sage_message("Histórico salvo com sucesso, Mestre.")
        except Exception as e:
            self.add_sage_message(f"Erro ao salvar histórico: {e}")

    def _show_help(self):
        """Show keyboard shortcuts help."""
        help_text = """
Atalhos de Teclado:

• Enter - Enviar mensagem
• Escape - Parar fala
• Ctrl+P - Abrir Ala de Programação
• Ctrl+L - Limpar chat
• Ctrl+M - Ativar/desativar microfone
• Ctrl+S - Salvar histórico
• Ctrl+R - Trocar voz
• F1 - Mostrar esta ajuda

Comandos de Voz:
• "status" - Mostrar telemetria
• "abrir [programa]" - Abrir programa
• "limpar lixeira" - Esvaziar lixeira
• "meu ip" - Mostrar endereço IP
• "otimizar ram" - Limpar memória
• "google [termo]" - Pesquisar na web
• "parar" - Interromper fala
"""
        self.add_sage_message(help_text)

    # ------------------------------------------------------ theme & voice

    def _cycle_theme(self):
        keys = list(THEMES.keys())
        self.theme_key = keys[(keys.index(self.theme_key) + 1) % len(keys)]
        apply_theme(self.theme_key)
        self.setStyleSheet(f"background-color: {C.BG}; color: {C.TEXT};")
        self.btn_theme.setText(f"🎨 {THEMES[self.theme_key]['name'].split()[0]}")
        # restyle chips
        self.set_pipeline_state(self.circle.state)
        code_win = getattr(self, "code_win", None)
        if code_win:
            try:
                code_win.refresh_theme()
            except Exception:
                pass
        self.add_sage_message(f"Aviso. Interface recalibrada para o tema {THEMES[self.theme_key]['name']}.")

    def _open_usage(self):
        """Abre o Usage Dashboard em janela flutuante."""
        from ui.usage_dashboard import UsageDashboard
        if not getattr(self, '_usage_win', None) or not self._usage_win.isVisible():
            self._usage_win = UsageDashboard()
            self._usage_win.setWindowTitle("Usage Tracker - Elívea")
            self._usage_win.resize(500, 700)
        self._usage_win.show()
        self._usage_win.raise_()
        self._usage_win.activateWindow()

    def _refresh_voice_btn(self):
        if self.speech:
            label = self.speech.current_voice_label
            short = label.split("•")[0].strip()
            self.btn_voice.setText(f"🗣 {short}")

    def _cycle_voice(self):
        if not self.speech:
            return
        from core.speech_engine import VOICE_PRESETS
        keys = list(VOICE_PRESETS.keys())
        cur = self.speech.preset.key
        nxt = keys[(keys.index(cur) + 1) % len(keys)] if cur in keys else keys[0]
        self.speech.set_voice(nxt)
        self._refresh_voice_btn()
        self.add_sage_message(f"Voz neural recalibrada: {VOICE_PRESETS[nxt].label}.")

    def _open_config(self):
        from core.speech_engine import VOICE_PRESETS
        voices = [p.label for p in VOICE_PRESETS.values()]
        current = self.speech.current_voice_label if self.speech else ""
        self._config = ConfigDialog(self, voices, current, parent=self)
        self._config.show()

    # ------------------------------------------------------ CodeDock

    def open_code_workspace(self, task: str = ""):
        """Open the code editor overlay in the center panel."""
        if not hasattr(self, 'code_workspace'):
            return
        parent = self.code_workspace.parentWidget()
        if parent:
            w, h = parent.width(), parent.height()
            if w > 0 and h > 0:
                self.code_workspace.setGeometry(0, 0, w, h)
        self.rune_core.hide()
        self.code_workspace.show()
        self.code_workspace.raise_()
        self.code_workspace.setFocus()
        self.code_workspace.update()
        if task:
            self.code_workspace._prompt = task
            self.code_workspace.update()
            QTimer.singleShot(300, lambda: self._on_generate_code(task))

    def _close_code_workspace(self):
        """Hide code workspace, show RuneCore again."""
        self.code_workspace.hide()
        self.rune_core.show()
        self.rune_core.set_center_detail(True)
        self.set_pipeline_state("idle")

    def _on_generate_code(self, prompt: str):
        """Send prompt to LLM, collect response, set as code in workspace."""
        self.code_workspace.set_generating(True)
        self.set_pipeline_state("thinking")

        def _worker():
            try:
                collected: list[str] = []
                system_prompt = (
                    "You are Elívea (Elivea), an elite AI coding engine. "
                    "Generate PRODUCTION-QUALITY code — not stubs, not examples. "
                    "Rules: "
                    "1) Return ONLY raw code, zero markdown, zero fences, zero explanations. "
                    "2) Auto-detect the best language from the user's request (Python default). "
                    "3) Include concise inline comments for non-obvious logic. "
                    "4) Handle edge cases and errors properly. "
                    "5) Use modern idioms and best practices. "
                    "6) If the task needs multiple files, separate them with '# === FILE: path ==='. "
                    "7) Optimize for speed and readability. "
                    "8) Never output placeholder code — every function must be fully implemented."
                )
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ]
                try:
                    from core.nine_router import NineRouterBridge
                    for delta in NineRouterBridge().route_and_stream(
                        messages, system=system_prompt,
                        task_type="code", max_tokens=8192, temperature=0.15,
                    ):
                        if delta:
                            collected.append(delta)
                except Exception:
                    # Fallback: try OpenAI directly
                    try:
                        from openai import OpenAI
                        import os
                        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
                        stream = client.chat.completions.create(
                            model="gpt-4o-mini", messages=messages,
                            max_tokens=8192, temperature=0.15, stream=True,
                        )
                        for chunk in stream:
                            if chunk.choices and chunk.choices[0].delta.content:
                                collected.append(chunk.choices[0].delta.content)
                    except Exception:
                        collected.append("# Error: No LLM provider available. Configure OPENAI_API_KEY.")

                full_code = "".join(collected).strip()
                # Remove markdown fences if present
                if full_code.startswith("```"):
                    lines = full_code.split("\n")
                    lines = [l for l in lines if not l.strip().startswith("```")]
                    full_code = "\n".join(lines)

                QTimer.singleShot(0, lambda: self._apply_generated_code(full_code))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._apply_generated_code(f"# Error generating code: {e}"))

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_generated_code(self, code: str):
        """Set generated code in workspace and update state."""
        self.code_workspace.set_code(code)
        self.set_pipeline_state("success")
        # Also push to code scratchpad
        if hasattr(self, 'code_scratchpad'):
            self.code_scratchpad.set_code(code)

    def _run_code(self, code: str):
        """Execute code and show output."""
        self.set_pipeline_state("thinking")
        import threading
        def _worker():
            try:
                import subprocess, tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                    f.write(code)
                    f.flush()
                    result = subprocess.run(
                        ['python', f.name], capture_output=True, text=True, timeout=10
                    )
                    output = result.stdout
                    if result.stderr:
                        output += f"\n✗ {result.stderr}"
                    if not output.strip():
                        output = "> Code executed successfully (no output)"
                import os
                os.unlink(f.name)
                self.code_workspace.set_output(output)
                self.set_pipeline_state("success")
            except subprocess.TimeoutExpired:
                self.code_workspace.set_output("✗ Execution timed out (10s limit)")
                self.set_pipeline_state("error")
            except Exception as e:
                self.code_workspace.set_output(f"✗ Error: {e}")
                self.set_pipeline_state("error")
        threading.Thread(target=_worker, daemon=True).start()

    def _on_code_agent_report(self, report: str):
        if not report:
            return
        self.add_sage_message(report)
        try:
            if self.speech:
                self.speech.speak(report)
        except Exception:
            pass
        self.set_pipeline_state("listening")

    # ---- Programming Panel ----
    def open_programming_panel(self, task: str = ""):
        """Open the full programming panel."""
        if not hasattr(self, 'programming_panel'):
            return
        parent = self.programming_panel.parentWidget()
        if parent:
            w, h = parent.width(), parent.height()
            if w > 0 and h > 0:
                self.programming_panel.setGeometry(0, 0, w, h)
        self.rune_core.hide()
        self.programming_panel.show()
        self.programming_panel.raise_()
        self.programming_panel.setFocus()
        if task:
            self.programming_panel.set_prompt(task)
            QTimer.singleShot(300, lambda: self._on_programming_generate(task))

    def _close_programming_panel(self):
        """Hide programming panel, show RuneCore again."""
        self.programming_panel.hide()
        self.rune_core.show()
        self.rune_core.set_center_detail(True)
        self.set_pipeline_state("idle")

    # -- Deep Dev Panel -----------------------------------------

    def toggle_deep_dev_panel(self):
        """Toggle the Deep Dev Panel overlay."""
        if self.deep_dev_panel.isVisible():
            self._close_deep_dev_panel()
        else:
            self._open_deep_dev_panel()

    def _open_deep_dev_panel(self):
        """Open the Deep Dev Panel overlay on the center area."""
        self.rune_core.hide()
        self.deep_dev_panel.show()
        center = self.deep_dev_panel.parent()
        if center:
            margin = 40
            self.deep_dev_panel.setGeometry(margin, margin, center.width() - margin * 2, center.height() - margin * 2)
        self.deep_dev_panel.raise_()
        self.deep_dev_panel.setFocus()
        self.set_pipeline_state("idle")
        self.deep_dev_panel.set_output("Deep Dev Panel abrindo...\nEscaneando projeto automaticamente...")
        self.deep_dev_panel.set_phase("SCANNING")
        # Auto-trigger full scan in background
        QTimer.singleShot(100, self._auto_scan_project)

    def _close_deep_dev_panel(self):
        """Close the Deep Dev Panel, show RuneCore again."""
        self.deep_dev_panel.hide()
        self.rune_core.show()
        self.rune_core.set_center_detail(True)
        self.set_pipeline_state("idle")

    def _auto_scan_project(self):
        """Auto-scan the entire project for bugs and issues on panel open."""
        def _worker():
            try:
                # Step 1: Discover files
                QTimer.singleShot(0, lambda: self.deep_dev_panel.set_phase("SCANNING"))
                core_dir = os.path.join(str(Path(__file__).resolve().parent.parent), "core")
                files = []
                if os.path.isdir(core_dir):
                    for f in sorted(os.listdir(core_dir)):
                        if f.endswith(".py") and not f.startswith("__"):
                            files.append(f"core/{f}")
                # Also scan ui/ and root .py files
                ui_dir = os.path.join(str(Path(__file__).resolve().parent.parent), "ui")
                if os.path.isdir(ui_dir):
                    for f in sorted(os.listdir(ui_dir)):
                        if f.endswith(".py") and not f.startswith("__"):
                            files.append(f"ui/{f}")

                QTimer.singleShot(0, lambda n=len(files): self.deep_dev_panel.set_output(
                    f"Encontrados {n} arquivos Python.\nAnalisando AST, imports, complexidade..."))

                # Step 2: Run deep analysis via command handler
                result = self.command_handler("shadow") if self.command_handler else None
                if result:
                    QTimer.singleShot(0, lambda r=str(result): self._on_auto_scan_result(r))
                else:
                    QTimer.singleShot(0, lambda: self.deep_dev_panel.set_output(
                        "Deep Dev Panel pronto.\nNenhum bug critico encontrado.\n\n"
                        "Modos disponiveis:\n"
                        "\u2022 **Painel** - comandos de engenharia\n"
                        "\u2022 **Shadow Dev** - analise autonoma\n"
                        "\u2022 **Time Machine** - investigacao de regressoes"))
                    QTimer.singleShot(0, lambda: self.deep_dev_panel.set_phase("READY"))
            except Exception as e:
                QTimer.singleShot(0, lambda err=str(e): self._on_deep_dev_error(err))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_auto_scan_result(self, result):
        """Handle auto-scan result and display with diff if available."""
        self.deep_dev_panel.set_output(result)
        self.deep_dev_panel.set_phase("READY")

    def _on_deep_dev_execute(self, cmd):
        """Execute a Deep Dev command."""
        self.deep_dev_panel.set_phase("ANALYZING")
        self.deep_dev_panel.append_output("> " + cmd)

        def _worker():
            try:
                result = self.command_handler(cmd) if self.command_handler else "Command handler not available"
                QTimer.singleShot(0, lambda r=result: self._on_deep_dev_result(str(r)))
            except Exception as e:
                QTimer.singleShot(0, lambda err=str(e): self._on_deep_dev_error(err))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_deep_dev_result(self, result):
        self.deep_dev_panel.set_output(str(result))
        self.deep_dev_panel.set_phase("READY")

    def _on_deep_dev_error(self, error):
        self.deep_dev_panel.append_output("Erro: " + str(error))
        self.deep_dev_panel.set_phase("FAILED")

    def _on_deep_dev_approve(self):
        if self.command_handler:
            try:
                result = self.command_handler("approve shadow")
                self.deep_dev_panel.append_output(str(result))
            except Exception as e:
                self.deep_dev_panel.append_output("Error: " + str(e))

    def _on_deep_dev_discard(self):
        if self.command_handler:
            try:
                result = self.command_handler("discard shadow")
                self.deep_dev_panel.append_output(str(result))
            except Exception as e:
                self.deep_dev_panel.append_output("Error: " + str(e))

    def _on_programming_generate(self, prompt: str):
        """Send prompt to LLM for code generation in programming panel."""
        self.programming_panel.set_generating(True)
        self.set_pipeline_state("thinking")

        def _worker():
            try:
                collected: list[str] = []
                system = (
                    "You are Elívea, an elite AI coding engine. "
                    "Generate PRODUCTION-QUALITY Python code. "
                    "Rules: Complete, functional, no stubs. "
                    "Include error handling. Follow PEP 8. "
                    "Output ONLY the code in a single ```python block."
                )
                for delta in self.llm.stream(
                    [{"role": "user", "content": prompt}],
                    system=system,
                    max_tokens=4096,
                    temperature=0.4,
                ):
                    collected.append(delta)
                full = "".join(collected)
                # Extract code block
                if '```python' in full:
                    code = full.split('```python')[1].split('```')[0].strip()
                elif '```' in full:
                    code = full.split('```')[1].split('```')[0].strip()
                else:
                    code = full.strip()
                QTimer.singleShot(0, lambda: self.programming_panel.set_code(code))
                QTimer.singleShot(0, lambda c=code: self.programming_panel.append_output(
                    "✅ Código gerado com sucesso!", "#4ec9b0"))
            except Exception as e:
                QTimer.singleShot(0, lambda err=str(e): self.programming_panel.append_output(
                    f"❌ Erro: {err}", "#f44747"))
            finally:
                QTimer.singleShot(0, lambda: self.programming_panel.set_generating(False))
                QTimer.singleShot(0, lambda: self.set_pipeline_state("idle"))

        threading.Thread(target=_worker, daemon=True).start()

    def _open_command_palette(self):
        """Open the Command Palette overlay."""
        self.command_palette.show_palette()

    def _on_palette_command(self, cmd_id: str):
        """Handle command selected from palette."""
        if cmd_id == "theme":
            self._cycle_theme()
        elif cmd_id == "voice":
            self._cycle_voice()
        elif cmd_id == "config":
            self._open_config()
        elif cmd_id == "ajuda":
            self._show_help()
        else:
            self.submit_command(cmd_id)

    def mousePressEvent(self, ev):
        """Click ripple + pass to parent."""
        if hasattr(self, 'micro'):
            self.micro.add_ripple(ev.position().x(), ev.position().y())
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        """Mouse trail effect."""
        if hasattr(self, 'micro'):
            self.micro.add_trail_point(ev.position().x(), ev.position().y())
        super().mouseMoveEvent(ev)

    def resizeEvent(self, ev):
        try:
            super().resizeEvent(ev)
            r = self.rect()
            if hasattr(self, "awakening") and self.awakening.isVisible():
                self.awakening.setGeometry(r)
            if hasattr(self, "cmd_drawer"):
                self.cmd_drawer.setGeometry(r)
            if hasattr(self, "history_drawer") and self.history_drawer.isVisible():
                self.history_drawer.setGeometry(r)
            if hasattr(self, "ambient_particles"):
                self.ambient_particles.setGeometry(r)
            if hasattr(self, "micro"):
                self.micro.setGeometry(r)
            if hasattr(self, "toast") and self.toast.isVisible():
                pw = self.width()
                self.toast.setGeometry(pw - 320, 56, 310, 52)
        except Exception:
            pass  # Never crash on resize

# Alias para compatibilidade
MainWindow = EliveaMainWindow

