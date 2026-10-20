# GSsmart Desktop Free

App de escritorio para conectarse a **cualquier proveedor de IA**,
tanto oficiales (OpenRouter, OpenAI, etc.) como personalizados
(endpoints locales tipo LM Studio, Ollama, vLLM o cualquier API
compatible con el formato OpenAI).

## Estructura

```
GSsmartDesktopFree/
├── main.py                      # CLI de prueba
├── gui_main.py                  # GUI principal  <-- corré esta
├── gui_cyberpunk.py             # GUI alternativa con telemetría
├── requirements.txt
├── .env.example
├── .gitignore
├── tests/
│   ├── run_all.py               # Corre todos los tests
│   ├── test_stream_parser.py    # Parser de streaming (keepalive, choices vacio)
│   ├── test_file_context.py     # Archivos adjuntos (binarios, truncado)
│   ├── test_config.py           # Registro de proveedores
│   └── test_smoke_gui.py        # Instancia las GUIs (detecta callbacks rotos)
├── legacy/                      # Interfaces viejas, NO son producto
└── src/
    ├── core/
    │   ├── config.py            # Registro de proveedores (carga .env)
    │   ├── router.py            # Router con fallback + streaming
    │   └── file_context.py      # Lee adjuntos para mandarlos al prompt
    └── providers/
        ├── base_provider.py     # Contrato + parser de streaming compartido
        ├── openrouter_provider.py
        └── custom_provider.py   # Cualquier API compatible OpenAI
```

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
funciona hoy puede dar 404 mañana (medido: `cohere/north-mini-code:free`
funcionaba hace 21h y ya no está en el catálogo).

El catálogo tiene **3241 entradas** de las cuales ~1300 son chat usable. El
filtro descarta imágenes/audio/embeddings y colapsa las variantes de
razonamiento (`glm-5.3-flash`, `glm-5.3-flash-xhigh`, `glm-5.3-flash[1m]`
son el mismo modelo). Los de arriba son los que más conviene probar.

### "Configurado" no es "funciona"

Una API key puede ser válida y la cuenta estar sin saldo. Caso real
medido: la key de Kimi daba `GET /models` 200 pero `chat/completions` 429
(*"account suspended due to insufficient balance"*). Nada de eso se ve
desde la config.

Por eso el botón **"Testear conexiones"** en la barra lateral hace una
request real por proveedor y dice quién responde de verdad. También
disponible desde código:

```python
from src.core import config

config.provider_report()          # solo config, sin red
await config.diagnose_providers()  # prueba real (cuesta 1 request c/u)
```

## Instalacion

```bash
cd C:\Users\Administrator\Trabajo\GSsmartDesktopFree
pip install -r requirements.txt
copy .env.example .env   # y completa tus claves
python main.py
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
# GSsmartDesktopFree
