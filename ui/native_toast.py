# -*- coding: utf-8 -*-
"""Toast notifications customizadas do Great Sage AI."""
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve

import logging

logger = logging.getLogger("greatsage.toast")

class ToastNotification(QWidget):
    _instance = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._container = QWidget()
        self._container.setStyleSheet("QWidget { background: #131008; border: 1px solid #5c4708; border-radius: 10px; }")
        inner = QVBoxLayout(self._container)
        inner.setContentsMargins(14, 10, 14, 10)

        self._title = QLabel()
        self._title.setStyleSheet("color: #ffd24a; font-weight: bold; font-size: 13px; border: none;")
        inner.addWidget(self._title)

        self._message = QLabel()
        self._message.setStyleSheet("color: #fff3d6; font-size: 12px; border: none;")
        self._message.setWordWrap(True)
        inner.addWidget(self._message)

        layout.addWidget(self._container)

        self._opacity = QGraphicsOpacityEffect(self._container)
        self._container.setGraphicsEffect(self._opacity)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)
        self._anim = None

    @classmethod
    def show_toast(cls, title: str, message: str, duration: int = 3000, parent=None):
        if cls._instance is None:
            cls._instance = cls(parent)
        inst = cls._instance
        inst._title.setText(title)
        inst._message.setText(message)
        inst._opacity.setOpacity(1.0)
        if parent:
            geo = parent.geometry()
            inst.move(geo.right() - inst.width() - 20, geo.top() + 20)
        inst.show()
        inst.raise_()
        inst._hide_timer.start(duration)

    def _fade_out(self):
        self._anim = QPropertyAnimation(self._opacity, b"opacity")
        self._anim.setDuration(300)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._anim.finished.connect(self.hide)
        self._anim.start()
