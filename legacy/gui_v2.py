"""
GSsmart Desktop - Interfaz Gráfica de Usuario (GUI) v2 simplificada.

Versión optimizada para evitar deadlocks y bucle infinito.
"""

import customtkinter as ctk
import asyncio
from typing import Optional

# Configuración inicial
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class GSsmartApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("GSsmart Desktop - IA Multi-Provider")
        self.geometry("800x600")
        self.minsize(600, 400)

        # --- Layout simple ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Frame superior: selector
        top = ctk.CTkFrame(self, corner_radius=0)
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        top.grid_columnconfigure(1, weight=1)

        self.label_provider = ctk.CTkLabel(top, text="Proveedor:", anchor="w")
        self.label_provider.grid(row=0, column=0, padx=(0, 8), pady=8)

        self.combo_provider = ctk.CTkComboBox(top, values=["OmniRoute", "OpenAI", "OpenRouter"], width=200)
        self.combo_provider.grid(row=0, column=1, padx=(0, 8), pady=8)
        self.combo_provider.set("OmniRoute")

        self.btn_connect = ctk.CTkButton(top, text="Conectar", command=self._toggle, width=100)
        self.btn_connect.grid(row=0, column=2, padx=(0, 8), pady=8)

        self.status = ctk.CTkLabel(top, text="Desconectado", text_color="gray")
        self.status.grid(row=0, column=3, padx=(0, 8), pady=8)

        # Área de chat
        self.chat = ctk.CTkScrollableFrame(self, corner_radius=0)
        self.chat.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.chat.grid_columnconfigure(0, weight=1)

        # Frame inferior: entrada
        bottom = ctk.CTkFrame(self, corner_radius=0)
        bottom.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        bottom.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkEntry(bottom, placeholder_text="Escribir prompt...", height=40)
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.entry.bind("<Return>", self._on_enter)

        self.btn_send = ctk.CTkButton(bottom, text="Enviar", height=40, command=self._send)
        self.btn_send.grid(row=0, column=1)

        # Estado interno
        self.provider_name = "OmniRoute"
        self.connected = False

        # Mensajes de ejemplo para probar
        self._add_msg("Sistema", "Proveedor OmniRoute listo. Escribí un prompt abajo.")

    def _add_msg(self, sender: str, text: str) -> None:
        """Agrega un mensaje al área de chat (hilo seguro)."""
        frame = ctk.CTkFrame(self.chat, fg_color="transparent")
        frame.pack(fill="x", pady=2, padx=(20, 0) if sender == "Tú" else (20, 0))
        label = ctk.CTkLabel(frame, text=f"{sender}: {text}", wraplength=400, justify="left")
        label.pack(anchor="w")

    def _add_system(self, text: str) -> None:
        self._add_msg("Sistema", text)

    def _toggle(self) -> None:
        self.connected = not self.connected
        if self.connected:
            self.status.configure(text="Conectado", text_color="green")
            self.btn_connect.configure(text="Desconectar")
            self._add_system("Proveedor activado.")
        else:
            self.status.configure(text="Desconectado", text_color="gray")
            self.btn_connect.configure(text="Conectar")
            self._add_system("Proveedor desactivado.")

    def _send(self) -> None:
        prompt = self.entry.get().strip()
        if not prompt:
            return
        self.entry.delete(0, "end")
        self._add_msg("Tú", prompt)
        # Simular respuesta (en producción sería async con router)
        self._add_msg("IA", "Respuesta simulada: " + prompt.upper())
        # En producción: asyncio.create_task(self._gen_real(prompt))

    def _on_enter(self, event) -> None:
        self._send()
        return "break"


def main() -> None:
    app = GSsmartApp()
    app.mainloop()


if __name__ == "__main__":
    main()