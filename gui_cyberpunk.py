"""
GSsmart Desktop - Interfaz HUD Ciberpunk
=========================================
Estilo: Futurista, neón cian, paneles flotantes, efecto de flotación
Inspirado en: HUDs de videojuegos, interfaces sci-fi, ciberpunk

Requisitos:
- customtkinter (ya instalado)
- Pillow (ya instalado)

Ejecutar: python gui_cyberpunk.py
"""

import customtkinter as ctk
import asyncio
import threading
from typing import Optional, List, Dict
from PIL import Image, ImageDraw, ImageFont
import math
import time

# ============================================================
# CONFIGURACIÓN DE COLORES Y ESTILO
# ============================================================

# Paleta de colores ciberpunk
COLORS = {
    "bg_dark": "#0D1117",           # Fondo principal oscuro
    "bg_panel": "#161B22",          # Fondo de paneles
    "bg_panel_transparent": "#161B2280",  # Panel semi-transparente
    "neon_cyan": "#00FFFF",         # Cian neón principal
    "neon_cyan_dim": "#008B8B",     # Cian atenuado
    "neon_magenta": "#FF0055",      # Magenta para alertas
    "neon_green": "#00FF7F",        # Verde neón para éxito
    "text_primary": "#E6EDF3",      # Texto principal
    "text_secondary": "#8B949E",    # Texto secundario
    "text_dim": "#484F58",          # Texto atenuado
    "border": "#30363D",            # Bordes estándar
    "border_neon": "#00FFFF",       # Bordes neón
    "grid": "#1F2937",              # Color de rejilla
    "glow": "#00FFFF40",            # Efecto de resplandor
}

# Configuración de la ventana
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
PANEL_MARGIN = 20
PANEL_PADDING = 15

# ============================================================
# CLASE PRINCIPAL DE LA APLICACIÓN
# ============================================================

class CyberpunkHUD(ctk.CTk):
    """
    Interfaz principal estilo HUD ciberpunk.
    """

    def __init__(self):
        super().__init__()

        # Configuración de la ventana
        self.title("GSsmart Desktop - HUD")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(900, 600)
        self.configure(fg_color=COLORS["bg_dark"])

        # Hacer la ventana transparente (efecto de flotación)
        self.attributes("-alpha", 0.95)
        self.attributes("-topmost", False)

        # Estado interno
        self.connected = False
        self.current_provider = "OmniRoute"
        self.messages: List[Dict] = []
        self.is_generating = False

        # Inicializar componentes
        self._setup_layout()
        self._create_background_grid()
        self._create_header_panel()
        self._create_provider_panel()
        self._create_chat_panel()
        self._create_status_panel()
        self._create_input_panel()
        self._create_decorative_elements()

        # Animaciones
        self._animate_status_light()
        self._animate_scan_line()

        # Mensaje inicial
        self._add_message("system", "Sistema iniciado. Conectando a proveedores...")
        self._add_message("system", "Proveedor OmniRoute detectado en localhost:20128")
        self._add_message("system", "Listo para recibir comandos.")

    # ============================================================
    # CONFIGURACIÓN DE LAYOUT
    # ============================================================

    def _setup_layout(self):
        """Configura la estructura general de la ventana."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Frame principal con padding
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=0, column=0, sticky="nsew", padx=PANEL_MARGIN, pady=PANEL_MARGIN)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=1)

        # Guardar referencia
        self.main_frame = main_frame

    # ============================================================
    # FONDO CON REJILLA
    # ============================================================

    def _create_background_grid(self):
        """Crea un fondo con rejilla sutil estilo HUD."""
        # Canvas para la rejilla (usar tkinter.Canvas directamente)
        import tkinter as tk
        grid_canvas = tk.Canvas(
            self,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            bg=COLORS["bg_dark"],
            highlightthickness=0
        )
        grid_canvas.place(x=0, y=0, relwidth=1, relheight=1)

        # Dibujar rejilla
        grid_size = 40

        # Líneas verticales
        for x in range(0, WINDOW_WIDTH, grid_size):
            grid_canvas.create_line(
                x, 0, x, WINDOW_HEIGHT,
                fill=COLORS["grid"],
                width=1
            )

        # Líneas horizontales
        for y in range(0, WINDOW_HEIGHT, grid_size):
            grid_canvas.create_line(
                0, y, WINDOW_WIDTH, y,
                fill=COLORS["grid"],
                width=1
            )

        # Coordenadas en las esquinas
        grid_canvas.create_text(
            10, 10,
            text="GSsmart v1.0",
            fill=COLORS["text_dim"],
            font=("Consolas", 8)
        )
        grid_canvas.create_text(
            WINDOW_WIDTH - 10, 10,
            text=f"SYS:{int(time.time())}",
            fill=COLORS["text_dim"],
            font=("Consolas", 8),
            anchor="ne"
        )
        grid_canvas.create_text(
            10, WINDOW_HEIGHT - 10,
            text="LAT: -34.9011 LON: -56.1645",
            fill=COLORS["text_dim"],
            font=("Consolas", 8)
        )
        grid_canvas.create_text(
            WINDOW_WIDTH - 10, WINDOW_HEIGHT - 10,
            text="STATUS: ONLINE",
            fill=COLORS["neon_green"],
            font=("Consolas", 8),
            anchor="se"
        )

    # ============================================================
    # PANEL DE CABECERA
    # ============================================================

    def _create_header_panel(self):
        """Crea el panel superior con título y estado."""
        header = ctk.CTkFrame(
            self.main_frame,
            fg_color=COLORS["bg_panel"],
            corner_radius=8,
            border_width=2,
            border_color=COLORS["neon_cyan"]
        )
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.grid_columnconfigure(1, weight=1)

        # Título con efecto neón
        title_label = ctk.CTkLabel(
            header,
            text="◈ GSMART DESKTOP ◈",
            font=("Consolas", 18, "bold"),
            text_color=COLORS["neon_cyan"],
            fg_color="transparent"
        )
        title_label.grid(row=0, column=0, padx=15, pady=10)

        # Subtítulo
        subtitle_label = ctk.CTkLabel(
            header,
            text="MULTI-PROVIDER AI INTERFACE",
            font=("Consolas", 10),
            text_color=COLORS["text_secondary"],
            fg_color="transparent"
        )
        subtitle_label.grid(row=0, column=1, padx=15, pady=10)

        # Indicador de estado
        self.status_indicator = ctk.CTkLabel(
            header,
            text="● ONLINE",
            font=("Consolas", 12, "bold"),
            text_color=COLORS["neon_green"],
            fg_color="transparent"
        )
        self.status_indicator.grid(row=0, column=2, padx=15, pady=10)

        # Línea decorativa
        line = ctk.CTkFrame(
            header,
            height=2,
            fg_color=COLORS["neon_cyan"],
            corner_radius=0
        )
        line.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 5))

    # ============================================================
    # PANEL DE PROVEEDORES
    # ============================================================

    def _create_provider_panel(self):
        """Crea el panel lateral izquierdo con selección de proveedores."""
        provider_panel = ctk.CTkFrame(
            self.main_frame,
            fg_color=COLORS["bg_panel"],
            corner_radius=8,
            border_width=2,
            border_color=COLORS["neon_cyan"]
        )
        provider_panel.grid(row=1, column=0, sticky="ns", padx=(0, 10))
        provider_panel.grid_columnconfigure(0, weight=1)

        # Título del panel
        title = ctk.CTkLabel(
            provider_panel,
            text="◈ PROVEEDORES ◈",
            font=("Consolas", 12, "bold"),
            text_color=COLORS["neon_cyan"],
            fg_color="transparent"
        )
        title.grid(row=0, column=0, padx=10, pady=(10, 5))

        # Lista de proveedores
        providers = ["OmniRoute", "OpenAI", "OpenRouter", "Custom"]
        self.provider_buttons = {}

        for i, provider in enumerate(providers):
            btn = ctk.CTkButton(
                provider_panel,
                text=f"  {provider}  ",
                font=("Consolas", 11),
                fg_color="transparent",
                hover_color=COLORS["neon_cyan_dim"],
                text_color=COLORS["text_primary"],
                border_width=1,
                border_color=COLORS["border"],
                command=lambda p=provider: self._select_provider(p)
            )
            btn.grid(row=i+1, column=0, sticky="ew", padx=10, pady=3)
            self.provider_buttons[provider] = btn

        # Botón de conectar
        self.connect_btn = ctk.CTkButton(
            provider_panel,
            text="◈ CONECTAR ◈",
            font=("Consolas", 12, "bold"),
            fg_color=COLORS["neon_cyan_dim"],
            hover_color=COLORS["neon_cyan"],
            text_color=COLORS["bg_dark"],
            border_width=2,
            border_color=COLORS["neon_cyan"],
            command=self._toggle_connection
        )
        self.connect_btn.grid(row=len(providers)+2, column=0, sticky="ew", padx=10, pady=(10, 10))

        # Información del proveedor actual
        self.provider_info = ctk.CTkLabel(
            provider_panel,
            text="Proveedor: OmniRoute\nModelo: auto/coding:free\nEstado: Desconectado",
            font=("Consolas", 9),
            text_color=COLORS["text_secondary"],
            fg_color=COLORS["bg_dark"],
            corner_radius=4,
            justify="left",
            anchor="w"
        )
        self.provider_info.grid(row=len(providers)+3, column=0, sticky="ew", padx=10, pady=(0, 10))

    # ============================================================
    # PANEL DE CHAT
    # ============================================================

    def _create_chat_panel(self):
        """Crea el panel central de conversación."""
        chat_panel = ctk.CTkFrame(
            self.main_frame,
            fg_color=COLORS["bg_panel"],
            corner_radius=8,
            border_width=2,
            border_color=COLORS["neon_cyan"]
        )
        chat_panel.grid(row=1, column=1, sticky="nsew", padx=(0, 10))
        chat_panel.grid_columnconfigure(0, weight=1)
        chat_panel.grid_rowconfigure(1, weight=1)

        # Título del panel
        title = ctk.CTkLabel(
            chat_panel,
            text="◈ CONVERSACIÓN ◈",
            font=("Consolas", 12, "bold"),
            text_color=COLORS["neon_cyan"],
            fg_color="transparent"
        )
        title.grid(row=0, column=0, padx=10, pady=(10, 5))

        # Área de mensajes (scrollable)
        self.chat_area = ctk.CTkScrollableFrame(
            chat_panel,
            fg_color=COLORS["bg_dark"],
            corner_radius=4,
            border_width=1,
            border_color=COLORS["border"]
        )
        self.chat_area.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.chat_area.grid_columnconfigure(0, weight=1)

        # Línea de escaneo animada
        self.scan_line = ctk.CTkFrame(
            chat_panel,
            height=2,
            fg_color=COLORS["neon_cyan"],
            corner_radius=0
        )
        self.scan_line.grid(row=2, column=0, sticky="ew", pady=(0, 10))

    # ============================================================
    # PANEL DE ESTADO
    # ============================================================

    def _create_status_panel(self):
        """Crea el panel derecho con indicadores de estado."""
        status_panel = ctk.CTkFrame(
            self.main_frame,
            fg_color=COLORS["bg_panel"],
            corner_radius=8,
            border_width=2,
            border_color=COLORS["neon_cyan"]
        )
        status_panel.grid(row=1, column=2, sticky="ns", padx=(0, 0))
        status_panel.grid_columnconfigure(0, weight=1)

        # Título del panel
        title = ctk.CTkLabel(
            status_panel,
            text="◈ ESTADO ◈",
            font=("Consolas", 12, "bold"),
            text_color=COLORS["neon_cyan"],
            fg_color="transparent"
        )
        title.grid(row=0, column=0, padx=10, pady=(10, 5))

        # Indicadores de estado
        indicators = [
            ("CPU", "12%", COLORS["neon_green"]),
            ("MEM", "45%", COLORS["neon_green"]),
            ("NET", "OK", COLORS["neon_green"]),
            ("GPU", "IDLE", COLORS["neon_cyan"]),
            ("API", "READY", COLORS["neon_green"]),
        ]

        for i, (label, value, color) in enumerate(indicators):
            # Frame del indicador
            indicator_frame = ctk.CTkFrame(
                status_panel,
                fg_color=COLORS["bg_dark"],
                corner_radius=4,
                border_width=1,
                border_color=COLORS["border"]
            )
            indicator_frame.grid(row=i+1, column=0, sticky="ew", padx=10, pady=3)
            indicator_frame.grid_columnconfigure(1, weight=1)

            # Etiqueta
            lbl = ctk.CTkLabel(
                indicator_frame,
                text=label,
                font=("Consolas", 10, "bold"),
                text_color=COLORS["text_secondary"],
                fg_color="transparent"
            )
            lbl.grid(row=0, column=0, padx=8, pady=5)

            # Valor
            val = ctk.CTkLabel(
                indicator_frame,
                text=value,
                font=("Consolas", 10, "bold"),
                text_color=color,
                fg_color="transparent"
            )
            val.grid(row=0, column=1, padx=8, pady=5, sticky="e")

        # Barra de progreso
        progress_frame = ctk.CTkFrame(
            status_panel,
            fg_color=COLORS["bg_dark"],
            corner_radius=4,
            border_width=1,
            border_color=COLORS["border"]
        )
        progress_frame.grid(row=len(indicators)+2, column=0, sticky="ew", padx=10, pady=(10, 5))
        progress_frame.grid_columnconfigure(0, weight=1)

        progress_label = ctk.CTkLabel(
            progress_frame,
            text="PROCESANDO",
            font=("Consolas", 9),
            text_color=COLORS["text_secondary"],
            fg_color="transparent"
        )
        progress_label.grid(row=0, column=0, padx=8, pady=(5, 0))

        self.progress_bar = ctk.CTkProgressBar(
            progress_frame,
            fg_color=COLORS["bg_panel"],
            progress_color=COLORS["neon_cyan"],
            height=8,
            corner_radius=4
        )
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 5))

        # Log de actividad
        log_title = ctk.CTkLabel(
            status_panel,
            text="◈ LOG ◈",
            font=("Consolas", 10, "bold"),
            text_color=COLORS["neon_cyan"],
            fg_color="transparent"
        )
        log_title.grid(row=len(indicators)+3, column=0, padx=10, pady=(10, 5))

        self.log_area = ctk.CTkScrollableFrame(
            status_panel,
            fg_color=COLORS["bg_dark"],
            corner_radius=4,
            border_width=1,
            border_color=COLORS["border"],
            height=150
        )
        self.log_area.grid(row=len(indicators)+4, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.log_area.grid_columnconfigure(0, weight=1)

        # Mensajes de log iniciales
        self._add_log("Sistema iniciado")
        self._add_log("Cargando proveedores...")
        self._add_log("OmniRoute detectado")
        self._add_log("Listo para operar")

    # ============================================================
    # PANEL DE ENTRADA
    # ============================================================

    def _create_input_panel(self):
        """Crea el panel inferior de entrada de texto."""
        input_panel = ctk.CTkFrame(
            self.main_frame,
            fg_color=COLORS["bg_panel"],
            corner_radius=8,
            border_width=2,
            border_color=COLORS["neon_cyan"]
        )
        input_panel.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        input_panel.grid_columnconfigure(0, weight=1)

        # Entrada de texto
        self.input_entry = ctk.CTkEntry(
            input_panel,
            placeholder_text="> Escribe tu prompt aquí...",
            font=("Consolas", 12),
            fg_color=COLORS["bg_dark"],
            border_width=1,
            border_color=COLORS["border"],
            height=40
        )
        self.input_entry.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        self.input_entry.bind("<Return>", self._on_enter)

        # Botón de enviar
        self.send_btn = ctk.CTkButton(
            input_panel,
            text="◈ ENVIAR ◈",
            font=("Consolas", 12, "bold"),
            fg_color=COLORS["neon_cyan_dim"],
            hover_color=COLORS["neon_cyan"],
            text_color=COLORS["bg_dark"],
            border_width=2,
            border_color=COLORS["neon_cyan"],
            command=self._send_message,
            width=120
        )
        self.send_btn.grid(row=0, column=1, padx=(0, 10), pady=10)

        # Botón de limpiar
        clear_btn = ctk.CTkButton(
            input_panel,
            text="LIMPIAR",
            font=("Consolas", 10),
            fg_color="transparent",
            hover_color=COLORS["neon_magenta"],
            text_color=COLORS["text_secondary"],
            border_width=1,
            border_color=COLORS["border"],
            command=self._clear_chat,
            width=80
        )
        clear_btn.grid(row=0, column=2, padx=(0, 10), pady=10)

    # ============================================================
    # ELEMENTOS DECORATIVOS
    # ============================================================

    def _create_decorative_elements(self):
        """Crea elementos decorativos estilo HUD."""
        # Esquinas decorativas
        corner_size = 30

        # Esquina superior izquierda
        self._create_corner(0, 0, corner_size, "tl")

        # Esquina superior derecha
        self._create_corner(WINDOW_WIDTH - corner_size, 0, corner_size, "tr")

        # Esquina inferior izquierda
        self._create_corner(0, WINDOW_HEIGHT - corner_size, corner_size, "bl")

        # Esquina inferior derecha
        self._create_corner(WINDOW_WIDTH - corner_size, WINDOW_HEIGHT - corner_size, corner_size, "br")

        # Líneas decorativas en los bordes
        # Línea superior
        top_line = ctk.CTkFrame(
            self,
            height=2,
            fg_color=COLORS["neon_cyan"],
            corner_radius=0
        )
        top_line.place(x=corner_size, y=0, width=WINDOW_WIDTH - 2*corner_size)

        # Línea inferior
        bottom_line = ctk.CTkFrame(
            self,
            height=2,
            fg_color=COLORS["neon_cyan"],
            corner_radius=0
        )
        bottom_line.place(x=corner_size, y=WINDOW_HEIGHT-2, width=WINDOW_WIDTH - 2*corner_size)

        # Línea izquierda
        left_line = ctk.CTkFrame(
            self,
            width=2,
            fg_color=COLORS["neon_cyan"],
            corner_radius=0
        )
        left_line.place(x=0, y=corner_size, height=WINDOW_HEIGHT - 2*corner_size)

        # Línea derecha
        right_line = ctk.CTkFrame(
            self,
            width=2,
            fg_color=COLORS["neon_cyan"],
            corner_radius=0
        )
        right_line.place(x=WINDOW_WIDTH-2, y=corner_size, height=WINDOW_HEIGHT - 2*corner_size)

    def _create_corner(self, x, y, size, position):
        """Crea una esquina decorativa usando tkinter.Canvas."""
        import tkinter as tk
        # Canvas de la esquina
        corner = tk.Canvas(
            self,
            width=size,
            height=size,
            bg=COLORS["bg_dark"],
            highlightthickness=0
        )
        corner.place(x=x, y=y)

        # Dibujar líneas de la esquina
        if position == "tl":  # Superior izquierda
            corner.create_line(0, 0, size, 0, fill=COLORS["neon_cyan"], width=2)
            corner.create_line(0, 0, 0, size, fill=COLORS["neon_cyan"], width=2)
        elif position == "tr":  # Superior derecha
            corner.create_line(0, 0, size, 0, fill=COLORS["neon_cyan"], width=2)
            corner.create_line(size, 0, size, size, fill=COLORS["neon_cyan"], width=2)
        elif position == "bl":  # Inferior izquierda
            corner.create_line(0, size, size, size, fill=COLORS["neon_cyan"], width=2)
            corner.create_line(0, 0, 0, size, fill=COLORS["neon_cyan"], width=2)
        elif position == "br":  # Inferior derecha
            corner.create_line(0, size, size, size, fill=COLORS["neon_cyan"], width=2)
            corner.create_line(size, 0, size, size, fill=COLORS["neon_cyan"], width=2)

    # ============================================================
    # ANIMACIONES
    # ============================================================

    def _animate_status_light(self):
        """Animación del indicador de estado (parpadeo)."""
        if self.connected:
            self.status_indicator.configure(text_color=COLORS["neon_green"])
        else:
            self.status_indicator.configure(text_color=COLORS["neon_magenta"])

        # Programar próxima animación
        self.after(1000, self._animate_status_light)

    def _animate_scan_line(self):
        """Animación de la línea de escaneo en el chat."""
        # Mover la línea de escaneo
        current_y = self.scan_line.winfo_y()
        max_y = self.chat_area.winfo_height()

        if current_y < max_y:
            self.scan_line.place(y=current_y + 2)
        else:
            self.scan_line.place(y=self.chat_area.winfo_y())

        # Programar próxima animación
        self.after(50, self._animate_scan_line)

    # ============================================================
    # FUNCIONES DE INTERACCIÓN
    # ============================================================

    def _select_provider(self, provider_name):
        """Selecciona un proveedor."""
        self.current_provider = provider_name

        # Actualizar botones
        for name, btn in self.provider_buttons.items():
            if name == provider_name:
                btn.configure(
                    fg_color=COLORS["neon_cyan_dim"],
                    text_color=COLORS["bg_dark"],
                    border_color=COLORS["neon_cyan"]
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=COLORS["text_primary"],
                    border_color=COLORS["border"]
                )

        # Actualizar información
        self.provider_info.configure(
            text=f"Proveedor: {provider_name}\nModelo: auto/coding:free\nEstado: Desconectado"
        )

        self._add_log(f"Proveedor seleccionado: {provider_name}")

    def _toggle_connection(self):
        """Alterna la conexión."""
        self.connected = not self.connected

        if self.connected:
            self.connect_btn.configure(
                text="◈ DESCONECTAR ◈",
                fg_color=COLORS["neon_magenta"],
                hover_color=COLORS["neon_magenta"],
                text_color=COLORS["text_primary"]
            )
            self.provider_info.configure(
                text=f"Proveedor: {self.current_provider}\nModelo: auto/coding:free\nEstado: Conectado"
            )
            self._add_log("Conectado al proveedor")
            self._add_message("system", f"Conectado a {self.current_provider}")
        else:
            self.connect_btn.configure(
                text="◈ CONECTAR ◈",
                fg_color=COLORS["neon_cyan_dim"],
                hover_color=COLORS["neon_cyan"],
                text_color=COLORS["bg_dark"]
            )
            self.provider_info.configure(
                text=f"Proveedor: {self.current_provider}\nModelo: auto/coding:free\nEstado: Desconectado"
            )
            self._add_log("Desconectado del proveedor")
            self._add_message("system", "Desconectado del proveedor")

    def _send_message(self):
        """Envía el mensaje del usuario."""
        prompt = self.input_entry.get().strip()
        if not prompt:
            return

        # Limpiar entrada
        self.input_entry.delete(0, "end")

        # Agregar mensaje del usuario
        self._add_message("user", prompt)

        # Simular respuesta (en producción sería async con router)
        self.is_generating = True
        self.progress_bar.set(0.3)
        self._add_log("Generando respuesta...")

        # Simular demora
        self.after(1500, lambda: self._simulate_response(prompt))

    def _simulate_response(self, prompt):
        """Simula una respuesta de la IA."""
        response = f"Respuesta simulada para: {prompt[:50]}..."

        self._add_message("ai", response)
        self.is_generating = False
        self.progress_bar.set(0)
        self._add_log("Respuesta generada")

    def _on_enter(self, event):
        """Maneja la tecla Enter."""
        self._send_message()
        return "break"

    def _clear_chat(self):
        """Limpia el chat."""
        for widget in self.chat_area.winfo_children():
            widget.destroy()
        self.messages.clear()
        self._add_log("Chat limpiado")

    # ============================================================
    # FUNCIONES DE MENSAJES
    # ============================================================

    def _add_message(self, sender, text):
        """Agrega un mensaje al chat."""
        # Crear frame del mensaje
        msg_frame = ctk.CTkFrame(
            self.chat_area,
            fg_color="transparent",
            corner_radius=0
        )
        msg_frame.pack(fill="x", pady=5, padx=5)
        msg_frame.grid_columnconfigure(0, weight=1)

        # Determinar color según el remitente
        if sender == "user":
            color = COLORS["neon_cyan"]
            prefix = "TÚ >"
        elif sender == "ai":
            color = COLORS["neon_green"]
            prefix = "IA >"
        else:
            color = COLORS["text_secondary"]
            prefix = "SYS >"

        # Etiqueta del mensaje
        label = ctk.CTkLabel(
            msg_frame,
            text=f"{prefix} {text}",
            font=("Consolas", 11),
            text_color=color,
            fg_color="transparent",
            justify="left",
            anchor="w",
            wraplength=500
        )
        label.grid(row=0, column=0, sticky="w")

        # Guardar mensaje
        self.messages.append({"sender": sender, "text": text, "time": time.time()})

        # Scroll al final
        self.chat_area.update_idletasks()
        self.chat_area._parent_canvas.yview_moveto(1.0)

    def _add_log(self, text):
        """Agrega una entrada al log."""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = ctk.CTkLabel(
            self.log_area,
            text=f"[{timestamp}] {text}",
            font=("Consolas", 8),
            text_color=COLORS["text_secondary"],
            fg_color="transparent",
            justify="left",
            anchor="w"
        )
        log_entry.pack(fill="x", pady=1, padx=5)

        # Scroll al final
        self.log_area.update_idletasks()
        self.log_area._parent_canvas.yview_moveto(1.0)


# ============================================================
# PUNTO DE ENTRADA
# ============================================================

def main():
    """Punto de entrada de la aplicación."""
    app = CyberpunkHUD()
    app.mainloop()


if __name__ == "__main__":
    main()