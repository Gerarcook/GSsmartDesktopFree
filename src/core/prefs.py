"""
Preferencias de usuario (no secretos).

Los secretos viven en .env. Esto guarda solo elecciones de UI:
proveedor activo, etc. Archivo JSON en la raiz del repo.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
PREFS_PATH = _ROOT / ".gssmart_prefs.json"

_DEFAULTS: Dict[str, Any] = {
    "active_provider": None,  # None = primero configurado
}


def load() -> Dict[str, Any]:
    data = dict(_DEFAULTS)
    if not PREFS_PATH.exists():
        return data
    try:
        raw = json.loads(PREFS_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            data.update(raw)
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return data


def save(data: Dict[str, Any]) -> None:
    merged = dict(_DEFAULTS)
    merged.update(data)
    try:
        text = json.dumps(merged, ensure_ascii=False, indent=2) + chr(10)
        PREFS_PATH.write_text(text, encoding="utf-8")
    except OSError:
        pass


def get_active_provider() -> Optional[str]:
    val = load().get("active_provider")
    return val if isinstance(val, str) and val.strip() else None


def set_active_provider(name: Optional[str]) -> None:
    data = load()
    data["active_provider"] = name
    save(data)
