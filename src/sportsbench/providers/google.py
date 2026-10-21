"""Google Gemini (Generative Language API)."""
from __future__ import annotations

import httpx
from .base import LLMProvider, ProviderError

DEFAULT_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GoogleProvider(LLMProvider):
    def complete(self, system: str, user: str) -> str:
        base = (self.base_url or DEFAULT_BASE).rstrip("/")
        url = f"{base}/models/{self.model}:generateContent"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-goog-api-key"] = self.api_key
        payload: dict = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        if self.temperature is not None:
            payload["generationConfig"]["temperature"] = self.temperature
        try:
            r = httpx.post(url, json=payload, headers=headers, timeout=self.timeout)
        except httpx.HTTPError as e:
            raise ProviderError(f"request failed: {e}") from e
        if r.status_code >= 400:
            raise ProviderError(f"{r.status_code}: {r.text[:300]}")
        data = r.json()
        try:
            return "".join(
                p.get("text", "")
                for p in data["candidates"][0]["content"]["parts"]
            )
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderError(f"unexpected response shape: {str(data)[:300]}") from e
