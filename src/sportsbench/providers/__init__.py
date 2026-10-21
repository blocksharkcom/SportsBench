"""Provider registry + factory."""
from __future__ import annotations

from ..config import ModelConfig
from .base import LLMProvider, ProviderError, extract_json
from .openai_compatible import OpenAICompatibleProvider
from .anthropic import AnthropicProvider
from .google import GoogleProvider

# Friendly aliases so config can say provider: grok / deepseek / ollama etc.
_OPENAI_COMPAT_PRESETS = {
    "openai": None,
    "openai_compatible": None,
    "xai": "https://api.x.ai/v1",
    "grok": "https://api.x.ai/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "together": "https://api.together.xyz/v1",
    "groq": "https://api.groq.com/openai/v1",
    "mistral": "https://api.mistral.ai/v1",
    "fireworks": "https://api.fireworks.ai/inference/v1",
    "ollama": "http://localhost:11434/v1",
    "lmstudio": "http://localhost:1234/v1",
}

__all__ = ["LLMProvider", "ProviderError", "extract_json", "build_provider", "PROVIDERS"]
PROVIDERS = sorted(set(list(_OPENAI_COMPAT_PRESETS) + ["anthropic", "google", "gemini"]))


def build_provider(mc: ModelConfig) -> LLMProvider:
    p = mc.provider.lower()
    if p == "anthropic":
        return AnthropicProvider(mc.model, mc.api_key(), mc.base_url, mc.temperature)
    if p in ("google", "gemini"):
        return GoogleProvider(mc.model, mc.api_key(), mc.base_url, mc.temperature)
    if p in _OPENAI_COMPAT_PRESETS:
        base = mc.base_url or _OPENAI_COMPAT_PRESETS[p]
        return OpenAICompatibleProvider(mc.model, mc.api_key(), base, mc.temperature)
    raise ProviderError(
        f"unknown provider '{mc.provider}'. Known: {', '.join(PROVIDERS)}"
    )
