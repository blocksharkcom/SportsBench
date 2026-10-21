"""OpenAI-compatible Chat Completions. Covers OpenAI itself AND every provider
that speaks the same API: xAI (Grok), DeepSeek, OpenRouter, Together, Groq,
Mistral, Fireworks, and local runtimes (Ollama, LM Studio, vLLM).

Point `base_url` at the vendor; bring the matching key. We pay nothing.
"""
from __future__ import annotations

import httpx
from .base import LLMProvider, ProviderError

DEFAULT_BASE = "https://api.openai.com/v1"


class OpenAICompatibleProvider(LLMProvider):
    def complete(self, system: str, user: str) -> str:
        base = (self.base_url or DEFAULT_BASE).rstrip("/")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        # Ask for JSON when the endpoint supports it; harmless if ignored.
        payload["response_format"] = {"type": "json_object"}

        try:
            r = httpx.post(f"{base}/chat/completions", json=payload,
                           headers=headers, timeout=self.timeout)
        except httpx.HTTPError as e:
            raise ProviderError(f"request failed: {e}") from e
        if r.status_code == 400 and "response_format" in r.text:
            payload.pop("response_format", None)  # older/odd endpoints
            r = httpx.post(f"{base}/chat/completions", json=payload,
                           headers=headers, timeout=self.timeout)
        if r.status_code >= 400:
            raise ProviderError(f"{r.status_code}: {r.text[:300]}")
        data = r.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise ProviderError(f"unexpected response shape: {str(data)[:300]}") from e
