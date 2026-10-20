"""
Burbuja de mensaje del chat — Cyberpunk high-end.

User: borde cyan + fondo teñido (operador alineado a la derecha en la GUI).
AI:   borde green + fondo success soft.
System / error: tonos muted / magenta.
"""

import time

import customtkinter as ctk

from src.ui.theme import COLORS, FONT_MONO, FONT_UI, RADIUS_PANEL, FS, DIM


class MessageBubble(ctk.CTkFrame):
    """Burbuja de mensaje con remitente, hora y boton COPIAR."""

    # (label, accent, background)
    STYLES = {
        # Mockup: bordes cian en ambas; user relleno cyan, AI panel oscuro
        "user": ("OPERADOR", COLORS["cyan"], COLORS["cyan_dim"]),
        "ai": ("GSSMART", COLORS["cyan"], COLORS["panel_raised"]),
        "system": ("SISTEMA", COLORS["text_muted"], COLORS["bg"]),
        "error": ("ERROR", COLORS["magenta"], COLORS["magenta_dim"]),
    }

    def __init__(self, master, sender: str, text: str, wraplength: int = 600):
        label, accent, bg = self.STYLES.get(sender, self.STYLES["system"])
        border = accent if sender != "system" else COLORS["border"]
        super().__init__(
            master,
            fg_color=bg,
            corner_radius=RADIUS_PANEL,
            border_width=1,
            border_color=COLORS["border_glow"] if sender != "error" else border,
        )
        self.sender = sender
        self.text = text
        self.grid_columnconfigure(0, weight=1)

        meta = ctk.CTkFrame(self, fg_color="transparent")
        meta.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 0))
        ctk.CTkLabel(
            meta, text=label, font=(FONT_MONO, FS["xs"], "bold"),
            text_color=accent,
        ).pack(side="left")
        ctk.CTkLabel(
            meta, text="  //  " + time.strftime("%H:%M:%S"),
            font=(FONT_MONO, FS["xs"]),
            text_color=COLORS["text_dim"],
        ).pack(side="left")
        if sender != "system":
            self.copy_btn = ctk.CTkButton(
                meta, text="COPIAR", width=58, height=18,
                font=(FONT_MONO, 8, "bold"),
                fg_color="transparent",
                hover_color=COLORS["cyan_dim"],
                text_color=COLORS["text_muted"],
                border_width=1,
                border_color=COLORS["border"],
                corner_radius=4,
                command=self._copy,
            )
            self.copy_btn.pack(side="right", padx=(12, 0))

        body_size = FS["sm"] if sender != "system" else FS["xs"]
        self.text_label = ctk.CTkLabel(
            self,
            text=text,
            font=(FONT_UI, body_size),
            text_color=COLORS["text"] if sender != "system" else COLORS["text_muted"],
            justify="left",
            anchor="w",
            wraplength=wraplength,
        )
        self.text_label.grid(row=1, column=0, sticky="w", padx=12, pady=(2, 10))

    def append(self, chunk: str) -> None:
        self.text += chunk
        self.text_label.configure(text=self.text)

    def set_text(self, text: str) -> None:
        self.text = text
        self.text_label.configure(text=text)

    def set_wraplength(self, value: int) -> None:
        self.text_label.configure(wraplength=value)

    def _copy(self) -> None:
        if not self.text.strip():
            return
        self.clipboard_clear()
        self.clipboard_append(self.text)
        self.copy_btn.configure(text="COPIADO", text_color=COLORS["green"])
        self.after(1200, self._reset_copy_label)

    def _reset_copy_label(self) -> None:
        if self.winfo_exists():
            self.copy_btn.configure(text="COPIAR", text_color=COLORS["text_muted"])
