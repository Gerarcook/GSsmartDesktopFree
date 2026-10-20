"""
Burbuja de mensaje del chat.

POR QUE ESTA EN src/ui Y NO EN LA GUI
    Originalmente vivia en gui_cyberpunk.py. Si la burbuja se queda ahi, la
    otra interfaz no puede usarla y terminamos con dos implementaciones de lo
    mismo. Ahora las dos la importan de acá.

Diferencias con la version que estaba en gui_cyberpunk.py:
    - Los STYLES distinguen "user" y "ai" con colores distintos. Antes los dos
      caian en la misma clave y se veian iguales.
    - El wraplength se recalcula solo con el <Configure> del contenedor, asi
      que al redimensionar la ventana las burbujas no quedan cortadas.
"""

import time
from typing import Optional

import customtkinter as ctk

from src.ui.theme import COLORS, FONT_MONO, FONT_UI, RADIUS_PANEL


class MessageBubble(ctk.CTkFrame):
    """Burbuja de mensaje con remitente, hora y boton COPIAR."""

    STYLES = {
        "user": ("OPERADOR", COLORS["cyan"], COLORS["panel_raised"]),
        "ai": ("GSSMART", COLORS["green"], COLORS["panel_raised"]),
        "system": ("SISTEMA", COLORS["text_muted"], COLORS["bg"]),
        "error": ("ERROR", COLORS["magenta"], COLORS["magenta_dim"]),
    }

    def __init__(self, master, sender: str, text: str, wraplength: int = 600):
        label, accent, bg = self.STYLES.get(sender, self.STYLES["system"])
        super().__init__(
            master,
            fg_color=bg,
            corner_radius=RADIUS_PANEL,
            border_width=1,
            border_color=accent if sender != "system" else COLORS["text_dim"],
        )
        self.sender = sender
        self.text = text
        self.grid_columnconfigure(0, weight=1)

        meta = ctk.CTkFrame(self, fg_color="transparent")
        meta.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 0))
        ctk.CTkLabel(meta, text=label, font=(FONT_MONO, 9, "bold"),
                     text_color=accent).pack(side="left")
        ctk.CTkLabel(meta, text=f"  //  {time.strftime('%H:%M:%S')}",
                     font=(FONT_MONO, 9),
                     text_color=COLORS["text_dim"]).pack(side="left")
        if sender != "system":
            self.copy_btn = ctk.CTkButton(
                meta, text="COPIAR", width=58, height=18, font=(FONT_MONO, 8, "bold"),
                fg_color="transparent", hover_color=COLORS["cyan_dim"],
                text_color=COLORS["text_muted"],
                border_width=1, border_color=COLORS["text_dim"], corner_radius=4,
                command=self._copy,
            )
            self.copy_btn.pack(side="right", padx=(12, 0))

        self.text_label = ctk.CTkLabel(
            self,
            text=text,
            font=(FONT_UI, 12 if sender != "system" else 10),
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