"""
Proveedor oficial para OpenRouter (https://openrouter.ai).

Como OpenRouter es compatible con el formato OpenAI, esta clase
tambien sirve como referencia para cualquier otro proveedor
compatible con OpenAI (vLLM, Groq, Together, etc).
"""

from typing import Any, AsyncIterator, Dict, List, Optional

from .base_provider import BaseProvider, parse_stream_line


class OpenRouterProvider(BaseProvider):
    async def _post(self, messages: list, **kwargs: Any) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": self.model, "messages": messages, **kwargs}

        resp = await self.client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    async def generate(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        history: Optional[List[Dict[str, str]]] = None,
        **kwargs: Any,
    ) -> str:
        messages = self.build_messages(prompt, system_prompt, history)
        data = await self._post(messages, **kwargs)
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
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": self.model, "messages": messages, "stream": True, **kwargs}

        async with self.client.stream("POST", f"{self.base_url}/chat/completions", headers=headers, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                piece = parse_stream_line(line)
                if piece is None:  # [DONE] -> fin del stream
                    break
                if piece:
                    yield piece

    # ------------------------------------------------------------------
    async def get_available_models(self) -> List[str]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        resp = await self.client.get(f"{self.base_url}/models", headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return [m["id"] for m in data.get("data", [])]
