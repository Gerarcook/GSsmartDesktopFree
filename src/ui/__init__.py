"""Tokens visuales y componentes compartidos de la UI. Ver src/ui/theme.py."""

from src.ui.theme import (
    COLORS, FONT_MONO, FONT_UI, RADIUS_PANEL, RADIUS_FIELD, RADIUS_PILL,
    DIM, FS, SPACE, mix, ghost_btn_kwargs, primary_btn_kwargs, rail_btn_kwargs, glass_panel_kwargs,
)

__all__ = [
    "COLORS", "FONT_MONO", "FONT_UI", "RADIUS_PANEL", "RADIUS_FIELD",
    "RADIUS_PILL", "DIM", "FS", "SPACE", "mix",
    "ghost_btn_kwargs", "primary_btn_kwargs", "rail_btn_kwargs", "glass_panel_kwargs",
    "MessageBubble",
]

# MessageBubble depende de customtkinter/Tk. En entornos headless (CI sin
# libtk) el import del package no debe reventar solo por pedir COLORS.
try:
    from src.ui.bubbles import MessageBubble  # noqa: E402
except Exception:  # pragma: no cover - solo sin Tk
    MessageBubble = None  # type: ignore[misc, assignment]
