"""
GSsmart Desktop - Interfaz Ciberpunk Futurista

Diseño con:
- Colores neón cian (#00FFFF) y magenta (#FF00FF)
- Fondo oscuro con efectos de brillo
- Botones flotantes con animaciones
- Iconos futuristas (Unicode)
- Estilo HUD (Heads-Up Display)

Para ejecutar: python gui_cyber.py
"""

import customtkinter as ctk
import asyncio
import threading
from typing import Optional
from datetime import datetime

# Configuración de tema ciberpunk
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Paleta de colores ciberpunk
CYBER_COLORS = {
    "bg_dark": "#0a0a0f",
    "bg_panel": "#1a1a2e",
    "bg_hover": "#16213e",
    "neon_cyan": "#00ffff",
    "neon_magenta": "#ff00ff",
    "neon_green": "#00ff88",
    "neon_yellow": "#ffff00",
    "text_primary": "#e0e0e0",
    "text_secondary": "#888888",
    "border": "#2a2a4e",
    "glow_cyan": "#00ffff40",
    "glow_magenta": "#ff00ff40",
}


class CyberButton(ctk.CTkButton):
    """Botón con efecto de brillo neón."""
    
    def __init__(self, master, text="", command=None, color="cyan", **kwargs):
        color_map = {
            "cyan": CYBER_COLORS["neon_cyan"],
            "magenta": CYBER_COLORS["neon_magenta"],
            "green": CYBER_COLORS["neon_green"],
            "yellow": CYBER_COLORS["neon_yellow"],
        }
        btn_color = color_map.get(color, CYBER_COLORS["neon_cyan"])
        
        super().__init__(
            master,
            text=text,
            command=command,
            fg_color=CYBER_COLORS["bg_panel"],
            hover_color=CYBER_COLORS["bg_hover"],
            border_color=btn_color,
            border_width=2,
            text_color=btn_color,
            font=("Segoe UI", 12, "bold"),
            **kwargs
        )
        
        # Efecto de brillo al pasar el mouse
        self._btn_color = btn_color
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
    
    def _on_enter(self, event):
        self.configure(border_width=3)
    
    def _on_leave(self, event):
        self.configure(border_width=2)


class CyberLabel(ctk.CTkLabel):
    """Etiqueta con estilo ciberpunk."""
    
    def __init__(self, master, text="", color="cyan", **kwargs):
        color_map = {
            "cyan": CYBER_COLORS["neon_cyan"],
            "magenta": CYBER_COLORS["neon_magenta"],
            "green": CYBER_COLORS["neon_green"],
            "yellow": CYBER_COLORS["neon_yellow"],
            "primary": CYBER_COLORS["text_primary"],
            "secondary": CYBER_COLORS["text_secondary"],
        }
        text_color = color_map.get(color, CYBER_COLORS["text_primary"])
        
        # Set default font if not provided
        if "font" not in kwargs:
            kwargs["font"] = ("Segoe UI", 11)
        
        super().__init__(
            master,
            text=text,
            text_color=text_color,
            **kwargs
        )


class CyberFrame(ctk.CTkFrame):
    """Frame con borde neón."""
    
    def __init__(self, master, color="cyan", **kwargs):
        color_map = {
            "cyan": CYBER_COLORS["neon_cyan"],
            "magenta": CYBER_COLORS["neon_magenta"],
            "green": CYBER_COLORS["neon_green"],
        }
        border_color = color_map.get(color, CYBER_COLORS["neon_cyan"])
        
        super().__init__(
            master,
            fg_color=CYBER_COLORS["bg_panel"],
            border_color=border_color,
            border_width=1,
            corner_radius=8,
            **kwargs
        )


class GSsmartCyberApp(ctk.CTk):
    """
    Aplicación principal con interfaz ciberpunk futurista.
    """
    
    def __init__(self):
        super().__init__()
        
        # Configuración de ventana
        self.title("GSsmart Desktop - Cyberpunk AI Interface")
        self.geometry("1000x700")
        self.minsize(800, 600)
        self.configure(fg_color=CYBER_COLORS["bg_dark"])
        
        # Inicializar router
        self.router = None
        self.current_provider = None
        self.connected = False
        
        # Layout principal
        self._setup_layout()
        
        # Cargar proveedores
        self.after(300, self._load_providers)
        
        # Animación de fondo
        self._animate_background()
    
    def _setup_layout(self):
        """Configura el layout principal de la interfaz."""
        
        # Grid principal
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # --- HEADER (Barra superior) ---
        header = CyberFrame(self, color="cyan")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        header.grid_columnconfigure(1, weight=1)
        
        # Logo/Icono
        logo_frame = ctk.CTkFrame(header, fg_color="transparent")
        logo_frame.grid(row=0, column=0, padx=(10, 10), pady=10)
        
        logo_label = CyberLabel(logo_frame, text="⚡", color="cyan", font=("Segoe UI", 24, "bold"))
        logo_label.pack(side="left")
        
        title_label = CyberLabel(logo_frame, text="GSsmart", color="cyan", font=("Segoe UI", 18, "bold"))
        title_label.pack(side="left", padx=(5, 0))
        
        subtitle_label = CyberLabel(logo_frame, text="CYBERPUNK AI", color="magenta", font=("Segoe UI", 10))
        subtitle_label.pack(side="left", padx=(5, 0))
        
        # Estado del sistema
        status_frame = ctk.CTkFrame(header, fg_color="transparent")
        status_frame.grid(row=0, column=1, padx=(0, 10), pady=10)
        
        self.status_icon = CyberLabel(status_frame, text="●", color="secondary", font=("Segoe UI", 12))
        self.status_icon.pack(side="left")
        
        self.status_text = CyberLabel(status_frame, text="OFFLINE", color="secondary", font=("Segoe UI", 10, "bold"))
        self.status_text.pack(side="left", padx=(5, 0))
        
        # Reloj
        self.clock_label = CyberLabel(status_frame, text="", color="cyan", font=("Segoe UI", 10))
        self.clock_label.pack(side="left", padx=(20, 0))
        
        # --- MAIN CONTENT (Contenido principal) ---
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)
        
        # --- PANEL IZQUIERDO (Proveedores) ---
        left_panel = CyberFrame(main_frame, color="magenta")
        left_panel.grid(row=0, column=0, sticky="ns", padx=(0, 5))
        left_panel.grid_rowconfigure(1, weight=1)
        
        # Título del panel
        left_title = CyberLabel(left_panel, text="◈ PROVIDERS", color="magenta", font=("Segoe UI", 12, "bold"))
        left_title.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))
        
        # Lista de proveedores
        self.providers_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        self.providers_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.providers_frame.grid_columnconfigure(0, weight=1)
        
        # --- PANEL CENTRAL (Chat) ---
        center_panel = CyberFrame(main_frame, color="cyan")
        center_panel.grid(row=0, column=1, sticky="nsew", padx=5)
        center_panel.grid_columnconfigure(0, weight=1)
        center_panel.grid_rowconfigure(1, weight=1)
        
        # Título del chat
        chat_title = CyberLabel(center_panel, text="◈ NEURAL INTERFACE", color="cyan", font=("Segoe UI", 12, "bold"))
        chat_title.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))
        
        # Área de mensajes
        self.chat_frame = ctk.CTkScrollableFrame(center_panel, fg_color=CYBER_COLORS["bg_dark"], corner_radius=0)
        self.chat_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.chat_frame.grid_columnconfigure(0, weight=1)
        
        # Mensaje de bienvenida
        self._add_message("system", "SISTEMA", "Interfaz neural inicializada. Selecciona un proveedor y conecta.")
        
        # --- PANEL DERECHO (Estado) ---
        right_panel = CyberFrame(main_frame, color="green")
        right_panel.grid(row=0, column=2, sticky="ns", padx=(5, 0))
        right_panel.grid_rowconfigure(1, weight=1)
        
        # Título del panel
        right_title = CyberLabel(right_panel, text="◈ STATUS", color="green", font=("Segoe UI", 12, "bold"))
        right_title.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))
        
        # Información del proveedor
        self.info_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        self.info_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.info_frame.grid_columnconfigure(0, weight=1)
        
        self.info_label = CyberLabel(self.info_frame, text="Sin proveedor seleccionado", color="secondary", font=("Segoe UI", 10))
        self.info_label.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        
        # --- INPUT AREA (Área de entrada) ---
        input_frame = CyberFrame(self, color="cyan")
        input_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(5, 10))
        input_frame.grid_columnconfigure(0, weight=1)
        
        # Entrada de texto
        self.entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="> Escribe tu prompt aquí...",
            height=50,
            fg_color=CYBER_COLORS["bg_dark"],
            border_color=CYBER_COLORS["neon_cyan"],
            border_width=1,
            text_color=CYBER_COLORS["text_primary"],
            font=("Segoe UI", 12)
        )
        self.entry.grid(row=0, column=0, sticky="ew", padx=(10, 5), pady=10)
        self.entry.bind("<Return>", self._on_enter)
        
        # Botón enviar
        self.send_btn = CyberButton(
            input_frame,
            text="▶ ENVIAR",
            command=self._send_message,
            color="cyan",
            width=120,
            height=50
        )
        self.send_btn.grid(row=0, column=1, padx=(0, 10), pady=10)
    
    def _load_providers(self):
        """Carga la lista de proveedores disponibles."""
        try:
            from src.core.config import list_providers
            providers = list_providers()
            
            for i, provider in enumerate(providers):
                btn = CyberButton(
                    self.providers_frame,
                    text=f"◈ {provider}",
                    command=lambda p=provider: self._select_provider(p),
                    color="cyan",
                    width=150,
                    height=40
                )
                btn.grid(row=i, column=0, padx=5, pady=5, sticky="ew")
            
            # Botón de conectar
            self.connect_btn = CyberButton(
                self.providers_frame,
                text="⚡ CONECTAR",
                command=self._toggle_connection,
                color="magenta",
                width=150,
                height=50
            )
            self.connect_btn.grid(row=len(providers), column=0, padx=5, pady=(10, 5), sticky="ew")
            
        except Exception as e:
            self._add_message("error", "ERROR", f"No se pudieron cargar proveedores: {str(e)}")
    
    def _select_provider(self, provider_name):
        """Selecciona un proveedor."""
        self.current_provider = provider_name
        self.info_label.configure(text=f"Proveedor: {provider_name}")
        self._add_message("system", "SISTEMA", f"Proveedor seleccionado: {provider_name}")
    
    def _toggle_connection(self):
        """Alterna la conexión con el proveedor."""
        if not self.current_provider:
            self._add_message("error", "ERROR", "Selecciona un proveedor primero")
            return
        
        self.connected = not self.connected
        
        if self.connected:
            self.status_icon.configure(text="●", text_color=CYBER_COLORS["neon_green"])
            self.status_text.configure(text="ONLINE", text_color=CYBER_COLORS["neon_green"])
            self.connect_btn.configure(text="⚡ DESCONECTAR")
            self._add_message("system", "SISTEMA", f"Conectado a {self.current_provider}")
        else:
            self.status_icon.configure(text="●", text_color=CYBER_COLORS["text_secondary"])
            self.status_text.configure(text="OFFLINE", text_color=CYBER_COLORS["text_secondary"])
            self.connect_btn.configure(text="⚡ CONECTAR")
            self._add_message("system", "SISTEMA", "Desconectado")
    
    def _send_message(self):
        """Envía el mensaje del usuario."""
        prompt = self.entry.get().strip()
        if not prompt:
            return
        
        self.entry.delete(0, "end")
        self._add_message("user", "TÚ", prompt)
        
        # Simular respuesta (en producción sería async con router)
        self._add_message("system", "SISTEMA", "Procesando...")
        
        # En producción: asyncio.create_task(self._generate_response(prompt))
        self.after(1000, lambda: self._add_message("ai", "IA", f"Respuesta simulada para: {prompt[:50]}..."))
    
    def _on_enter(self, event):
        """Maneja la tecla Enter."""
        self._send_message()
        return "break"
    
    def _add_message(self, msg_type, sender, text):
        """Agrega un mensaje al área de chat."""
        colors = {
            "user": CYBER_COLORS["neon_cyan"],
            "ai": CYBER_COLORS["neon_magenta"],
            "system": CYBER_COLORS["neon_green"],
            "error": CYBER_COLORS["neon_yellow"],
        }
        
        color = colors.get(msg_type, CYBER_COLORS["text_primary"])
        
        frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        frame.pack(fill="x", pady=3, padx=5)
        
        # Timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        time_label = CyberLabel(frame, text=f"[{timestamp}]", color="secondary", font=("Segoe UI", 8))
        time_label.pack(anchor="w")
        
        # Mensaje
        msg_label = CyberLabel(frame, text=f"{sender}: {text}", color=msg_type, font=("Segoe UI", 11), wraplength=400, justify="left")
        msg_label.pack(anchor="w", pady=(2, 0))
        
        # Scroll al final
        self.chat_frame._parent_canvas.yview_moveto(1.0)
    
    def _animate_background(self):
        """Animación sutil de fondo (efecto de pulso)."""
        # Actualizar reloj
        now = datetime.now().strftime("%H:%M:%S")
        self.clock_label.configure(text=f"◈ {now}")
        
        # Programar próxima actualización
        self.after(1000, self._animate_background)


def main():
    """Punto de entrada de la aplicación."""
    app = GSsmartCyberApp()
    app.mainloop()


if __name__ == "__main__":
    main()