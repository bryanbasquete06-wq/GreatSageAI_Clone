"""
Elívea — Elivea Orb (＜Elivea＞ Flutuante)
===================================================
Esfera de luz flutuante estilo o anime Tensura: quando o Rimuru anda
pelo mundo, o Elívea o acompanha como um orbe brilhante. Aqui, sempre
que a janela principal sai da tela (minimizar/fechar), este orbe assume:

  • Círculo mágico dourado em miniatura (runas, heptagrama, núcleo)
  • Reage em tempo real: escutando / pensando / falando (ondas de voz)
  • Arraste para posicioná-lo em qualquer canto da tela (posição salva)
  • Clique → restaura a janela • Botão direito → menu completo
  • Sempre no topo, sem aparecer na barra de tarefas, ~0% de CPU
"""

from __future__ import annotations

import json
import math
import random
import threading
import time
from collections import deque
from pathlib import Path

try:
    from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
    from PySide6.QtGui import QAction, QBrush, QColor, QFont, QLinearGradient, QPainter, QPen, QRadialGradient
    from PySide6.QtWidgets import QMenu, QWidget
except ImportError:
    from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
    from PyQt6.QtGui import QAction, QBrush, QColor, QFont, QLinearGradient, QPainter, QPen, QRadialGradient
    from PyQt6.QtWidgets import QMenu, QWidget

ORBSIZE = 160
SETTINGS_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.json"
RUNES = list("ᚠᚢᚦᚨᚱᚲᚷᚹᚺᚾᛁᛃᛇᛈᛉᛊᛏᛒᛖᛗᛚᛜᛞᛟ")
RUNES_MIRROR = list("ᛟᛞᛜᛚᛗᛖᛒᛊᛏᛉᛈᛇᛃᛁᚾᚺᚹᚷᚲᚱᚨᚦᚢᚠ")


def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h)
    c.setAlpha(a)
    return c

STATE_INFO = {
    "idle":      dict(rot=0.10, core=1.00, glow=0.55, col=None),
    "listening": dict(rot=0.16, core=1.03, glow=0.75, col=None),
    "thinking":  dict(rot=0.34, core=1.06, glow=0.95, col=None),
    "speaking":  dict(rot=0.52, core=1.18, glow=1.10, col=None),
}


class EliveaOrb(QWidget):
    """Floating companion orb — the Sage's presence outside the main window."""

    def __init__(self, main_window):
        super().__init__(None)
        self.main = main_window
        self._settings_lock = threading.Lock()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(ORBSIZE, ORBSIZE)
        self.setToolTip("＜Elivea＞ Elívea — clique para abrir, botão direito para o menu")

        self.state = "idle"
        self._t = 0.0
        self._rune_rot = 0.0
        self._rune_rot2 = 0.0
        self._arc_rot = 0.0
        self._star_rot = 0.0
        self._core = 1.0
        self._glow = 0.55
        self._rms_hist = deque([0.0] * 48, maxlen=48)
        self._ripples: list[float] = []
        self._particles: list[list] = []
        self._press_pos = None
        self._dragging = False

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

        self._load_position()

    # ------------------------------------------------------------ lifecycle

    def showEvent(self, ev):
        self._timer.start()
        super().showEvent(ev)

    def hideEvent(self, ev):
        self._timer.stop()
        super().hideEvent(ev)

    # -------------------------------------------------------------- inputs

    def set_state(self, state: str):
        self.state = state if state in STATE_INFO else "idle"

    def push_rms(self, rms: float):
        if self.isVisible():
            self._rms_hist.append(rms)

    # ------------------------------------------------------------ animation

    def _tick(self):
        info = STATE_INFO.get(self.state, STATE_INFO["idle"])
        speaking = self.state == "speaking"
        thinking = self.state == "thinking"
        self._t += 0.033

        self._rune_rot = (self._rune_rot + info["rot"]) % 360
        self._rune_rot2 = (self._rune_rot2 - info["rot"] * 0.6) % 360
        self._arc_rot = (self._arc_rot - info["rot"] * 0.7) % 360
        self._star_rot = (self._star_rot + info["rot"] * 0.2) % 360

        if speaking:
            tgt_core, tgt_glow = random.uniform(1.12, 1.28), random.uniform(1.0, 1.2)
            if random.random() < 0.25:
                self._ripples.append(0.0)
        elif thinking:
            tgt_core, tgt_glow = random.uniform(1.04, 1.10), 0.92
        else:
            tgt_core, tgt_glow = info["core"], info["glow"]

        k = 0.28 if speaking else 0.10
        self._core += (tgt_core - self._core) * k
        self._glow += (tgt_glow - self._glow) * k

        self._ripples = [r + 0.022 for r in self._ripples if r + 0.022 < 1.0]

        if len(self._particles) < 18 and random.random() < 0.4:
            ang = random.uniform(0, 2 * math.pi)
            self._particles.append([ang, random.uniform(0.75, 1.0), random.uniform(0.002, 0.005)])
        self._particles = [[a, d - s, s * 1.02] for a, d, s in self._particles if d - s > 0.2]

        self.update()

    # ---------------------------------------------------------------- paint

    def paintEvent(self, _):
        from ui.qt_ui import C

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W = self.width()
        cx, cy = W / 2, W / 2
        R = W * 0.40
        glow = max(0.0, min(1.25, self._glow))
        dim = self.state == "idle"
        base_a = 100 if dim else 180

        # ---- outer soft halo (large, atmospheric)
        halo = QRadialGradient(cx, cy, R * 1.8)
        halo.setColorAt(0.0, QColor(255, 215, 90, int(55 * glow)))
        halo.setColorAt(0.5, QColor(255, 200, 70, int(20 * glow)))
        halo.setColorAt(1.0, QColor(255, 200, 70, 0))
        p.setBrush(QBrush(halo))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - R * 1.8, cy - R * 1.8, R * 3.6, R * 3.6))

        # ---- voice ripples (speaking energy waves)
        for r in self._ripples:
            rr = R * (0.55 + r * 0.95)
            a = int(120 * (1.0 - r))
            p.setPen(QPen(QColor(255, 226, 150, a), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - rr, cy - rr, rr * 2, rr * 2))

        # ---- outer double ring + ticks (symmetric)
        for rr, pen_w, alpha in [(1.05, 1.8, int(base_a * 0.9)), (1.01, 1.0, int(base_a * 0.5))]:
            p.setPen(QPen(qcol(C.ACC, alpha), pen_w))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - R * rr, cy - R * rr, R * rr * 2, R * rr * 2))

        p.setPen(QPen(qcol(C.ACC, int(base_a * 0.6)), 1))
        for i in range(48):
            ang = math.radians(i * 7.5)
            big = i % 6 == 0
            r1 = R * 1.05
            r2 = R * (0.99 if big else 1.015)
            p.drawLine(
                int(cx + r1 * math.cos(ang)), int(cy + r1 * math.sin(ang)),
                int(cx + r2 * math.cos(ang)), int(cy + r2 * math.sin(ang)),
            )

        # ---- inner ring
        p.setPen(QPen(qcol(C.PRI, int(base_a * 0.35)), 0.8))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(cx - R * 0.92, cy - R * 0.92, R * 1.84, R * 1.84))

        # ---- rune ring (outer, clockwise)
        rune_r = R * 0.88
        p.save()
        p.translate(cx, cy)
        p.rotate(self._rune_rot)
        p.setFont(QFont("Microsoft YaHei UI", 6))
        for i, rune in enumerate(RUNES[:20]):
            ang = i * 360 / 20
            p.save()
            p.rotate(ang)
            p.translate(0, -rune_r)
            p.rotate(180)
            alpha = int(base_a * (0.65 + 0.35 * math.sin(self._t * 1.8 + i * 0.5)))
            p.setPen(QPen(qcol(C.ACC, alpha)))
            p.drawText(QRectF(-10, -7, 20, 14), Qt.AlignmentFlag.AlignCenter, rune)
            p.restore()
        p.restore()

        # ---- rune ring 2 (inner, counter-clockwise — symmetry)
        rune_r2 = R * 0.76
        p.save()
        p.translate(cx, cy)
        p.rotate(self._rune_rot2)
        p.setFont(QFont("Microsoft YaHei UI", 5))
        for i, rune in enumerate(RUNES_MIRROR[:16]):
            ang = i * 360 / 16
            p.save()
            p.rotate(ang)
            p.translate(0, -rune_r2)
            p.rotate(180)
            alpha = int(base_a * (0.45 + 0.30 * math.sin(self._t * 1.5 + i * 0.7)))
            p.setPen(QPen(qcol(C.PRI, alpha)))
            p.drawText(QRectF(-8, -6, 16, 12), Qt.AlignmentFlag.AlignCenter, rune)
            p.restore()
        p.restore()

        # ---- counter-rotating HUD arcs (3 layers)
        arc_cfg = [
            (0.68, 2.2, 80, 52, C.PRI),
            (0.58, 1.6, 56, 68, C.ACC2),
            (0.50, 1.2, 36, 84, C.ACC),
        ]
        for r_f, pen_w, arc_len, gap, col in arc_cfg:
            rr = R * r_f
            alpha = int(base_a * min(1.0, glow) * 0.8)
            p.setPen(QPen(qcol(col, alpha), pen_w))
            p.setBrush(Qt.BrushStyle.NoBrush)
            rect = QRectF(cx - rr, cy - rr, rr * 2, rr * 2)
            ang = self._arc_rot
            while ang < self._arc_rot + 360:
                p.drawArc(rect, int(ang * 16), int(arc_len * 16))
                ang += arc_len + gap

        # ---- heptagram sigil (Elivea's star)
        star_r = R * 0.46
        rot = self._star_rot
        pts = []
        for i in range(7):
            a = math.radians(i * (360 / 7) + rot - 90)
            pts.append((cx + star_r * math.cos(a), cy + star_r * math.sin(a)))

        star_alpha = int(190 * min(1.0, glow + 0.15))
        p.setPen(QPen(qcol(C.PRI, star_alpha), 1.6))
        p.setBrush(Qt.BrushStyle.NoBrush)
        path_pts = [pts[0]]
        for k in range(1, 8):
            path_pts.append(pts[(k * 3) % 7])
        try:
            from PySide6.QtGui import QPainterPath
        except ImportError:
            from PyQt6.QtGui import QPainterPath
        star_path = QPainterPath()
        star_path.moveTo(*path_pts[0])
        for pt in path_pts[1:]:
            star_path.lineTo(*pt)
        star_path.closeSubpath()
        p.drawPath(star_path)

        # inner heptagon
        poly_r = star_r * 0.38
        p.setPen(QPen(qcol(C.ACC, int(130 * glow)), 1.0))
        for i in range(7):
            a1 = math.radians(i * (360 / 7) + rot - 90)
            a2 = math.radians((i + 1) * (360 / 7) + rot - 90)
            p.drawLine(
                int(cx + poly_r * math.cos(a1)), int(cy + poly_r * math.sin(a1)),
                int(cx + poly_r * math.cos(a2)), int(cy + poly_r * math.sin(a2)),
            )

        # vertex dots
        for vx, vy in pts:
            p.setBrush(QBrush(qcol(C.ACC, 200)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(vx, vy), 2.2, 2.2)

        # ---- particles drifting inward
        for ang, dist, _ in self._particles:
            px = cx + R * dist * math.cos(ang)
            py = cy + R * dist * math.sin(ang)
            alpha = int(140 * (1.05 - dist))
            p.setPen(QPen(qcol(C.ACC, max(20, alpha)), 1.2))
            p.drawPoint(int(px), int(py))

        # ---- radial voice bars (symmetric)
        n = 48
        for i in range(n):
            rms = self._rms_hist[i] if i < len(self._rms_hist) else 0
            norm = min(1.0, rms / 260.0) * (1.4 if self.state == "listening" else 1.0)
            ln = 1.5 + norm * R * 0.14
            ang = math.radians(i * 360 / n - 90)
            r1 = R * 1.08
            r2 = r1 + ln
            col = QColor(C.GREEN if norm > 0.55 else C.PRI)
            col.setAlpha(int(70 + 170 * norm))
            p.setPen(QPen(col, 1.8))
            p.drawLine(int(cx + r1 * math.cos(ang)), int(cy + r1 * math.sin(ang)),
                       int(cx + r2 * math.cos(ang)), int(cy + r2 * math.sin(ang)))

        # ---- pulsing golden core (multi-layer)
        orb_r = R * 0.30 * self._core

        # outer glow
        glow_r = orb_r * 2.0
        glow_grad = QRadialGradient(cx, cy, glow_r)
        glow_grad.setColorAt(0.0, QColor(255, 220, 100, int(60 * glow)))
        glow_grad.setColorAt(0.6, QColor(255, 200, 60, int(20 * glow)))
        glow_grad.setColorAt(1.0, QColor(255, 200, 60, 0))
        p.setBrush(QBrush(glow_grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2))

        # main core
        grad = QRadialGradient(cx, cy, orb_r * 1.6)
        core_col = QColor(C.GOLD) if self.state == "thinking" else QColor(255, 248, 220)
        grad.setColorAt(0.0, QColor(core_col.red(), core_col.green(), core_col.blue(), int(245 * min(1, glow))))
        grad.setColorAt(0.30, QColor(255, 215, 80, int(210 * min(1, glow))))
        grad.setColorAt(0.65, QColor(255, 195, 45, int(80 * glow)))
        grad.setColorAt(1.0, QColor(255, 195, 45, 0))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - orb_r * 1.6, cy - orb_r * 1.6, orb_r * 3.2, orb_r * 3.2))

        # bright center point
        p.setBrush(QBrush(QColor(255, 255, 248, int(220 * min(1, glow)))))
        p.drawEllipse(QRectF(cx - orb_r * 0.28, cy - orb_r * 0.28, orb_r * 0.56, orb_r * 0.56))

    # ------------------------------------------------------------ mouse I/O

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._press_pos = ev.globalPosition().toPoint()
            self._dragging = False

    def mouseMoveEvent(self, ev):
        if self._press_pos is None:
            return
        gp = ev.globalPosition().toPoint()
        if not self._dragging and (gp - self._press_pos).manhattanLength() > 6:
            self._dragging = True
        if self._dragging:
            self.move(self.pos() + (gp - self._press_pos))
            self._press_pos = gp

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton and not self._dragging:
            if self.main:
                self.main._restore_from_orb()
        elif self._dragging:
            self._save_position()
        self._press_pos = None
        self._dragging = False

    def contextMenuEvent(self, ev):
        from ui.qt_ui import C

        m = QMenu(self)
        m.setStyleSheet(f"""
            QMenu {{ background: {C.PANEL}; color: {C.TEXT}; border: 1px solid {C.BORDER_B};
                     border-radius: 8px; padding: 6px; font-size: 13px; }}
            QMenu::item {{ padding: 6px 24px; border-radius: 5px; }}
            QMenu::item:selected {{ background: {C.GHOST}; color: {C.ACC}; }}
        """)

        states = {"idle": "Em espera", "listening": "Escutando", "thinking": "Processando", "speaking": "Falando"}
        title = QAction(f"＜Elivea＞ {states.get(self.state, '—')}", m)
        title.setEnabled(False)
        m.addAction(title)
        m.addSeparator()

        a_restore = QAction("Restaurar janela", m)
        a_restore.triggered.connect(lambda: self.main and self.main._restore_from_orb())
        m.addAction(a_restore)

        a_stop = QAction("Silenciar fala", m)
        a_stop.triggered.connect(lambda: self.main and self.main._stop_speech())
        m.addAction(a_stop)

        a_mode = QAction("Alternar modo de escuta", m)
        a_mode.triggered.connect(lambda: self.main and self.main._toggle_listen_mode())
        m.addAction(a_mode)

        m.addSeparator()
        a_exit = QAction("Encerrar Elivea", m)
        a_exit.triggered.connect(self._exit_app)
        m.addAction(a_exit)

        m.exec(ev.globalPos())

    def _exit_app(self):
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError:
            from PyQt6.QtWidgets import QApplication
        if self.main:
            self.main._real_exit = True
        QApplication.quit()

    # ----------------------------------------------------------- persistence

    def _save_position(self):
        try:
            with self._settings_lock:
                data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
                data["orb_pos"] = [self.x(), self.y()]
                SETTINGS_PATH.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def _load_position(self):
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            pos = data.get("orb_pos")
            if isinstance(pos, list) and len(pos) == 2:
                x, y = int(pos[0]), int(pos[1])
                screen = self.screen()
                if screen is None:
                    try:
                        from PySide6.QtWidgets import QApplication
                    except ImportError:
                        from PyQt6.QtWidgets import QApplication
                    screen = QApplication.primaryScreen()
                if screen is not None:
                    geo = screen.availableGeometry()
                    if geo.left() - 60 <= x <= geo.right() - 60 and geo.top() <= y <= geo.bottom() - 80:
                        self.move(x, y)
                        return
        except Exception:
            pass
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError:
            from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.right() - ORBSIZE - 28, geo.bottom() - ORBSIZE - 28)
