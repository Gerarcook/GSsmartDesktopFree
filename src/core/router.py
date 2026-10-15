"""
ProviderRouter: gestiona todos los proveedores registrados.

Tareas:
  - Crear instancias de cada proveedor con su config.
  - Enrutar una solicitud al proveedor que el usuario elija.
  - Fallback automatico: si el proveedor principal falla,
    probar con los demas en orden hasta encontrar uno que responda.
"""

import asyncio
from typing import Any, AsyncIterator, List, Optional

from src.providers.base_provider import BaseProvider
from src.core import config


class ProviderRouter:
    def __init__(self) -> None:
        self._instances: dict = {}
        self._load_providers()

    # ------------------------------------------------------------------
    def _load_providers(self) -> None:
        """Instancia todos los proveedores registrados en config.py que tengan base_url configurado."""
        for name, cfg in config.PROVIDERS.items():
            base_url = cfg.get("base_url", "")
            # Saltamos proveedores sin base_url (evita crear instancias inútiles)
            if not base_url or base_url.strip() == "":
                print(f"[Config] Proveedor '{name}' omitido: base_url vacío.")
                continue
            provider_class = cfg["class"]
            self._instances[name] = provider_class(
                api_key=cfg.get("api_key", ""),
                base_url=base_url,
                model=cfg.get("model", ""),
            )

    # ------------------------------------------------------------------
    @property
    def providers(self) -> List[str]:
        return list(self._instances.keys())

    # ------------------------------------------------------------------
    def get(self, name: str) -> BaseProvider:
        if name not in self._instances:
            raise KeyError(f"Proveedor '{name}' no disponible. Usa: {self.providers}")
        return self._instances[name]

    # ------------------------------------------------------------------
    async def generate(
        self,
        prompt: str,
        provider: Optional[str] = None,
        system_prompt: str = "You are a helpful assistant.",
        fallback: bool = True,
        **kwargs: Any,
    ) -> str:
        """
        Envia el prompt. Si provider es None, prueba con todos
        los proveedores hasta que uno responda (fallback automatico).
        """
        targets = [provider] if provider else self.providers
        last_error: Optional[Exception] = None

        for name in targets:
            try:
                prov = self.get(name)
                return await prov.generate(prompt, system_prompt=system_prompt, **kwargs)
            except Exception as e:
                last_error = e
                print(f"[{name}] fallo: {e}")

        if fallback and not provider:
            for name in self.providers:
                try:
                    prov = self.get(name)
                    return await prov.generate(prompt, system_prompt=system_prompt, **kwargs)
                except Exception as e:
                    last_error = e

        raise RuntimeError(f"Todos los proveedores fallaron. Ultimo error: {last_error}")

    # ------------------------------------------------------------------
    async def generate_stream(
        self,
        prompt: str,
        provider: Optional[str] = None,
        system_prompt: str = "You are a helpful assistant.",
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Igual que generate pero con streaming (va devolviendo texto por partes)."""
        name = provider or self.providers[0]
        prov = self.get(name)
        async for chunk in prov.generate_stream(prompt, system_prompt=system_prompt, **kwargs):
            yield chunk

    # ------------------------------------------------------------------
    async def close_all(self) -> None:
        for prov in self._instances.values():
            try:
                await prov.close()
            except Exception:
                pass

# ------------------------------------------------------------------
# Helper sincrono para la GUI / scripts simples.
# ProviderRouter.generate() es async, pero Tkinter necesita una funcion sync.
# ------------------------------------------------------------------
_sync_router = ProviderRouter()


def get_ai_response(text: str, provider: Optional[str] = None, **kwargs: Any) -> str:
    """Envia el texto al router y devuelve la respuesta como string."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        raise RuntimeError("No llames get_ai_response() desde un async. Usa ProviderRouter.generate().")

    return asyncio.run(_sync_router.generate(text, provider=provider, **kwargs))