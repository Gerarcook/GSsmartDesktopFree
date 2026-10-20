"""
BytePlusProvider: video con Seedance via BytePlus ModelArk.

POR QUE ESTE Y NO OTRO
    Los otros tres proveedores que probamos hoy estaban caidos o sin cuota:
    - OmniRoute veo-free/seedance: 600s sin responder
    - AI Horde (imagen): 503, sin workers
    - Space de Wan2.2 en HF: acepta el job y nunca entrega
    JSON2Video funciona pero cobra ~204 creditos por un render de 3s, asi
    que no renderea nada con el saldo actual.

    ModelArk da 500.000 tokens gratis por modelo. A ~247K tokens por clip de
    5s a 1080p (referencia de la doc oficial) son ~2 clips, o ~4 en 720p.

DIFERENCIA CON LOS OTROS
    Seedance factura por TOKENS, no por creditos ni por segundos. El costo
    depende de resolucion y duracion, y hay que Mirar el campo `usage` de
    la respuesta para saber cuanto salio. Un provider que no lo reporta es
    una caja negra: es exactamente el problema quenous paso con JSON2Video,
    donde un render de 3s costo 204 creditos sin avisar.

API (docs oficiales de ModelArk)
    POST /api/v3/contents/generations/tasks
    GET  /api/v3/contents/generations/tasks/{id}
    Auth: Authorization: Bearer $ARK_API_KEY
"""

import asyncio
from typing import Any, Optional

import httpx

from src.media.base_video_provider import BaseVideoProvider, VideoResult


#: Tokens de referencia por segundo de video, segun la documentacion.
#: Solo para mostrar un estimado ANTES de renderizar. El costo real viene
#: en el campo `usage` de la respuesta y se guarda en VideoResult.meta.
TOKENS_POR_SEGUNDO_720P = 24_000   # ~110K por clip de 5s, medido en logs


class BytePlusProvider(BaseVideoProvider):
    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://ark.ap-southeast.bytepluses.com/api/v3",
        model: str = "seedance-1-0-pro-250528",
    ):
        super().__init__(api_key=api_key, base_url=base_url, model=model)
        # Generar video tarda minutos. El timeout de cliente tiene que ser
        # holgado o la conexion se corta en el peor momento.
        self.client = httpx.AsyncClient(timeout=120.0)

    @property
    def name(self) -> str:
        return "BytePlus Seedance"

    def supports_image(self) -> bool:
        """Seedance acepta imagen como keyframe (image-to-video)."""
        return True

    # ------------------------------------------------------------------
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    # ------------------------------------------------------------------
    @staticmethod
    def estimar_tokens(duration: float, resolution: str = "720p") -> int:
        """Estimacion previa. Es una aproximacion, NO el precio final.

        Sirve para que la UI muestre "esto va a salir ~72.000 tokens" antes
        de que el usuarioRenderice. El dato exacto viene en la respuesta.
        """
        factor = {"480p": 0.45, "720p": 1.0, "1080p": 2.25}.get(resolution, 1.0)
        return int(duration * TOKENS_POR_SEGUNDO_720P * factor)

    # ------------------------------------------------------------------
    async def render(
        self,
        prompt: str,
        *,
        image: Optional[str] = None,
        duration: Optional[float] = None,
        seed: Optional[int] = None,
        **kwargs: Any,
    ) -> VideoResult:
        dur = int(duration or 5)
        if not 4 <= dur <= 15:
            raise ValueError(f"Seedance acepta entre 4 y 15 segundos; pediste {dur}")

        model = kwargs.pop("model", None) or self.model
        resolution = kwargs.pop("resolution", "720p")
        generate_audio = bool(kwargs.pop("generate_audio", False))

        content: list[dict] = [{"type": "text", "text": prompt}]
        if image:
            # Seedance NO lee tu disco: la imagen tiene que ser una URL
            # publica. Mismo criterio que file_context.py con los adjuntos.
            if not image.startswith(("http://", "https://")):
                raise ValueError(
                    "Seedance necesita la imagen como URL publica, no como ruta "
                    "local. Subila primero (JSON2VideoProvider.upload_image o "
                    "cualquier hosting)."
                )
            content.append({"type": "image_url", "image_url": {"url": image}})

        payload: dict = {
            "model": model,
            "content": content,
            "ratio": kwargs.pop("ratio", "adaptive"),
            "duration": dur,
            "generate_audio": generate_audio,
            "watermark": kwargs.pop("watermark", True),
        }
        if resolution != "adaptive":
            payload["resolution"] = resolution
        if seed is not None:
            payload["seed"] = seed

        resp = await self.client.post(
            f"{self.base_url}/contents/generations/tasks", json=payload, headers=self._headers()
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"ModelArk rechazo el render: HTTP {resp.status_code} {resp.text[:300]}")
        task_id = (resp.json() or {}).get("id")
        if not task_id:
            raise RuntimeError(f"Respuesta inesperada: {resp.text[:200]}")

        return await self._await_task(task_id, dur)

    # ------------------------------------------------------------------
    async def _await_task(self, task_id: str, dur: int) -> VideoResult:
        """El render es asincrono: queued -> running -> succeeded/failed.

        Techo de 25 min. Seedance en hora pico puede tardar bastante.
        """
        for _ in range(300):          # 300 x 5s = 25 min
            await asyncio.sleep(5)
            r = await self.client.get(
                f"{self.base_url}/contents/generations/tasks/{task_id}", headers=self._headers()
            )
            if r.status_code >= 400:
                # Un 404 acá significa que el task expiro, no que la key
                # este mal: el distinto de errores importa.
                raise RuntimeError(f"El task {task_id} devolvio HTTP {r.status_code}")
            data = r.json() or {}
            status = data.get("status")
            if status == "succeeded":
                url = ((data.get("content") or {}).get("video_url")) or ""
                usage = data.get("usage") or {}
                return VideoResult(
                    url=url,
                    duration=float(data.get("duration") or dur),
                    provider=self.name,
                    seed=data.get("seed"),
                    credits_remaining=usage.get("total_tokens"),
                    meta={
                        "task_id": task_id,
                        "model": data.get("model"),
                        "resolution": data.get("resolution"),
                        "tokens_usados": usage.get("total_tokens"),
                    },
                )
            if status in ("failed", "cancelled"):
                raise RuntimeError(f"El render {status}: {data.get('error') or 'sin detalle'}")

        raise TimeoutError(f"El task {task_id} no termino en 25 min")

    # ------------------------------------------------------------------
    async def is_available(self) -> tuple[bool, str]:
        """Request real, de solo lectura: listar tasks no genera ni cobra."""
        if not self.api_key:
            return False, "falta ARK_API_KEY en .env"
        try:
            r = await self.client.get(
                f"{self.base_url}/contents/generations/tasks",
                headers=self._headers(),
                params={"filter.status": "succeeded"},
                timeout=30.0,
            )
        except Exception as e:
            return False, f"sin conexion: {type(e).__name__}"
        if r.status_code == 401:
            return False, "ARK_API_KEY invalida"
        if r.status_code == 403:
            return False, "la key no tiene permiso en este proyecto"
        if r.status_code >= 400:
            return False, f"HTTP {r.status_code}"
        return True, f"ok (modelo {self.model})"

    async def close(self) -> None:
        await self.client.aclose()