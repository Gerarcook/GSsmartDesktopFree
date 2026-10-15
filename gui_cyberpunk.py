"""
GSsmart Desktop - Interfaz de chat HUD Ciberpunk
================================================
Estilo: futurista, neón cian, paneles flotantes con bordes luminosos.

Funciones:
- Chat con burbujas flotantes (operador / IA / sistema) y marcas de tiempo
- Respuestas reales en streaming a través de ProviderRouter (src/core/router.py)
- Modo demo automático si no hay proveedores configurados
- Panel de telemetría en vivo (latencia, tokens, CPU/MEM si psutil está instalado)
- Enter envía, Shift+Enter inserta salto de línea

Ejecutar: python gui_cyberpunk.py
"""

import asyncio
import queue
import random
import threading
import time
import tkinter as tk
from typing import Dict, List, Optional

import customtkinter as ctk

try:
    import psutil
except ImportError:
    psutil = None

try:
    from src.core.router import ProviderRouter
except Exception as import_error:
    ProviderRouter = None
    ROUTER_IMPORT_ERROR: Optional[str] = str(import_error)
else:
    ROUTER_IMPORT_ERROR = None


# ============================================================
# PALETA Y TIPOGRAFÍA
# ============================================================

COLORS = {
    "bg": "#05070D",
    "panel": "#0A111C",
    "panel_raised": "#0E1726",
    "cyan": "#00F0FF",
    "cyan_mid": "#00A8B5",
    "cyan_dim": "#0B3A44",
    "magenta": "#FF2A6D",
    "magenta_dim": "#3D0F22",
    "green": "#05FFA1",
    "text": "#E4F6F8",
    "text_muted": "#7A8EA0",
    "text_dim": "#3A4A5C",
    "grid": "#0C1624",
}

FONT = "Consolas"
DEMO_PROVIDER = "DEMO"
SYSTEM_PROMPT = "Sos GSsmart, un asistente útil. Respondé de forma clara y concisa."
MAX_HISTORY_MESSAGES = 20
UI_POLL_MS = 30


# ============================================================
# EJECUTOR ASYNC EN SEGUNDO PLANO
# ============================================================

class AsyncRunner:
    """Mantiene un event loop en un hilo aparte para no bloquear Tkinter."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()

    def submit(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def stop(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)


# ============================================================
# COMPONENTES REUTILIZABLES
# ============================================================

class NeonPanel(ctk.CTkFrame):
    """Panel flotante con borde neón que se ilumina al pasar el mouse."""

    def __init__(self, master, title: str, tag: str = "", **kwargs):
        super().__init__(
            master,
            fg_color=COLORS["panel"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["cyan_dim"],
            **kwargs,
        )
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkFrame(header, width=3, height=14, fg_color=COLORS["cyan"], corner_radius=0).grid(
            row=0, column=0, padx=(0, 8)
        )
        ctk.CTkLabel(
            header, text=title.upper(), font=(FONT, 11, "bold"), text_color=COLORS["cyan"]
        ).grid(row=0, column=1, sticky="w")
        if tag:
            ctk.CTkLabel(
                header, text=tag, font=(FONT, 9), text_color=COLORS["text_dim"]
            ).grid(row=0, column=2, sticky="e")

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.body.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.bind("<Enter>", lambda _e: self.configure(border_color=COLORS["cyan_mid"]))
        self.bind("<Leave>", lambda _e: self.configure(border_color=COLORS["cyan_dim"]))


class MessageBubble(ctk.CTkFrame):
    """Burbuja de mensaje flotante."""

    STYLES = {
        "user": ("OPERADOR", COLORS["cyan"], COLORS["panel_raised"], "e"),
        "ai": ("GSSMART", COLORS["green"], COLORS["panel_raised"], "w"),
        "system": ("SISTEMA", COLORS["text_muted"], COLORS["bg"], "center"),
        "error": ("ERROR", COLORS["magenta"], COLORS["magenta_dim"], "w"),
    }

    def __init__(self, master, sender: str, text: str, wraplength: int):
        label, accent, bg, self.align = self.STYLES.get(sender, self.STYLES["system"])
        super().__init__(
            master,
            fg_color=bg,
            corner_radius=10,
            border_width=1,
            border_color=accent if sender != "system" else COLORS["text_dim"],
        )
        self.sender = sender
        self.grid_columnconfigure(0, weight=1)

        meta = ctk.CTkFrame(self, fg_color="transparent")
        meta.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 0))
        ctk.CTkLabel(meta, text=f"◢ {label}", font=(FONT, 9, "bold"), text_color=accent).pack(side="left")
        ctk.CTkLabel(
            meta, text=time.strftime("  //  %H:%M:%S"), font=(FONT, 9), text_color=COLORS["text_dim"]
        ).pack(side="left")

        self.text_label = ctk.CTkLabel(
            self,
            text=text,
            font=(FONT, 12 if sender != "system" else 10),
            text_color=COLORS["text"] if sender != "system" else COLORS["text_muted"],
            justify="left",
            anchor="w",
            wraplength=wraplength,
        )
        self.text_label.grid(row=1, column=0, sticky="w", padx=12, pady=(2, 10))
        self.text = text

    def append(self, chunk: str) -> None:
        self.text += chunk
        self.text_label.configure(text=self.text)

    def set_text(self, text: str) -> None:
        self.text = text
        self.text_label.configure(text=text)

    def set_wraplength(self, value: int) -> None:
        self.text_label.configure(wraplength=value)


# ============================================================
# APLICACIÓN PRINCIPAL
# ============================================================

class CyberpunkHUD(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")

        self.title("GSsmart Desktop // Neural Chat")
        self.geometry("1240x800")
        self.minsize(960, 620)
        self.configure(fg_color=COLORS["bg"])
        try:
            self.attributes("-alpha", 0.97)
        except tk.TclError:
            pass

        self.runner = AsyncRunner()
        self.router = None
        self.provider_names: List[str] = []
        self.current_provider: str = DEMO_PROVIDER
        self.bubbles: List[MessageBubble] = []
        self.messages: List[Dict] = []
        self.is_generating = False
        self._closing = False
        self._ui_queue: "queue.Queue[tuple]" = queue.Queue()
        self._current_future = None
        self._router_error: Optional[str] = None
        self.token_count = 0
        self.last_latency_ms: Optional[int] = None
        self._scan_x = 0
        self._blink = False
        self._thinking_step = 0

        self._init_router()

        self._create_background()
        self._create_layout()
        self._create_header()
        self._create_sidebar()
        self._create_chat()
        self._create_telemetry()
        self._create_input()

        self._select_provider(self.current_provider, log=False)
        self._boot_sequence()

        self._animate_scan()
        self._animate_status()
        self._update_telemetry()
        self._drain_ui_queue()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------
    # PUENTE HILO DE FONDO -> HILO DE TKINTER
    # ------------------------------------------------------------

    def _post(self, fn, *args) -> None:
        """Llamable desde cualquier hilo: encola una actualización de la UI.

        Tkinter no es thread-safe, así que el hilo asyncio nunca toca widgets;
        solo deja tareas en la cola que el hilo principal procesa en _drain_ui_queue.
        """
        if not self._closing:
            self._ui_queue.put((fn, args))

    def _drain_ui_queue(self) -> None:
        if self._closing:
            return
        try:
            while True:
                fn, args = self._ui_queue.get_nowait()
                fn(*args)
        except queue.Empty:
            pass
        self.after(UI_POLL_MS, self._drain_ui_queue)

    # ------------------------------------------------------------
    # BACKEND
    # ------------------------------------------------------------

    def _init_router(self) -> None:
        if ProviderRouter is None:
            self._router_error = ROUTER_IMPORT_ERROR
            return
        try:
            self.router = ProviderRouter()
            self.provider_names = list(self.router.providers)
        except Exception as e:
            self.router = None
            self._router_error = str(e)
        if self.provider_names:
            self.current_provider = self.provider_names[0]

    def _provider_details(self, name: str) -> Dict[str, str]:
        if name == DEMO_PROVIDER or not self.router:
            return {"model": "simulador-local", "endpoint": "offline"}
        prov = self.router.get(name)
        return {"model": prov.model or "auto", "endpoint": prov.base_url or "-"}

    # ------------------------------------------------------------
    # FONDO
    # ------------------------------------------------------------

    def _create_background(self) -> None:
        self.bg_canvas = tk.Canvas(self, bg=COLORS["bg"], highlightthickness=0, bd=0)
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.bg_canvas.bind("<Configure>", self._draw_background)

    def _draw_background(self, event) -> None:
        c = self.bg_canvas
        c.delete("all")
        w, h, step = event.width, event.height, 32
        for x in range(0, w, step):
            c.create_line(x, 0, x, h, fill=COLORS["grid"])
        for y in range(0, h, step):
            c.create_line(0, y, w, y, fill=COLORS["grid"])

        size = 26
        for (x, y, dx, dy) in [(6, 6, 1, 1), (w - 6, 6, -1, 1), (6, h - 6, 1, -1), (w - 6, h - 6, -1, -1)]:
            c.create_line(x, y, x + dx * size, y, fill=COLORS["cyan"], width=2)
            c.create_line(x, y, x, y + dy * size, fill=COLORS["cyan"], width=2)

        c.create_text(40, h - 10, text="LAT -34.9011 / LON -56.1645", fill=COLORS["text_dim"],
                      font=(FONT, 8), anchor="w")
        c.create_text(w - 40, h - 10, text="GSSMART // BUILD 2.0", fill=COLORS["text_dim"],
                      font=(FONT, 8), anchor="e")

    # ------------------------------------------------------------
    # LAYOUT
    # ------------------------------------------------------------

    def _create_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.root_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.root_frame.grid(row=0, column=0, sticky="nsew", padx=22, pady=(20, 24))
        self.root_frame.grid_columnconfigure(1, weight=1)
        self.root_frame.grid_rowconfigure(1, weight=1)

    # ------------------------------------------------------------
    # CABECERA
    # ------------------------------------------------------------

    def _create_header(self) -> None:
        header = ctk.CTkFrame(
            self.root_frame, fg_color=COLORS["panel"], corner_radius=10,
            border_width=1, border_color=COLORS["cyan_dim"], height=58,
        )
        header.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 14))
        header.grid_columnconfigure(1, weight=1)

        brand = ctk.CTkFrame(header, fg_color="transparent")
        brand.grid(row=0, column=0, padx=18, pady=10, sticky="w")
        ctk.CTkLabel(brand, text="◈ GSSMART", font=(FONT, 20, "bold"),
                     text_color=COLORS["cyan"]).pack(side="left")
        ctk.CTkLabel(brand, text="  NEURAL//CHAT", font=(FONT, 12),
                     text_color=COLORS["text_muted"]).pack(side="left", pady=(4, 0))

        self.scan_canvas = tk.Canvas(header, height=4, bg=COLORS["panel"], highlightthickness=0, bd=0)
        self.scan_canvas.grid(row=0, column=1, sticky="ew", padx=10)

        status = ctk.CTkFrame(header, fg_color=COLORS["bg"], corner_radius=6,
                              border_width=1, border_color=COLORS["cyan_dim"])
        status.grid(row=0, column=2, padx=18, pady=10, sticky="e")
        self.status_dot = ctk.CTkLabel(status, text="●", font=(FONT, 12), text_color=COLORS["green"])
        self.status_dot.pack(side="left", padx=(10, 4), pady=4)
        self.status_text = ctk.CTkLabel(status, text="ENLACE ACTIVO", font=(FONT, 10, "bold"),
                                        text_color=COLORS["text"])
        self.status_text.pack(side="left", padx=(0, 10), pady=4)

    # ------------------------------------------------------------
    # BARRA LATERAL: PROVEEDORES
    # ------------------------------------------------------------

    def _create_sidebar(self) -> None:
        panel = NeonPanel(self.root_frame, "Proveedores", tag="NODE-01", width=230)
        panel.grid(row=1, column=0, rowspan=2, sticky="nsw", padx=(0, 14))
        panel.grid_propagate(False)
        body = panel.body

        names = self.provider_names or [DEMO_PROVIDER]
        self.provider_buttons: Dict[str, ctk.CTkButton] = {}
        for i, name in enumerate(names):
            btn = ctk.CTkButton(
                body, text=f"▸ {name}", anchor="w", font=(FONT, 11), height=34,
                fg_color="transparent", hover_color=COLORS["cyan_dim"],
                text_color=COLORS["text"], border_width=1, border_color=COLORS["text_dim"],
                corner_radius=6, command=lambda n=name: self._select_provider(n),
            )
            btn.grid(row=i, column=0, sticky="ew", pady=3)
            self.provider_buttons[name] = btn

        info = ctk.CTkFrame(body, fg_color=COLORS["bg"], corner_radius=6,
                            border_width=1, border_color=COLORS["text_dim"])
        info.grid(row=len(names), column=0, sticky="ew", pady=(14, 0))
        info.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(info, text="MODELO", font=(FONT, 8, "bold"),
                     text_color=COLORS["text_dim"]).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 0))
        self.model_label = ctk.CTkLabel(info, text="-", font=(FONT, 10), text_color=COLORS["cyan"],
                                        anchor="w", justify="left", wraplength=180)
        self.model_label.grid(row=1, column=0, sticky="w", padx=10)
        ctk.CTkLabel(info, text="ENDPOINT", font=(FONT, 8, "bold"),
                     text_color=COLORS["text_dim"]).grid(row=2, column=0, sticky="w", padx=10, pady=(6, 0))
        self.endpoint_label = ctk.CTkLabel(info, text="-", font=(FONT, 9), text_color=COLORS["text_muted"],
                                           anchor="w", justify="left", wraplength=180)
        self.endpoint_label.grid(row=3, column=0, sticky="w", padx=10, pady=(0, 8))

        if not self.provider_names:
            hint = "Sin proveedores en .env\nModo demo activo."
            if ROUTER_IMPORT_ERROR:
                hint = "Router no disponible.\nModo demo activo."
            ctk.CTkLabel(body, text=hint, font=(FONT, 9), text_color=COLORS["magenta"],
                         justify="left", anchor="w").grid(row=len(names) + 1, column=0, sticky="w", pady=(10, 0))

        ctk.CTkButton(
            body, text="NUEVA SESIÓN", font=(FONT, 11, "bold"), height=36,
            fg_color="transparent", hover_color=COLORS["magenta_dim"], text_color=COLORS["magenta"],
            border_width=1, border_color=COLORS["magenta"], corner_radius=6,
            command=self._clear_chat,
        ).grid(row=len(names) + 2, column=0, sticky="ew", pady=(16, 0))

    # ------------------------------------------------------------
    # CHAT
    # ------------------------------------------------------------

    def _create_chat(self) -> None:
        panel = NeonPanel(self.root_frame, "Canal de conversación", tag="STREAM // LIVE")
        panel.grid(row=1, column=1, sticky="nsew")
        panel.body.grid_rowconfigure(0, weight=1)

        self.chat_area = ctk.CTkScrollableFrame(
            panel.body, fg_color=COLORS["bg"], corner_radius=8,
            scrollbar_button_color=COLORS["cyan_dim"], scrollbar_button_hover_color=COLORS["cyan_mid"],
        )
        self.chat_area.grid(row=0, column=0, sticky="nsew")
        self.chat_area.grid_columnconfigure(0, weight=1)
        self.chat_area.bind("<Configure>", self._on_chat_resize)

        self.thinking_label = ctk.CTkLabel(panel.body, text="", font=(FONT, 10),
                                           text_color=COLORS["cyan_mid"], anchor="w")
        self.thinking_label.grid(row=1, column=0, sticky="w", pady=(6, 0))

    def _bubble_wraplength(self) -> int:
        width = self.chat_area.winfo_width()
        return max(260, int(width * 0.68))

    def _on_chat_resize(self, _event) -> None:
        wrap = self._bubble_wraplength()
        for bubble in self.bubbles:
            bubble.set_wraplength(wrap if bubble.sender != "system" else wrap + 80)

    # ------------------------------------------------------------
    # TELEMETRÍA
    # ------------------------------------------------------------

    def _create_telemetry(self) -> None:
        panel = NeonPanel(self.root_frame, "Telemetría", tag="LIVE", width=240)
        panel.grid(row=1, column=2, rowspan=2, sticky="nse", padx=(14, 0))
        panel.grid_propagate(False)
        body = panel.body
        body.grid_rowconfigure(6, weight=1)

        self.metric_labels: Dict[str, ctk.CTkLabel] = {}
        self.metric_bars: Dict[str, ctk.CTkProgressBar] = {}
        for i, key in enumerate(["CPU", "MEM"]):
            self._metric_row(body, i, key, with_bar=True)
        for i, key in enumerate(["LATENCIA", "TOKENS", "MENSAJES"], start=2):
            self._metric_row(body, i, key, with_bar=False)

        ctk.CTkLabel(body, text="◢ REGISTRO", font=(FONT, 10, "bold"),
                     text_color=COLORS["cyan"]).grid(row=5, column=0, sticky="w", pady=(14, 4))
        self.log_box = ctk.CTkTextbox(
            body, font=(FONT, 9), fg_color=COLORS["bg"], text_color=COLORS["text_muted"],
            corner_radius=6, border_width=1, border_color=COLORS["text_dim"], wrap="word",
        )
        self.log_box.grid(row=6, column=0, sticky="nsew")
        self.log_box.configure(state="disabled")

    def _metric_row(self, parent, row: int, key: str, with_bar: bool) -> None:
        frame = ctk.CTkFrame(parent, fg_color=COLORS["bg"], corner_radius=6,
                             border_width=1, border_color=COLORS["text_dim"])
        frame.grid(row=row, column=0, sticky="ew", pady=3)
        frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(frame, text=key, font=(FONT, 9, "bold"),
                     text_color=COLORS["text_muted"]).grid(row=0, column=0, sticky="w", padx=10, pady=(6, 2 if with_bar else 6))
        value = ctk.CTkLabel(frame, text="--", font=(FONT, 11, "bold"), text_color=COLORS["cyan"])
        value.grid(row=0, column=1, sticky="e", padx=10, pady=(6, 2 if with_bar else 6))
        self.metric_labels[key] = value
        if with_bar:
            bar = ctk.CTkProgressBar(frame, height=4, corner_radius=2, fg_color=COLORS["panel_raised"],
                                     progress_color=COLORS["cyan"])
            bar.set(0)
            bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 8))
            self.metric_bars[key] = bar

    # ------------------------------------------------------------
    # ENTRADA
    # ------------------------------------------------------------

    def _create_input(self) -> None:
        panel = ctk.CTkFrame(self.root_frame, fg_color=COLORS["panel"], corner_radius=10,
                             border_width=1, border_color=COLORS["cyan_mid"])
        panel.grid(row=2, column=1, sticky="ew", pady=(14, 0))
        panel.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(panel, text=">_", font=(FONT, 16, "bold"),
                     text_color=COLORS["cyan"]).grid(row=0, column=0, padx=(16, 4), pady=12, sticky="n")

        self.input_box = ctk.CTkTextbox(
            panel, height=56, font=(FONT, 12), fg_color="transparent",
            text_color=COLORS["text"], border_width=0, wrap="word",
        )
        self.input_box.grid(row=0, column=1, sticky="ew", pady=8)
        self.input_box.bind("<Return>", self._on_enter)

        actions = ctk.CTkFrame(panel, fg_color="transparent")
        actions.grid(row=0, column=2, padx=(6, 12), pady=10)
        self.send_btn = ctk.CTkButton(
            actions, text="TRANSMITIR", width=130, height=38, font=(FONT, 12, "bold"),
            fg_color=COLORS["cyan"], hover_color=COLORS["cyan_mid"], text_color=COLORS["bg"],
            corner_radius=6, command=self._send_message,
        )
        self.send_btn.pack()
        ctk.CTkLabel(actions, text="ENTER enviar · SHIFT+ENTER salto", font=(FONT, 8),
                     text_color=COLORS["text_dim"]).pack(pady=(4, 0))

        self.input_box.focus_set()

    # ------------------------------------------------------------
    # ANIMACIONES
    # ------------------------------------------------------------

    def _animate_scan(self) -> None:
        c = self.scan_canvas
        w = max(c.winfo_width(), 1)
        c.delete("all")
        c.create_line(0, 2, w, 2, fill=COLORS["cyan_dim"])
        seg = max(60, w // 6)
        self._scan_x = (self._scan_x + 6) % (w + seg)
        c.create_line(self._scan_x - seg, 2, self._scan_x, 2, fill=COLORS["cyan"], width=2)
        self.after(30, self._animate_scan)

    def _animate_status(self) -> None:
        self._blink = not self._blink
        color = COLORS["magenta"] if self.is_generating else COLORS["green"]
        self.status_dot.configure(text_color=color if self._blink else COLORS["text_dim"])
        self.status_text.configure(text="PROCESANDO" if self.is_generating else "ENLACE ACTIVO")

        if self.is_generating:
            self._thinking_step = (self._thinking_step + 1) % 4
            bars = "▮" * (self._thinking_step + 1) + "▯" * (3 - self._thinking_step)
            self.thinking_label.configure(text=f"{self.current_provider} decodificando señal {bars}")
        else:
            self.thinking_label.configure(text="")
        self.after(450, self._animate_status)

    def _update_telemetry(self) -> None:
        if psutil:
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory().percent
        else:
            cpu = random.uniform(8, 28) + (35 if self.is_generating else 0)
            mem = random.uniform(40, 48)
        for key, value in (("CPU", cpu), ("MEM", mem)):
            self.metric_labels[key].configure(
                text=f"{value:.0f}%", text_color=COLORS["magenta"] if value > 80 else COLORS["cyan"]
            )
            self.metric_bars[key].set(min(value / 100, 1))

        latency = f"{self.last_latency_ms} ms" if self.last_latency_ms is not None else "--"
        self.metric_labels["LATENCIA"].configure(text=latency)
        self.metric_labels["TOKENS"].configure(text=str(self.token_count))
        self.metric_labels["MENSAJES"].configure(text=str(len(self.messages)))
        self.after(1500, self._update_telemetry)

    # ------------------------------------------------------------
    # INTERACCIÓN
    # ------------------------------------------------------------

    def _boot_sequence(self) -> None:
        self._log("Núcleo iniciado")
        if self.provider_names:
            self._log(f"Proveedores: {', '.join(self.provider_names)}")
            self._add_message("system", f"Enlace establecido con {len(self.provider_names)} proveedor(es). Listo para recibir comandos.")
        elif self._router_error:
            self._log("Error al iniciar el router: modo demo")
            self._add_message(
                "error",
                f"No se pudo iniciar el router de proveedores: {self._router_error}. "
                "Modo demo activo: las respuestas son simuladas.",
                record=False,
            )
        else:
            self._log("Sin proveedores: modo demo")
            self._add_message("system", "No se detectaron proveedores en .env. Modo demo activo: las respuestas son simuladas.")

    def _select_provider(self, name: str, log: bool = True) -> None:
        if self.is_generating:
            return
        self.current_provider = name
        for n, btn in self.provider_buttons.items():
            active = n == name
            btn.configure(
                fg_color=COLORS["cyan_dim"] if active else "transparent",
                border_color=COLORS["cyan"] if active else COLORS["text_dim"],
                text_color=COLORS["cyan"] if active else COLORS["text"],
            )
        details = self._provider_details(name)
        self.model_label.configure(text=details["model"])
        self.endpoint_label.configure(text=details["endpoint"])
        if log:
            self._log(f"Proveedor activo: {name}")

    def _on_enter(self, event):
        if event.state & 0x0001:
            return None
        self._send_message()
        return "break"

    def _send_message(self) -> None:
        if self.is_generating:
            return
        prompt = self.input_box.get("1.0", "end").strip()
        if not prompt:
            return
        self.input_box.delete("1.0", "end")

        history = self._build_history()
        self._add_message("user", prompt)
        bubble = self._add_message("ai", "")
        self._set_generating(True)
        self._log(f"Transmitiendo a {self.current_provider}")

        started = time.perf_counter()
        provider = self.current_provider
        if self.router and provider != DEMO_PROVIDER:
            coro = self._stream_real(prompt, history, provider, bubble, started)
        else:
            coro = self._stream_demo(prompt, bubble, started)
        self._current_future = self.runner.submit(coro)

    def _build_history(self) -> List[Dict[str, str]]:
        """Últimos N turnos de la conversación en formato OpenAI (sin errores ni avisos)."""
        roles = {"user": "user", "ai": "assistant"}
        history = [
            {"role": roles[m["sender"]], "content": m["text"]}
            for m in self.messages
            if m["sender"] in roles and m["text"].strip()
        ]
        return history[-MAX_HISTORY_MESSAGES:]

    async def _stream_real(
        self, prompt: str, history: List[Dict[str, str]], provider: str,
        bubble: MessageBubble, started: float,
    ) -> None:
        first_chunk = True
        try:
            async for chunk in self.router.generate_stream(
                prompt, provider=provider, system_prompt=SYSTEM_PROMPT, history=history
            ):
                if first_chunk:
                    self._post(self._set_latency, started)
                    first_chunk = False
                self._post(self._append_chunk, bubble, chunk)
            if first_chunk:
                text = await self.router.generate(
                    prompt, provider=provider, system_prompt=SYSTEM_PROMPT, history=history
                )
                self._post(self._set_latency, started)
                self._post(self._append_chunk, bubble, text)
            self._post(self._finish_generation, bubble, None)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._post(self._finish_generation, bubble, str(e))

    async def _stream_demo(self, prompt: str, bubble: MessageBubble, started: float) -> None:
        await asyncio.sleep(0.6)
        self._post(self._set_latency, started)
        reply = (
            f"Señal recibida: \"{prompt[:80]}\". Estoy funcionando en modo demo. "
            "Configurá un proveedor en tu archivo .env (OmniRoute, OpenRouter o uno personalizado) "
            "para obtener respuestas reales en streaming."
        )
        for word in reply.split(" "):
            self._post(self._append_chunk, bubble, word + " ")
            await asyncio.sleep(0.04)
        self._post(self._finish_generation, bubble, None)

    def _set_latency(self, started: float) -> None:
        self.last_latency_ms = int((time.perf_counter() - started) * 1000)

    def _append_chunk(self, bubble: MessageBubble, chunk: str) -> None:
        bubble.append(chunk)
        self.token_count += max(1, len(chunk.split()))
        self._scroll_to_bottom()

    def _finish_generation(self, bubble: MessageBubble, error: Optional[str]) -> None:
        if error:
            if not bubble.text.strip():
                bubble.destroy()
                self.bubbles.remove(bubble)
            self._add_message("error", f"Fallo de enlace con {self.current_provider}: {error}")
            self._log("Error en la transmisión")
        else:
            bubble.set_text(bubble.text.strip() or "(respuesta vacía)")
            self.messages.append({"sender": "ai", "text": bubble.text, "time": time.time()})
            self._log("Respuesta recibida")
        self._current_future = None
        self._set_generating(False)

    def _set_generating(self, value: bool) -> None:
        self.is_generating = value
        self.send_btn.configure(
            state="disabled" if value else "normal",
            text="EN CURSO..." if value else "TRANSMITIR",
            fg_color=COLORS["cyan_dim"] if value else COLORS["cyan"],
        )

    def _clear_chat(self) -> None:
        if self.is_generating:
            return
        for bubble in self.bubbles:
            bubble.destroy()
        self.bubbles.clear()
        self.messages.clear()
        self.token_count = 0
        self.last_latency_ms = None
        self._log("Sesión reiniciada")
        self._add_message("system", "Nueva sesión iniciada.")

    # ------------------------------------------------------------
    # MENSAJES Y LOG
    # ------------------------------------------------------------

    def _add_message(self, sender: str, text: str, record: bool = True) -> MessageBubble:
        wrap = self._bubble_wraplength()
        bubble = MessageBubble(self.chat_area, sender, text, wrap if sender != "system" else wrap + 80)
        if bubble.align == "e":
            bubble.grid(row=len(self.bubbles), column=0, sticky="e", padx=(80, 8), pady=6)
        elif bubble.align == "w":
            bubble.grid(row=len(self.bubbles), column=0, sticky="w", padx=(8, 80), pady=6)
        else:
            bubble.grid(row=len(self.bubbles), column=0, pady=6)
        self.bubbles.append(bubble)
        if record and sender in ("user", "error"):
            self.messages.append({"sender": sender, "text": text, "time": time.time()})
        self._scroll_to_bottom()
        return bubble

    def _scroll_to_bottom(self) -> None:
        self.chat_area.update_idletasks()
        self.chat_area._parent_canvas.yview_moveto(1.0)

    def _log(self, text: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{time.strftime('%H:%M:%S')}] {text}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _on_close(self) -> None:
        if self._closing:
            return
        self._closing = True

        future = self._current_future
        if future is not None and not future.done():
            future.cancel()
            try:
                future.result(timeout=2)
            except BaseException:
                pass

        if self.router:
            try:
                self.runner.submit(self.router.close_all()).result(timeout=2)
            except Exception:
                pass
        self.runner.stop()
        self.runner.thread.join(timeout=2)
        self.destroy()


def main():
    app = CyberpunkHUD()
    app.mainloop()


if __name__ == "__main__":
    main()
