import customtkinter as ctk
from tkinter import scrolledtext, filedialog, scrolledtext as tk_st
import sys
import difflib
import threading
from pathlib import Path
from typing import List

from src.core.file_context import build_file_context, describe_files

# -------------------------------------------------
# 1. CONFIGURACIÓN GLOBAL
# -------------------------------------------------
BASE_DIR = Path(__file__).parent.parent

# Antes esto insertaba "src/core" en sys.path e importaba "router" a pelo.
# Eso rompia: router.py hace imports absolutos ("from src.providers..."), asi
# que Needs the RAIZ del repo en el path, y el except ImportError caia en un
# stub que DEVUELVE una frase de exito falsa. Si el import se rompia, la app
# arrancaba igual y mentia sobre el estado del router.
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from src.core.router import get_ai_response
    ROUTER_IMPORT_ERROR = None
except Exception as _err:  # noqa: BLE001 - queremos ver la causa real
    ROUTER_IMPORT_ERROR = str(_err)

    def get_ai_response(text: str) -> str:
        # Falla en voz alta en vez de fingir que la IA respondio.
        raise RuntimeError(
            f"El router de proveedores no se pudo importar: {ROUTER_IMPORT_ERROR}"
        )

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# Paleta. El input comparte fondo con el footer: si no, el "#0f172a" del
# entry sobre el "#111827" del footer se ve como un bloque azul distinto
# pegado abajo, que es lo que pasaba antes.
FOOTER_BG = "#111827"


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
            bg="#0f172a",
            fg="white",
            insertbackground="white",
            font=("Consolas", 11),
            wrap="word",
            borderwidth=0,
            highlightthickness=0,
            padx=8, pady=8
        )
        self.tag_config("diff-unchanged", background="#0f172a", foreground="#cbd5e1")
        self.tag_config("diff-added", background="#064e3b", foreground="#34d399")
        self.tag_config("diff-removed", background="#450a0a", foreground="#f87171")

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
        super().__init__(master, width=280, fg_color="#111827", corner_radius=0)
        self.on_option_click = on_option_click
        self.grid_remove() # Oculto por defecto

        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Configuración", font=("Segoe UI", 18, "bold"), text_color="white").grid(row=0, column=0, sticky="w", padx=18, pady=18)

        options = ["Preferencias", "Apariencia", "Audio", "Modelo", "Atajos", "Privacidad", "Sistema", "Avanzado"]
        for i, opt in enumerate(options):
            ctk.CTkButton(
                self, text=opt, anchor="w", fg_color="#1f2937", hover_color="#374151", 
                text_color="white", font=("Segoe UI", 12), 
                command=lambda o=opt: self.on_option_click(o)
            ).grid(row=i+1, column=0, sticky="ew", padx=14, pady=4)

    def toggle(self):
        if self.winfo_ismapped():
            self.grid_remove()
        else:
            self.grid(row=0, column=1, rowspan=3, sticky="nsew")


class FooterBar(ctk.CTkFrame):
    """Barra inferior con input y acciones."""
    def __init__(self, master, on_send, on_attach, on_model, on_audio_toggle):
        super().__init__(master, fg_color="#111827", corner_radius=20)

        # COLUMNA 0 = input (crece)  |  COLUMNA 1 = acciones (ancho fijo)
        # Sin weight=1 en la col 0, grid le daba al input solo el ancho minimo
        # de su contenido y quedaba un bloque de fondo vacio al lado.
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=0)

        # --- Fila de input: ocupa toda la columna 0 ---
        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.grid(row=0, column=0, sticky="ew", padx=(12, 8), pady=12)
        self.input_frame.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkEntry(
            self.input_frame, placeholder_text="Escribe tu mensaje aquí...",
            height=42, fg_color=FOOTER_BG, text_color="white", border_width=0
        )
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.entry.bind("<Return>", lambda e: on_send(self.entry.get()))

        self.send_btn = ctk.CTkButton(
            self.input_frame, text="Enviar", width=100, height=42, fg_color="#00d9ff",
            hover_color="#00b8d9", text_color="black", corner_radius=21,
            command=lambda: on_send(self.entry.get())
        )
        self.send_btn.grid(row=0, column=1)

        # --- Acciones: columna fija a la derecha, alineadas al fondo ---
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e", padx=(0, 12), pady=12)
        actions.grid_columnconfigure(0, weight=1)

        self.attach_btn = ModernButton(
            actions, text="📎 Adjuntar", fg_color="#1e293b", text_color="white",
            hover_color="#334155", width=110, height=34, command=on_attach
        )
        self.attach_btn.grid(row=0, column=0, padx=(0, 6))

        self.model_btn = ModernButton(
            actions, text="🤖 Modelo", fg_color="#1e293b", text_color="white",
            hover_color="#334155", width=100, height=34, command=on_model
        )
        self.model_btn.grid(row=0, column=1, padx=(0, 6))

        self.audio_switch = ctk.CTkSwitch(
            actions, text="Audio", progress_color="#00d9ff",
            button_color="#94a3b8", button_hover_color="#cbd5e1",
            width=44, command=on_audio_toggle
        )
        self.audio_switch.grid(row=0, column=2)

    def set_busy(self, busy):
        """Bloquea el input mientras se espera a la IA."""
        state = "disabled" if busy else "normal"
        self.entry.configure(state=state)
        self.send_btn.configure(
            state=state,
            text="Pensando..." if busy else "Enviar",
            fg_color="#1e3a5f" if busy else "#00d9ff",
        )

    def set_attached_count(self, count):
        """Muestra cuantos archivos hay adjuntos en el boton."""
        self.attach_btn.configure(
            text=f"📎 Adjuntar ({count})" if count else "📎 Adjuntar"
        )


class EditorArea(ctk.CTkFrame):
    """Área principal con Chat y Revisión (usa grid)."""
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. Chat Area
        self.chat_frame = ctk.CTkFrame(self, fg_color="#0f172a", corner_radius=10)
        self.chat_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.chat_text = scrolledtext.ScrolledText(
            self.chat_frame, bg="#0f172a", fg="white", insertbackground="white",
            font=("Segoe UI", 12), wrap="word", borderwidth=0, highlightthickness=0
        )
        self.chat_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.chat_text.config(state="disabled")

        # 2. Review Panel (Diff)
        self.review_frame = ctk.CTkFrame(self, fg_color="#0f172a", corner_radius=10)
        self.review_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
        self.review_frame.grid_remove() # Oculto por defecto
        self.review_frame.grid_columnconfigure(0, weight=1)
        self.review_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self.review_frame, text="Revisión de Código (Diff)", font=("Segoe UI", 14, "bold"),
            text_color="#cbd5e1"
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))

        self.diff_widget = DiffText(self.review_frame)
        self.diff_widget.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))


# -------------------------------------------------
# 4. CLASE PRINCIPAL
# -------------------------------------------------
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("GSsmart Desktop AI")
        self.geometry("1280x800")
        self.minsize(1100, 700)
        self.configure(bg="#0b1220")

        # Archivos adjuntos del mensaje en curso.
        self.attached_files: List[str] = []

        # Layout Grid Principal
        #   col 0 = sidebar | col 1 = settings | col 2 = contenido
        #   row 0 = top_bar | row 1 = editor_area | row 2 = footer_bar
        self.grid_columnconfigure(0, weight=0, minsize=220)  # Sidebar
        self.grid_columnconfigure(1, weight=0)                # Settings
        self.grid_columnconfigure(2, weight=1)                # Content
        self.grid_rowconfigure(0, weight=0)                   # TopBar
        self.grid_rowconfigure(1, weight=1)                   # EditorArea <- único que crece
        self.grid_rowconfigure(2, weight=0)                   # FooterBar

        # --- Inicializar Componentes ---
        self.sidebar = ctk.CTkFrame(self, width=220, fg_color="#0f172a", corner_radius=0)
        self.sidebar.grid(row=0, column=0, rowspan=3, sticky="nsew")
        self.sidebar.grid_propagate(False)

        self.settings_panel = SettingsPanel(self, on_option_click=self.handle_settings_option)
        
        self.top_bar = ctk.CTkFrame(self, fg_color="#0f172a", height=60, corner_radius=0)
        self.top_bar.grid(row=0, column=2, sticky="ew", padx=10, pady=(10, 0))
        self.top_bar.grid_propagate(False)
        self.top_bar.grid_columnconfigure(0, weight=1)

        self.editor_area = EditorArea(self)
        self.editor_area.grid(row=1, column=2, sticky="nsew", padx=10, pady=10)

        self.footer_bar = FooterBar(
            self, on_send=self.send_message, on_attach=self.attach_files,
            on_model=self.choose_model, on_audio_toggle=self.toggle_audio
        )
        self.footer_bar.grid(row=2, column=2, sticky="ew", padx=10, pady=(0, 10))

        # --- Construcción del Sidebar ---
        ctk.CTkLabel(
            self.sidebar, text="GSsmart", font=("Segoe UI", 24, "bold"), text_color="#00d9ff"
        ).pack(pady=(30, 20))

        ctk.CTkLabel(
            self.sidebar, text="Panel de Control", font=("Segoe UI", 12, "bold"), 
            text_color="#64748b"
        ).pack(pady=(0, 10))

        self.settings_sidebar_btn = ctk.CTkButton(
            self.sidebar, text="⚙ Configuración", fg_color="transparent", 
            text_color="white", hover_color="#1e293b", border_width=1, border_color="#334155",
            command=self.toggle_settings
        )
        self.settings_sidebar_btn.pack(fill="x", padx=15, pady=10)

        self.review_sidebar_btn = ctk.CTkButton(
            self.sidebar, text="🧾 Revisión", fg_color="transparent",
            text_color="white", hover_color="#1e293b", border_width=1, border_color="#334155",
            command=self.toggle_revision
        )
        self.review_sidebar_btn.pack(fill="x", padx=15, pady=10)

        # --- Cabecera Superior (contenido; el grid ya se aplicó arriba) ---
        ctk.CTkLabel(
            self.top_bar, text="Editor / Chat", font=("Segoe UI", 16, "bold"), 
            text_color="white"
        ).grid(row=0, column=0, sticky="w", padx=20)

        self.top_review_btn = ctk.CTkButton(
            self.top_bar, text="Mostrar Revisión", width=160, fg_color="#2563eb",
            hover_color="#1d4ed8", corner_radius=8, command=self.toggle_revision
        )
        self.top_review_btn.grid(row=0, column=1, sticky="e", padx=20)

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


    def _on_response(self, response):
        self.footer_bar.set_busy(False)
        self._append_chat(f"[IA]: {response}")

    def _on_response_error(self, error):
        self.footer_bar.set_busy(False)
        self._append_chat(f"[ERROR]: {error}")

    def _append_chat(self, line):
        self.editor_area.chat_text.config(state="normal")
        self.editor_area.chat_text.insert("end", line + "\n\n", "diff-unchanged")
        self.editor_area.chat_text.config(state="disabled")
        self.editor_area.chat_text.see("end")

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

        self._append_chat(f"[Tú]: {text}")
        self.footer_bar.entry.delete(0, "end")

        # La llamada real tarda 5-23s (medido contra OmniRoute). Si la llamo
        # directo, Tkinter se congela ese tiempo. Va en un hilo aparte y
        # vuelve al hilo principal por after(), que es el unico seguro.
        self.footer_bar.set_busy(True)
        threading.Thread(
            target=self._ask_worker, args=(text, archivos), daemon=True
        ).start()

    def _ask_worker(self, text, archivos):
        """Hilo secundario: arma el contexto y llama a la IA. NO toca widgets.

        build_file_context() puede leer cientos de KB y tardar, por eso va
        aca y no en el hilo de la interfaz.
        """
        try:
            contexto = build_file_context(archivos)
            response = get_ai_response(text, file_context=contexto or None)
            self.after(0, self._on_response, response)
        except Exception as e:
            self.after(0, self._on_response_error, str(e))

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
