"""
Configuracion central: aca se registran TODOS los proveedores
disponibles y se leen las claves desde el archivo .env

Para agregar un proveedor nuevo:
  1. Importa su clase
  2. Agregalo al diccionario PROVIDERS con un nombre unico

El programa va a poder usarlo al instante, sin tocar nada mas.
"""

import os
from typing import Dict, Type
from pathlib import Path

from dotenv import load_dotenv

from src.providers.base_provider import BaseProvider
from src.providers.openrouter_provider import OpenRouterProvider
from src.providers.custom_provider import CustomProvider

# Forzamos que busque el .env en la RAIZ del proyecto (donde vive main.py),
# para que importe las variables aunque la app se corra desde otra carpeta.
_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_ROOT / ".env", override=False)
# DEBUG
import os as _os
print(f"[DEBUG] _ROOT = {_ROOT}")
print(f"[DEBUG] .env existe = {(_ROOT / '.env').exists()}")
print(f"[DEBUG] OMNIROUTE_BASE_URL = {_os.getenv('OMNIROUTE_BASE_URL')}")
print(f"[DEBUG] OMNIROUTE_API_KEY = {_os.getenv('OMNIROUTE_API_KEY')}")
print(f"[DEBUG] OPENAI_BASE_URL = {_os.getenv('OPENAI_BASE_URL')}")


# ------------------------------------------------------------------
# Registro de proveedores
# La clave es el nombre que se muestra en la app.
# El dict interno dice que clase usar y de donde sacar api_key,
# base_url y model.
# ------------------------------------------------------------------
PROVIDERS: Dict[str, dict] = {
    "OmniRoute": {
        "class": OpenRouterProvider,
        "api_key": os.getenv("OMNIROUTE_API_KEY", ""),
        "base_url": os.getenv("OMNIROUTE_BASE_URL", "http://localhost:20128/v1"),
        "model": os.getenv("OMNIROUTE_MODEL", "auto/coding:free"),
    },
    "OpenAI": {
        "class": CustomProvider,
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    },
    "OpenRouter": {
        "class": OpenRouterProvider,
        "api_key": os.getenv("OPENROUTER_API_KEY", ""),
        "base_url": os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        "model": os.getenv("OPENROUTER_MODEL", "mistralai/mistral-7b-instruct:free"),
    },
    "Custom (compatible OpenAI)": {
        "class": CustomProvider,
        "api_key": os.getenv("CUSTOM_API_KEY", ""),
        "base_url": os.getenv("CUSTOM_BASE_URL", "http://localhost:1234/v1"),
        "model": os.getenv("CUSTOM_MODEL", "local-model"),
    },
}


def get_provider_class(name: str) -> Type[BaseProvider]:
    """Devuelve la clase del proveedor por nombre."""
    if name not in PROVIDERS:
        raise KeyError(f"Proveedor '{name}' no registrado. Disponibles: {list(PROVIDERS.keys())}")
    return PROVIDERS[name]["class"]


def get_provider_config(name: str) -> dict:
    """Devuelve la config completa (clase + credenciales) de un proveedor."""
    if name not in PROVIDERS:
        raise KeyError(f"Proveedor '{name}' no registrado. Disponibles: {list(PROVIDERS.keys())}")
    return PROVIDERS[name]


def list_providers() -> list:
    """Devuelve los nombres de todos los proveedores registrados."""
    return list(PROVIDERS.keys())
