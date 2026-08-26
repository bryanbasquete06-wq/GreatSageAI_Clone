# -*- coding: utf-8 -*-
"""Sistema de temas — dark/light com toggle ao vivo."""
from typing import Dict, List, Tuple
import json
from pathlib import Path

SETTINGS = Path(__file__).resolve().parent.parent / "config" / "settings.json"

from PySide6.QtGui import QFont

THEMES: Dict[str, dict] = {
    "tensura_gold": dict(
        name="Tensura Dourado",
        BG="#060913", PANEL="#131008", PANEL2="#1d180c", GHOST="#332708",
        BORDER="#5c4708", BORDER_B="#a8801c", BORDER_A="#7a5e10",
        PRI="#ffd24a", ACC="#ffedb0", ACC2="#f5a623", GOLD="#ffe27a",
        GREEN="#7dff9e", RED="#ff4d6d", TEXT="#fff3d6", TEXT_DIM="#9d8a5a",
        TEXT_MED="#e0c98a", WHITE="#ffffff",
    ),
    "tensura": dict(
        name="Tensura Blue",
        BG="#020817", PANEL="#06122b", PANEL2="#0a1c3d", GHOST="#0e2c55",
        BORDER="#0f3a6e", BORDER_B="#1e5fa8", BORDER_A="#16457e",
        PRI="#4fd8ff", ACC="#aef0ff", ACC2="#22b8f0", GOLD="#ffd76a",
        GREEN="#39ff9e", RED="#ff4d6d", TEXT="#dff4ff", TEXT_DIM="#5f88ad",
        TEXT_MED="#9fc9e8", WHITE="#ffffff",
    ),
    "dark": dict(
        name="Dark Professional",
        BG="#1a1a2e", PANEL="#16213e", PANEL2="#0f3460", GHOST="#1a1a4e",
        BORDER="#e94560", BORDER_B="#ff6b6b", BORDER_A="#ee5a5a",
        PRI="#e94560", ACC="#ff6b6b", ACC2="#ff4757", GOLD="#ffa502",
        GREEN="#2ed573", RED="#ff4757", TEXT="#ffffff", TEXT_DIM="#747d8c",
        TEXT_MED="#a4b0be", WHITE="#ffffff",
    ),
    "matrix": dict(
        name="Matrix Green",
        BG="#000000", PANEL="#001100", PANEL2="#002200", GHOST="#003300",
        BORDER="#00ff00", BORDER_B="#00cc00", BORDER_A="#009900",
        PRI="#00ff00", ACC="#00ff00", ACC2="#00cc00", GOLD="#00ff00",
        GREEN="#00ff00", RED="#ff0000", TEXT="#00ff00", TEXT_DIM="#007700",
        TEXT_MED="#009900", WHITE="#ffffff",
    ),
    "light": dict(
        name="Light Professional",
        BG="#f5f5f5", PANEL="#ffffff", PANEL2="#e8e8e8", GHOST="#d0d0d0",
        BORDER="#b0b0b0", BORDER_B="#888888", BORDER_A="#999999",
        PRI="#2196F3", ACC="#64B5F6", ACC2="#1976D2", GOLD="#FFC107",
        GREEN="#4CAF50", RED="#F44336", TEXT="#212121", TEXT_DIM="#757575",
        TEXT_MED="#424242", WHITE="#ffffff",
    ),
}

class ThemeManager:
    _current = "tensura_gold"
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_saved()
        return cls._instance

    def _load_saved(self):
        try:
            if SETTINGS.exists():
                data = json.loads(SETTINGS.read_text(encoding="utf-8"))
                self._current = data.get("theme", "tensura_gold")
        except Exception:
            pass

    def get_theme(self, name: str = None) -> dict:
        return THEMES.get(name or self._current, THEMES["tensura_gold"])

    def set_theme(self, name: str):
        if name in THEMES:
            self._current = name
            self._save()

    def _save(self):
        try:
            SETTINGS.parent.mkdir(parents=True, exist_ok=True)
            data = json.loads(SETTINGS.read_text(encoding="utf-8")) if SETTINGS.exists() else {}
            data["theme"] = self._current
            SETTINGS.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    @property
    def name(self):
        return self._current

    @property
    def display_name(self):
        return THEMES.get(self._current, {}).get("name", self._current)

    def get_available(self) -> List[Tuple[str, str]]:
        return [(k, v["name"]) for k, v in THEMES.items()]

class C:
    BG = "#060913"
    PANEL = "#131008"
    PANEL2 = "#1d180c"
    GHOST = "#332708"
    BORDER = "#5c4708"
    BORDER_B = "#a8801c"
    BORDER_A = "#7a5e10"
    PRI = "#ffd24a"
    ACC = "#ffedb0"
    ACC2 = "#f5a623"
    GOLD = "#ffe27a"
    GREEN = "#7dff9e"
    RED = "#ff4d6d"
    TEXT = "#fff3d6"
    TEXT_DIM = "#9d8a5a"
    TEXT_MED = "#e0c98a"
    WHITE = "#ffffff"

_theme_manager = ThemeManager()

def apply_theme(name: str = None):
    t = _theme_manager.get_theme(name)
    for k, v in t.items():
        if k != "name" and hasattr(C, k.upper()):
            setattr(C, k.upper(), v)

def get_theme() -> ThemeManager:
    return _theme_manager

def font_ui(size: int = 12, bold: bool = False):
    f = QFont("Segoe UI", size)
    f.setBold(bold)
    return f

def font_mono(size: int = 11, bold: bool = False):
    f = QFont("Cascadia Code, Consolas, monospace", size)
    f.setBold(bold)
    return f

apply_theme()
