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
from src.core import config as app_config
from src.core import prefs as user_prefs
from src.core import sessions_store
from src.core.model_catalog import set_model_in_env, set_env_var
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
    """Panel lateral: editar api_key / base_url / model por proveedor."""

    def __init__(self, master, on_saved=None):
        super().__init__(
            master, width=340, fg_color=COLORS["panel"],
            corner_radius=0, border_width=1, border_color=COLORS["border_glow"],
        )
        self.on_saved = on_saved
        self._selected: Optional[str] = None
        self.grid_remove()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            self, text="Configuración", font=(FONT_MONO, FS["lg"], "bold"),
            text_color=COLORS["cyan"],
        ).grid(row=0, column=0, sticky="w", padx=SPACE[4], pady=(SPACE[4], SPACE[1]))

        ctk.CTkLabel(
            self, text="Proveedores · keys en .env",
            font=(FONT_MONO, FS["xs"]), text_color=COLORS["text_dim"],
        ).grid(row=1, column=0, sticky="w", padx=SPACE[4], pady=(0, SPACE[2]))

        # Lista de proveedores
        self.list_frame = ctk.CTkScrollableFrame(
            self, fg_color=COLORS["bg"], height=140,
            scrollbar_button_color=COLORS["border_glow"],
            scrollbar_button_hover_color=COLORS["cyan_mid"],
        )
        self.list_frame.grid(row=2, column=0, sticky="nsew", padx=SPACE[3], pady=SPACE[1])
        self.list_frame.grid_columnconfigure(0, weight=1)

        # Formulario
        form = ctk.CTkFrame(self, fg_color="transparent")
        form.grid(row=3, column=0, sticky="ew", padx=SPACE[3], pady=SPACE[2])
        form.grid_columnconfigure(0, weight=1)

        self.lbl_name = ctk.CTkLabel(
            form, text="—", font=(FONT_MONO, FS["sm"], "bold"),
            text_color=COLORS["text"], anchor="w",
        )
        self.lbl_name.grid(row=0, column=0, sticky="ew", pady=(0, SPACE[2]))

        ctk.CTkLabel(form, text="BASE URL", font=(FONT_MONO, FS["xs"]),
                     text_color=COLORS["text_muted"], anchor="w").grid(row=1, column=0, sticky="w")
        self.entry_url = ctk.CTkEntry(
            form, height=30, fg_color=COLORS["panel_raised"],
            text_color=COLORS["text"], border_color=COLORS["border"],
            placeholder_text_color=COLORS["text_dim"],
        )
        self.entry_url.grid(row=2, column=0, sticky="ew", pady=(0, SPACE[2]))

        ctk.CTkLabel(form, text="API KEY", font=(FONT_MONO, FS["xs"]),
                     text_color=COLORS["text_muted"], anchor="w").grid(row=3, column=0, sticky="w")
        self.entry_key = ctk.CTkEntry(
            form, height=30, fg_color=COLORS["panel_raised"],
            text_color=COLORS["text"], border_color=COLORS["border"],
            placeholder_text="(vacío = sin key / local)",
            placeholder_text_color=COLORS["text_dim"], show="*",
        )
        self.entry_key.grid(row=4, column=0, sticky="ew", pady=(0, SPACE[1]))

        self.btn_show_key = ctk.CTkButton(
            form, text="Mostrar key", height=24, width=100,
            command=self._toggle_key_visibility, **ghost_btn_kwargs(),
        )
        self.btn_show_key.grid(row=5, column=0, sticky="w", pady=(0, SPACE[2]))

        ctk.CTkLabel(form, text="MODELO", font=(FONT_MONO, FS["xs"]),
                     text_color=COLORS["text_muted"], anchor="w").grid(row=6, column=0, sticky="w")
        self.entry_model = ctk.CTkEntry(
            form, height=30, fg_color=COLORS["panel_raised"],
            text_color=COLORS["text"], border_color=COLORS["border"],
            placeholder_text_color=COLORS["text_dim"],
        )
        self.entry_model.grid(row=7, column=0, sticky="ew", pady=(0, SPACE[2]))

        self.lbl_status = ctk.CTkLabel(
            form, text="", font=(FONT_MONO, FS["xs"]),
            text_color=COLORS["text_dim"], anchor="w", wraplength=300,
        )
        self.lbl_status.grid(row=8, column=0, sticky="ew", pady=(0, SPACE[1]))

        actions = ctk.CTkFrame(form, fg_color="transparent")
        actions.grid(row=9, column=0, sticky="ew", pady=(SPACE[1], SPACE[3]))
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            actions, text="Guardar", height=34,
            command=self._save_current, **primary_btn_kwargs(),
        ).grid(row=0, column=0, sticky="ew", padx=(0, SPACE[1]))
        ctk.CTkButton(
            actions, text="Cerrar", height=34,
            command=self.toggle, **ghost_btn_kwargs(),
        ).grid(row=0, column=1, sticky="ew", padx=(SPACE[1], 0))

        self._key_visible = False
        self._rebuild_list()

    def _rebuild_list(self) -> None:
        for w in self.list_frame.winfo_children():
            w.destroy()
        for i, name in enumerate(app_config.list_providers()):
            cfg = app_config.get_provider_config(name)
            ready = app_config.is_configured(name)
            mark = "●" if ready else "○"
            color = COLORS["green"] if ready else COLORS["text_dim"]
            btn = ctk.CTkButton(
                self.list_frame,
                text=f"{mark}  {name}",
                anchor="w", height=28,
                font=(FONT_MONO, FS["xs"]),
                fg_color=COLORS["cyan_dim"] if name == self._selected else "transparent",
                hover_color=COLORS["cyan_dim"],
                text_color=color if name != self._selected else COLORS["text"],
                border_width=0,
                command=lambda n=name: self._select(n),
            )
            btn.grid(row=i, column=0, sticky="ew", pady=1)

    def _select(self, name: str) -> None:
        self._selected = name
        try:
            cfg = app_config.get_provider_config(name)
        except KeyError:
            return
        self.lbl_name.configure(text=name)
        self.entry_url.delete(0, "end")
        self.entry_url.insert(0, cfg.get("base_url") or "")
        self.entry_key.delete(0, "end")
        self.entry_key.insert(0, cfg.get("api_key") or "")
        self.entry_model.delete(0, "end")
        self.entry_model.insert(0, cfg.get("model") or "")
        masked = app_config.mask_secret(cfg.get("api_key") or "")
        self.lbl_status.configure(
            text=f"key: {masked or '(vacía)'}  ·  env: {cfg.get('api_key_env') or '?'}",
            text_color=COLORS["text_dim"],
        )
        self._rebuild_list()

    def _toggle_key_visibility(self) -> None:
        self._key_visible = not self._key_visible
        self.entry_key.configure(show="" if self._key_visible else "*")
        self.btn_show_key.configure(text="Ocultar key" if self._key_visible else "Mostrar key")

    def _save_current(self) -> None:
        name = self._selected
        if not name:
            self.lbl_status.configure(text="Elegí un proveedor de la lista.", text_color=COLORS["warning"])
            return
        url = self.entry_url.get().strip()
        key = self.entry_key.get().strip()
        model = self.entry_model.get().strip()

        errs = []
        for env_name, val in (
            (app_config.base_url_env_for(name), url),
            (app_config.api_key_env_for(name), key),
            (app_config.model_env_for(name), model),
        ):
            if not env_name:
                continue
            ok, det = set_env_var(env_name, val, create_if_missing=True)
            if not ok:
                errs.append(det)

        # Runtime hot apply
        app_config.apply_provider_runtime(name, api_key=key, base_url=url, model=model)

        if errs:
            self.lbl_status.configure(
                text="Parcial: " + "; ".join(errs)[:120],
                text_color=COLORS["magenta"],
            )
        else:
            self.lbl_status.configure(
                text="Guardado en .env · activo en caliente",
                text_color=COLORS["green"],
            )
        self._rebuild_list()
        if self.on_saved:
            try:
                self.on_saved(name)
            except Exception:
                pass

    def toggle(self) -> None:
        if self.winfo_ismapped():
            self.grid_remove()
        else:
            self._rebuild_list()
            if self._selected is None:
                names = app_config.list_providers()
                if names:
                    self._select(names[0])
            self.grid(row=0, column=1, rowspan=3, sticky="nsew")


class FooterBar(ctk.CTkFrame):
    """Composer: fila 1 = input + CTA; fila 2 = toolbar ghost."""
    def __init__(self, master, on_send, on_attach, on_model, on_pick_model=None):
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

        # Scroll: follow=True mientras el usuario no se mueva arriba a mano.
        # _scroll_job coalesca updates del stream.
        self._scroll_follow = True
        self._scroll_job = None
        self.session_id = user_prefs.get_current_session_id() or sessions_store.new_id()

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

        self.settings_panel = SettingsPanel(self, on_saved=self._on_provider_settings_saved)

        self.top_bar = ctk.CTkFrame(
            self, fg_color=COLORS["panel"], height=56, corner_radius=RADIUS_PANEL,
            border_width=1, border_color=COLORS["border"],
        )
        self.top_bar.grid(row=0, column=2, sticky="ew", padx=SPACE[2], pady=(SPACE[2], 0))
        self.top_bar.grid_propagate(False)
        self.top_bar.grid_columnconfigure(0, weight=1)

        self.editor_area = EditorArea(self)
        self.editor_area.grid(row=1, column=2, sticky="nsew", padx=SPACE[2], pady=SPACE[2])
        # Si el usuario sube el scroll a mano, no lo arrastramos de vuelta.
        # Al volver cerca del fondo, reactivamos follow.
        try:
            canvas = self.editor_area.chat_area._parent_canvas
            canvas.bind("<MouseWheel>", self._on_chat_user_scroll, add="+")
            canvas.bind("<Button-4>", self._on_chat_user_scroll, add="+")
            canvas.bind("<Button-5>", self._on_chat_user_scroll, add="+")
            canvas.bind("<ButtonPress-1>", self._on_chat_user_scroll, add="+")
        except Exception:
            pass

        self.footer_bar = FooterBar(
            self, on_send=self.send_message, on_attach=self.attach_files,
            on_model=self.choose_model, on_pick_model=self.pick_model,
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

        self.load_session_btn = _rail_btn("☰  Cargar sesión", self.load_session_dialog)
        self.load_session_btn.pack(fill="x", padx=SPACE[3], pady=SPACE[1])

        self.save_session_btn = _rail_btn("💾  Guardar sesión", self.save_current_session)
        self.save_session_btn.pack(fill="x", padx=SPACE[3], pady=SPACE[1])

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
        self.top_review_btn.grid(row=0, column=5, sticky="e", padx=(0, SPACE[2]))

        # Selector de proveedor (persistido en .gssmart_prefs.json)
        prov_wrap = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        prov_wrap.grid(row=0, column=6, sticky="e", padx=(0, SPACE[4]))
        ctk.CTkLabel(
            prov_wrap, text="PROV", font=(FONT_MONO, FS["xs"], "bold"),
            text_color=COLORS["text_dim"],
        ).pack(side="left", padx=(0, SPACE[1]))

        self._provider_names = app_config.configured_providers()
        if not self._provider_names:
            self._provider_names = ["(sin proveedores)"]

        preferred = user_prefs.get_active_provider()
        self.active_provider = app_config.resolve_active_provider(preferred)
        if self.active_provider is None:
            self.active_provider = self._provider_names[0]

        self.provider_menu = ctk.CTkOptionMenu(
            prov_wrap,
            values=self._provider_names,
            width=160, height=28,
            font=(FONT_MONO, FS["xs"]),
            fg_color=COLORS["panel_raised"],
            button_color=COLORS["cyan_dim"],
            button_hover_color=COLORS["cyan_mid"],
            dropdown_fg_color=COLORS["panel"],
            dropdown_hover_color=COLORS["cyan_dim"],
            text_color=COLORS["text"],
            command=self._on_provider_change,
        )
        self.provider_menu.pack(side="left")
        if self.active_provider in self._provider_names:
            self.provider_menu.set(self.active_provider)

        # La arranca al final: self.after(0, ...) garantiza que el Canvas ya
        # tiene tamano cuando corre el primer frame. Si se llama directo, el
        # primer dibujado sale con width=1 y la onda aparece chueca un rato.
        self.after(0, self._animate_voice)
        self.after(10, self._startup_session)
        self.after(20, self._refresh_provider_label)

    # --- Lógica de Interacción ---

    def toggle_settings(self):
        self.settings_panel.toggle()

    def _on_provider_settings_saved(self, name: str) -> None:
        names = app_config.configured_providers() or ["(sin proveedores)"]
        self._provider_names = names
        if hasattr(self, "provider_menu"):
            self.provider_menu.configure(values=names)
            if self.active_provider in names:
                self.provider_menu.set(self.active_provider)
            elif names and names[0] != "(sin proveedores)":
                self.active_provider = names[0]
                self.provider_menu.set(names[0])
                user_prefs.set_active_provider(names[0])
        self._refresh_provider_label()
        self._append_chat(f"[Sistema] Proveedor actualizado: {name}")

    def toggle_revision(self):
        if self.editor_area.review_frame.winfo_ismapped():
            self.editor_area.review_frame.grid_remove()
            self.top_review_btn.configure(text="Mostrar Revisión")
        else:
            self.editor_area.review_frame.grid()
            self.top_review_btn.configure(text="Ocultar Revisión")
            self.editor_area.diff_widget.load_diff("", "funcion_hola() {\n  return 'Hola Mundo';\n}")

    def _on_provider_change(self, name: str) -> None:
        """Usuario eligio proveedor en el menu. Persiste y actualiza label."""
        if name == "(sin proveedores)":
            return
        self.active_provider = name
        user_prefs.set_active_provider(name)
        self._refresh_provider_label()
        self._append_chat(f"[Sistema] Proveedor activo: {name}")

    def _refresh_provider_label(self) -> None:
        """Muestra el modelo del proveedor activo en el status del footer."""
        name = getattr(self, "active_provider", None)
        if not name or name == "(sin proveedores)":
            return
        try:
            cfg = app_config.get_provider_config(name)
            modelo = cfg.get("model") or "?"
        except Exception:
            modelo = "?"
        if hasattr(self, "footer_bar"):
            self.footer_bar.set_status(f"{name} · {modelo}")

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
        """Baja al ultimo mensaje (siempre, p.ej. al agregar burbuja nueva)."""
        self._scroll_follow = True
        self._schedule_scroll(immediate=True)

    def _request_stream_scroll(self) -> None:
        """Scroll durante streaming: coalescido (~50ms) para no saturar Tk.

        Cada token llamaba yview_moveto antes de que el label creciera y el
        canvas actualizara scrollregion → el chat se quedaba quieto a mitad.
        """
        if not getattr(self, "_scroll_follow", True):
            return
        self._schedule_scroll(immediate=False)

    def _schedule_scroll(self, immediate: bool = False) -> None:
        if getattr(self, "_scroll_job", None) is not None:
            if immediate:
                try:
                    self.after_cancel(self._scroll_job)
                except Exception:
                    pass
                self._scroll_job = None
            else:
                return  # ya hay uno pendiente: coalescer
        delay = 0 if immediate else 50
        self._scroll_job = self.after(delay, self._do_scroll_to_bottom)

    def _do_scroll_to_bottom(self) -> None:
        """Fuerza layout + scrollregion y mueve al fondo.

        Orden critico:
          1) update_idletasks  → el label ya tiene altura real
          2) bbox("all")      → scrollregion cubre el contenido nuevo
          3) yview_moveto(1)  → ahora si llega al final
          4) after(16) reintento → segunda pasada por si el wrap de CTk
             termina un frame tarde
        """
        self._scroll_job = None
        try:
            area = self.editor_area.chat_area
            canvas = area._parent_canvas
        except Exception:
            return

        def _apply(retry: bool = True) -> None:
            try:
                area.update_idletasks()
                bbox = canvas.bbox("all")
                if bbox:
                    canvas.configure(scrollregion=bbox)
                canvas.yview_moveto(1.0)
                if retry:
                    # Segunda pasada: wraplength/fuente a veces redimensionan
                    # un frame despues del primer update_idletasks.
                    self.after(16, lambda: _apply(retry=False))
            except Exception:
                pass

        _apply(retry=True)

    def _on_chat_user_scroll(self, _event=None) -> None:
        """Si el usuario se aleja del fondo, pausa auto-scroll; si vuelve, reanuda."""
        try:
            canvas = self.editor_area.chat_area._parent_canvas
            # yview() -> (top, bottom) fracciones 0..1
            _top, bottom = canvas.yview()
            self._scroll_follow = bottom >= 0.92
        except Exception:
            self._scroll_follow = True

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

    def _startup_session(self) -> None:
        """Carga la ultima sesion si existe; si no, welcome limpio."""
        sid = user_prefs.get_current_session_id()
        if sid:
            data = sessions_store.load(sid)
            if data and (data.get("messages") or []):
                self.session_id = data.get("id") or sid
                self.conversation = list(data.get("messages") or [])
                self._add_bubble("system", f"Sesión restaurada: {data.get('title') or sid}")
                for m in self.conversation:
                    role = m.get("role")
                    content = m.get("content") or ""
                    if role == "user":
                        self._add_bubble("user", content)
                    elif role == "assistant":
                        self._add_bubble("ai", content)
                self._scroll_chat_to_bottom()
                return
        self.session_id = sid or sessions_store.new_id()
        user_prefs.set_current_session_id(self.session_id)
        self._welcome()

    def _welcome(self) -> None:
        """Mensaje inicial."""
        self._add_bubble("system", "GSsmart Desktop AI")
        prov = getattr(self, "active_provider", None) or "ninguno"
        self._add_bubble(
            "system",
            f"Proveedor: {prov}. Escribí abajo para chatear.\n"
            "PROV (arriba) · Configuración (keys) · Guardar/Cargar sesión.",
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

        # Burbuja vacia de IA: el worker la llena token a token (streaming).
        # Se crea en el hilo de Tk, nunca desde el worker.
        ai_bubble = self._add_bubble("ai", "…")

        self.footer_bar.set_busy(True)
        self.set_voice_active(True)
        provider = self.active_provider
        if provider == "(sin proveedores)":
            provider = None
        threading.Thread(
            target=self._ask_worker,
            args=(text, archivos, ai_bubble, provider),
            daemon=True,
        ).start()

    def _ask_worker(self, text, archivos, ai_bubble, provider):
        """Hilo secundario: stream al proveedor. NO toca widgets (solo after).

        Streaming en vivo: cada chunk de content se append a la burbuja.
        Reasoning va al status bar (no al chat).
        """
        partes = []
        first_content = True
        try:
            contexto = build_file_context(archivos)
            historial = session_lib.build_history(self.conversation[:-1])
            router = ProviderRouter()
            try:
                async def _consumir():
                    nonlocal first_content
                    async for kind, piece in router.generate_stream(
                        text,
                        provider=provider,
                        file_context=contexto or None,
                        history=historial or None,
                    ):
                        if kind == "content":
                            partes.append(piece)
                            # Limpia el placeholder "…" en el primer token.
                            if first_content:
                                first_content = False
                                self.after(0, ai_bubble.set_text, piece)
                            else:
                                self.after(0, ai_bubble.append, piece)
                            self.after(0, self._request_stream_scroll)
                        else:
                            self.after(0, self._on_reasoning, piece)
                    return "".join(partes).strip()

                respuesta = asyncio.run(_consumir())
            finally:
                try:
                    asyncio.run(router.close_all())
                except Exception:
                    pass

            if respuesta:
                self.after(0, self._on_response, respuesta, ai_bubble)
            else:
                self.after(
                    0, self._on_response_error,
                    "El proveedor no devolvio contenido (puede ser rate-limit).",
                    ai_bubble,
                )
        except Exception as e:
            self.after(0, self._on_response_error, str(e), ai_bubble)

    def _on_reasoning(self, texto):
        """Muestra que el modelo esta pensando, sin ensuciar el chat."""
        limpio = " ".join(texto.split())
        if limpio:
            self.footer_bar.set_status(f"pensando: {limpio[-70:]}")

    def _on_response(self, response, ai_bubble=None):
        self.footer_bar.set_busy(False)
        self.set_voice_active(False)
        session_lib.add_assistant(self.conversation, response)
        # La burbuja ya tiene el texto del stream; solo asegúrate del final.
        if ai_bubble is not None and getattr(ai_bubble, "winfo_exists", lambda: False)():
            try:
                if (ai_bubble.text or "").strip() in ("", "…"):
                    ai_bubble.set_text(response)
                elif ai_bubble.text != response:
                    ai_bubble.set_text(response)
            except Exception:
                pass
        self._scroll_chat_to_bottom()
        self._autosave_session(silent=True)
        self._update_session_info()

    def _update_session_info(self):
        """Muestra el tamano del contexto en la barra de estado."""
        self.footer_bar.set_status(session_lib.summarize(self.conversation))

    def new_session(self):
        """Guarda la actual (si hay turnos) y abre una sesion nueva."""
        self._autosave_session(silent=True)
        self.conversation.clear()
        self.session_id = sessions_store.new_id()
        user_prefs.set_current_session_id(self.session_id)
        self._clear_chat_area()
        self._welcome()
        self._append_chat("[Sistema] Nueva sesión. Contexto reiniciado.")

    def save_current_session(self) -> None:
        sid = self._autosave_session(silent=False)
        if sid:
            self._append_chat(f"[Sistema] Sesión guardada: {sid}")
        else:
            self._append_chat("[Sistema] Nada que guardar (sin mensajes user/assistant).")

    def _autosave_session(self, silent: bool = True) -> Optional[str]:
        usable = [
            m for m in self.conversation
            if m.get("role") in ("user", "assistant") and (m.get("content") or "").strip()
        ]
        if not usable:
            return None
        sid = self.session_id or sessions_store.new_id()
        self.session_id = sessions_store.save(
            sid, self.conversation,
            provider=getattr(self, "active_provider", None),
        )
        user_prefs.set_current_session_id(self.session_id)
        return self.session_id

    def load_session_dialog(self) -> None:
        rows = sessions_store.list_sessions(limit=30)
        win = ctk.CTkToplevel(self)
        win.title("Sesiones guardadas")
        win.geometry("480x420")
        win.configure(fg_color=COLORS["panel"])
        win.transient(self)
        win.grid_columnconfigure(0, weight=1)
        win.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            win, text="Sesiones", font=(FONT_MONO, FS["md"], "bold"),
            text_color=COLORS["cyan"],
        ).grid(row=0, column=0, sticky="w", padx=SPACE[4], pady=SPACE[3])

        lst = ctk.CTkScrollableFrame(win, fg_color=COLORS["bg"])
        lst.grid(row=1, column=0, sticky="nsew", padx=SPACE[3], pady=SPACE[2])
        lst.grid_columnconfigure(0, weight=1)

        if not rows:
            ctk.CTkLabel(
                lst, text="No hay sesiones guardadas.",
                font=(FONT_UI, FS["sm"]), text_color=COLORS["text_muted"],
            ).grid(row=0, column=0, pady=SPACE[5])
        for i, row in enumerate(rows):
            title = row.get("title") or row.get("id")
            meta = f"{row.get('n_messages', 0)} msgs · {row.get('provider') or '-'}"
            frame = ctk.CTkFrame(
                lst, fg_color=COLORS["panel_raised"], corner_radius=RADIUS_FIELD,
            )
            frame.grid(row=i, column=0, sticky="ew", pady=2, padx=2)
            frame.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                frame, text=title, font=(FONT_MONO, FS["sm"]),
                text_color=COLORS["text"], anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=SPACE[2], pady=(SPACE[1], 0))
            ctk.CTkLabel(
                frame, text=meta, font=(FONT_MONO, FS["xs"]),
                text_color=COLORS["text_dim"], anchor="w",
            ).grid(row=1, column=0, sticky="w", padx=SPACE[2], pady=(0, SPACE[1]))
            ctk.CTkButton(
                frame, text="Abrir", width=70, height=28,
                command=lambda sid=row["id"], w=win: self._open_session(sid, w),
                **ghost_btn_kwargs(),
            ).grid(row=0, column=1, rowspan=2, padx=SPACE[2])

    def _open_session(self, session_id: str, win=None) -> None:
        data = sessions_store.load(session_id)
        if not data:
            self._append_chat(f"[ERROR]: No se pudo cargar {session_id}")
            return
        self._autosave_session(silent=True)
        self.session_id = data.get("id") or session_id
        user_prefs.set_current_session_id(self.session_id)
        self.conversation = list(data.get("messages") or [])
        self._clear_chat_area()
        self._add_bubble("system", f"Sesión: {data.get('title') or self.session_id}")
        for m in self.conversation:
            role = m.get("role")
            content = m.get("content") or ""
            if role == "user":
                self._add_bubble("user", content)
            elif role == "assistant":
                self._add_bubble("ai", content)
        if win is not None:
            try:
                win.destroy()
            except Exception:
                pass
        self._scroll_chat_to_bottom()

    def _on_response_error(self, error, ai_bubble=None):
        self.footer_bar.set_busy(False)
        self.set_voice_active(False)
        if ai_bubble is not None:
            try:
                if ai_bubble.winfo_exists():
                    # Reemplaza la burbuja vacia por una de error
                    ai_bubble.destroy()
                    if ai_bubble in self.editor_area.bubbles:
                        self.editor_area.bubbles.remove(ai_bubble)
            except Exception:
                pass
        self._append_chat(f"[ERROR]: {error}")
        self._refresh_provider_label()

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

        self._probe_provider = getattr(self, "active_provider", None) or "OmniRoute"
        if self._probe_provider == "(sin proveedores)":
            self._probe_provider = "OmniRoute"
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
        prov = getattr(self, "active_provider", None) or "OmniRoute"
        env_var = app_config.model_env_for(prov) or "OMNIROUTE_MODEL"
        try:
            ok, detalle = set_model_in_env(env_var, modelo)
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
            # Aplica en caliente: el router se re-instancia en cada mensaje
            # y lee PROVIDERS + os.environ.
            import os
            os.environ[env_var] = modelo
            if prov in app_config.PROVIDERS:
                app_config.PROVIDERS[prov]["model"] = modelo
            self._append_chat(
                f"[Sistema] {env_var} = {modelo}\n"
                "Modelo activo actualizado (sin reiniciar)."
            )
            self._refresh_provider_label()
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
