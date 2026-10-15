# GSsmart Desktop Free

App de escritorio para conectarse a **cualquier proveedor de IA**,
tanto oficiales (OpenRouter, OpenAI, etc.) como personalizados
(endpoints locales tipo LM Studio, Ollama, vLLM o cualquier API
compatible con el formato OpenAI).

## Estructura

```
GSsmartDesktopFree/
├── main.py                      # Punto de entrada (CLI de prueba)
├── requirements.txt             # Dependencias
├── .env.example                 # Plantilla de configuracion
├── .gitignore
└── src/
    ├── core/
    │   ├── config.py            # Registro central de proveedores
    │   └── router.py            # Router con fallback automatico
    └── providers/
        ├── base_provider.py     # Contrato que cumplen todos
        ├── openrouter_provider.py  # OpenRouter (oficial)
        └── custom_provider.py   # Cualquier API compatible OpenAI
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
