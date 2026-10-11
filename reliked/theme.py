"""Motyw „Midnight Vinyl”: paleta, fonty, ikony i skalowanie DPI."""

import ctypes
import sys
import tkinter.font as tkfont

# --- Paleta ---------------------------------------------------------------
BG = "#08100C"            # tło okna
FIELD = "#0C1611"         # pola i kafelki wpuszczone w karty
PANEL = "#101A15"         # karty
PANEL_HOVER = "#15231C"
PANEL_DISABLED = "#131D18"
LINE = "#1E2C25"
LINE_SOFT = "#17221C"
LINE_STRONG = "#2B3D33"
TEXT = "#E9F3ED"
MUTED = "#7F978A"
DIM = "#4C6155"
GREEN = "#1ED760"
GREEN_HI = "#3BE477"
GREEN_PRESS = "#17B851"
GREEN_INK = "#04220F"
GREEN_SOFT = "#14301F"
GREEN_SOFT_HI = "#1A3D28"
GREEN_LINE = "#1F5A37"
RED = "#FF6B6B"
RED_SOFT = "#2A1316"
RED_LINE = "#5A2329"
AMBER = "#F5B544"
AMBER_SOFT = "#2A2112"
AMBER_LINE = "#5A4520"

# --- Ikony (Segoe Fluent Icons / Segoe MDL2 Assets) -----------------------
ICON = {
    "music": "\uE8D6",
    "playlist": "\uE90B",
    "upload": "\uE898",
    "check": "\uE73E",
    "close": "\uE711",
    "arrow": "\uE72A",
    "heart": "\uEB51",
    "heart_fill": "\uEB52",
    "lock": "\uE72E",
    "settings": "\uE713",
    "link": "\uE71B",
    "search": "\uE721",
    "done": "\uE930",
    "done_fill": "\uEC61",
    "error": "\uE783",
    "warning": "\uE7BA",
    "clock": "\uE823",
    "person": "\uE77B",
    "external": "\uE8A7",
    "info": "\uE946",
    "refresh": "\uE72C",
    "book": "\uE82D",
    "shield": "\uEA18",
    "eye": "\uE890",
    "headphones": "\uE7F6",
}

_scale = 1.0
FONTS = {}


def px(value):
    """Przelicza piksele logiczne (96 DPI) na fizyczne."""
    return int(round(value * _scale))


def hairline():
    """Grubość cienkiej ramki: 1 px fizyczny do 199% skalowania."""
    return max(1, int(_scale))


def init(root):
    """Ustala skalę DPI i tworzy fonty. Wywołać raz, zaraz po utworzeniu Tk."""
    global _scale
    _scale = max(1.0, root.winfo_fpixels("1i") / 96)
    families = set(tkfont.families(root))

    def pick(*names):
        return next((n for n in names if n in families), None)

    display = pick("Segoe UI Variable Display Semib", "Segoe UI Semibold")
    text = pick("Segoe UI Variable Text", "Segoe UI") or "TkDefaultFont"
    text_bold = pick("Segoe UI Variable Text Semibold", "Segoe UI Semibold")
    mono = pick("Cascadia Mono", "Consolas") or "TkFixedFont"
    icons = pick("Segoe Fluent Icons", "Segoe MDL2 Assets") or text

    # Brak wariantu „Semibold” → zwykła rodzina z pogrubieniem.
    bold = (text_bold, "normal") if text_bold else (text, "bold")
    heading = (display, "normal") if display else bold

    spec = {
        "h1": (*heading, 32),
        "brand": (*heading, 19),
        "stat": (*heading, 21),
        "h2": (*bold, 15),
        "h3": (*bold, 14),
        "body": (text, "normal", 13),
        "body_b": (*bold, 13),
        "small": (text, "normal", 12),
        "tiny": (text, "normal", 11),
        "eyebrow": (*bold, 11),
        "btn": (*bold, 14),
        "btn_s": (*bold, 12),
        "mono": (mono, "normal", 12),
        "mono_s": (mono, "normal", 11),
        "icon_xs": (icons, "normal", 11),
        "icon_s": (icons, "normal", 13),
        "icon": (icons, "normal", 16),
        "icon_l": (icons, "normal", 20),
        "icon_xl": (icons, "normal", 26),
    }
    for name, (family, weight, size) in spec.items():
        FONTS[name] = tkfont.Font(root, family=family, size=-px(size), weight=weight)


def font(name):
    return FONTS[name]


def mix(c1, c2, t):
    """Miesza dwa kolory hex: t=0 → c1, t=1 → c2."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(a, b))


def spaced(text):
    """Imituje letter-spacing (Tk go nie obsługuje) wąskimi spacjami."""
    return "\u2009".join(text)


def enable_dpi_awareness():
    """Ostre fonty na ekranach HiDPI. Wywołać przed utworzeniem Tk."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("reliked.spotify.import")
    except (AttributeError, OSError):
        pass


def _colorref(hex_color):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return ctypes.c_int(r | (g << 8) | (b << 16))


def style_titlebar(window):
    """Ciemny, dopasowany do tła pasek tytułu (Windows 11; na starszych tylko ciemny)."""
    if sys.platform != "win32":
        return
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        dwm = ctypes.windll.dwmapi
        on = ctypes.c_int(1)
        dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(on), ctypes.sizeof(on))
        for attribute, color in ((35, BG), (36, TEXT), (34, LINE)):
            value = _colorref(color)
            dwm.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value))
    except (AttributeError, OSError):
        pass
