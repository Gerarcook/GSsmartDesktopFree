# GSsmart Desktop Free

App de escritorio para conectarse a **cualquier proveedor de IA**,
tanto oficiales (OpenRouter, OpenAI, etc.) como personalizados
(endpoints locales tipo LM Studio, Ollama, vLLM o cualquier API
compatible con el formato OpenAI).

## Diseño visual (cyberpunk glassmorphism)

UI premium inspirada en el mockup conceptual **GSsmart Desktop AI**:

| Zona | Elementos |
|------|-----------|
| **Header** | Marca `GSsmart Desktop AI` + `GSsmartDesing`, pastilla **Búsqueda Web**, waveform de voz |
| **Rail izquierdo** | Módulo flotante: **Proyectos**, **Configuración**, **Ayuda** |
| **Centro** | Panel de chat holográfico con burbujas (OPERADOR / GSSMART) |
| **Rail derecho** | Franja estrecha dual-pane (`⧉`) que expande área de trabajo |
| **Footer** | Input `Escribe tu mensaje aquí...`, **➤**, **Adjuntar**, **Modelos**, **Audio** |
| **Hint** | `Sin adjuntos · Intro para enviar` |

**Tokens** (`src/ui/theme.py`):

- Fondo void `#02060F`, paneles glass `#061018`
- Acento neón cian **`#00E5FF`** (bordes, CTA, glow)
- Radios: panel 18 · field 12 · pill 50
- Glass panels: `border_width=2`, `border_color=border_glow`

Ejecutar la GUI principal:

```bash
python gui_main.py
```

HUD cyberpunk alternativo (telemetría):

```bash
python gui_cyberpunk.py
```

## Estructura

```
GSsmartDesktopFree/
├── gui_main.py                  # GUI principal  <-- corré esta
├── gui_cyberpunk.py             # HUD opcional (telemetría)
├── main.py                      # CLI de prueba
├── requirements.txt
├── .env.example
├── sessions/                    # Chats guardados (local, gitignored)
├── tests/
├── legacy/                      # GUIs viejas, NO son producto
└── src/
    ├── core/
    │   ├── config.py            # Registro de proveedores + apply en caliente
    │   ├── router.py            # Router + streaming
    │   ├── session.py           # Historial en memoria (OpenAI format)
    │   ├── sessions_store.py    # Persistencia de chats en disco
    │   ├── prefs.py             # Preferencias UI (proveedor activo, sesión)
    │   ├── model_catalog.py     # Catálogo + set_env_var (.env)
    │   └── file_context.py      # Adjuntos → texto para el prompt
    ├── providers/
    └── ui/
        ├── theme.py             # Tokens cyberpunk glassmorphism
        └── bubbles.py           # Burbujas OPERADOR / GSSMART
```

## Cómo usar

```bash
cp .env.example .env   # o editar keys desde Configuración en la app
pip install -r requirements.txt
python gui_main.py
```

- **PROV** (arriba): elige proveedor.
- **Configuración** (sidebar): edita `base_url`, `api_key` y `model` → se guardan en `.env` y aplican en caliente.
- **Guardar / Cargar sesión**: chats en `sessions/`.
- **Ver modelos**: catálogo en vivo del proveedor.

## Tests

```bash
python tests/run_all.py
```

El smoke test (`test_smoke_gui.py`) **instancia** las interfaces. Eso detecta
bugs que `py_compile` no ve: los callbacks se resuelven en `__init__`, así que
un método faltante solo explota al arrancar la app.

## Dos cosas que conviene saber

**El streaming no es opcional.** Los gateways con cola de rate-limit cortan
la respuesta completa si no entra en la ventana (HTTP 504). Medido contra
OmniRoute: no-streaming da 504 en el 100% de los intentos, streaming da 200
con contenido en el 100%. Por eso `router.generate()` delega en
`generate_stream()`.

**Los adjuntos viajan como texto, no como rutas.** Los endpoints
OpenAI-compatible no leen tu disco: `file_context.py` lee el contenido y lo
inyecta en el prompt, con límites por archivo y total.

## Proveedores

Los proveedores se registran en `src/core/config.py`. Para agregar uno:
escribir su bloque con `api_key`, `base_url` y `model` leídos del `.env`.

| Proveedor | Estado |
|---|---|
| OmniRoute | Proxy local. Con cuenta gratuita: 20-226s y a veces vacío. |
| Kimi | API key propia (sin proxy). **Requiere saldo.** |
| Local (LM Studio) | Sin key, sin saldo. La única vía independiente. |
| OpenRouter | Plan gratuito con límites diarios. |
| OpenAI | Requiere key real de OpenAI. |

### Elegir modelo

El botón **"Ver modelos"** consulta el catálogo en vivo. No hardcodees un
modelo en el `.env`: OmniRoute rota sus modelos gratuitos y uno que
funciona hoy puede dar 404 mañana.

### "Configurado" no es "funciona"

Una API key puede ser válida y la cuenta estar sin saldo. Por eso el botón
**"Testear conexiones"** en la barra lateral hace una request real por
proveedor y dice quién responde de verdad.

```python
from src.core import config

config.provider_report()          # solo config, sin red
await config.diagnose_providers()  # prueba real (cuesta 1 request c/u)
```

## Instalacion

```bash
cd GSsmartDesktopFree
pip install -r requirements.txt
copy .env.example .env   # y completa tus claves
python gui_main.py
```

## Agregar un proveedor nuevo

1. Creá `src/providers/mi_proveedor.py` con una clase que herede de `BaseProvider`.
2. Implementá `generate()`, `generate_stream()` y `get_available_models()`.
3. Registralo en `src/core/config.py` dentro del dict `PROVIDERS`.

Listo. La app lo detecta y lo usa sin tocar nada más.

## Proveedores compatibles (formato OpenAI)

| Proveedor            | Base URL                          |
|----------------------|-----------------------------------|
| OpenRouter           | https://openrouter.ai/api/v1      |
| OpenAI               | https://api.openai.com/v1         |
| LM Studio (local)    | http://localhost:1234/v1          |
| Ollama (local)       | http://localhost:11434/v1         |
| vLLM (local)         | http://localhost:8000/v1          |
| Groq                 | https://api.groq.com/openai/v1    |
| Mistral              | https://api.mistral.ai/v1         |
| Together             | https://api.together.xyz/v1       |
| Fireworks            | https://api.fireworks.ai/inference/v1 |

Si tu proveedor no es compatible con OpenAI (Anthropic, Google, etc),
creá su clase propia heredando de `BaseProvider` — la arquitectura
está pensada exactamente para eso.
