"""
JSON2VideoProvider: video via la API de JSON2Video.

Gratis hasta un limite (plan Free: 590 unidades de quota), despues cobra.
Cada motor tiene su costo por segundo:
    seedance-v1.5-pro   20 credits/seg   text-to-video
    wan-v2.5            30 credits/seg   image-to-video

Es el unico motor de los dos que se puede probar de punta a punta hoy: el
Space de Wan2.2 en HF estaba caido (devuelve event:error con data:null).

Endpoints publicos (docs v2, unica base valida):
    POST /v2/movies            -> {"project": "..."}
    GET  /v2/movies?project=   -> estado hasta "done"
    POST /v2/media/file        -> sube un keyframe local y devuelve URL
Auth: header x-api-key.
"""

import asyncio
import mimetypes
from pathlib import Path
from typing import Any, Optional

import httpx

from src.media.base_video_provider import BaseVideoProvider, VideoResult


#: Modelos disponibles con su costo. La UI puede mostrar esto para no
#: prometer un video largo que se coma toda la quota.
MODEL_INFO = {
    "seedance-v1.5-pro": {"credits_per_second": 20, "image": False},
    "wan-v2.5": {"credits_per_second": 30, "image": True},
}


class JSON2VideoProvider(BaseVideoProvider):
    def __init__(self, api_key: str = "", base_url: str = "https://api.json2video.com/v2", model: str = "seedance-v1.5-pro"):
        super().__init__(api_key=api_key, base_url=base_url, model=model)
        self.client = httpx.AsyncClient(timeout=120.0)

    @property
    def name(self) -> str:
        return "JSON2Video"

    def supports_image(self) -> bool:
        return MODEL_INFO.get(self.model, {}).get("image", False)

    # ------------------------------------------------------------------
    def _headers(self) -> dict:
        return {"x-api-key": self.api_key, "Content-Type": "application/json"}

    # ------------------------------------------------------------------
    async def upload_image(self, path: str, folder: str = "video_inputs") -> str:
        """Sube un keyframe local y devuelve la URL publica.

        Necesario porque el endpoint de movies NO lee tu disco: el src del
        elemento de video tiene que ser una URL que JSON2Video pueda bajar.
        (Mismo criterio que file_context.py con los adjuntos de chat.)

        La subida es de DOS pasos, no multipart (medido oct-2026):
          1. POST /v2/media/file con {name, contentType, size, folder}
             -> devuelve un uploadUrl presignado de S3
          2. PUT de los bytes directo a ese uploadUrl
        Mandar multipart a /v2/media/file da 400 "name is required".

        El uploadUrl expira a los 120s, asi que el PUT va inmediato.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"No existe el keyframe: {path}")

        data = await asyncio.to_thread(p.read_bytes)
        ctype = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
        name = p.name

        # 409 = ya existe un archivo con ese nombre. Se resuelve con un
        # sufijo, no reintentando igual (reintentar el mismo nombre da 409
        # otra vez).
        for intento in range(3):
            resp = await self.client.post(
                f"{self.base_url}/media/file",
                headers={"x-api-key": self.api_key, "Content-Type": "application/json"},
                json={"name": name, "contentType": ctype, "size": len(data), "folder": folder},
                timeout=60.0,
            )
            if resp.status_code == 409 and intento < 2:
                stem, _, ext = name.rpartition(".")
                name = f"{stem}_{int(asyncio.get_event_loop().time())}{('.' + ext) if ext else ''}"
                continue
            break

        if resp.status_code >= 400:
            raise RuntimeError(f"La API rechazo la subida: HTTP {resp.status_code} {resp.text[:200]}")
        body = resp.json()
        upload_url = body.get("uploadUrl")
        file_url = body.get("fileUrl")
        if not upload_url or not file_url:
            raise RuntimeError(f"La API no devolvio uploadUrl/fileUrl: {body}")

        put = await self.client.put(
            upload_url, content=data, headers={"Content-Type": ctype}, timeout=300.0
        )
        if put.status_code >= 400:
            raise RuntimeError(f"El PUT a S3 fallo: HTTP {put.status_code} {put.text[:200]}")
        return file_url

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
        dur = float(duration or 5.0)
        if dur <= 0:
            raise ValueError("duration tiene que ser > 0")

        model = kwargs.pop("model", None) or self.model
        if model not in MODEL_INFO:
            raise ValueError(f"Modelo desconocido: {model}. Disponibles: {list(MODEL_INFO)}")

        # Text-to-video
        if not image:
            if MODEL_INFO[model]["image"]:
                raise ValueError(f"{model} es image-to-video: hace falta image=")
            element: dict = {
                "type": "video",
                "model": model,
                "prompt": prompt,
                "aspect-ratio": "horizontal",
                "resize": "cover",
                "duration": dur,
            }
        # Image-to-video
        else:
            if not MODEL_INFO[model]["image"]:
                raise ValueError(f"{model} es text-to-video: no acepta image=")
            src = image
            if not image.startswith(("http://", "https://")):
                src = await self.upload_image(image)
            # OJO: para image-to-video la imagen va en model-settings.image,
            # NO en src. Con src el proveedor responde 400:
            #   field "image" is required (medido oct-2026).
            element = {
                "type": "video",
                "model": model,
                "model-settings": {"image": src, "duration": dur},
                "prompt": prompt,
                "aspect-ratio": "horizontal",
                "resize": "cover",
                "duration": dur,
            }
        if seed is not None:
            element["model-settings"] = {**element.get("model-settings", {}), "seed": seed}

        movie = {
            "resolution": "full-hd",
            "scenes": [{"duration": dur, "background-color": "#000000", "elements": [element]}],
        }

        resp = await self.client.post(f"{self.base_url}/movies", json=movie, headers=self._headers())
        if resp.status_code >= 400:
            raise RuntimeError(f"La API rechazo el render: HTTP {resp.status_code} {resp.text[:200]}")
        project = (resp.json() or {}).get("project")
        if not project:
            raise RuntimeError(f"Respuesta inesperada de /movies: {resp.text[:200]}")

        # El render es asincrono en el servidor. Poll cada 4s.
        # Techo de 30 min: con cola larga, seedance puede tardar bastante.
        for _ in range(450):
            await asyncio.sleep(4)
            estado = (await self.client.get(
                f"{self.base_url}/movies", params={"project": project}, headers=self._headers()
            )).json()
            movie_state = estado.get("movie") or {}
            status = movie_state.get("status")
            if status == "done":
                quota = (estado.get("remaining_quota") or {}).get("time")
                return VideoResult(
                    url=movie_state.get("url", ""),
                    duration=float(movie_state.get("duration") or dur),
                    provider=self.name,
                    credits_remaining=quota,
                    meta={"project": project, "model": model},
                )
            if status == "error":
                raise RuntimeError(f"El render fallo en el servidor: {movie_state.get('message') or 'sin detalle'}")

        raise TimeoutError(f"El render {project} no termino en 30 min (queda de credits o cola)")

    # ------------------------------------------------------------------
    async def is_available(self) -> tuple[bool, str]:
        """Request real:GET /templates. Una key sin creditos responde 200
        en algunos endpoints y falla al renderizar, asi que ademas miramos
        el plan si viene."""
        if not self.api_key:
            return False, "falta API key (JSON2VIDEO_API_KEY en .env)"
        try:
            r = await self.client.get(f"{self.base_url}/templates", headers={"x-api-key": self.api_key}, timeout=20.0)
        except Exception as e:
            return False, f"sin conexion: {type(e).__name__}"
        if r.status_code == 403:
            return False, "API key invalida"
        if r.status_code >= 400:
            return False, f"HTTP {r.status_code}"
        return True, f"ok (modelo {self.model})"

    async def close(self) -> None:
        await self.client.aclose()