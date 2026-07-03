"""LiteLLM uzerinden tum saglayicilari (Ollama, Groq, Gemini, OpenRouter,
Cerebras, ...) tek bir arayuzden cagirmayi saglayan ince katman."""

from __future__ import annotations

from dataclasses import dataclass

from .config import ModelSpec

DEFAULT_TIMEOUT_SECONDS = 45


class ProviderError(RuntimeError):
    """Bir modele yapilan cagri basarisiz oldugunda firlatilir."""

    def __init__(self, model_name: str, cause: Exception):
        super().__init__(f"{model_name} basarisiz oldu: {cause}")
        self.model_name = model_name
        self.cause = cause


@dataclass
class ModelReply:
    model_name: str
    litellm_id: str
    content: str


async def call_model(
    spec: ModelSpec,
    messages: list[dict],
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    temperature: float = 0.7,
) -> ModelReply:
    """Tek bir modele mesaj gonderir ve cevabini dondurur.

    LiteLLM importu fonksiyon icinde yapilir; boylece paket kurulu degilken
    bile (ornegin sadece config/router testleri calistirilirken) bu modul
    import edilebilir.
    """
    import litellm

    try:
        response = await litellm.acompletion(
            model=spec.litellm_id,
            messages=messages,
            timeout=timeout,
            temperature=temperature,
        )
        content = response["choices"][0]["message"]["content"] or ""
        return ModelReply(model_name=spec.name, litellm_id=spec.litellm_id, content=content.strip())
    except Exception as exc:  # noqa: BLE001 - saglayici hatalari cok cesitli
        raise ProviderError(spec.name, exc) from exc
