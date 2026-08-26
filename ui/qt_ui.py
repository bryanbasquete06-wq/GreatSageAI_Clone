"""
Great Sage AI — Tensura Holographic Interface (＜大贤者＞)
==========================================================
Interface inspirada no anime "Tensei Shitara Slime Daitaiken" (Tensura):

  • Círculo mágico do Grande Sábio: anel de runas rotativo, arcos
    contrarrotativos, heptagrama de Raphael e núcleo pulsante
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
        name="Tensura Dourado ＜大贤者＞",
        BG="#060913", PANEL="#131008", PANEL2="#1d180c", GHOST="#332708",
        BORDER="#5c4708", BORDER_B="#a8801c", BORDER_A="#7a5e10",
        PRI="#ffd24a", ACC="#ffedb0", ACC2="#f5a623", GOLD="#ffe27a",
        GREEN="#7dff9e", RED="#ff4d6d", TEXT="#fff3d6", TEXT_DIM="#9d8a5a",
        TEXT_MED="#e0c98a", WHITE="#ffffff",
    ),
    "tensura": dict(
        name="Tensura Blue ＜大贤者＞",
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
        app_name = "GreatSageAI_Raphael"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        if enable:
            app_script = Path(__file__).resolve().parent.parent / "great_sage_app.py"
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
# ＜大贤者＞ Magic Circle — the centerpiece
# ===========================================================================

RUNES = list("ᚠᚢᚦᚨᚱᚲᚷᚹᚺᚾᛁᛃᛇᛈᛉᛊᛏᛒᛖᛗᛚᛜᛞᛟ")


class MagicCircleWidget(QWidget):
    """Great Sage magic circle: rune ring, counter-rotating arcs, heptagram,
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

        # ---- heptagram (7/3 star) — Raphael's sigil
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

        # ---- title ＜大贤者＞
        p.setPen(QPen(qcol(C.ACC, 235), 1))
        p.setFont(font_cjk(17))
        p.drawText(QRectF(0, cy + R * 1.02, W, 30), Qt.AlignmentFlag.AlignCenter, "＜大贤者＞")
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
            self.lbl_header.setText("『Great Sage』 ＜大贤者＞")
            self.lbl_header.setStyleSheet(f"color: {C.PRI}; background: transparent; border: none;")
            self.lbl_body.setStyleSheet(f"color: {C.TEXT}; background: transparent; border: none;")
        else:
            try:
                from GreatSageAI_Clone.core.persona import _load_user_name
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

BOOT_LINES = [
    "＜大贤者＞ GREAT SAGE AI — RAPHAEL CLASS v3.0",
    "",
    "▶ Núcleo neural ........................ ONLINE",
    "▶ Síntese de voz neural ............... ONLINE",
    "▶ Pipeline de áudio unificado .......... ONLINE",
    "▶ Whisper V3 Turbo (STT) .............. ONLINE",
    "▶ Conversor de voz (Gisele Vechin) ..... ONLINE",
    "▶ Memória do usuário ................. CARREGADA",
    "▶ Módulos de automação ............... CARREGADOS",
    "▶ Agente de código inteligente ........ ONLINE",
    "▶ Motor de busca DuckDuckGo ........... ONLINE",
    "▶ Otimizador de performance ........... ONLINE",
    "",
    "＜大贤者＞ Todos os sistemas operacionais.",
    "＜大贤者＞ Pronta para servir, Mestre.",
]


class BootOverlay(QWidget):
    done = pyqtSignal()

    def __init__(self, parent: None | QWidget):
        super().__init__(parent)
        if parent:
            self.setGeometry(parent.rect())
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        self._lines_shown: list[str] = []
        self._current = ""
        self._line_idx = 0
        self._char_idx = 0
        self._lines_done_at: float | None = None
        self._ring_r = 8.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)

        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(1.0)
        self.setGraphicsEffect(self._effect)

    def _tick(self):
        # expanding ring on start
        self._ring_r += 14
        if self._line_idx < len(BOOT_LINES):
            line = BOOT_LINES[self._line_idx]
            if self._char_idx < len(line):
                self._char_idx += 2
                self._current = line[:self._char_idx]
            else:
                self._lines_shown.append(line)
                self._current = ""
                self._line_idx += 1
                self._char_idx = 0
                if self._line_idx >= len(BOOT_LINES):
                    self._lines_done_at = time.time()
        elif time.time() - (self._lines_done_at or time.time()) > 1.3:
            self._timer.stop()
            self.done.emit()
            return
        self.update()

    def fade_out(self):
        anim = QPropertyAnimation(self._effect, b"opacity", self)
        anim.setDuration(700)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        anim.finished.connect(self.hide)
        anim.start()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        p.fillRect(self.rect(), qcol(C.BG))

        # expanding startup rings
        cx, cy = W / 2, H * 0.40
        for i in range(4):
            r = (self._ring_r - i * 80) % (min(W, H) * 0.85)
            if r > 4:
                alpha = max(0, 140 - int(r * 0.35))
                p.setPen(QPen(qcol(C.PRI, alpha), 1.5))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # ＜大贤者＞ emblem
        p.setPen(QPen(qcol(C.ACC, 245), 1))
        p.setFont(font_cjk(32))
        p.drawText(QRectF(0, cy - 140, W, 60), Qt.AlignmentFlag.AlignCenter, "＜大贤者＞")
        p.setFont(font_mono(10))
        p.setPen(QPen(qcol(C.PRI, 220), 1))
        p.drawText(QRectF(0, cy - 80, W, 20), Qt.AlignmentFlag.AlignCenter, "GREAT SAGE AI — RAPHAEL CLASS")

        # typed boot log
        log = self._lines_shown + ([self._current + "▊"] if self._current or self._line_idx < len(BOOT_LINES) else [])
        p.setFont(font_mono(9))
        y = cy
        for line in log[-9:]:
            is_final = line.startswith("＜")
            is_blank = line.strip() == ""
            if is_blank:
                y += 8
                continue
            p.setPen(QPen(qcol(C.ACC if is_final else C.TEXT_MED, 240), 1))
            p.drawText(QRectF(W / 2 - 320, y, 640, 18), Qt.AlignmentFlag.AlignLeft, line)
            y += 19

    def mousePressEvent(self, _):
        # click to skip boot
        self._timer.stop()
        self.done.emit()


# ===========================================================================
# Config dialog
# ===========================================================================

class ConfigDialog(QWidget):
    def __init__(self, main_win, voices: list[str], current_voice: str, parent=None):
        super().__init__(parent)
        self.main_win = main_win
        self.setWindowTitle("Configurações — Great Sage AI")
        self.resize(560, 420)
        self.setStyleSheet(f"background-color: {C.PANEL}; color: {C.TEXT};")

        lay = QVBoxLayout(self)
        title = QLabel("⚙ CONFIGURAÇÕES DO GRANDE SÁBIO")
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
        lbl2 = QLabel("🗣 VOZ NEURAL DO GRANDE SÁBIO")
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

class GreatSageMainWindow(QMainWindow):
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

        self.theme_key = "tensura_gold"
        self._stream_bubble: ChatBubble | None = None
        self._t0_cmd = 0.0
        self._real_exit = False

        self.setWindowTitle("＜大贤者＞ Great Sage AI — Raphael • Gisele Vechin [by: bryan]")
        self.resize(1180, 780)
        self.setMinimumSize(940, 640)
        self.setStyleSheet(f"background-color: {C.BG}; color: {C.TEXT};")

        self._build_ui()
        self._start_telemetry()

        # Boot overlay
        self.boot = BootOverlay(self)
        self.boot.done.connect(self._on_boot_done)
        self.boot.show()
        self.boot.raise_()

        # Raphael companion orb (visible when the window leaves the screen)
        from GreatSageAI_Clone.ui.orb_widget import RaphaelOrb
        self.orb = RaphaelOrb(self)

    # ------------------------------------------------------------------- UI

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # ============ HEADER ============
        hdr = QHBoxLayout()
        emblem = QLabel("＜大贤者＞")
        emblem.setFont(font_cjk(17))
        emblem.setStyleSheet(f"color: {C.ACC}; background: transparent;")
        hdr.addWidget(emblem)

        title = QLabel("GREAT SAGE AI")
        title.setFont(font_mono(15))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        hdr.addWidget(title)

        by = QLabel("[by: bryan]")
        by.setFont(font_mono(9))
        by.setStyleSheet(f"color: {C.GOLD}; background: transparent;")
        hdr.addWidget(by)
        hdr.addStretch()

        # status chips
        self.chip_state = StatusChip("◉", "EM ESPERA", C.TEXT_DIM)
        self.chip_stt = StatusChip("🎙", "STT —")
        self.chip_ttft = StatusChip("⚡", "TTFT —")
        self.chip_model = StatusChip("◈", "LLM —")
        hdr.addWidget(self.chip_state)
        hdr.addWidget(self.chip_stt)
        hdr.addWidget(self.chip_ttft)
        hdr.addWidget(self.chip_model)

        self.btn_theme = QPushButton("🎨 Tema")
        self.btn_voice = QPushButton("🗣 Voz")
        self.btn_config = QPushButton("⚙")
        for b, w in [(self.btn_theme, 90), (self.btn_voice, 200), (self.btn_config, 34)]:
            b.setFont(font_mono(8))
            b.setFixedWidth(w)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{ background: {C.PANEL2}; color: {C.PRI}; border: 1px solid {C.BORDER_B}; border-radius: 5px; }}
                QPushButton:hover {{ background: {C.GHOST}; border: 1px solid {C.PRI}; }}
            """)
            hdr.addWidget(b)
        self.btn_theme.clicked.connect(self._cycle_theme)
        self.btn_voice.clicked.connect(self._cycle_voice)
        self.btn_config.clicked.connect(self._open_config)
        self._refresh_voice_btn()

        root.addLayout(hdr)

        # ============ BODY ============
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {C.PANEL}; }}")

        # ---- left: magic circle + telemetry
        left = QWidget()
        llay = QVBoxLayout(left)
        llay.setContentsMargins(0, 0, 0, 0)
        llay.setSpacing(6)

        self.circle = MagicCircleWidget()
        llay.addWidget(self.circle, stretch=5)

        self.waveform = WaveformWidget()
        llay.addWidget(self.waveform)

        metrics = QHBoxLayout()
        self.m_cpu = MetricBar("CPU")
        self.m_ram = MetricBar("RAM")
        self.m_mic = MetricBar("MIC", color=None)
        for m in (self.m_cpu, self.m_ram, self.m_mic):
            metrics.addWidget(m)
        llay.addLayout(metrics)
        splitter.addWidget(left)

        # ---- right: chat + quick actions
        right = QWidget()
        rlay = QVBoxLayout(right)
        rlay.setContentsMargins(0, 0, 0, 0)
        rlay.setSpacing(8)

        self.chat = ChatFlow()
        rlay.addWidget(self.chat, stretch=1)

        quick = QHBoxLayout()
        quick_btns = [
            ("⚡ Status", "status"),
            ("📡 Meu IP", "meu ip"),
            ("💾 Discos", "meus discos"),
            ("🚀 RAM", "otimizar ram"),
            ("🧹 Lixeira", "limpar lixeira"),
            ("📸 Print", "capturar tela"),
            ("📝 Notas", "minhas notas"),
            ("🕐 Hora", "que horas são"),
            ("🧹 Chat", "limpar conversa"),
            ("❓ Ajuda", "ajuda"),
            ("⌨️ Programar", "programar"),
        ]
        for name, cmd in quick_btns:
            b = QPushButton(name)
            b.setFont(font_mono(8))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip(cmd)
            b.setStyleSheet(f"""
                QPushButton {{ background: {C.PANEL2}; color: {C.PRI}; border: 1px solid {C.BORDER}; border-radius: 5px; padding: 6px 4px; }}
                QPushButton:hover {{ background: {C.GHOST}; border: 1px solid {C.PRI}; color: {C.ACC}; }}
            """)
            b.clicked.connect(lambda _, c=cmd: self.submit_command(c))
            quick.addWidget(b)
        rlay.addLayout(quick)
        splitter.addWidget(right)
        splitter.setSizes([470, 660])
        root.addWidget(splitter, stretch=1)

        # ============ INPUT ROW ============
        inp = QHBoxLayout()

        self.btn_ptt = QPushButton(" 🎙 OUVIR ")
        self.btn_ptt.setFont(font_mono(9))
        self.btn_ptt.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ptt.setStyleSheet(f"""
            QPushButton {{ background: {C.PANEL2}; color: {C.ACC}; border: 1px solid {C.PRI}; border-radius: 6px; padding: 8px 12px; }}
            QPushButton:hover {{ background: {C.GHOST}; }}
        """)
        self.btn_ptt.clicked.connect(self._push_to_talk)
        inp.addWidget(self.btn_ptt)

        self.btn_mode = QPushButton(" 📡 SEMPRE OUVINDO ")
        self.btn_mode.setFont(font_mono(9))
        self.btn_mode.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode.setStyleSheet(f"""
            QPushButton {{ background: {C.PANEL2}; color: {C.GREEN}; border: 1px solid {C.GREEN}; border-radius: 6px; padding: 8px 10px; }}
            QPushButton:hover {{ background: {C.GHOST}; }}
        """)
        self.btn_mode.clicked.connect(self._toggle_listen_mode)
        inp.addWidget(self.btn_mode)

        self.btn_stop = QPushButton(" 🛑 CALAR ")
        self.btn_stop.setFont(font_mono(9))
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.setStyleSheet(f"""
            QPushButton {{ background: {C.PANEL2}; color: {C.RED}; border: 1px solid {C.RED}; border-radius: 6px; padding: 8px 10px; }}
            QPushButton:hover {{ background: {C.RED}; color: {C.WHITE}; }}
        """)
        self.btn_stop.clicked.connect(self._stop_speech)
        inp.addWidget(self.btn_stop)

        prompt_lbl = QLabel("Mestre ➤")
        prompt_lbl.setFont(font_mono(10))
        prompt_lbl.setStyleSheet(f"color: {C.GOLD};")
        inp.addWidget(prompt_lbl)

        self.entry = QLineEdit()
        self.entry.setFont(font_ui(11))
        self.entry.setPlaceholderText("Fale com o Grande Sábio ou digite aqui… (Enter envia • Esc cala a voz)")
        self.entry.setStyleSheet(f"""
            QLineEdit {{
                background: {C.PANEL}; color: {C.WHITE};
                border: 1px solid {C.BORDER_B}; border-radius: 6px; padding: 8px 12px;
                font-size: 13px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        self.entry.returnPressed.connect(self._on_enter)
        inp.addWidget(self.entry, stretch=1)

        send = QPushButton("EXECUTAR ➤")
        send.setFont(font_mono(9))
        send.setCursor(Qt.CursorShape.PointingHandCursor)
        send.setStyleSheet(f"""
            QPushButton {{ background: {C.PRI}; color: {C.BG}; border: none; border-radius: 6px; padding: 8px 16px; font-weight: bold; }}
            QPushButton:hover {{ background: {C.ACC}; }}
        """)
        send.clicked.connect(self._on_enter)
        inp.addWidget(send)

        root.addLayout(inp)

        # Atalhos — compatível PySide6/PyQt6
        try:
            from PySide6.QtGui import QShortcut, QKeySequence
        except ImportError:
            from PyQt6.QtGui import QShortcut, QKeySequence
        QShortcut(QKeySequence("Escape"), self).activated.connect(self._stop_speech)
        QShortcut(QKeySequence("Ctrl+P"), self).activated.connect(lambda: self.open_code_workspace())
        QShortcut(QKeySequence("Ctrl+L"), self).activated.connect(self._clear_chat)
        QShortcut(QKeySequence("Ctrl+M"), self).activated.connect(self._toggle_mic)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._save_history)
        QShortcut(QKeySequence("Ctrl+R"), self).activated.connect(self._cycle_voice)
        QShortcut(QKeySequence("F1"), self).activated.connect(self._show_help)

    # ------------------------------------------------------------ boot

    def _on_boot_done(self):
        self.boot.fade_out()
        try:
            from GreatSageAI_Clone.core.persona import _load_user_name
            user = _load_user_name()
        except Exception:
            user = "Mestre"
        self.add_sage_message(
            f"Grande Sábio online, {user}. Todos os sistemas nominais. "
            "Pode falar comigo naturalmente — estou te ouvindo."
        )

    # -------------------------------------------------- window ↔ orb modes

    def changeEvent(self, ev):
        if ev.type() == QEvent.Type.WindowStateChange and self.isMinimized():
            QTimer.singleShot(0, self._hide_to_orb)
        super().changeEvent(ev)

    def closeEvent(self, ev):
        if not self._real_exit:
            ev.ignore()
            self._hide_to_orb()
            return
        self.orb.hide()
        super().closeEvent(ev)

    def _hide_to_orb(self):
        """Minimizar/fechar → o Raphael vira o orbe flutuante do anime."""
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
        bubble = self.chat.add_bubble("master", int(self.chat.width() * 0.8))
        bubble.set_text(text)

    def add_sage_message(self, text: str):
        bubble = self.chat.add_bubble("sage", int(self.chat.width() * 0.85))
        bubble.type_in(text)
        return bubble

    def begin_sage_stream(self):
        self._stream_bubble = self.chat.add_bubble("sage", int(self.chat.width() * 0.85))

    def append_sage_stream(self, delta: str):
        if self._stream_bubble:
            self._stream_bubble.stream_append(delta)
            sb = self.chat.verticalScrollBar()
            if sb.maximum() - sb.value() < 140:
                sb.setValue(sb.maximum())

    def end_sage_stream(self):
        if self._stream_bubble:
            self._stream_bubble.stream_end()
            self._stream_bubble = None

    # ------------------------------------------------------ state/telemetry

    def set_pipeline_state(self, state: str):
        # state: idle | listening | thinking | speaking
        self.circle.set_state(state)
        self.waveform.set_state(state)
        icons = {"idle": ("EM ESPERA", C.TEXT_DIM),
                 "listening": ("ESCUTANDO", C.GREEN),
                 "thinking": ("PROCESSANDO", C.GOLD),
                 "speaking": ("FALANDO", C.PRI)}
        icon, col = icons.get(state, ("EM ESPERA", C.TEXT_DIM))
        self.chip_state.set_value(icon, col)
        if self.orb.isVisible():
            self.orb.set_state(state)

    def update_mic_rms(self, rms: float):
        try:
            self.circle.push_rms(rms)
            self.waveform.push_rms(rms)
            self.orb.push_rms(rms)
            val = min(100.0, (rms / 260.0) * 100.0)
            self.m_mic.set_value(val, f"{rms:.0f}")
        except Exception:
            pass

    def update_telemetry(self, stt_engine: str, stt_ms: int, model: str, ttft_ms: int):
        self.chip_stt.set_value(f"STT {stt_engine} {stt_ms}ms")
        self.chip_model.set_value(f"LLM {model.split('-')[0]}")
        self.chip_ttft.set_value(f"TTFT {ttft_ms}ms", C.GREEN if ttft_ms and ttft_ms < 1500 else C.GOLD)

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

    def submit_command(self, cmd: str, echo: bool = True):
        """Show master bubble and dispatch to the app brain (async)."""
        if not cmd.strip():
            return
        if echo:
            self.add_master_message(cmd)
        self.set_pipeline_state("thinking")
        self._t0_cmd = time.perf_counter()
        if self.command_handler:
            threading.Thread(target=self._exec_async, args=(cmd,), daemon=True).start()

    def _exec_async(self, cmd: str):
        try:
            self.command_handler(cmd)
        except Exception as e:
            print(f"[UI] command error: {e}")

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
            self.btn_mode.setText(" 🔑 SÓ COM 'GRANDE SÁBIO' ")
            self.btn_mode.setStyleSheet(f"""
                QPushButton {{ background: {C.PANEL2}; color: {C.GOLD}; border: 1px solid {C.GOLD}; border-radius: 6px; padding: 8px 10px; }}
            """)
            self.add_sage_message("Modo de escuta seletiva ativado. Diga 'Grande Sábio' para me chamar, Mestre.")
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
            from GreatSageAI_Clone.memory.memory_manager import MemoryManager
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

    def _refresh_voice_btn(self):
        if self.speech:
            label = self.speech.current_voice_label
            short = label.split("•")[0].strip()
            self.btn_voice.setText(f"🗣 {short}")

    def _cycle_voice(self):
        if not self.speech:
            return
        from GreatSageAI_Clone.core.speech_engine import VOICE_PRESETS
        keys = list(VOICE_PRESETS.keys())
        cur = self.speech.preset.key
        nxt = keys[(keys.index(cur) + 1) % len(keys)] if cur in keys else keys[0]
        self.speech.set_voice(nxt)
        self._refresh_voice_btn()
        self.add_sage_message(f"Voz neural recalibrada: {VOICE_PRESETS[nxt].label}.")

    def _open_config(self):
        from GreatSageAI_Clone.core.speech_engine import VOICE_PRESETS
        voices = [p.label for p in VOICE_PRESETS.values()]
        current = self.speech.current_voice_label if self.speech else ""
        self._config = ConfigDialog(self, voices, current, parent=self)
        self._config.show()

    # ------------------------------------------------------ CodeDock

    def open_code_workspace(self, task: str = ""):
        """Abre (ou traz à frente) a Ala de Programação — estilo Cursor/ZCode."""
        from GreatSageAI_Clone.ui.code_workspace import CodeWorkspaceWindow
        if not getattr(self, "code_win", None):
            self.code_win = CodeWorkspaceWindow(llm=self.llm, parent=self)
            self.code_win.report_signal.connect(self._on_code_agent_report)
            self.code_win.destroyed.connect(lambda _: setattr(self, "code_win", None))
        self.code_win.show()
        self.code_win.raise_()
        self.code_win.activateWindow()
        if isinstance(task, str) and task.strip():
            self.code_win.run_task(task.strip())

    def _on_code_agent_report(self, report: str):
        """Relatório final do agente chega ao chat principal (e à voz)."""
        if not report:
            return
        self.add_sage_message(report)
        try:
            if self.speech:
                self.speech.speak(report)
        except Exception:
            pass
        self.set_pipeline_state("listening")

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if hasattr(self, "boot") and self.boot.isVisible():
            self.boot.setGeometry(self.rect())

# Alias para compatibilidade
MainWindow = GreatSageMainWindow

