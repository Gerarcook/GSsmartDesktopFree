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

import json
from typing import Any, AsyncIterator, Dict, List, Optional

from .base_provider import BaseProvider


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
    ) -> AsyncIterator[str]:
        messages = self.build_messages(prompt, system_prompt, history)
        payload = {"model": self.model, "messages": messages, "stream": True, **kwargs}

        async with self.client.stream("POST", f"{self.base_url}/chat/completions", headers=await self._headers(), json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    data = json.loads(chunk)
                    delta = data["choices"][0]["delta"].get("content")
                    if delta:
                        yield delta
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

    # ------------------------------------------------------------------
    async def get_available_models(self) -> List[str]:
        try:
            resp = await self.client.get(f"{self.base_url}/models", headers=await self._headers())
            resp.raise_for_status()
            data = resp.json()
            return [m["id"] for m in data.get("data", [])]
        except Exception:
            return [self.model]
