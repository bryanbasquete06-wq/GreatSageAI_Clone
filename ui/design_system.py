"""
Elívea — Design System v1.0 (Direction B: Rune Keeper)
=====================================================
Central token system for the entire UI. All widgets import from here.
No more hardcoded colors — every visual element references these tokens.

by: bryan
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Tuple

# ═══════════════════════════════════════════════════════════════════════════
# COLOR TOKENS — Direction B: Rune Keeper (Gold + Black Fantasy)
# ═══════════════════════════════════════════════════════════════════════════

# --- Backgrounds (depth scale) ---
BG_VOID = "#020204"       # Deepest background (below everything)
BG_DEEP = "#060609"       # Main window background
BG_SURFACE = "#0d0d12"    # Cards, panels
BG_ELEVATED = "#141419"   # Hover states, dropdowns
BG_CARD = "#1a1a20"       # Modal backgrounds

# --- Gold System (Primary Identity) ---
GOLD_ANCIENT = "#6B5A1E"      # Subtle borders, dark backgrounds
GOLD_DIM = "#8B7A2E"          # Alias for GOLD_WEATHERED (backward compat)
GOLD_WEATHERED = "#8B7A2E"    # Secondary text, sidebar labels
GOLD_PRIMARY = "#C9A84C"      # Active borders, icons, accents
GOLD_BRIGHT = "#E8C55A"       # Headings, highlighted text
GOLD_LUMINOUS = "#FFD966"     # Hover states, bright accents
GOLD_WHITE = "#FFF3CC"        # Light text on dark (WCAG AAA)

# --- Energy System (Active States) ---
ENERGY_WARM = "#D4A020"       # Warm energy, subtle pulse
ENERGY_HOT = "#FFD700"        # Active state, streaming indicator

# --- Text Hierarchy ---
TEXT_BONE = "#E8E0D0"         # Primary text (WCAG AAA on dark)
TEXT_STONE = "#9A9080"        # Secondary text (WCAG AA)
TEXT_RUNE = "#6B6358"         # Tertiary text, placeholders
TEXT_GHOST = "#3A3530"        # Dividers, invisible borders

# --- Semantic Colors ---
SUCCESS = "#7DB87D"           # Success states (desaturated green)
WARNING = "#D4A843"           # Warning states
ERROR = "#C45B5B"             # Error states (desaturated red)
INFO = "#7DA8C4"              # Info states (desaturated blue)

# --- Rune Decorative ---
RUNE_SYMBOLS = list("ᚠᚢᚦᚨᚱᚲᚷᚹᚺᚾᛁᛃᛈᛇᛉᛊᛏᛒᛖᛗᛚᛜᛞᛟ")
RUNE_DIVIDER = "ᚠ ᚢ ᚦ ᚨ ᚱ"
RUNE_DIVIDER_2 = "ᚲ ᚷ ᚹ ᚺ ᚾ"

# ═══════════════════════════════════════════════════════════════════════════
# SPACING TOKENS (base unit = 4px)
# ═══════════════════════════════════════════════════════════════════════════
SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 12
SPACING_LG = 16
SPACING_XL = 20
SPACING_2XL = 24
SPACING_3XL = 32
SPACING_4XL = 40
SPACING_5XL = 48
SPACING_6XL = 64

# ═══════════════════════════════════════════════════════════════════════════
# BORDER RADIUS TOKENS
# ═══════════════════════════════════════════════════════════════════════════
RADIUS_SM = 6
RADIUS_MD = 10
RADIUS_LG = 14
RADIUS_XL = 20
RADIUS_PILL = 9999

# ═══════════════════════════════════════════════════════════════════════════
# TYPOGRAPHY TOKENS
# ═══════════════════════════════════════════════════════════════════════════
FONT_PRIMARY = "Inter"         # Body text
FONT_SERIF = "Cinzel"          # Headings, decorative
FONT_MONO = "Cascadia Code"    # Code, technical

# Type scale (size, weight_name, font_family)
TYPE_DISPLAY_LG = (28, "Bold", FONT_SERIF)
TYPE_DISPLAY_MD = (22, "Bold", FONT_SERIF)
TYPE_HEADING = (16, "SemiBold", FONT_SERIF)
TYPE_BODY = (13, "Normal", FONT_PRIMARY)
TYPE_BODY_BOLD = (13, "SemiBold", FONT_PRIMARY)
TYPE_CAPTION = (11, "Normal", FONT_PRIMARY)
TYPE_MICRO = (9, "Normal", FONT_PRIMARY)

# ═══════════════════════════════════════════════════════════════════════════
# ANIMATION TOKENS
# ═══════════════════════════════════════════════════════════════════════════
ANIM_INSTANT = 80      # ms — hover states
ANIM_FAST = 150        # ms — panel transitions
ANIM_NORMAL = 250      # ms — page transitions
ANIM_SLOW = 400        # ms — complex animations
ANIM_GLACIAL = 800     # ms — onboarding, reveals

# ═══════════════════════════════════════════════════════════════════════════
# LAYOUT CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════
SIDEBAR_WIDTH = 240
ICON_RAIL_WIDTH = 52
RIGHT_PANEL_WIDTH = 270
TITLE_BAR_HEIGHT = 48
RUNE_AREA_HEIGHT = 300
INPUT_HEIGHT = 44
MIN_WINDOW_WIDTH = 900
MIN_WINDOW_HEIGHT = 600
DEFAULT_WINDOW_WIDTH = 1400
DEFAULT_WINDOW_HEIGHT = 850

# ═══════════════════════════════════════════════════════════════════════════
# PERFORMANCE TOKENS
# ═══════════════════════════════════════════════════════════════════════════
MAX_PARTICLES_IDLE = 12
MAX_PARTICLES_ACTIVE = 45
STREAM_THROTTLE_MS = 80       # Min ms between chat updates during streaming
FPS_TARGET = 60
FPS_MIN_ACCEPTABLE = 30

# ═══════════════════════════════════════════════════════════════════════════
# ACCESSIBILITY TOKENS
# ═══════════════════════════════════════════════════════════════════════════
FOCUS_OUTLINE_WIDTH = 2
FOCUS_OUTLINE_OFFSET = 2
MIN_FONT_SIZE = 9
CONTRAST_AA_RATIO = 4.5
CONTRAST_AAA_RATIO = 7.0

# ═══════════════════════════════════════════════════════════════════════════
# STATE COLORS (for RuneCoreWidget, status indicators)
# ═══════════════════════════════════════════════════════════════════════════
STATE_COLORS = {
    "idle":      {"ring": GOLD_WEATHERED, "star": GOLD_PRIMARY, "glow": GOLD_BRIGHT},
    "thinking":  {"ring": GOLD_PRIMARY,   "star": GOLD_LUMINOUS, "glow": GOLD_PRIMARY},
    "speaking":  {"ring": GOLD_BRIGHT,    "star": GOLD_LUMINOUS, "glow": GOLD_LUMINOUS},
    "success":   {"ring": SUCCESS,        "star": SUCCESS,       "glow": SUCCESS},
    "error":     {"ring": ERROR,          "star": ERROR,         "glow": ERROR},
    "listening": {"ring": GOLD_PRIMARY,   "star": GOLD_BRIGHT,   "glow": GOLD_PRIMARY},
}

# ═══════════════════════════════════════════════════════════════════════════
# STYLE SHEETS (reusable QSS fragments)
# ═══════════════════════════════════════════════════════════════════════════

def _alpha_hex(color: str, alpha_pct: int) -> str:
    """Convert #RRGGBB to rgba(R,G,B,A%) string."""
    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)
    return f"rgba({r},{g},{b},{alpha_pct}%)"


# Panel/card base style
PANEL_STYLE = f"""
    background: {_alpha_hex(BG_SURFACE, 85)};
    border: 1px solid {_alpha_hex(GOLD_ANCIENT, 30)};
    border-radius: {RADIUS_LG}px;
"""

# Button styles
BTN_IDLE = f"""
    QPushButton {{
        background: {_alpha_hex(BG_ELEVATED, 100)};
        border: 1px solid {_alpha_hex(GOLD_ANCIENT, 40)};
        border-radius: {RADIUS_SM}px;
        color: {TEXT_STONE};
        padding: 6px 14px;
        font-size: 11px;
        font-family: '{FONT_PRIMARY}', sans-serif;
    }}
    QPushButton:hover {{
        border-color: {_alpha_hex(GOLD_PRIMARY, 60)};
        color: {GOLD_BRIGHT};
        background: {_alpha_hex(BG_ELEVATED, 100)};
    }}
    QPushButton:pressed {{
        background: {_alpha_hex(GOLD_ANCIENT, 30)};
        color: {GOLD_WHITE};
    }}
"""

BTN_PRIMARY = f"""
    QPushButton {{
        background: {_alpha_hex(GOLD_ANCIENT, 100)};
        border: 1px solid {_alpha_hex(GOLD_PRIMARY, 50)};
        border-radius: {RADIUS_SM}px;
        color: {GOLD_BRIGHT};
        padding: 6px 14px;
        font-size: 11px;
        font-weight: 600;
        font-family: '{FONT_PRIMARY}', sans-serif;
    }}
    QPushButton:hover {{
        background: {_alpha_hex(GOLD_PRIMARY, 80)};
        color: {BG_VOID};
    }}
"""

INPUT_STYLE = f"""
    QLineEdit {{
        background: {_alpha_hex(BG_DEEP, 100)};
        border: 1px solid {_alpha_hex(TEXT_GHOST, 60)};
        border-radius: {RADIUS_MD}px;
        color: {TEXT_BONE};
        padding: 10px 14px;
        font-size: 13px;
        font-family: '{FONT_PRIMARY}', sans-serif;
        selection-background-color: {_alpha_hex(GOLD_PRIMARY, 40)};
    }}
    QLineEdit:focus {{
        border-color: {GOLD_PRIMARY};
    }}
    QLineEdit::placeholder {{
        color: {TEXT_RUNE};
    }}
"""

# Scrollbar style
SCROLLBAR_STYLE = f"""
    QScrollBar:vertical {{
        background: transparent;
        width: 4px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {_alpha_hex(GOLD_ANCIENT, 40)};
        border-radius: 2px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {_alpha_hex(GOLD_PRIMARY, 60)};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}
"""

# ═══════════════════════════════════════════════════════════════════════════
# ACCESSIBILITY CHECKS
# ═══════════════════════════════════════════════════════════════════════════

def _relative_luminance(hex_color: str) -> float:
    """Calculate relative luminance per WCAG 2.0."""
    r = int(hex_color[1:3], 16) / 255.0
    g = int(hex_color[3:5], 16) / 255.0
    b = int(hex_color[5:7], 16) / 255.0
    # Linearize sRGB
    def linearize(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def contrast_ratio(color1: str, color2: str) -> float:
    """Calculate WCAG contrast ratio between two hex colors."""
    l1 = _relative_luminance(color1)
    l2 = _relative_luminance(color2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def check_wcag_aa(fg: str, bg: str) -> bool:
    """Check if foreground on background passes WCAG AA (4.5:1)."""
    return contrast_ratio(fg, bg) >= CONTRAST_AA_RATIO


def check_wcag_aaa(fg: str, bg: str) -> bool:
    """Check if foreground on background passes WCAG AAA (7:1)."""
    return contrast_ratio(fg, bg) >= CONTRAST_AAA_RATIO


# ═══════════════════════════════════════════════════════════════════════════
# ADAPTIVE QUALITY (hardware detection)
# ═══════════════════════════════════════════════════════════════════════════

class QualityLevel:
    """Detect hardware capability and set animation quality."""
    ULTRA = 3    # Full particles, blur, all effects
    HIGH = 2     # Reduced particles, no blur
    LOW = 1      # Minimal particles, no effects
    MINIMAL = 0  # No animations at all

    _instance = None
    _level = None

    @classmethod
    def get(cls) -> int:
        if cls._level is not None:
            return cls._level
        try:
            import psutil
            ram_gb = psutil.virtual_memory().total / (1024**3)
            cpu_count = psutil.cpu_count(logical=True) or 4
            if ram_gb >= 8 and cpu_count >= 8:
                cls._level = cls.ULTRA
            elif ram_gb >= 4 and cpu_count >= 4:
                cls._level = cls.HIGH
            elif ram_gb >= 2:
                cls._level = cls.LOW
            else:
                cls._level = cls.MINIMAL
        except Exception:
            cls._level = cls.HIGH
        return cls._level

    @classmethod
    def particle_max(cls) -> int:
        level = cls.get()
        if level >= cls.ULTRA:
            return MAX_PARTICLES_ACTIVE
        elif level >= cls.HIGH:
            return int(MAX_PARTICLES_ACTIVE * 0.6)
        elif level >= cls.LOW:
            return MAX_PARTICLES_IDLE
        return 0

    @classmethod
    def should_animate(cls) -> bool:
        return cls.get() > cls.MINIMAL

    @classmethod
    def should_glow(cls) -> bool:
        return cls.get() >= cls.HIGH

    @classmethod
    def should_particles(cls) -> bool:
        return cls.get() >= cls.LOW


# ═══════════════════════════════════════════════════════════════════════════
# REDUCED MOTION CHECK
# ═══════════════════════════════════════════════════════════════════════════

def is_reduced_motion() -> bool:
    """Check system + app settings for reduced motion preference."""
    # App-level setting
    try:
        import json
        from pathlib import Path
        settings_path = Path(__file__).resolve().parent.parent / "config" / "settings.json"
        if settings_path.exists():
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            if data.get("reduce_motion"):
                return True
    except Exception:
        pass
    return False


# ═══════════════════════════════════════════════════════════════════════════
# QUICK VALIDATION (run once at import to verify WCAG compliance)
# ═══════════════════════════════════════════════════════════════════════════
def validate_contrast():
    """Validate key color combinations pass WCAG AA."""
    checks = [
        (GOLD_BRIGHT, BG_DEEP, "Gold bright on deep"),
        (TEXT_BONE, BG_DEEP, "Bone text on deep"),
        (TEXT_STONE, BG_DEEP, "Stone text on deep"),
        (GOLD_WHITE, BG_DEEP, "Gold white on deep"),
        (TEXT_BONE, BG_SURFACE, "Bone text on surface"),
        (GOLD_BRIGHT, BG_SURFACE, "Gold bright on surface"),
    ]
    results = []
    for fg, bg, label in checks:
        ratio = contrast_ratio(fg, bg)
        passed = ratio >= CONTRAST_AA_RATIO
        results.append((label, ratio, passed))
    return results
