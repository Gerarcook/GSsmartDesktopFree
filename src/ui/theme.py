"""
Tokens visuales GSsmart Desktop — Cyberpunk holográfico (mockup).

Estética: paneles flotantes de vidrio, borde cian neón, CTA único cyan.
"""

from typing import Dict


COLORS: Dict[str, str] = {
    # Superficies (void + glass)
    "bg": "#02060F",
    "panel": "#061018",
    "panel_raised": "#0A1A28",
    "surface_3": "#0E2436",
    # Bordes neón (glass edge)
    "border": "#0A3A4A",
    "border_glow": "#00C8E0",
    # Primario
    "cyan": "#00E5FF",
    "cyan_mid": "#00B8D4",
    "cyan_dim": "#003844",
    # Semánticos
    "magenta": "#FF2D6F",
    "magenta_dim": "#4A0F28",
    "green": "#00FFA3",
    "green_dim": "#0A3D32",
    "violet": "#7B61FF",
    "violet_dim": "#2A1F66",
    "warning": "#FFB020",
    # Texto
    "text": "#E8F7FA",
    "text_muted": "#7EB0C2",
    "text_dim": "#3D5A6A",
    "grid": "#071420",
}

FONT_MONO = "Consolas"
FONT_UI = "Segoe UI"

FS = {"xs": 11, "sm": 12, "md": 14, "lg": 18, "xl": 24}
SPACE = {1: 4, 2: 8, 3: 12, 4: 16, 5: 24, 6: 32}

RADIUS_PANEL = 18
RADIUS_FIELD = 12
RADIUS_PILL = 50


def mix(hex_a: str, hex_b: str, t: float) -> str:
    a = hex_a.lstrip("#")
    b = hex_b.lstrip("#")
    out = []
    for i in (0, 2, 4):
        ca, cb = int(a[i:i + 2], 16), int(b[i:i + 2], 16)
        out.append(round(ca + (cb - ca) * t))
    return "#" + "".join(f"{v:02X}" for v in out)


DIM = {
    "accent_disabled": mix(COLORS["cyan"], COLORS["bg"], 0.55),
    "surface_disabled": mix(COLORS["panel"], COLORS["bg"], 0.5),
    "user_bubble": mix(COLORS["cyan_dim"], COLORS["panel_raised"], 0.4),
    "ai_bubble": mix(COLORS["panel"], COLORS["panel_raised"], 0.5),
}


def glass_panel_kwargs() -> dict:
    """Marco de módulo flotante (borde neón grueso, estilo mockup)."""
    return {
        "fg_color": COLORS["panel"],
        "corner_radius": RADIUS_PANEL,
        "border_width": 2,
        "border_color": COLORS["border_glow"],
    }


def ghost_btn_kwargs() -> dict:
    return {
        "fg_color": "transparent",
        "hover_color": COLORS["cyan_dim"],
        "text_color": COLORS["text"],
        "border_width": 1,
        "border_color": COLORS["border_glow"],
        "corner_radius": RADIUS_FIELD,
        "font": (FONT_MONO, FS["sm"]),
    }


def primary_btn_kwargs() -> dict:
    return {
        "fg_color": COLORS["cyan"],
        "hover_color": COLORS["cyan_mid"],
        "text_color": COLORS["bg"],
        "corner_radius": RADIUS_PILL,
        "font": (FONT_MONO, FS["sm"], "bold"),
    }


def rail_btn_kwargs() -> dict:
    return {
        "fg_color": "transparent",
        "hover_color": COLORS["cyan_dim"],
        "text_color": COLORS["text"],
        "border_width": 0,
        "font": (FONT_MONO, FS["sm"]),
        "corner_radius": RADIUS_FIELD,
        "anchor": "w",
    }
