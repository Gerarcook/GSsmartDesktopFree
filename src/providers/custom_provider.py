"""
Proveedor PERSONALIZADO: se conecta a CUALQUIER API compatible
con el formato OpenAI. Esto cubre:

  - LM Studio local:        http://localhost:1234/v1
  - Ollama (modo OpenAI):   http://localhost:11434/v1
  - vLLM / TGI local:       http://localhost:8000/v1
  - Groq, Mistral, Together, Fireworks, DeepInfra, etc.
  - Cualquier endpoint propio que hables con tu equipo.

Si tu proveedor usa otro formato (Anthropic, Google, etc),
solo crea una clase nueva heredando de BaseProvider con la
misma logica pero el payload de ese proveedor.
"""

from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from .base_provider import BaseProvider, parse_stream_line, split_reasoning


class CustomProvider(BaseProvider):
    async def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    # ------------------------------------------------------------------
    async def generate(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> str:
        messages = self.build_messages(prompt, system_prompt, history)
        payload = {"model": self.model, "messages": messages, **kwargs}

        resp = await self.client.post(f"{self.base_url}/chat/completions", headers=await self._headers(), json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    # ------------------------------------------------------------------
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> AsyncIterator[Tuple[str, str]]:
        messages = self.build_messages(prompt, system_prompt, history)
        payload = {"model": self.model, "messages": messages, "stream": True, **kwargs}

        async with self.client.stream("POST", f"{self.base_url}/chat/completions", headers=await self._headers(), json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                piece = parse_stream_line(line)
                if piece is None:  # [DONE] -> fin del stream
                    break
                # El razonamiento viaja aparte: la UI lo muestra como
                # "pensando..." y nunca lo mete en la respuesta.
                razon, texto = split_reasoning(piece)
                if razon:
                    yield ("reasoning", razon)
                elif texto:
                    yield ("content", texto)

    # ------------------------------------------------------------------
    async def get_available_models(self) -> List[str]:
        try:
            resp = await self.client.get(f"{self.base_url}/models", headers=await self._headers())
            resp.raise_for_status()
            data = resp.json()
            return [m["id"] for m in data.get("data", [])]
        except Exception:
            return [self.model]
