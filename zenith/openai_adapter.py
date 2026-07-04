"""OpenAI API uyumluluğu.

Zenith'i OpenAI API uyumlu bir sunucu olarak da kullanabilmek için adapter.
Ki başka araçlar/UI'ler doğrudan Zenith'i kullanabilsin.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class OpenAIMessage:
    role: str
    content: str


@dataclass
class OpenAIChoice:
    index: int
    message: OpenAIMessage
    finish_reason: str = "stop"


@dataclass
class OpenAIUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class OpenAIChatCompletion:
    id: str
    object: str = "chat.completion"
    created: int = 0
    model: str = "zenith"
    choices: list[OpenAIChoice] | None = None
    usage: OpenAIUsage | None = None

    def to_dict(self) -> dict[str, Any]:
        """OpenAI API uyumlu dict'e çevir."""
        return {
            "id": self.id,
            "object": self.object,
            "created": self.created,
            "model": self.model,
            "choices": [
                {
                    "index": c.index,
                    "message": {"role": c.message.role, "content": c.message.content},
                    "finish_reason": c.finish_reason,
                }
                for c in (self.choices or [])
            ],
            "usage": {
                "prompt_tokens": self.usage.prompt_tokens if self.usage else 0,
                "completion_tokens": self.usage.completion_tokens if self.usage else 0,
                "total_tokens": self.usage.total_tokens if self.usage else 0,
            },
        }
