import customtkinter as ctk
from tkinter import scrolledtext

# =============================================================================
# CONFIGURACIÓN DE ESTÉTICA (Cyberpunk Theme)
# =============================================================================
COLOR_BG = "#0a0f1a"        # Azul noche profundo
COLOR_PANEL = "#0f172a"    # Azul oscuro para paneles
COLOR_ACCENT = "#00ffff"     # Cian Neón
COLOR_TEXT = "#e2e8f0"      # Blanco grisáceo

ctk.set_appearance_mode("dark") 

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AI Command Center - GSsmart")
        self.geometry("1200x700")
        self.configure(fg_color=COLOR_BG)

        # Estado del panel de chat (Abierto/Cerrado)
        self.chat_open = True

        # ---------------------------------------------------------------------
        # 1. SIDEBAR IZQUIERDO (Opciones y Proveedores)
        # ---------------------------------------------------------------------
        self.sidebar = ctk.CTkFrame(self, width=200, fg_color=COLOR_PANEL, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")

        self.logo_label = ctk.CTkLabel(self.sidebar, text="GSsmart AI", 
                                     font=ctk.CTkFont(size=20, weight="bold"), 
                                     text_color=COLOR_ACCENT)
        self.logo_label.pack(pady=20, padx=10)

        # Botones de Proveedores (Ejemplos)
        self.btn_openai = ctk.CTkButton(self.sidebar, text="OpenAI", fg_color="transparent", 
                                         border_color=COLOR_ACCENT, border_width=1, 
                                         text_color=COLOR_TEXT, hover_color="#1e293b")
        self.btn_openai.pack(pady=10, padx=20, fill="x")

        self.btn_ollama = ctk.CTkButton(self.sidebar, text="Ollama", fg_color="transparent", 
                                         border_color=COLOR_ACCENT, border_width=1, 
                                         text_color=COLOR_TEXT, hover_color="#1e293b")
        self.btn_ollama.pack(pady=10, padx=20, fill="x")

        # ---------------------------------------------------------------------
        # 2. ÁREA DE TRABAJO CENTRAL (Código/Documentos)
        # ---------------------------------------------------------------------
        self.work_area = ctk.CTkFrame(self, fg_color=COLOR_BG)
        self.work_area.pack(side="left", fill="both", expand=True)

        self.editor_label = ctk.CTkLabel(self.work_area, text="EDITOR DE CÓDIGO / TRABAJO", 
                                            font=ctk.CTkFont(size=12), text_color="gray")
        self.editor_label.pack(pady=10)

        self.textbox = scrolledtext.ScrolledText(self.work_area, bg="#0f172a", fg=COLOR_TEXT, 
                                               insertbackground="white", font=("Consolas", 12),
                                               borderwidth=0, highlightthickness=0)
        self.textbox.pack(expand=True, fill="both", padx=20, pady=20)

        # ---------------------------------------------------------------------
        # 3. PANEL DE CHAT DESPLEGABLE (Derecha)
        # ---------------------------------------------------------------------
        self.chat_panel = ctk.CTkFrame(self, width=350, fg_color=COLOR_PANEL)
        self.chat_panel.pack