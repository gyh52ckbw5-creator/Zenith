"""Tek-model modu: gorev etiketlerine gore en uygun modeli secer, basarisiz
olursa oncelik sirasindaki bir sonraki modele gecer (fallback zinciri)."""

from __future__ import annotations

from .config import ZenithConfig
from .providers import ModelReply, ProviderError, call_model


class NoAvailableModelError(RuntimeError):
    """Hicbir model kullanilabilir (API anahtari / Ollama) durumda degilse."""


async def ask(
    config: ZenithConfig,
    messages: list[dict],
    *,
    tags: tuple[str, ...] = (),
) -> ModelReply:
    candidates = config.models_for_tags(tags)
    if not candidates:
        raise NoAvailableModelError(
            "Kullanilabilir model yok. config/models.yaml icindeki modeller icin "
            "gerekli API anahtarlarini .env dosyasina ekleyin ya da Ollama'yi calistirin."
        )

    errors: list[ProviderError] = []
    for spec in candidates:
        try:
            return await call_model(spec, messages)
        except ProviderError as exc:
            errors.append(exc)
            continue

    details = "; ".join(str(e) for e in errors)
    raise NoAvailableModelError(f"Denenen tum modeller basarisiz oldu: {details}")
