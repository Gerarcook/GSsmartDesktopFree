import customtkinter as ctk
from tkinter import scrolledtext, filedialog, scrolledtext as tk_st
import tkinter as tk
import sys
import difflib
import threading
import asyncio
from pathlib import Path
from typing import List, Dict, Optional

from src.core.file_context import build_file_context, describe_files
from src.core import session as session_lib
from src.core import model_catalog
from src.core.model_catalog import set_model_in_env
from src.ui.theme import (
    COLORS, FONT_MONO, FONT_UI, RADIUS_PANEL, RADIUS_FIELD, RADIUS_PILL,
    DIM, FS, SPACE, ghost_btn_kwargs, primary_btn_kwargs, rail_btn_kwargs,
)
from src.ui.bubbles import MessageBubble

# -------------------------------------------------
# 1. CONFIGURACIÓN GLOBAL
# -------------------------------------------------
# gui_main.py vive en la RAIZ del repo → parent, no parent.parent.
BASE_DIR = Path(__file__).resolve().parent

# Antes esto insertaba "src/core" en sys.path e importaba "router" a pelo.
# Eso rompia: router.py hace imports absolutos ("from src.providers..."), asi
# que Needs the RAIZ del repo en el path, y el except ImportError caia en un
# stub que DEVUELVE una frase de exito falsa. Si el import se rompia, la app
# arrancaba igual y mentia sobre el estado del router.
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from src.core.router import ProviderRouter
    ROUTER_IMPORT_ERROR = None
except Exception as _err:  # noqa: BLE001 - queremos ver la causa real
    ROUTER_IMPORT_ERROR = str(_err)
    ProviderRouter = None

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# El input comparte fondo con el footer a proposito: si no, el campo se ve
# como un bloque distinto pegado abajo. Antes eran "#0f172a" sobre "#111827";
# ahora ambos salen del token "panel", asi que el cambio es automatico si
# mañana se toca la paleta.
FOOTER_BG = COLORS["panel"]


# -------------------------------------------------
# 2. COMPONENTES PERSONALIZADOS
# -------------------------------------------------
class ModernButton(ctk.CTkButton):
    """Botones estilo 'Pill' (redondeados)."""
    def __init__(self, master, text, **kwargs):
        # setdefault y no un height=36 fijo: si el que llama pasa height,
        # un argumento explicito adelante pisa al de **kwargs y Python
        # tira "got multiple values for keyword argument 'height'".
        kwargs.setdefault("height", 36)
        kwargs.setdefault("corner_radius", 50)
        super().__init__(master, text=text, **kwargs)


class DiffText(tk_st.ScrolledText):
    """Widget de texto para diff con colores."""
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        # Configuración base
        self.configure(
            bg=COLORS["bg"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            font=(FONT_MONO, 11),
            wrap="word",
            borderwidth=0,
            highlightthickness=0,
            padx=8, pady=8
        )
        self.tag_config("diff-unchanged", background=COLORS["bg"], foreground=COLORS["text_muted"])
        self.tag_config("diff-added", background=COLORS.get("green_dim", COLORS["cyan_dim"]), foreground=COLORS["green"])
        self.tag_config("diff-removed", background=COLORS["magenta_dim"], foreground=COLORS["magenta"])

    def load_diff(self, old_text: str, new_text: str):
        """Carga el texto y colorea diferencias."""
        self.config(state="normal")
        self.delete("1.0", "end")

        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()
        diff = difflib.ndiff(old_lines, new_lines)

        for line in diff:
            if line.startswith("  "):
                self.insert("end", line[2:] + "\n", "diff-unchanged")
            elif line.startswith("- "):
                self.insert("end", line[2:] + "\n", "diff-removed")
            elif line.startswith("+ "):
                self.insert("end", line[2:] + "\n", "diff-added")
            else:
                self.insert("end", line[2:] + "\n", "diff-unchanged")

        self.config(state="disabled")


# -------------------------------------------------
# 3. CLASES DE LA INTERFAZ
# -------------------------------------------------
class SettingsPanel(ctk.CTkFrame):
    """Panel lateral desplegable."""
    def __init__(self, master, on_option_click):
        super().__init__(master, width=280, fg_color=COLORS["panel"],
                         corner_radius=0, border_width=1, border_color=COLORS["border_glow"])
        self.on_option_click = on_option_click
        self.grid_remove()  # Oculto por defecto

        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self, text="Configuración", font=(FONT_MONO, FS["lg"], "bold"),
            text_color=COLORS["cyan"],
        ).grid(row=0, column=0, sticky="w", padx=SPACE[4], pady=SPACE[4])

        options = ["Preferencias", "Apariencia", "Audio", "Modelo", "Atajos", "Privacidad", "Sistema", "Avanzado"]
        for i, opt in enumerate(options):
            ctk.CTkButton(
                self, text=opt, command=lambda o=opt: self.on_option_click(o),
                **ghost_btn_kwargs(),
            ).grid(row=i + 1, column=0, sticky="ew", padx=SPACE[3], pady=SPACE[1])

    def toggle(self):
        if self.winfo_ismapped():
            self.grid_remove()
        else:
            self.grid(row=0, column=1, rowspan=3, sticky="nsew")


class FooterBar(ctk.CTkFrame):
    """Composer: fila 1 = input + CTA; fila 2 = toolbar ghost."""
    def __init__(self, master, on_send, on_attach, on_model, on_audio_toggle,
                 on_pick_model=None):
        super().__init__(
            master, fg_color=FOOTER_BG, corner_radius=RADIUS_PANEL,
            border_width=1, border_color=COLORS["border_glow"],
        )

        # row0: input | Enviar
        # row1: toolbar full-width
        # row2: status (razonamiento)
        # row3: hint idle
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        self.entry = ctk.CTkEntry(
            self, placeholder_text="Escribe tu mensaje aquí...",
            height=42,
            fg_color=COLORS["panel_raised"],
            text_color=COLORS["text"],
            border_width=1,
            border_color=COLORS["border"],
            placeholder_text_color=COLORS["text_dim"],
        )
        self.entry.grid(
            row=0, column=0, sticky="ew",
            padx=(SPACE[3], SPACE[2]), pady=(SPACE[3], SPACE[2]),
        )
        self.entry.bind("<Return>", lambda e: on_send(self.entry.get()))
        self.entry.bind(
            "<FocusIn>",
            lambda _e: self.entry.configure(border_color=COLORS["cyan"]),
        )
        self.entry.bind(
            "<FocusOut>",
            lambda _e: self.entry.configure(border_color=COLORS["border"]),
        )

        self.send_btn = ctk.CTkButton(
            self, text="Enviar", width=110, height=42,
            command=lambda: on_send(self.entry.get()),
            **primary_btn_kwargs(),
        )
        self.send_btn.grid(
            row=0, column=1, sticky="e",
            padx=(0, SPACE[3]), pady=(SPACE[3], SPACE[2]),
        )

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(
            row=1, column=0, columnspan=2, sticky="ew",
            padx=SPACE[3], pady=(0, SPACE[2]),
        )

        ghost = ghost_btn_kwargs()
        self.attach_btn = ctk.CTkButton(
            actions, text="📎 Adjuntar", width=110, height=32,
            command=on_attach, **ghost,
        )
        self.attach_btn.pack(side="left", padx=(0, SPACE[2]))

        self.model_btn = ctk.CTkButton(
            actions, text="🤖 Modelo", width=100, height=32,
            command=on_model, **ghost,
        )
        self.model_btn.pack(side="left", padx=(0, SPACE[2]))

        self.model_pick_btn = ctk.CTkButton(
            actions, text="Ver modelos", width=110, height=32,
            command=on_pick_model, **ghost,
        )
        self.model_pick_btn.pack(side="left", padx=(0, SPACE[2]))

        self.audio_switch = ctk.CTkSwitch(
            actions, text="Audio", progress_color=COLORS["cyan"],
            button_color=COLORS["text_muted"], button_hover_color=COLORS["text"],
            text_color=COLORS["text_muted"], font=(FONT_MONO, FS["xs"]),
            width=44, command=on_audio_toggle,
        )
        self.audio_switch.pack(side="left", padx=(SPACE[2], 0))

        self.hint_label = ctk.CTkLabel(
            self, text="Sin adjuntos · Intro para enviar",
            font=(FONT_MONO, FS["xs"]), text_color=COLORS["text_dim"], anchor="e",
        )
        self.hint_label.grid(
            row=3, column=0, columnspan=2, sticky="ew",
            padx=SPACE[3], pady=(0, SPACE[1]),
        )

    def set_busy(self, busy):
        """Bloquea el input mientras se espera a la IA."""
        state = "disabled" if busy else "normal"
        self.entry.configure(state=state)
        self.send_btn.configure(
            state=state,
            text="Pensando..." if busy else "Enviar",
            fg_color=DIM["accent_disabled"] if busy else COLORS["cyan"],
        )

    def set_attached_count(self, count):
        """Muestra cuantos archivos hay adjuntos en el boton."""
        self.attach_btn.configure(
            text=f"📎 Adjuntar ({count})" if count else "📎 Adjuntar"
        )

    def set_status(self, text):
        """Barra de estado: muestra el razonamiento del modelo mientras piensa.

        Los modelos de razonamiento pueden tardar 40s antes de emitir la
        primera palabra de la respuesta. Sin esto el usuario ve un boton
        "Pensando..." sin ningun feedback de que algo esta pasando.
        """
        if not hasattr(self, "status_label"):
            self.status_label = ctk.CTkLabel(
                self, text="", font=(FONT_MONO, FS["xs"]),
                text_color=COLORS["text_dim"], anchor="w",
            )
            self.status_label.grid(
                row=2, column=0, columnspan=2, sticky="w", padx=SPACE[3],
            )
        # Razonamiento → warning (legible, no confunde con muted idle)
        self.status_label.configure(
            text=text[:110] if text else "",
            text_color=COLORS["warning"] if text else COLORS["text_dim"],
        )
        # El pie solo describe el estado idle. Con razonamiento en curso el
        # texto "Intro para enviar" miente: la app esta ocupada pensando.
        if hasattr(self, "hint_label"):
            self.hint_label.configure(
                text="" if text else f"Sin adjuntos · Intro para enviar"
            )


def _dark_scrolled_text(parent, **kwargs):
    """Reservado: se usaba para el chat plano.

    Ya no se usa (el chat migro a burbujas en CTkScrollableFrame, que trae su
    propio scrollbar oscuro). Se deja el codigo porque la vista de diff podria
    necesitar un scrollbar tematizado si someday se migra tambien.
    ScrolledText de tkinter mete un tk.Scrollbar con los colores del sistema
    que en Windows queda gris claro sobre fondo oscuro.
    """
    box = ctk.CTkFrame(parent, fg_color="transparent")
    text = scrolledtext.Text(box, borderwidth=0, highlightthickness=0, **kwargs)
    bar = tk.Scrollbar(
        box,
        orient="vertical",
        command=text.yview,
        bg=COLORS["panel_raised"],
        troughcolor=COLORS["bg"],
        activebackground=COLORS["cyan_dim"],
        highlightthickness=0,
        width=12,
        bd=0,
    )
    text.configure(yscrollcommand=bar.set)
    text.pack(side="left", fill="both", expand=True)
    bar.pack(side="right", fill="y")
    return box, text


class EditorArea(ctk.CTkFrame):
    """Área principal: chat (1fr) + review opcional (~0.4fr)."""
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1, minsize=320)
        self.grid_columnconfigure(1, weight=0, minsize=280)
        self.grid_rowconfigure(0, weight=1)

        self.chat_frame = ctk.CTkFrame(
            self, fg_color=COLORS["panel"], corner_radius=RADIUS_PANEL,
            border_width=1, border_color=COLORS["border_glow"],
        )
        self.chat_frame.grid(
            row=0, column=0, sticky="nsew",
            padx=(SPACE[2], SPACE[1]), pady=SPACE[2],
        )

        self.chat_area = ctk.CTkScrollableFrame(
            self.chat_frame, fg_color="transparent",
            scrollbar_button_color=COLORS["border_glow"],
            scrollbar_button_hover_color=COLORS["cyan_mid"],
        )
        self.chat_area.pack(fill="both", expand=True, padx=SPACE[2], pady=SPACE[2])
        self.chat_area.grid_columnconfigure(0, weight=1)
        self.bubbles: List[MessageBubble] = []
        self.chat_area.bind("<Configure>", self._on_chat_resize)

        # Review panel: en __init__ (antes vivía por error dentro del resize)
        self.review_frame = ctk.CTkFrame(
            self, fg_color=COLORS["panel"], corner_radius=RADIUS_PANEL,
            border_width=1, border_color=COLORS["border_glow"],
        )
        self.review_frame.grid(
            row=0, column=1, sticky="nsew",
            padx=(SPACE[1], SPACE[2]), pady=SPACE[2],
        )
        self.review_frame.grid_remove()
        self.review_frame.grid_columnconfigure(0, weight=1)
        self.review_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self.review_frame, text="Revisión de Código (Diff)",
            font=(FONT_MONO, FS["sm"], "bold"), text_color=COLORS["cyan"],
        ).grid(row=0, column=0, sticky="w", padx=SPACE[3], pady=(SPACE[3], SPACE[2]))

        self.diff_widget = DiffText(self.review_frame)
        self.diff_widget.grid(
            row=1, column=0, sticky="nsew", padx=SPACE[3], pady=(0, SPACE[3]),
        )

    def _on_chat_resize(self, _event) -> None:
        """Recalcula el wrap de cada burbuja al cambiar el ancho."""
        width = max(280, self.chat_area.winfo_width() - 70)
        for b in self.bubbles:
            b.set_wraplength(width)


# -------------------------------------------------
# 4. CLASE PRINCIPAL
# -------------------------------------------------
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("GSsmart Desktop // Neural Chat")
        self.geometry("1280x800")
        self.minsize(960, 640)
        self.configure(fg_color=COLORS["bg"], bg=COLORS["bg"])

        # Archivos adjuntos del mensaje en curso.
        self.attached_files: List[str] = []

        # Memoria de la conversacion. El formato de messages vive en
        # src/core/session.py, no aca: es logica de negocio y asi las dos
        # GUIs pueden reutilizarla.
        self.conversation: List[Dict[str, str]] = []

        # Layout Grid Principal
        #   col 0 = sidebar | col 1 = settings | col 2 = contenido
        #   row 0 = top_bar | row 1 = editor_area | row 2 = footer_bar
        self.grid_columnconfigure(0, weight=0, minsize=240)  # Sidebar
        self.grid_columnconfigure(1, weight=0)                # Settings
        self.grid_columnconfigure(2, weight=1)                # Content
        self.grid_rowconfigure(0, weight=0)                   # TopBar
        self.grid_rowconfigure(1, weight=1)                   # EditorArea <- único que crece
        self.grid_rowconfigure(2, weight=0)                   # FooterBar

        # --- Inicializar Componentes ---
        self.sidebar = ctk.CTkFrame(
            self, width=240, fg_color=COLORS["panel"], corner_radius=0,
            border_width=1, border_color=COLORS["border"],
        )
        self.sidebar.grid(row=0, column=0, rowspan=3, sticky="nsew")
        self.sidebar.grid_propagate(False)

        self.settings_panel = SettingsPanel(self, on_option_click=self.handle_settings_option)

        self.top_bar = ctk.CTkFrame(
            self, fg_color=COLORS["panel"], height=56, corner_radius=RADIUS_PANEL,
            border_width=1, border_color=COLORS["border"],
        )
        self.top_bar.grid(row=0, column=2, sticky="ew", padx=SPACE[2], pady=(SPACE[2], 0))
        self.top_bar.grid_propagate(False)
        self.top_bar.grid_columnconfigure(0, weight=1)

        self.editor_area = EditorArea(self)
        self.editor_area.grid(row=1, column=2, sticky="nsew", padx=SPACE[2], pady=SPACE[2])

        self.footer_bar = FooterBar(
            self, on_send=self.send_message, on_attach=self.attach_files,
            on_model=self.choose_model, on_audio_toggle=self.toggle_audio,
            on_pick_model=self.pick_model,
        )
        self.footer_bar.grid(row=2, column=2, sticky="ew", padx=SPACE[2], pady=(0, SPACE[2]))

        # --- Sidebar brand + rail ---
        ctk.CTkLabel(
            self.sidebar, text="GSsmart", font=(FONT_MONO, FS["lg"], "bold"),
            text_color=COLORS["cyan"],
        ).pack(pady=(SPACE[5], SPACE[1]))
        ctk.CTkLabel(
            self.sidebar, text="DESKTOP // FREE", font=(FONT_MONO, FS["xs"]),
            text_color=COLORS["text_dim"],
        ).pack(pady=(0, SPACE[4]))

        ctk.CTkLabel(
            self.sidebar, text="PANEL DE CONTROL", font=(FONT_MONO, FS["xs"], "bold"),
            text_color=COLORS["text_muted"],
        ).pack(pady=(0, SPACE[2]))

        def _rail_btn(text, command):
            return ctk.CTkButton(
                self.sidebar, text=text, command=command, **rail_btn_kwargs(),
            )

        self.settings_sidebar_btn = _rail_btn("⚙  Configuración", self.toggle_settings)
        self.settings_sidebar_btn.pack(fill="x", padx=SPACE[3], pady=SPACE[1])

        self.review_sidebar_btn = _rail_btn("🧾  Revisión", self.toggle_revision)
        self.review_sidebar_btn.pack(fill="x", padx=SPACE[3], pady=SPACE[1])

        self.test_sidebar_btn = _rail_btn("◈  Testear conexiones", self.test_providers)
        self.test_sidebar_btn.pack(fill="x", padx=SPACE[3], pady=SPACE[1])

        self.new_session_btn = _rail_btn("＋  Nueva sesión", self.new_session)
        self.new_session_btn.pack(fill="x", padx=SPACE[3], pady=SPACE[1])

        # --- Cabecera Superior ---
        # col 0 = marca | col 1 = hueco | col 2 = búsqueda | col 3 = hueco
        # col 4 = onda de voz
        # Los huecos con weight=1 mantienen la búsqueda al centro sin calcular
        # pixeles cada vez que se redimensiona la ventana.
        self.top_bar.grid_columnconfigure(1, weight=1)
        self.top_bar.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(
            self.top_bar, text="Editor / Chat", font=(FONT_MONO, FS["md"], "bold"),
            text_color=COLORS["text"],
        ).grid(row=0, column=0, sticky="w", padx=SPACE[4])

        # Búsqueda Web: visual only (sin backend). Deshabilitada para no mentir.
        search_wrap = ctk.CTkFrame(
            self.top_bar, fg_color=COLORS["panel_raised"],
            corner_radius=RADIUS_PILL, border_width=1,
            border_color=COLORS["border"], height=32, width=280,
        )
        search_wrap.grid(row=0, column=2, pady=SPACE[2])
        search_wrap.grid_propagate(False)
        ctk.CTkLabel(
            search_wrap, text="⌕", font=(FONT_MONO, FS["md"], "bold"),
            text_color=COLORS["cyan_mid"],
        ).pack(side="left", padx=(SPACE[3], SPACE[1]))
        self.search_entry = ctk.CTkEntry(
            search_wrap, placeholder_text="Búsqueda Web (próx.)", height=24, width=220,
            font=(FONT_MONO, FS["xs"]), fg_color="transparent", border_width=0,
            text_color=COLORS["text"], placeholder_text_color=COLORS["text_dim"],
            state="disabled",
        )
        self.search_entry.pack(side="left", padx=(0, SPACE[3]))

        # Onda de voz = única señal de "generando" (glow vivo)
        self.wave_wrap = ctk.CTkFrame(
            self.top_bar, fg_color=COLORS["panel_raised"],
            corner_radius=RADIUS_FIELD, border_width=1,
            border_color=COLORS["border"], height=32, width=112,
        )
        self.wave_wrap.grid(row=0, column=4, padx=(0, SPACE[3]), pady=SPACE[2])
        self.wave_wrap.grid_propagate(False)
        self.voice_canvas = tk.Canvas(
            self.wave_wrap, height=18, width=92,
            bg=COLORS["panel_raised"], highlightthickness=0, bd=0,
        )
        self.voice_canvas.pack(pady=7)
        self.voice_bars = [0.05] * 14
        self.voice_active = False
        self._voice_job = None

        self.top_review_btn = ctk.CTkButton(
            self.top_bar, text="Mostrar Revisión", width=150, height=32,
            command=self.toggle_revision, **ghost_btn_kwargs(),
        )
        self.top_review_btn.grid(row=0, column=5, sticky="e", padx=(0, SPACE[4]))

        # La arranca al final: self.after(0, ...) garantiza que el Canvas ya
        # tiene tamano cuando corre el primer frame. Si se llama directo, el
        # primer dibujado sale con width=1 y la onda aparece chueca un rato.
        self.after(0, self._animate_voice)
        self.after(10, self._welcome)

    # --- Lógica de Interacción ---

    def toggle_settings(self):
        self.settings_panel.toggle()

    def handle_settings_option(self, option):
        print(f"Seleccionada opción de config: {option}")

    def toggle_revision(self):
        if self.editor_area.review_frame.winfo_ismapped():
            self.editor_area.review_frame.grid_remove()
            self.top_review_btn.configure(text="Mostrar Revisión")
        else:
            self.editor_area.review_frame.grid()
            self.top_review_btn.configure(text="Ocultar Revisión")
            self.editor_area.diff_widget.load_diff("", "funcion_hola() {\n  return 'Hola Mundo';\n}")

    def toggle_audio(self):
        print("Audio toggled")



    def _add_bubble(self, sender: str, text: str) -> MessageBubble:
        """Agrega una burbuja al chat y la devuelve (para append en streaming).

        La lista vive en EditorArea porque es el duenio del contenedor; App
        solo la consulta. Tenerla en los dos lados ya Schrodinger.
        """
        area = self.editor_area
        wrap = max(320, area.chat_area.winfo_width() - 70)
        b = MessageBubble(area.chat_area, sender, text, wraplength=wrap)
        # User a la derecha (operador); AI/system a la izquierda.
        # sticky no-ew: el wraplength define el ancho, no el panel completo.
        side = "e" if sender == "user" else "w"
        b.grid(
            row=len(area.bubbles), column=0, sticky=side,
            padx=SPACE[1], pady=(0, SPACE[2]),
        )
        area.bubbles.append(b)
        self._scroll_chat_to_bottom()
        return b

    def _scroll_chat_to_bottom(self) -> None:
        """Baja al ultimo mensaje.

        CTkScrollableFrame no expone see(): hay que ir al Canvas de Tk que
        tiene por dentro. after_idle espera al recalculo del layout, si se
        llama directo el scroll no llega al fondo porque las burbujas todavia
        no tienen altura definitiva.
        """
        area = self.editor_area
        self.after_idle(lambda: area.chat_area._parent_canvas.yview_moveto(1.0))

    def _append_chat(self, line):
        """Mensaje de sistema con formato viejo ("[IA]: ...").

        Se mantiene porque varias partes del codigo loguean con ese prefijo
        (diagnostico de proveedores, errores). Se traduce a una burbuja.
        """
        text = line
        if text.startswith("[IA]:"):
            sender = "ai"
            text = text[len("[IA]:"):].lstrip()
        elif text.startswith("[ERROR]:"):
            sender = "error"
            text = text[len("[ERROR]:"):].lstrip()
        elif text.startswith("[Tú]:") or text.startswith("[Tu]:"):
            sender = "user"
            text = text.split(":", 1)[-1].lstrip()
        else:
            sender = "system"
        self._add_bubble(sender, text)

    def _clear_chat_area(self) -> None:
        for b in self.editor_area.bubbles:
            b.destroy()
        self.editor_area.bubbles.clear()

    def _welcome(self) -> None:
        """Mensaje inicial. Sin esto el chat abre como una caja negra vacia
        y no se distingue de una app que no cargo."""
        self._add_bubble("system", "GSsmart Desktop AI")
        self._add_bubble(
            "system",
            "Conectado. Escribi abajo para hablar con el proveedor activo.\n"
            "Adjunta archivos con Adjuntar, cambia de modelo con Modelo o "
            "proba uno con Ver modelos.",
        )

    # ------------------------------------------------------------------
    # ARCHIVOS ADJUNTOS
    # ------------------------------------------------------------------
    def attach_files(self):
        """Abre el explorador y guarda las rutas en self.attached_files.

        Los archivos se ACUMULAN entre llamadas: podes abrir el dialogo
        varias veces antes de mandar el mensaje. No se borran al elegir,
        solo cuando se manda el mensaje o se limpia a mano.

        La lectura del contenido NO pasa por aca: leer un .iso de 4GB en el
        hilo de Tk congelaria la ventana. Eso lo hace el worker, en
        send_message().
        """
        rutas = filedialog.askopenfilenames(
            title="Seleccionar archivos para adjuntar",
        )
        if not rutas:
            return

        # Un archivo no puede estar dos veces en la misma lista.
        nuevas = [r for r in rutas if r not in self.attached_files]
        self.attached_files.extend(nuevas)
        self.footer_bar.set_attached_count(len(self.attached_files))

        self._append_chat(f"[Adjuntos] {describe_files(self.attached_files)}")

    def clear_attachments(self):
        """Suelta los adjuntos del mensaje en curso."""
        self.attached_files.clear()
        self.footer_bar.set_attached_count(0)

    # ------------------------------------------------------------------
    # ONDA DE VOZ
    # ------------------------------------------------------------------
    def set_voice_active(self, active: bool) -> None:
        """Enciende/apaga la onda. Se llama al empezar y terminar de generar.

        Es la unica senal visible de que algo esta pasando: con modelos de
        razonamiento el chat puede quedarse 40s sin emitir nada.
        """
        self.voice_active = bool(active)
        if hasattr(self, "wave_wrap"):
            self.wave_wrap.configure(
                border_color=COLORS["cyan"] if active else COLORS["border"],
            )

    def _animate_voice(self) -> None:
        """Barras que suben y bajan. Apagada, decaen a una linea de reposo."""
        import random
        c = self.voice_canvas
        c.delete("all")
        h, n = 18, len(self.voice_bars)
        gap, bw = 92 / n, 4.0

        for i in range(n):
            if self.voice_active:
                self.voice_bars[i] = min(1.0, max(0.15,
                                         self.voice_bars[i] + random.uniform(-0.28, 0.34)))
            else:
                self.voice_bars[i] = max(0.12, self.voice_bars[i] - 0.10)
            # minimo de 3px: por debajo las barras se leen como puntos sueltos
            # y el modulo parece roto en vez de en reposo.
            bh = max(3.0, self.voice_bars[i] * (h - 2))
            x = i * gap + (gap - bw) / 2
            color = COLORS["cyan"] if self.voice_active else COLORS["cyan_dim"]
            c.create_rectangle(x, (h - bh) / 2, x + bw, (h + bh) / 2,
                               fill=color, outline="")

        # Activa va rapido para verse continua; en reposo va lento para no
        # quemar CPU con una ventana abierta todo el dia.
        self._voice_job = self.after(60 if self.voice_active else 220, self._animate_voice)

    def _stop_voice(self) -> None:
        if getattr(self, "_voice_job", None):
            try:
                self.after_cancel(self._voice_job)
            except Exception:
                pass
            self._voice_job = None

    # ------------------------------------------------------------------
    # ENVIO
    # ------------------------------------------------------------------
    def send_message(self, message=None):
        text = message if message else self.footer_bar.entry.get()
        if not text.strip():
            return

        # Copia la lista y la limpia YA: si el worker falla, el usuario no
        # debe encontrar sus adjuntos magicamente reaparecidos.
        archivos = list(self.attached_files)
        self.clear_attachments()

        # Guardar el turno del usuario ANTES de llamar: si el worker falla,
        # el contexto igual refleja lo que se pregunto.
        session_lib.add_user(self.conversation, text)

        self._append_chat(f"[Tú]: {text}")
        self.footer_bar.entry.delete(0, "end")

        # La llamada real tarda 5-226s segun el proveedor. Si la llamo
        # directo, Tkinter se congela ese tiempo. Va en un hilo aparte y
        # vuelve al hilo principal por after(), que es el unico seguro.
        self.footer_bar.set_busy(True)
        self.set_voice_active(True)
        threading.Thread(
            target=self._ask_worker, args=(text, archivos), daemon=True
        ).start()

    def _ask_worker(self, text, archivos):
        """Hilo secundario: arma el contexto y consume el stream. NO toca widgets.

        Usa generate_stream() y no get_ai_response() por dos razones:
          1. El no-streaming da 504 con estos gateways (medido: 100% de fallas).
          2. El streaming deja ver el razonamiento en vivo. Con hcnsec/auto
             el modelo emite ~1250 chars de reasoning ANTES de la respuesta;
             sin esto el usuario mira un chat congelado durante 40s.

        build_file_context() puede leer cientos de KB y tardar, por eso va
        aca y no en el hilo de la interfaz.
        """
        partes = []
        try:
            contexto = build_file_context(archivos)
            # Copia el historial: el worker corre en otro hilo y la GUI
            # puede seguir agregando mensajes mientras espera. El [:-1]
            # saca el user que acabamos de agregar, porque ese ya viaja
            # como prompt.
            historial = session_lib.build_history(self.conversation[:-1])
            router = ProviderRouter()
            try:
                async def _consumir():
                    async for kind, piece in router.generate_stream(
                        text, file_context=contexto or None, history=historial or None
                    ):
                        if kind == "content":
                            partes.append(piece)
                        else:
                            # Va como indicador, no a la respuesta.
                            self.after(0, self._on_reasoning, piece)
                    return "".join(partes).strip()

                respuesta = asyncio.run(_consumir())
            finally:
                asyncio.run(router.close_all())

            if respuesta:
                self.after(0, self._on_response, respuesta)
            else:
                self.after(
                    0, self._on_response_error,
                    "El proveedor no devolvio contenido (puede ser rate-limit).",
                )
        except Exception as e:
            self.after(0, self._on_response_error, str(e))

    def _on_reasoning(self, texto):
        """Muestra que el modelo esta pensando, sin ensuciar el chat."""
        limpio = " ".join(texto.split())
        if limpio:
            self.footer_bar.set_status(f"pensando: {limpio[-70:]}")

    def _on_response(self, response):
        self.footer_bar.set_busy(False)
        self.footer_bar.set_status("")
        self.set_voice_active(False)
        session_lib.add_assistant(self.conversation, response)
        self._append_chat(f"[IA]: {response}")
        self._update_session_info()

    def _update_session_info(self):
        """Muestra el tamano del contexto en la barra de estado."""
        self.footer_bar.set_status(session_lib.summarize(self.conversation))

    def new_session(self):
        """Limpia la conversacion. El historial es memoria, no archivo."""
        self.conversation.clear()
        self._clear_chat_area()
        self._welcome()
        self._append_chat("[Sistema] Nueva sesion. Contexto reiniciado.")

    def _on_response_error(self, error):
        self.footer_bar.set_busy(False)
        self.footer_bar.set_status("")
        self.set_voice_active(False)
        self._append_chat(f"[ERROR]: {error}")

    # ------------------------------------------------------------------
    # DIAGNOSTICO DE PROVEEDORES
    # ------------------------------------------------------------------
    def test_providers(self):
        """Prueba cada proveedor configurado y muestra quien responde de verdad.

        Existe por una razon concreta: la config dice que un proveedor esta
        "listo" y aun asi puede fallar. Medido oct-2026 con la key de Kimi:
        GET /models daba 200 (key valida) pero chat/completions daba 429
        "account suspended due to insufficient balance". Eso NO se ve desde
        la config, solo haciendo una request real.

        Cuesta una request por proveedor (5-30s cada una con gateways lentos),
        asi que corre en un hilo y va reportando segun terminan.
        """
        self.test_sidebar_btn.configure(state="disabled", text="Testeando...")
        self._append_chat("[Test] Probando proveedores, puede tardar...")
        threading.Thread(target=self._test_worker, daemon=True).start()

    def _test_worker(self):
        """Hilo secundario: hace las requests. NO toca widgets."""
        import asyncio
        from src.core import config

        async def _run():
            return await config.diagnose_providers()

        try:
            resultados = asyncio.run(_run())
        except Exception as e:
            self.after(0, self._on_test_done, None, str(e))
            return
        self.after(0, self._on_test_done, resultados, None)

    def _on_test_done(self, resultados, error):
        self.test_sidebar_btn.configure(state="normal", text="Testear conexiones")

        if error:
            self._append_chat(f"[Test] ERROR: {error}")
            return

        lineas = ["[Test] Resultado:"]
        for r in resultados:
            marca = "OK  " if r["ok"] else "FALLA"
            lineas.append(f"  [{marca}] {r['nombre']}: {r['detalle']}")
        utiles = [r["nombre"] for r in resultados if r["ok"]]
        lineas.append("")
        if utiles:
            lineas.append(f"Respondiendo: {', '.join(utiles)}")
        else:
            lineas.append(
                "Ninguno responde. Causas comunes: sin saldo en el proveedor, "
                "o el servidor local (LM Studio / Ollama) no esta corriendo."
            )
        self._append_chat("\n".join(lineas))

    # ------------------------------------------------------------------
    # SELECTOR DE MODELOS
    # ------------------------------------------------------------------
    def pick_model(self):
        """Muestra el catalogo en vivo y deja elegir un modelo.

        Por que existe: un modelo escrito a mano en .env se rompe solo.
        MEDIDO oct-2026: `cohere/north-mini-code:free` funcionaba hace 21h
        y hoy da "not available in the active live catalog". El catalogo
        tiene 3241 entradas y muchas no funcionan. Consultarlo y probarlo
        es la unica forma de saber cual sirve ahora.
        """
        if getattr(self, "_model_win", None) is not None:
            try:
                self._model_win.lift()
                return
            except Exception:
                self._model_win = None

        win = ctk.CTkToplevel(self)
        self._model_win = win
        win.title("Modelos disponibles")
        win.geometry("640x560")
        win.configure(fg_color=COLORS["panel"])
        win.transient(self)

        win.grid_columnconfigure(0, weight=1)
        win.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            win, text="Consultando el catálogo en vivo...",
            font=(FONT_UI, FS["sm"]), text_color=COLORS["text"]
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 4))

        # Campo de filtro: 110 modelos es buscable, 3241 no.
        self.model_filter = ctk.CTkEntry(
            win, placeholder_text="Filtrar modelos...", height=34,
            fg_color=COLORS["panel_raised"], text_color=COLORS["text"], border_width=1,
            border_color=COLORS["border"]
        )
        self.model_filter.grid(row=1, column=0, sticky="ew", padx=16, pady=8)
        self.model_filter.bind("<KeyRelease>", lambda _e: self._refresh_model_list())

        # Lista
        self.model_list = ctk.CTkScrollableFrame(win, fg_color=COLORS["bg"], corner_radius=RADIUS_FIELD)
        self.model_list.grid(row=2, column=0, sticky="nsew", padx=16, pady=8)
        self.model_list.grid_columnconfigure(0, weight=1)

        self.model_status = ctk.CTkLabel(
            win, text="", font=(FONT_UI, FS["xs"]), text_color=COLORS["text_muted"], anchor="w"
        )
        self.model_status.grid(row=3, column=0, sticky="w", padx=16)

        acciones = ctk.CTkFrame(win, fg_color="transparent")
        acciones.grid(row=4, column=0, sticky="ew", padx=16, pady=(8, 16))
        acciones.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            acciones, text="Probar seleccionado", height=34,
            command=self._probe_selected_model, **ghost_btn_kwargs()
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            acciones, text="Usar este modelo", height=34,
            command=self._apply_selected_model, **primary_btn_kwargs()
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        self._all_models: List[str] = []
        self._filtered_models: List[str] = []
        self._selected_model: Optional[str] = None

        threading.Thread(target=self._load_models_worker, daemon=True).start()

    def _load_models_worker(self):
        """Hilo secundario: pide el catalogo. NO toca widgets."""
        import asyncio

        async def _run():
            router = ProviderRouter()
            try:
                todos = []
                for nombre in router.providers:
                    try:
                        todos.extend(await model_catalog.listar(router.get(nombre)))
                    except Exception:
                        continue
                return todos
            finally:
                await router.close_all()

        try:
            modelos = asyncio.run(_run())
        except Exception as e:
            self.after(0, self._set_model_status, f"Error: {e}")
            return

        self.after(0, self._set_models, modelos)

    def _set_models(self, modelos):
        self._all_models = sorted(set(modelos))
        self.model_filter.focus_set()
        self._refresh_model_list()
        if not self._all_models:
            self._set_model_status(
                "No se encontraron modelos. Revisa que el proveedor tenga base_url."
            )

    def _refresh_model_list(self):
        """Repinta la lista segun el filtro. Deja solo los N primeros."""
        if not hasattr(self, "_all_models"):
            return

        texto = (self.model_filter.get() or "").strip().lower()
        modelos = [
            m for m in self._all_models
            if not texto or texto in m.lower()
        ]
        # 60 filas es suficiente para elegir y evita colgar el scroll.
        self._filtered_models = modelos[:60]

        for child in self.model_list.winfo_children():
            child.destroy()

        if not modelos:
            ctk.CTkLabel(
                self.model_list, text="Sin coincidencias", font=(FONT_UI, FS["sm"]),
                text_color=COLORS["text_muted"]
            ).grid(row=0, column=0, pady=20)
        for i, m in enumerate(self._filtered_models):
            btn = ctk.CTkButton(
                self.model_list, text=m, anchor="w", height=30,
                font=(FONT_MONO, FS["xs"]), fg_color="transparent",
                hover_color=COLORS["cyan_dim"], text_color=COLORS["text"],
                corner_radius=4, command=lambda mm=m: self._select_model(mm)
            )
            btn.grid(row=i, column=0, sticky="ew", padx=4, pady=1)

        extra = len(modelos) - len(self._filtered_models)
        sufijo = f" (+{extra} mas, acota el filtro)" if extra > 0 else ""
        self._set_model_status(f"{len(modelos)} modelos{sufijo}")

    def _select_model(self, modelo):
        self._selected_model = modelo
        self._set_model_status(f"Seleccionado: {modelo}")

    def _set_model_status(self, texto):
        if hasattr(self, "model_status"):
            self.model_status.configure(text=texto[:120])

    def _probe_selected_model(self):
        """Prueba el modelo elegido con una request minima."""
        if not self._selected_model:
            self._set_model_status("Elegi un modelo de la lista primero.")
            return
        modelo = self._selected_model
        self._set_model_status(f"Probando {modelo}...")
        threading.Thread(target=self._probe_worker, args=(modelo,), daemon=True).start()

    def _probe_worker(self, modelo):
        import asyncio

        async def _run():
            router = ProviderRouter()
            try:
                prov = router.get(self._probe_provider)
                return await model_catalog.probar(prov, modelo)
            finally:
                await router.close_all()

        self._probe_provider = getattr(self, "_probe_provider", None) or "OmniRoute"
        try:
            res = asyncio.run(_run())
        except Exception as e:
            self.after(0, self._set_model_status, f"Error: {str(e)[:80]}")
            return

        if res["ok"]:
            ttft = res["ttft"] or 0
            msg = f"OK  {modelo}  respondio en {ttft:.1f}s"
        else:
            msg = f"FALLA {modelo}: {res['motivo'][:60]}"
        self.after(0, self._set_model_status, msg)

    def _apply_selected_model(self):
        """Guarda el modelo elegido en .env y avisa que reinicie."""
        if not self._selected_model:
            self._set_model_status("Elegi un modelo de la lista primero.")
            return

        modelo = self._selected_model
        try:
            ok, detalle = set_model_in_env("OMNIROUTE_MODEL", modelo)
        except Exception as e:
            self._set_model_status(f"No se pudo escribir .env: {e}")
            return

        try:
            if self._model_win is not None:
                self._model_win.destroy()
                self._model_win = None
        except Exception:
            pass

        if ok:
            self._append_chat(
                f"[Sistema] OMNIROUTE_MODEL = {modelo}\n"
                "Cerrá y abrí la app para que tome el cambio. "
                "Mientras tanto sigue usando el modelo anterior."
            )
        else:
            self._append_chat(f"[Sistema] No se pudo guardar: {detalle}")

    def choose_model(self):
        """Muestra el modelo que esta usando cada proveedor configurado."""
        try:
            from src.core import config
        except Exception as e:
            self._append_chat(f"[ERROR] No se pudo leer la config: {e}")
            return

        lineas = ["[Modelos configurados]"]
        for nombre in config.list_providers():
            cfg = config.get_provider_config(nombre)
            modelo = cfg.get("model") or "(sin modelo)"
            lineas.append(f"- {nombre}: {modelo}")
        self._append_chat("\n".join(lineas))


if __name__ == "__main__":
    app = App()
    app.mainloop()
