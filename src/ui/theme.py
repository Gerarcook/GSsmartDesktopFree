"""
Tokens visuales de GSsmart Desktop — Cyberpunk high-end.

Fuente UNICA de color y tipografia. Ningun widget deberia hardcodear
un "#00E5FF": si cambia el acento, se cambia aca.

Paleta (oct-2026 art direction):
  - Fondos casi void, capas de superficie legibles
  - Un solo neón primario (cyan) para CTA / focus
  - Semanticos: green=AI/OK, magenta=error, amber=thinking, violet=secundario
  - Contraste AA: text sobre surface-1 ~12:1; muted ~5.5:1
"""

from typing import Dict


#: Paleta cyberpunk de alta gama. Fondos fríos; acentos quirúrgicos.
COLORS: Dict[str, str] = {
    # Superficies
    "bg": "#03050A",            # void / fondo ventana
    "panel": "#0A1220",         # sidebar, cards, footer
    "panel_raised": "#0F1A2E",  # inputs, chips, burbujas base
    "surface_3": "#152238",     # overlays, dropdowns
    # Bordes
    "border": "#1A2A40",
    "border_glow": "#0E4A55",
    # Primario (cyan)
    "cyan": "#00E5FF",
    "cyan_mid": "#00B4C8",
    "cyan_dim": "#003D48",
    # Semánticos
    "magenta": "#FF2D6F",
    "magenta_dim": "#4A0F28",
    "green": "#00FFA3",
    "green_dim": "#0A3D32",
    "violet": "#7B61FF",
    "violet_dim": "#2A1F66",
    "warning": "#FFB020",
    # Texto (WCAG AA sobre panel)
    "text": "#E8F7FA",
    "text_muted": "#8BA3B8",
    "text_dim": "#4A5D72",
    # HUD
    "grid": "#0C1828",
}

#: Tipografia. HUD en mono; cuerpo en proporcional.
FONT_MONO = "Consolas"
FONT_UI = "Segoe UI"

#: Escala tipografica (px) — mono/UI comparten tamaños.
FS = {
    "xs": 11,
    "sm": 12,
    "md": 14,
    "lg": 18,
    "xl": 24,
}

#: Ritmo de spacing (px). Preferir estos sobre magics sueltos.
SPACE = {
    1: 4,
    2: 8,
    3: 12,
    4: 16,
    5: 24,
    6: 32,
}

#: Radios compartidos — misma "textura" en paneles y botones.
RADIUS_PANEL = 12
RADIUS_FIELD = 8
RADIUS_PILL = 50


def mix(hex_a: str, hex_b: str, t: float) -> str:
    """Interpola dos colores hex. t=0 → a, t=1 → b."""
    a = hex_a.lstrip("#")
    b = hex_b.lstrip("#")
    out = []
    for i in (0, 2, 4):
        ca, cb = int(a[i:i + 2], 16), int(b[i:i + 2], 16)
        out.append(round(ca + (cb - ca) * t))
    return "#" + "".join(f"{v:02X}" for v in out)


#: Estados derivados (disabled / soft fills).
DIM = {
    "accent_disabled": mix(COLORS["cyan"], COLORS["bg"], 0.55),
    "surface_disabled": mix(COLORS["panel"], COLORS["bg"], 0.5),
    "user_bubble": mix(COLORS["cyan_dim"], COLORS["panel_raised"], 0.45),
    "ai_bubble": mix(COLORS["green_dim"], COLORS["panel_raised"], 0.35),
}


def ghost_btn_kwargs() -> dict:
    """Estilo ghost: sin relleno, borde sutil, hover con tinte cyan.

    Un solo CTA neón (Enviar); el resto de acciones usan esto.
    """
    return {
        "fg_color": "transparent",
        "hover_color": COLORS["cyan_dim"],
        "text_color": COLORS["text"],
        "border_width": 1,
        "border_color": COLORS["border"],
        "corner_radius": RADIUS_FIELD,
        "font": (FONT_MONO, FS["sm"]),
    }


def primary_btn_kwargs() -> dict:
    """CTA primario — el unico boton solido cyan."""
    return {
        "fg_color": COLORS["cyan"],
        "hover_color": COLORS["cyan_mid"],
        "text_color": COLORS["bg"],
        "corner_radius": RADIUS_PILL,
        "font": (FONT_MONO, FS["sm"], "bold"),
    }


def rail_btn_kwargs() -> dict:
    """Botones del sidebar: ghost full-width."""
    return {
        "fg_color": "transparent",
        "hover_color": COLORS["cyan_dim"],
        "text_color": COLORS["text_muted"],
        "border_width": 1,
        "border_color": COLORS["border"],
        "font": (FONT_MONO, FS["sm"]),
        "corner_radius": RADIUS_FIELD,
        "anchor": "w",
    }
