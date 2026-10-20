"""
Persistencia de chats en disco (JSON).

Cada sesion es un archivo en sessions/<id>.json. No guarda secretos:
solo mensajes user/assistant y metadata liviana.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
SESSIONS_DIR = _ROOT / "sessions"


def _ensure_dir() -> Path:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_DIR


def new_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]


def _path(session_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", session_id)[:80]
    return _ensure_dir() / f"{safe}.json"


def title_from_messages(messages: List[Dict[str, str]], fallback: str = "Nueva sesion") -> str:
    for m in messages:
        if m.get("role") == "user" and (m.get("content") or "").strip():
            t = " ".join(m["content"].split())
            return (t[:48] + "…") if len(t) > 48 else t
    return fallback


def save(
    session_id: str,
    messages: List[Dict[str, str]],
    *,
    provider: Optional[str] = None,
    title: Optional[str] = None,
) -> str:
    """Guarda y devuelve el id. Sobrescribe si ya existe."""
    sid = session_id or new_id()
    payload: Dict[str, Any] = {
        "id": sid,
        "title": title or title_from_messages(messages),
        "provider": provider,
        "updated": time.time(),
        "messages": [
            {"role": m.get("role"), "content": m.get("content") or ""}
            for m in messages
            if m.get("role") in ("user", "assistant") and (m.get("content") or "").strip()
        ],
    }
    # created: preserve if updating
    p = _path(sid)
    if p.exists():
        try:
            old = json.loads(p.read_text(encoding="utf-8"))
            payload["created"] = old.get("created", payload["updated"])
        except (OSError, json.JSONDecodeError):
            payload["created"] = payload["updated"]
    else:
        payload["created"] = payload["updated"]

    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return sid


def load(session_id: str) -> Optional[Dict[str, Any]]:
    p = _path(session_id)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def list_sessions(limit: int = 40) -> List[Dict[str, Any]]:
    """Mas recientes primero. Solo metadata (sin messages completos en listado ligero)."""
    _ensure_dir()
    rows: List[Dict[str, Any]] = []
    for p in SESSIONS_DIR.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        rows.append({
            "id": data.get("id") or p.stem,
            "title": data.get("title") or p.stem,
            "provider": data.get("provider"),
            "updated": data.get("updated") or p.stat().st_mtime,
            "n_messages": len(data.get("messages") or []),
        })
    rows.sort(key=lambda r: r.get("updated") or 0, reverse=True)
    return rows[:limit]


def delete(session_id: str) -> bool:
    p = _path(session_id)
    try:
        if p.exists():
            p.unlink()
            return True
    except OSError:
        pass
    return False
