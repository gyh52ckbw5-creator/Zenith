"""Deneysel özellikler (beta, değişebilir).

Yeni fikirler ve beta özellikler burada test edilir.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable


class ExperimentalFeature:
    """Bir deneysel özellik."""

    def __init__(
        self,
        name: str,
        description: str,
        enabled: bool = False,
        warning: str | None = None,
    ):
        self.name = name
        self.description = description
        self.enabled = enabled
        self.warning = warning or "Bu özellik beta aşamasındadır ve değişebilir."

    def __call__(self, func: Callable) -> Callable:
        """Fonksiyonu deneysel özellik olarak işaretle."""

        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not self.enabled:
                raise RuntimeError(
                    f"'{self.name}' deneysel özelliği etkinleştirilmemiştir. "
                    f"Açıklaması: {self.description}"
                )
            print(f"⚠️  {self.warning}")
            return await func(*args, **kwargs)

        return wrapper


# Deneysel özellikler
MULTI_TURN_REASONING = ExperimentalFeature(
    name="multi_turn_reasoning",
    description="Çok aşamalı akıl yürütme ve planlama",
    enabled=False,
)

FUNCTION_COMPOSITION = ExperimentalFeature(
    name="function_composition",
    description="Araçları birleştirerek kompleks görevleri çözme",
    enabled=False,
)

VISION_REASONING = ExperimentalFeature(
    name="vision_reasoning",
    description="Görüntüler üzerinde karmaşık analiz",
    enabled=False,
)

VOICE_STREAMING = ExperimentalFeature(
    name="voice_streaming",
    description="Gerçek zamanlı ses akışı ve konuşma tanıma",
    enabled=False,
)
