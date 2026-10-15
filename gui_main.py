import customtkinter as ctk
from tkinter import scrolledtext
import sys
from pathlib import Path

# -------------------------------------------------
# 1️⃣ CONFIGURACIÓN DE RUTAS – resuelta con pathlib
# -------------------------------------------------
BASE_DIR = Path(__file__).parent
CORE_PATH = (BASE_DIR / "src" / "core").resolve()

if str(CORE_PATH) not in sys.path:
    sys.path.insert(0, str(CORE_PATH))

try:
    from router import get_ai_response
except ImportError as e:
    def get_ai_response(text: str) -> str:
        return (
            f"Error al importar router desde {CORE_PATH}.\n"
            f"Detalles: {import_error}\n"
            "Verifica que 'src/core/router.py' exista y sea un módulo Python válido."
        )

# -------------------------------------------------
# 2️⃣ CONFIGURACIÓN DE LA INTERFAZ
# -------------------------------------------------
ctk.set_appearance_mode("dark")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AI Command Center - GSsmart")
        self.geometry("1100x600")

        # Barra lateral
        self.sidebar = ctk.CTkFrame(self, width=200, fg_color="#0f172a", corner_radius=0)
        self.sidebar.pack(side="left", fill="y", padx=5, pady=5)
        ctk.CTkLabel(
            self.sidebar,
            text="GSsmart AI",
            font=("Arial", 20, "bold"),
            text_color="#00ffff"
        ).pack(pady=20)

        # Panel de chat (lado derecho)
        self.chat_frame = ctk.CTkFrame(self, width=500, fg_color="#1e293b")
        self.chat_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        self.chat_display = scrolledtext.ScrolledText(
            self.chat_frame,
            bg="#0f172a",
            fg="white",
            font=("Segoe UI", 12),
            borderwidth=0,
            highlightthickness=0,
            wrap="word"
        )
        self.chat_display.pack(padx=10, pady=10, fill="both", expand=True)
        self.chat_display.config(state='disabled')

        # Entrada de usuario + botón de envío
        self.input_frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        self.input_frame.pack(fill="x", padx=10, pady=10)

        self.user_input = ctk.CTkEntry(
            self.input_frame,
            placeholder_text="Escribe tu mensaje aquí...",
            fg_color="#0f172a",
            text_color="white",
            height=40
        )
        self.user_input.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.send_button = ctk.CTkButton(
            self.input_frame,
            text="Enviar",
            width=80,
            fg_color="#00ffff",
            text_color="black",
            command=self.send_message
        )
        self.send_button.pack(side="right")

    # -------------------------------------------------
    # 3️⃣ LÓGICA DE INTERACCIÓN
    # -------------------------------------------------
    def send_message(self):
        message = self.user_input.get()
        if not message:
            return

        self.update_chat(f"Tú: {message}\n")
        self.user_input.delete(0, 'end')

        response = get_ai_response(message)
        self.update_chat(f"IA: {response}\n\n")

    def update_chat(self, text):
        self.chat_display.config(state='normal')
        self.chat_display.insert('end', text)
        self.chat_display.config(state='disabled')
        self.chat_display.see('end')

if __name__ == "__main__":
    app = App()
    app.mainloop()
