"""
ProviderRouter: gestiona todos los proveedores registrados.

Tareas:
  - Crear instancias de cada proveedor con su config.
  - Enrutar una solicitud al proveedor que el usuario elija.
  - Fallback automatico: si el proveedor principal falla,
    probar con los demas en orden hasta encontrar uno que responda.
"""

import asyncio
import sys
from typing import Any, AsyncIterator, List, Optional, Tuple

from src.providers.base_provider import BaseProvider
from src.core import config

# Los prints de diagnostico de este modulo necesitan UTF-8. La consola de
# Windows usa cp1252 y un proveedor que responda con un emoji (hola 👋)
# reventaba con UnicodeEncodeError. errors="replace" degrada en vez de morir.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        # Sin reconfigure: puede ser un stream que no lo soporta (pytest,
        # notebooks, o stdout redirigido en Windows viejo).
        pass


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
    @staticmethod
    def _compose_prompt(prompt: str, file_context: Optional[str]) -> str:
        """Pega el contexto de adjuntos delante del prompt del usuario.

        Se hace ACA y no en el payload porque los endpoints OpenAI-compatible
        no aceptan un campo "files": solo leen `messages`. El contenido tiene
        que viajar dentro del mensaje para que el modelo lo vea.
        """
        if not file_context:
            return prompt
        return f"{file_context}\n\nPREGUNTA DEL USUARIO:\n{prompt}"

    # ------------------------------------------------------------------
    async def generate(
        self,
        prompt: str,
        provider: Optional[str] = None,
        system_prompt: str = "You are a helpful assistant.",
        fallback: bool = True,
        file_context: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Devuelve la respuesta completa como string.

        IMPORTANTE: no hace una llamada no-streaming. Reutiliza generate_stream()
        y junta los trozos. Motivo (medido contra OmniRoute, oct-2026):

            no-streaming  -> 504 en el 100% de los intentos (~33s)
            streaming     -> 200 con contenido real en el 100% (5-23s)

        Los gateways con cola de rate-limit (maxWaitMs) cortan la respuesta
        completa si no entra en la ventana. El streaming entrega el primer
        chunk antes de que venza ese reloj, asi que esquiva el limite.

        Por eso hay UN solo camino de codigo: si divergen, el fix se aplica
        una vez y no queda un path viejo queSIGA dando 504.
        """
        targets = [provider] if provider else self.providers
        if not targets:
            raise RuntimeError("No hay proveedores configurados.")

        composed = self._compose_prompt(prompt, file_context)
        last_error: Optional[Exception] = None
        for name in targets:
            try:
                chunks: List[str] = []
                async for kind, piece in self.generate_stream(
                    composed, provider=name, system_prompt=system_prompt, **kwargs
                ):
                    # El razonamiento no va a la respuesta: se muestra aparte
                    # en la UI pero el usuario lee solo el content.
                    if kind == "content":
                        chunks.append(piece)
                text = "".join(chunks).strip()
                if text:
                    return text
                # 200 sin contenido: el gateway respondio vacio. No es un exito.
                last_error = RuntimeError(f"[{name}] respondio 200 pero sin contenido.")
                print(f"[{name}] {last_error}")
            except Exception as e:
                last_error = e
                print(f"[{name}] fallo: {e}")

        raise RuntimeError(
            f"Todos los proveedores fallaron ({len(targets)} intentados). "
            f"Ultimo error: {last_error}"
        )

    # ------------------------------------------------------------------
    async def generate_stream(
        self,
        prompt: str,
        provider: Optional[str] = None,
        system_prompt: str = "You are a helpful assistant.",
        file_context: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncIterator[Tuple[str, str]]:
        """Igual que generate pero con streaming.

        Yield de tuplas (tipo, texto): ("content", ...) o ("reasoning", ...).
        Ver BaseProvider.generate_stream() para el detalle de por que se
        separan en vez de mezclarse.
        """
        if not provider and not self.providers:
            raise RuntimeError("No hay proveedores configurados.")
        name = provider or self.providers[0]
        prov = self.get(name)
        composed = self._compose_prompt(prompt, file_context)
        async for chunk in prov.generate_stream(composed, system_prompt=system_prompt, **kwargs):
            yield chunk

    # ------------------------------------------------------------------
    async def close_all(self) -> None:
        for prov in self._instances.values():
            try:
                await prov.close()
            except Exception:
                pass

# ------------------------------------------------------------------
# Helpers para la GUI.
#
# OJO con get_ai_response(): es SINCRONICO, o sea BLOQUEA el hilo principal
# de Tkinter. Con la latencia real de estos gateways (5-23s medidos) eso
# congela la ventana entera. Para una GUI usá `ask_async()` en un hilo, o
# mejor, consumí `generate_stream()` que va mostrando el texto mientras llega.
# ------------------------------------------------------------------
def get_ai_response(
    text: str,
    provider: Optional[str] = None,
    file_context: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """Envia el texto al router y devuelve la respuesta completa.

    Solo para scripts/CLI. En una GUI bloquea el hilo principal: usá ask_async().

    file_context: texto ya construido con build_file_context(), NO rutas.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError(
            "get_ai_response() es sync y no se puede llamar desde un async. "
            "Usá ProviderRouter.generate() o ask_async()."
        )

    async def _run() -> str:
        router = ProviderRouter()
        try:
            return await router.generate(
                text, provider=provider, file_context=file_context, **kwargs
            )
        finally:
            await router.close_all()

    return asyncio.run(_run())


async def ask_async(
    text: str,
    provider: Optional[str] = None,
    file_context: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """Igual que get_ai_response() pero awaitable.

    Para backends de GUI: await ask_async(...) desde el hilo de asyncio.
    """
    router = ProviderRouter()
    try:
        return await router.generate(
            text, provider=provider, file_context=file_context, **kwargs
        )
    finally:
        await router.close_all()
