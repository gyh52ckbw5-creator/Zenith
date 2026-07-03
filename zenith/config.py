"""Model registry: config/models.yaml dosyasini yukler ve hangi modellerin
su an kullanilabilir oldugunu (API anahtari mevcut / Ollama yerel) belirler."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "models.yaml"


@dataclass(frozen=True)
class ModelSpec:
    name: str
    litellm_id: str
    provider: str
    requires_key: str | None
    tags: tuple[str, ...] = field(default_factory=tuple)
    priority: int = 100

    def is_available(self) -> bool:
        if self.requires_key is None:
            return True
        return bool(os.environ.get(self.requires_key))


@dataclass(frozen=True)
class ZenithConfig:
    models: tuple[ModelSpec, ...]
    council_max_parallel: int
    synthesizer_tags: tuple[str, ...]

    def available_models(self) -> list[ModelSpec]:
        return sorted(
            (m for m in self.models if m.is_available()),
            key=lambda m: m.priority,
        )

    def models_for_tags(self, tags: tuple[str, ...]) -> list[ModelSpec]:
        available = self.available_models()
        if not tags:
            return available
        tagged = [m for m in available if set(tags) & set(m.tags)]
        return tagged or available


def load_config(path: str | Path | None = None) -> ZenithConfig:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    with open(config_path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    models = tuple(
        ModelSpec(
            name=m["name"],
            litellm_id=m["litellm_id"],
            provider=m["provider"],
            requires_key=m.get("requires_key"),
            tags=tuple(m.get("tags", [])),
            priority=m.get("priority", 100),
        )
        for m in raw.get("models", [])
    )

    council = raw.get("council", {})
    return ZenithConfig(
        models=models,
        council_max_parallel=council.get("max_parallel_models", 4),
        synthesizer_tags=tuple(council.get("synthesizer_tags", ["reasoning"])),
    )
