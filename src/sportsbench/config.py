"""Configuration: which models to run, with which keys. YAML + env, zero magic.

Free core = bring-your-own API keys (we pay nothing). The optional `pro` block
points at modelfights.com and unlocks managed data / hosted runs / cloud publish.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:  # pragma: no cover
    pass

CONFIG_NAMES = ("sportsbench.config.yaml", "sportsbench.config.yml", ".sportsbench.yaml")


@dataclass
class ModelConfig:
    name: str
    provider: str                       # openai | anthropic | google | openai_compatible
    model: str
    api_key_env: Optional[str] = None   # name of the env var holding the key
    base_url: Optional[str] = None      # for openai_compatible (xAI, DeepSeek, Ollama, …)
    temperature: Optional[float] = None
    enabled: bool = True

    def api_key(self) -> Optional[str]:
        return os.environ.get(self.api_key_env) if self.api_key_env else None


@dataclass
class ProConfig:
    api_key_env: str = "SPORTSBENCH_API_KEY"
    base_url: str = "https://modelfights.com/v1"

    def api_key(self) -> Optional[str]:
        return os.environ.get(self.api_key_env)

    @property
    def enabled(self) -> bool:
        return bool(self.api_key())


@dataclass
class Config:
    models: list[ModelConfig] = field(default_factory=list)
    sport: str = "football"
    devig: str = "multiplicative"
    stake_unit: float = 1.0
    kelly_fraction: float = 0.25
    branding: bool = True
    pro: ProConfig = field(default_factory=ProConfig)
    path: Optional[str] = None

    def active_models(self) -> list[ModelConfig]:
        return [m for m in self.models if m.enabled]

    @classmethod
    def find(cls, start: Optional[str] = None) -> Optional[str]:
        d = Path(start or os.getcwd()).resolve()
        for parent in (d, *d.parents):
            for name in CONFIG_NAMES:
                p = parent / name
                if p.is_file():
                    return str(p)
        return None

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Config":
        path = path or cls.find()
        if not path:
            return cls()  # sensible empty default; CLI will guide `sportsbench init`
        if yaml is None:
            raise RuntimeError("pyyaml is required to read config (pip install pyyaml)")
        data = yaml.safe_load(Path(path).read_text()) or {}
        defaults = data.get("defaults", {})
        pro = data.get("pro", {})
        models = [ModelConfig(**m) for m in data.get("models", [])]
        return cls(
            models=models,
            sport=defaults.get("sport", "football"),
            devig=defaults.get("devig", "multiplicative"),
            stake_unit=float(defaults.get("stake_unit", 1.0)),
            kelly_fraction=float(defaults.get("kelly_fraction", 0.25)),
            branding=bool(data.get("branding", True)),
            pro=ProConfig(**pro) if pro else ProConfig(),
            path=path,
        )
