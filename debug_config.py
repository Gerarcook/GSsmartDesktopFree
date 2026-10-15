"""Muestra la configuración de proveedores enmascarando cualquier credencial."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.core import config  # noqa: E402

SECRET_HINTS = ("key", "token", "secret", "password")


def mask(name: str, value):
    if isinstance(value, str) and any(h in name.lower() for h in SECRET_HINTS):
        return f"<definida, {len(value)} caracteres>" if value else "<vacía>"
    if isinstance(value, type):
        return value.__name__
    return value


for name in config.list_providers():
    cfg = config.get_provider_config(name)
    print(f"{name}:")
    for field, value in cfg.items():
        print(f"  {field}: {mask(field, value)}")
