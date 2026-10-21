"""Anthropic Messages API (Claude)."""
from __future__ import annotations

import httpx
from .base import LLMProvider, ProviderError

DEFAULT_BASE = "https://api.anthropic.com/v1"
API_VERSION = "2023-06-01"


class AnthropicProvider(LLMProvider):
    def complete(self, system: str, user: str) -> str:
        base = (self.base_url or DEFAULT_BASE).rstrip("/")
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": API_VERSION,
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
        payload: dict = {
            "model": self.model,
            "max_tokens": 1024,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        try:
            r = httpx.post(f"{base}/messages", json=payload,
                           headers=headers, timeout=self.timeout)
        except httpx.HTTPError as e:
            raise ProviderError(f"request failed: {e}") from e
        if r.status_code >= 400:
            raise ProviderError(f"{r.status_code}: {r.text[:300]}")
        data = r.json()
        try:
            return "".join(block.get("text", "") for block in data["content"])
        except (KeyError, TypeError) as e:
            raise ProviderError(f"unexpected response shape: {str(data)[:300]}") from e
