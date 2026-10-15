"""Diagnóstico de OMNIROUTE_API_KEY sin mostrar nunca su valor."""

import os
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent
load_dotenv(_ROOT / ".env", override=False)

key = os.getenv("OMNIROUTE_API_KEY") or ""
print(f"Definida: {bool(key)}")
print(f"Largo: {len(key)}")
print(f"Empieza con 'sk-': {key.startswith('sk-')}")
print(f"Tiene espacios: {' ' in key}")
print(f"Tiene saltos de línea: {chr(10) in key or chr(13) in key}")
