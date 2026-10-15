"""
GSsmart Desktop - Interfaz Gráfica de Usuario (GUI)

Una ventana tipo chat moderna con:
- Selector de proveedor dropdown
- Área de historial de conversación
- Campo de entrada de prompts
- Integración con el ProviderRouter (múltiples proveedores)

Para correr: python gui.py
"""

import customtkinter as ctk
import asyncio
import threading
from typing import Optional, Callable

# Configuración de la ventana principal
ctk.set_appearance_mode("System")  # Modo: "System" (default), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Tema de colores

from src.core.router import ProviderRouter
from src.core.config import list_providers


class GSsmartApp(ctk.CTk):
    """
    Aplicación principal de GSsmart Desktop.
    Proporciona una interfaz gráfica para interactuar con proveedores de IA.
    """

    def __init__(self) -> None:
        super().__init__()

        # Título y geometría
        self.title("GSsmart Desktop - IA Multi-Provider")
        self.geometry("800x600")
        self.minsize(600, 400)

        # Inicializar router
        self.router = ProviderRouter()
        self.current_provider_name: Optional[str] = None

        # Cola para comunicación hilo-hilo (async -> GUI)
        self._queue: "asyncio.Queue" = asyncio.Queue()

        # --- Layout de la ventana ---
        self._setup_layout()

        # Cargar proveedores después de que la ventana esté lista
        self.after(200, self._load_providers_gui)

        # Bucle para procesar la cola de mensajes
        self._process_queue()

    # ------------------------------------------------------------------
    def _setup_layout(self) -> None:
        """Configura la disposición de los widgets."""
        # Frame principal con grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- Barra superior: selector y botones ---
        top_frame = ctk.CTkFrame(self, corner_radius=0)
        top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        top_frame.grid_columnconfigure(1, weight=1)

        # Etiqueta de proveedor
        self.label_provider = ctk.CTkLabel(top_frame, text="Proveedor:", anchor="w")
        self.label_provider.grid(row=0, column=0, padx=(0, 8), pady=8)

        # Dropdown de proveedores (será poblado después)
        self.combo_provider = ctk.CTkComboBox(top_frame, values=["Cargando..."], width=200)
        self.combo_provider.grid(row=0, column=1, padx=(0, 8), pady=8)
        self.combo_provider.set("Seleccionar proveedor")

        # Botón de conectar/desconectar
        self.btn_connect = ctk.CTkButton(top_frame, text="Conectar", command=self._toggle_provider, width=100)
        self.btn_connect.grid(row=0, column=2, padx=(0, 8), pady=8)

        # Indicador de estado
        self.status_label = ctk.CTkLabel(top_frame, text="Desconectado", text_color="gray")
        self.status_label.grid(row=0, column=3, padx=(0, 8), pady=8)

        # --- Área de conversación central ---
        self.chat_frame = ctk.CTkScrollableFrame(self, corner_radius=0)
        self.chat_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.chat_frame.grid_columnconfigure(0, weight=1)

        # Frame para los mensajes (se irán agregando aquí)
        self.messages_frame = ctk.CTkFrame(self.chat_frame, corner_radius=0)
        self.messages_frame.grid(row=0, column=0, sticky="nsew")
        self.messages_frame.grid_columnconfigure(0, weight=1)

        # --- Barra inferior: entrada de texto ---
        bottom_frame = ctk.CTkFrame(self, corner_radius=0)
        bottom_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        bottom_frame.grid_columnconfigure(0, weight=1)

        # Campo de entrada de prompt
        self.entry_prompt = ctk.CTkEntry(
            bottom_frame,
            placeholder_text="Escribir prompt...",
            height=40,
            font=("Segoe UI", 13)
        )
        self.entry_prompt.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.entry_prompt.bind("<Return>", self._on_enter_key)

        # Botón de enviar
        self.btn_send = ctk.CTkButton(
            bottom_frame,
            text="Enviar",
            height=40,
            command=self._on_send_click,
            width=80
        )
        self.btn_send.grid(row=0, column=1, padx=(0, 0))

        # Bind Enter también al botón (opcional, pero bueno)
        self.entry_prompt.bind("<Shift-Return>", self._on_shift_enter)

    # ------------------------------------------------------------------
    def _load_providers_gui(self) -> None:
        """Carga la lista de proveedores disponibles en el dropdown."""
        providers = list_providers()
        self.combo_provider.configure(values=providers)
        if providers:
            self.combo_provider.set(providers[0])
            self._on_provider_select(providers[0])

    # ------------------------------------------------------------------
    def _toggle_provider(self) -> None:
        """Alternar entre conectar/desconectar el proveedor actual."""
        if self.current_provider_name is None:
            # Intentar conectar el seleccionado
            selected = self.combo_provider.get()
            if selected and selected != "Seleccionar proveedor":
                self._connect_provider(selected)
        else:
            # Desconectar (cerrar instancias)
            self._disconnect_provider()

    # ------------------------------------------------------------------
    def _connect_provider(self, name: str) -> None:
        """Conectar y configurar un proveedor específico."""
        try:
            cfg = self.router.get(name)
            self.current_provider_name = name
            self.status_label.configure(text=f"Conectado: {name}", text_color="green")
            self.btn_connect.configure(text="Desconectar")
            self._add_system_message(f"Proveedor '{name}' activado (modelo: {cfg.model})")
        except Exception as e:
            self._show_error(f"Error al configurar proveedor: {e}")

    def _disconnect_provider(self) -> None:
        """Desconectar el proveedor actual."""
        self.router.close_all()
        self.current_provider_name = None
        self.status_label.configure(text="Desconectado", text_color="gray")
        self.btn_connect.configure(text="Conectar")
        self._add_system_message("Proveedor desconectado.")

    # ------------------------------------------------------------------
    def _on_provider_select(self, name: str) -> None:
        """Callback cuando el usuario selecciona un proveedor del dropdown."""
        self._connect_provider(name)

    # ------------------------------------------------------------------
    def _on_send_click(self) -> None:
        """Manejador del botón Enviar."""
        prompt = self.entry_prompt.get().strip()
        if not prompt:
            return
        self.entry_prompt.delete(0, "end")
        self._add_user_message(prompt)
        self._generate_response(prompt)

    # ------------------------------------------------------------------
    def _on_enter_key(self, event) -> None:
        """Presionar Enter para enviar (sin Shift)."""
        self._on_send_click()
        return "break"  # Evitar el newline automático

    def _on_shift_enter(self, event) -> None:
        """Shift+Enter para nuevo renglón (opcional)."""
        return None  # Permite newline

    # ------------------------------------------------------------------
    def _add_user_message(self, text: str) -> None:
        """Agrega un mensaje del usuario al historial (hilo principal)."""
        # Usamos un hilo seguro para actualizar GUI
        def _insert():
            frame = ctk.CTkFrame(self.messages_frame, fg_color="transparent")
            frame.grid(sticky="e", pady=2, padx=(20, 0))
            label = ctk.CTkLabel(
                frame,
                text=f"Tú: {text}",
                justify="left",
                anchor="w",
                wraplength=400
            )
            label.pack(anchor="w")
            # Forzar actualización y scroll
            self.messages_frame.update_idletasks()
            # Scroll al final
            self.chat_frame._parent_canvas.yview_moveto(1.0)

        self.after(0, _insert)

    def _add_system_message(self, text: str) -> None:
        """Agrega un mensaje del sistema (estado, errores)."""
        def _insert():
            frame = ctk.CTkFrame(self.messages_frame, fg_color="transparent")
            frame.grid(sticky="w", pady=2, padx=(20, 0))
            label = ctk.CTkLabel(
                frame,
                text=f"Sistema: {text}",
                text_color="gray",
                justify="left",
                anchor="w",
                wraplength=400
            )
            label.pack(anchor="w")
            self.messages_frame.update_idletasks()
            self.chat_frame._parent_canvas.yview_moveto(1.0)

        self.after(0, _insert)

    # ------------------------------------------------------------------
    async def _generate_response(self, prompt: str) -> None:
        """
        Genera una respuesta usando el proveedor actual.
        Ejecuta la llamada async y muestra el resultado.
        """
        if not self.current_provider_name:
            self._add_system_message("No hay proveedor seleccionado.")
            return

        try:
            prov = self.router.get(self.current_provider_name)
            # Mostrar indicador de "pensando..."
            self._add_system_message("Pensando...")
            # Generar respuesta (esto es async, pero usamos threading para no congelar GUI)
            response = await self.router.generate(
                prompt,
                provider=self.current_provider_name,
                system_prompt="You are a helpful assistant."
            )
            # Reemplazar "Pensando..." por la respuesta real
            self._replace_last_system_message(response)
        except Exception as e:
            self._add_system_message(f"Error: {str(e)[:100]}")

    def _replace_last_system_message(self, text: str) -> None:
        """Reemplaza el último mensaje 'Pensando...' por el texto real."""
        # Buscar el último frame de sistema y cambiar su label
        children = self.messages_frame.winfo_children()
        for child in reversed(children):
            for widget in child.winfo_children():
                if isinstance(widget, ctk.CTkLabel) and widget.cget("text").startswith("Sistema: Pensando"):
                    widget.configure(text=f"IA: {text}")
                    return
        # Si no encontró, agregamos uno nuevo (por si acaso)
        self._add_system_message(text)

    # ------------------------------------------------------------------
    def _show_error(self, message: str) -> None:
        """Muestra un mensaje de error en la interfaz."""
        self._add_system_message(f"⚠ Error: {message}")

    # ------------------------------------------------------------------
    def _process_queue(self) -> None:
        """
        Bucle principal para procesar la cola async->GUI.
        Se llama a sí mismo cada 100ms.
        """
        try:
            # Intentar obtener sin bloquear
            while True:
                item = self._queue.get_nowait()
                # Los items pueden ser: ('update_status', name) o ('message', text, tipo)
                if item[0] == "update_status":
                    _, name = item
                    self._update_status_name(name)
                elif item[0] == "message":
                    _, text, msg_type = item
                    if msg_type == "user":
                        self._add_user_message(text)
                    elif msg_type == "system":
                        self._add_system_message(text)
        except Exception:
            pass  # Cola vacía, está bien

        # Volver a programar después de 100ms
        self.after(100, self._process_queue)

    def _update_status_name(self, name: str) -> None:
        """Actualiza la etiqueta de estado en la barra superior."""
        self.status_label.configure(text=f"Conectado: {name}", text_color="green")

    # ------------------------------------------------------------------
    def _generate_response_thread(self, prompt: str) -> None:
        """
        Ejecuta la generación de respuesta en un hilo separado
        para no congelar la interfaz gráfica.
        """
        try:
            # Creamos un nuevo event loop para este hilo
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._generate_response(prompt))
            finally:
                loop.close()
        except Exception as e:
            self._show_error(f"Error en hilo: {e}")

    # ------------------------------------------------------------------
    def _on_shift_enter(self, event) -> None:
        """Maneja Shift+Enter para insertar nuevo renglón en el entry."""
        self.entry_prompt.insert("end", "\n")


# ----------------------------------------------------------------------
def main() -> None:
    """Punto de entrada de la aplicación GUI."""
    app = GSsmartApp()
    app.mainloop()


if __name__ == "__main__":
    main()