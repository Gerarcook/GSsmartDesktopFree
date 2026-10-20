"""
WanProvider: Wan2.2 14B image-to-video en un Space de HuggingFace / ZeroGPU.

Gratis, sin API key. A cambio: cola compartida (puede tardar 10-15 min) y el
Space es de un tercero, asi que puede caerse o cambiar de dueño en cualquier
momento.

Fricciones medidas (oct-2026) que ya estan resueltas aca:

1. `urllib.request` devuelve 404 contra este host donde `curl` y `httpx`
   devuelven 200. No es el User-Agent ni la URL: es urllib. Este provider
   usa httpx como el resto del proyecto y no tiene el problema.

2. El GET del resultado TIENE que ser `client.stream()`. Un `get()` normal
   se queda esperando el body entero de un SSE que no cierra nunca, y el
   thread queda colgado. Con `aiter_lines()` y break al `event: complete`
   funciona.

3. No existe `/gradio_api/upload/file` en Gradio 6 (404). El parametro
   `input_image` acepta URL publica o base64, asi que los locales se mandan
   como data URI.

4. Algunos Spaces de Gradio 6 declaran `mcp_server: true` pero cuelgan en
   `/gradio_api/mcp`. Por eso esto habla REST, no MCP.
"""

import asyncio
import base64
import json
import mimetypes
from pathlib import Path
from typing import Any, Optional

import httpx

from src.media.base_video_provider import BaseVideoProvider, VideoResult


DEFAULT_SPACE = "zerogpu-aoti/wan2-2-fp8da-aoti-faster"

#: El negative prompt por defecto del Space esta en chino y cubre los
#: artefactos tipicos (dedos, limbs, texto). Se mantiene igual.
NEGATIVE_DEFAULT = (
    "色调艳丽, 过曝, 静态, 细节模糊不清, 字幕, 风格, 作品, 画作, 画面, 静止, "
    "整体发灰, 最差质量, 低质量, JPEG压缩残留, 丑陋的, 残缺的, 多余的手指, "
    "画得不好的手部, 画得不好的脸部, 畸形的, 毁容的, 形态畸形的肢体, 手指融合, "
    "静止不动的画面, 杂乱的背景, 三条腿, 背景人很多, 倒着走"
)


class WanProvider(BaseVideoProvider):
    def __init__(
        self,
        space: str = DEFAULT_SPACE,
        model: str = "wan2.2-14b-fast",
        timeout: float = 900.0,
    ):
        self.space = space
        host = f"{space.replace('/', '-').lower()}.hf.space"
        super().__init__(api_key="", base_url=f"https://{host}", model=model)
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=timeout))

    @property
    def name(self) -> str:
        return "Wan2.2 (HF)"

    def supports_image(self) -> bool:
        return True

    # ------------------------------------------------------------------
    async def _as_src(self, image: str) -> str:
        """URL publica tal cual, o data URI si es archivo local."""
        if image.startswith(("http://", "https://", "data:")):
            return image
        p = Path(image)
        if not p.exists():
            raise FileNotFoundError(f"No existe el keyframe: {image}")
        ctype = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
        raw = await asyncio.to_thread(p.read_bytes)
        return f"data:{ctype};base64,{base64.b64encode(raw).decode('ascii')}"

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
        if not image:
            raise ValueError("Wan2.2 es image-to-video: hace falta image=")

        dur = float(duration or 3.5)
        steps = float(kwargs.pop("steps", 6))
        negative = kwargs.pop("negative_prompt", NEGATIVE_DEFAULT)

        payload = {
            "data": [
                await self._as_src(image),
                prompt,
                steps,
                negative,
                dur,
                float(kwargs.pop("guidance", 1.0)),
                float(kwargs.pop("guidance_2", 1.0)),
                float(seed if seed is not None else 42),
                seed is None,
            ]
        }

        try:
            r = await self.client.post(f"{self.base_url}/gradio_api/call/generate_video", json=payload)
        except Exception as e:
            raise RuntimeError(f"No se pudo contactar el Space: {type(e).__name__}") from e
        if r.status_code >= 400:
            raise RuntimeError(f"El Space rechazo el pedido: HTTP {r.status_code} {r.text[:200]}")

        event_id = (r.json() or {}).get("event_id")
        if not event_id:
            raise RuntimeError(f"Respuesta inesperada del Space: {r.text[:200]}")

        return await self._await_render(event_id, dur)

    # ------------------------------------------------------------------
    async def _await_render(self, event_id: str, dur: float) -> VideoResult:
        """Sigue el stream SSE del job hasta complete/error.

        OJO: stream(), no get(). Ver nota 2 en el docstring del modulo.
        """
        url = f"{self.base_url}/gradio_api/call/generate_video/{event_id}"
        deadline = asyncio.get_event_loop().time() + self.timeout

        async with self.client.stream("GET", url, headers={"Accept": "text/event-stream"}) as resp:
            if resp.status_code >= 400:
                raise RuntimeError(f"El Space devolvio HTTP {resp.status_code} al consultar el job")

            event = None
            async for line in resp.aiter_lines():
                line = line.strip()
                if line.startswith("event:"):
                    event = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    data = line[5:].strip()
                    if event == "error":
                        # data:null con show_error:false = el backend fallo y
                        # se comio el motivo. No hay nada mejor que reportar.
                        raise RuntimeError(
                            "El Space fallo al renderizar (event:error). "
                            "Casi siempre es el Space caido, no los parametros: "
                            "probalo desde la web del Space."
                        )
                    if event == "complete":
                        try:
                            payload = json.loads(data)
                        except Exception as e:
                            raise RuntimeError(f"Respuesta final ilegible: {data[:120]}") from e
                        files = payload.get("data") or []
                        if not files or not files[0]:
                            raise RuntimeError("El render termino sin devolver video")
                        out_url = files[0].get("url")
                        if not out_url:
                            raise RuntimeError(f"Sin URL en el resultado: {files[0]}")
                        used_seed = files[1] if len(files) > 1 else None
                        return VideoResult(
                            url=out_url,
                            duration=dur,
                            provider=self.name,
                            seed=int(used_seed) if isinstance(used_seed, (int, float)) else None,
                            meta={"project": event_id, "space": self.space},
                        )
                if asyncio.get_event_loop().time() > deadline:
                    raise TimeoutError(f"El render no termino en {self.timeout:.0f}s (cola de ZeroGPU)")

        raise RuntimeError("El stream del Space cerro sin resultado")

    # ------------------------------------------------------------------
    async def is_available(self) -> tuple[bool, str]:
        """Chequea /config, que es barato y no encola GPU.

        OJO: que /config responda 200 NO significa que el render funcione.
        Cuando el backend estaba caido, /config daba 200 y generate_video
        devolvia event:error. Por eso el chequeo de verdad es un render.
        """
        try:
            r = await self.client.get(f"{self.base_url}/config", timeout=20.0)
        except Exception as e:
            return False, f"Space inalcanzable: {type(e).__name__}"
        if r.status_code >= 400:
            return False, f"HTTP {r.status_code}"
        if "mcp_server" in r.text and r.json().get("mcp_server"):
            return True, "ok (Space en linea; MCP cuelga, se usa REST)"
        return True, "ok (Space en linea)"

    async def close(self) -> None:
        await self.client.aclose()