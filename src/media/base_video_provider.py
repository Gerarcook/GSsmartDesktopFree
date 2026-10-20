"""
BaseVideoProvider: contrato para motores de VIDEO.

Por que NO es un BaseProvider:
    El contrato de BaseProvider (src/providers/base_provider.py) es de chat:
    devuelve texto y hace streaming de texto. Un motor de video toma una
    imagen y devuelve un archivo .mp4 despues de una espera de minutos.
    Meterlo en PROVIDERS romperia diagnose_providers(), que llama
    router.generate("di ok") sobre cada provider: sin imagen no hay nada que
    renderizar y el provider seeria marcado como roto en el boton
    "Testear conexiones". Por eso esto va aparte, en VIDEO_PROVIDERS.

Lo que si comparte con el resto del proyecto:
    - httpx async (mismo cliente que los providers de chat)
    - is_available() con request real, por la misma razon que
      diagnose_providers(): "configurado" no es "funciona". Una key valida
      con la cuenta sin creditos responde 200 en /models y 429 al renderizar.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class VideoResult:
    """Resultado de un render.

    Se separa url (remoto) de path (local) porque un provider puede no
    descargar el archivo: devuelve solo la URL y la GUI la abre con el
    navegador. download() se usa cuando querés el archivo en disco.
    """

    url: str = ""
    path: str = ""
    seed: Optional[int] = None
    duration: float = 0.0
    provider: str = ""
    credits_remaining: Optional[int] = None
    meta: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return bool(self.url or self.path)

    async def download(self, client, dest: str) -> str:
        """Descarga la URL a dest. Necesita el cliente httpx abierto."""
        if not self.url:
            raise ValueError("Este resultado no tiene URL para descargar")
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        resp = await client.get(self.url, timeout=300.0)
        resp.raise_for_status()
        Path(dest).write_bytes(resp.content)
        self.path = dest
        return dest


class BaseVideoProvider(ABC):
    def __init__(self, api_key: str = "", base_url: str = "", model: str = ""):
        self.api_key = api_key or ""
        self.base_url = base_url.rstrip("/")
        self.model = model or ""

    # ------------------------------------------------------------------
    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre corto para mostrar en la UI."""
        ...

    # ------------------------------------------------------------------
    @abstractmethod
    async def render(
        self,
        prompt: str,
        *,
        image: Optional[str] = None,
        duration: Optional[float] = None,
        seed: Optional[int] = None,
        **kwargs: Any,
    ) -> VideoResult:
        """Genera un video.

        Args:
            prompt:      descripcion del MOVIMIENTO (la imagen ya aporta la
                         composicion). Para text-to-video, la escena completa.
            image:       ruta local o URL publica del keyframe. None = text-to-video.
            duration:    segundos. Depende del motor (ver MODEL_INFO).
            seed:        para reproducibilidad. None = aleatorio.
        """
        ...

    # ------------------------------------------------------------------
    @abstractmethod
    async def is_available(self) -> tuple[bool, str]:
        """Prueba real de que el motor anda. Devuelve (ok, detalle).

        NO confies en que haya config: hace una request de verdad. Es el
        equivalente a diagnose_providers() pero para video.
        """
        ...

    # ------------------------------------------------------------------
    @abstractmethod
    def supports_image(self) -> bool:
        """True si acepta keyframe (image-to-video). False = solo texto."""
        ...

    async def close(self) -> None:
        """Libera recursos. Por defecto no hay nada que liberar."""
        return None