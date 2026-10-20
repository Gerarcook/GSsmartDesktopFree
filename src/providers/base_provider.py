"""
BaseProvider: contrato que TODO proveedor (oficial o personalizado) debe cumplir.

Para conectar un proveedor nuevo, solo tenes que:
  1. Crear una clase que herede de BaseProvider
  2. Implementar generate() y get_available_models()
  3. Registrarlo en src/core/config.py

No hace falta tocar nada mas del programa.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, AsyncIterator, Tuple
import json

import httpx


# ------------------------------------------------------------------
# Parser de streaming: compartido por TODOS los proveedores.
#
# Por que existe: los gateways (OmniRoute, vLLM, etc) meten en el mismo
# stream tres tipos de linea que no son texto:
#   1. keepalive  -> {"model":"keepalive","delta":{}}  (no debe contar como token)
#   2. usage      -> {"choices":[]}                    (rompia con IndexError)
#   3. basura     -> lineas que no son JSON
# Confiarlos al "try/except" de cada provider hacia errores silenciosos y
# metricas de latencia falsas, asi que se parsea una sola vez y aqui.
# ------------------------------------------------------------------

#: Modelo que usan los keepalive de los gateways.
KEEPALIVE_MODEL = "keepalive"

#: Marca interna que el stream va pensando todavia. NO es contenido: los
#: providers la filtran. Sirve para que la UI pueda decir "pensando..."
#: en vez de mostrar un chat congelado, y para no報告ar "vacio" cuando el
#: modelo solo emitio razonamiento.
REASONING_MARKER = "\x00__reasoning__"


def parse_stream_line(line: str) -> Optional[str]:
    """Convierte una linea SSE en texto, o en None si el stream termino.

    Devuelve:
        str    -> el fragmento de texto (puede ser "" si la linea no aporta nada)
        None   -> el stream finished (data: [DONE])
    """
    if not line or not line.startswith("data:"):
        return ""

    payload = line[5:].strip()
    if not payload:
        return ""
    if payload == "[DONE]":
        return None

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return ""

    # Keepalive: el gateway mantiene la conexion viva. No es una respuesta.
    if data.get("model") == KEEPALIVE_MODEL:
        return ""

    # Chunks de usage/heartbeat vienen con choices vacio. Antes: IndexError.
    choices = data.get("choices") or []
    if not choices:
        return ""

    delta = choices[0].get("delta") or {}

    # Los modelos de razonamiento (Qwen3, DeepSeek-R1, sensenova-6.8...)
    # emiten delta.reasoning ANTES de delta.content. Medido: hcnsec/auto
    # produce 1250 chars de reasoning y 0 de content si el presupuesto de
    # tokens se agota pensando. El usuario ve un chat congelado 40s.
    #
    # El marcador lleva el texto adentro para que la UI pueda mostrarlo
    # como "pensando..." en vez de tratar todo el stream como vacio.
    if not delta.get("content") and delta.get("reasoning"):
        return REASONING_MARKER + delta["reasoning"]

    return delta.get("content") or ""


def split_reasoning(piece: Optional[str]):
    """Separa un pedazo de stream en (razonamiento, contenido).

    Devuelve (razonamiento, contenido) y ambos pueden ser "".
    """
    if not piece:
        return "", ""
    if piece.startswith(REASONING_MARKER):
        return piece[len(REASONING_MARKER):], ""
    return "", piece


def is_reasoning(piece: Optional[str]) -> bool:
    """True si el pedazo es razonamiento, no texto para el usuario."""
    return bool(piece) and piece.startswith(REASONING_MARKER)


class BaseProvider(ABC):
    def __init__(self, api_key: str = "", base_url: str = "", model: str = ""):
        self.api_key = api_key or ""
        self.base_url = base_url.rstrip("/")
        self.model = model or ""
        self.client = httpx.AsyncClient(timeout=120.0)

    # ------------------------------------------------------------------
    @staticmethod
    def build_messages(
        prompt: str,
        system_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, str]]:
        """Arma la lista de mensajes: system + historial previo + mensaje actual.

        history usa el formato OpenAI: [{"role": "user"|"assistant", "content": "..."}].
        """
        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for item in history or []:
            role = item.get("role")
            content = item.get("content")
            if role in ("user", "assistant") and isinstance(content, str) and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": prompt})
        return messages

    # ------------------------------------------------------------------
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> str:
        """Envia un mensaje y devuelve la respuesta completa (modo no-stream)."""
        ...

    # ------------------------------------------------------------------
    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> AsyncIterator[Tuple[str, str]]:
        """Envia un mensaje y va devolviendo el texto por partes (streaming).

        Cada yield es una tupla (tipo, texto) donde tipo es:

            ("content",   "Hola")  -> texto de la respuesta, va al chat
            ("reasoning", "...")  -> el modelo pensando, va a la UI como
                                     indicador pero NUNCA a la respuesta

        Se separa porque los modelos de razonamiento emiten delta.reasoning
        antes de delta.content, y confundirlos dejaba al usuario mirando un
        chat congelado o una respuesta vacia.
        """
        ...

    # ------------------------------------------------------------------
    @abstractmethod
    async def get_available_models(self) -> List[str]:
        """Devuelve la lista de modelos disponibles en el proveedor."""
        ...

    # ------------------------------------------------------------------
    async def close(self) -> None:
        await self.client.aclose()
