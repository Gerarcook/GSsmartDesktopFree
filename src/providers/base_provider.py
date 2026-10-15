"""
BaseProvider: contrato que TODO proveedor (oficial o personalizado) debe cumplir.

Para conectar un proveedor nuevo, solo tenes que:
  1. Crear una clase que herede de BaseProvider
  2. Implementar generate() y get_available_models()
  3. Registrarlo en src/core/config.py

No hace falta tocar nada mas del programa.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, AsyncIterator
import httpx


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
    ) -> AsyncIterator[str]:
        """Envia un mensaje y va devolviendo el texto por partes (streaming)."""
        ...

    # ------------------------------------------------------------------
    @abstractmethod
    async def get_available_models(self) -> List[str]:
        """Devuelve la lista de modelos disponibles en el proveedor."""
        ...

    # ------------------------------------------------------------------
    async def close(self) -> None:
        await self.client.aclose()
