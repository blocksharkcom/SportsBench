"""Provider abstraction. One job: given a system+user prompt, return raw JSON text.

We talk HTTP directly (httpx) instead of pulling every vendor SDK, so the install
stays tiny and there's no dependency-version roulette.
"""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Optional


class ProviderError(RuntimeError):
    pass


class LLMProvider(ABC):
    def __init__(self, model: str, api_key: Optional[str], base_url: Optional[str] = None,
                 temperature: Optional[float] = None, timeout: float = 60.0):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature
        self.timeout = timeout

    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        """Return the model's raw text response (expected to contain JSON)."""
        ...


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model response, tolerating code fences
    and chatter around it."""
    if not text:
        raise ProviderError("empty response")
    text = text.strip()
    # strip ```json fences
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        return json.loads(text)
    except Exception:
        pass
    # last resort: first balanced-looking {...}
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start:end + 1])
    raise ProviderError(f"could not parse JSON from response: {text[:200]!r}")
