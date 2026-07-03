"""Basit, dosya tabanli konusma hafizasi. Zenith'in oturumlar arasinda
konusmayi hatirlamasini saglar (Jarvis'in seni hatirlamasi gibi)."""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_MEMORY_PATH = Path.home() / ".zenith" / "memory.json"
MAX_TURNS = 40


class ConversationMemory:
    def __init__(self, path: Path | None = None, max_turns: int = MAX_TURNS):
        self.path = path or DEFAULT_MEMORY_PATH
        self.max_turns = max_turns
        self.messages: list[dict] = self._load()

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.messages, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def add(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        overflow = len(self.messages) - self.max_turns
        if overflow > 0:
            self.messages = self.messages[overflow:]
        self.save()

    def reset(self) -> None:
        self.messages = []
        self.save()

    def as_messages(self, system_prompt: str) -> list[dict]:
        return [{"role": "system", "content": system_prompt}, *self.messages]
